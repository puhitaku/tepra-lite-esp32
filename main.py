import binascii
import json
import machine
import time
import uasyncio
from ucollections import OrderedDict

import tepra
import wifi
from typ1ng import Optional, Tuple
from nanoweb.nanoweb import Nanoweb


# Models
class Print:
    dimension: Tuple[int, int]
    done: bool

    def __init__(self, dimension, done):
        self.dimension = dimension
        self.done = done


app = Nanoweb()
prints = OrderedDict()


def log(fmt, *args):
    print('[{:04.02f}]'.format(time.ticks_ms() / 1000), fmt.format(*args))


def respond(fn):
    """A mixin decorator to simplify handlers like Flask"""

    async def wrapper(req):
        log('{} {}', req.method, req.url)
        res = await fn(req)

        if isinstance(res, tuple):
            # Tuple = a tuple of status code and the body
            status, body = res
        else:
            # Others = implies "200 OK"
            status, body = 200, res

        # Start writing the response header
        await req.write('HTTP/1.1 {}\r\n'.format(status))

        if isinstance(body, dict) or isinstance(body, list):
            # Dict or list = jsonified
            await req.write('Content-Type: application/json\r\n\r\n')
            await req.write(json.dumps(body))
        elif isinstance(body, Response):
            await req.write('Content-Type: application/json\r\n\r\n')
            await req.write(body.jsonify())
        else:
            # Others = implies a plain text and be transmitted as-is
            await req.write('Content-Type: text/plain\r\n\r\n')
            await req.write(body)

    return wrapper


class Response:
    error = None
    error: Optional[str]

    def __init__(self, **kwargs):
        self.error = None
        for k, v in kwargs.items():
            setattr(self, k, v)

    def jsonify(self) -> str:
        d = dict()
        items = ((k, v) for k, v in self.__dict__.items() if not k.startswith('__'))
        for k, v in items:
            d[k] = str(v)
        return json.dumps(d)


@app.route('/battery')
@respond
async def handle_battery(req):
    if req.method != 'GET':
        return 405, Response(error='method not allowed')
    r = Response()
    r.battery = None

    success, bat = t.fetch_remaining_battery()
    if success:
        r.battery = bat
        return 200, r
    else:
        r.error = 'failed to read'
        return 500, r


@app.route('/prints')
@respond
async def handle_prints(req):
    if req.method == 'GET':
        return 200, Response(prints=prints)
    elif req.method == 'POST':
        typ = req.headers.get('Content-Type', '')
        if typ != 'application/json':
            return 400, Response(error='bad request, invalid content type')

        content_len = req.headers.get('Content-Length', 0)
        if content_len == 0:
            return 400, Response(error='bad request, content length is not specified or zero')

        body = await req.read(int(content_len))

        image = []

        try:
            j = json.loads(body.decode())
        except ValueError as e:
            return 400, Response(error='broken JSON: {}'.format(e))

        image_raw = j.get('image')
        if image_raw is None:
            return 400, Response(error='JSON has no image key')

        for i in range(0, len(image_raw), 16):
            try:
                image.append(binascii.unhexlify(image_raw[i:i+16]))
            except ValueError as e:
                return 400, Response(error='invalid hexstr: {}'.format(e))

        if len(prints) == 0:
            print_id = 0
        else:
            last_print_id = list(prints.items())[-1][0]
            print_id = last_print_id + 1
        prints[print_id] = Print((len(image), 64), False)

        success = t.print(image)
        if not success:
            return 500, Response(error='failed to print')

        return 200, Response()
    else:
        return 405, Response(error='method not allowed')


# Read the config
with open('config.json', 'r') as f:
    conf = json.load(f)

# Bring up the Wi-Fi
success = wifi.up(conf['ssid'], conf['psk'])
if not success:
    log('Failed to establish a Wi-Fi connection, resetting')
    machine.reset()

wifi.show_ifconfig()

t = tepra.Tepra(debug=True)

log('Waiting for a Tepra Lite')
while not t.connect():
    time.sleep_ms(1000)

log('Connected')
log('Launching the Tepra API')

loop = uasyncio.get_event_loop()
loop.create_task(app.run())
loop.run_forever()

