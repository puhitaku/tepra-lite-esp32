import gc
import json
import machine
import time
import uasyncio
import zlib

from nanoweb.nanoweb import Nanoweb

import tepra
import wifi
from typ1ng import Optional, Tuple


class Print:
    id: int
    size: Tuple[int, int]
    done: bool

    def __init__(self, pid, size, done):
        self.id = pid
        self.size = size
        self.done = done

    def to_dict(self):
        return {'id': self.id, 'width': self.size[0], 'height': self.size[1], 'done': self.done}


app = Nanoweb()


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
    gc.collect()

    if req.method not in ('GET', 'POST'):
        return 405, Response(error='method not allowed')

    typ = req.headers.get('Content-Type', '')
    if typ != 'application/octet-stream':
        log('bad request, invalid content type')
        return 400, Response(error='bad request, invalid content type')

    content_len = req.headers.get('Content-Length')
    if content_len is None:
        log('bad request, content length is not specified or zero')
        return 400, Response(error='bad request, content length is not specified or zero')

    zl = await req.read(int(content_len))
    log('read from request body: {} bytes'.format(len(zl)))
    body = zlib.decompress(zl)
    log('decompressed: {} bytes'.format(len(body)))

    success, reason = t.print(body)
    if not success:
        return 500, Response(error='failed to print: ' + reason)
    return 200, Response()


# Read the config
with open('config.json', 'r') as f:
    conf = json.load(f)

# Bring up the Wi-Fi
ok = wifi.up(conf['ssid'], conf['psk'])
if not ok:
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
