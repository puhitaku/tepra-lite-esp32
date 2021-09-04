import binascii
import gc
import json
import machine
import time
import uasyncio
from ucollections import OrderedDict

import tepra
import wifi
from typ1ng import Optional, Tuple

gc.collect()

from uqr.uQR import QRCode, ERROR_CORRECT_L, ERROR_CORRECT_M, ERROR_CORRECT_Q, ERROR_CORRECT_H
from nanoweb.nanoweb import Nanoweb


# Models
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
    gc.collect()

    if req.method not in ('GET', 'POST'):
        return 405, Response(error='method not allowed')

    if req.method == 'GET':
        prints_dicts = []
        for p in prints.values():
            prints_dicts.append(p.to_dict())
        return 200, Response(prints=prints_dicts)

    typ = req.headers.get('Content-Type', '')
    if typ != 'application/json':
        log('bad request, invalid content type')
        return 400, Response(error='bad request, invalid content type')

    content_len = req.headers.get('Content-Length', 0)
    if content_len == 0:
        log('bad request, content length is not specified or zero')
        return 400, Response(error='bad request, content length is not specified or zero')

    body = await req.read(int(content_len))

    del typ, content_len
    gc.collect()

    try:
        j = json.loads(body.decode())
    except ValueError as e:
        log('bad request, broken JSON: {}', e)
        return 400, Response(error='bad request, broken JSON: {}'.format(e))

    del body
    gc.collect()

    parts = j.get('parts')

    if parts is None:
        log('bad request, JSON has no "parts" key')
        return 400, Response(error='bad request, JSON has no "parts" key')

    rendered = []

    for pi, p in enumerate(parts):
        typ = p.get('type')
        if typ not in ('space', 'image', 'qr'):
            log('part {}: this part has no printable data', pi)
            return 400, Response(error='part {} has no printable data'.format(pi))

        if typ == 'space':
            length = p.get('length')
            if length is None or not isinstance(length, int):
                log('part {}: space has no "length" key', pi)
                return 400, Response(error='part {}: space has no "length" key'.format(pi))
            rendered.append([b'\x00' * 8] * length)

            del length
            gc.collect()

        if typ == 'image':
            image = p.get('image')
            if image is None:
                log('part {}: image has no "image" key', pi)
                return 400, Response(error='part {}: image has no "image" key'.format(pi))

            buf = []
            for i in range(0, len(image), 16):
                try:
                    buf.append(binascii.unhexlify(image[i:i+16]))
                except ValueError as e:
                    log('part {}: invalid hexstr: {}', pi, e)
                    return 400, Response(error='invalid hexstr: {}'.format(e))
            rendered.append(buf)

            del image, buf
            gc.collect()

        elif typ == 'qr':
            qr_str = p.get('string')
            if qr_str is None:
                log('part {}: QR has no "string" key', pi)
                return 400, Response(error='part {}: QR has no "string" key'.format(pi))

            error_correction = p.get('qr_error_correction', 'm')
            if error_correction == 'l':
                qrc = QRCode(version=1, border=0, error_correction=ERROR_CORRECT_L)
            elif error_correction == 'm':
                qrc = QRCode(version=1, border=0, error_correction=ERROR_CORRECT_M)
            elif error_correction == 'q':
                qrc = QRCode(version=1, border=0, error_correction=ERROR_CORRECT_Q)
            elif error_correction == 'h':
                qrc = QRCode(version=1, border=0, error_correction=ERROR_CORRECT_H)
            else:
                log('part {}: invalid error correction level: {}', pi, error_correction)
                return 400, Response(error='invalid error correction level: ' + error_correction)

            log('QR string: {}', qr_str)
            log('Error correction level: {}', error_correction.upper())

            qrc.add_data(qr_str)
            mat = qrc.get_matrix()

            del p, qr_str, error_correction, qrc
            gc.collect()

            width = len(mat[0])
            log('QR code width (original): {}', width)
            if width > 64:
                log('Exceeds 64px')
                return 400, Response(
                    error='width of QR code ({}px) exceeds 64px, try using lower error correction level' .format(width)
                )
            scale = 64 // width
            log('QR code width (scaled): {}', width * scale)

            rotated_qr = []

            for y in range(width):
                aggregated = 0
                for x in range(width):
                    for i in range(scale):
                        aggregated += 1 << (x * scale + i) if mat[x][y] else 0
                aggregated <<= (64 - width * scale) // 2
                for _ in range(scale):
                    log("QR: {:016x}", aggregated)
                    rotated_qr.append(aggregated.to_bytes(8, 'big'))

            border = (84 - len(rotated_qr)) // 2 + 1
            border = max(border, 8)  # Leave at least 8 lines for reliable printing and decoding
            spacing = [0] * 8
            for _ in range(border):
                rotated_qr.insert(0, spacing)
                rotated_qr.append(spacing)

            rendered.append([bytes(r) for r in rotated_qr])

            del width, scale, aggregated, border, spacing, rotated_qr, mat
            gc.collect()

    if len(prints) == 0:
        print_id = 0
    else:
        last_print_id = list(prints.items())[-1][0]
        print_id = last_print_id + 1

    merged = []
    for r in rendered:
        log('Merging {} lines', len(r))
        merged += r

    prints[print_id] = Print(print_id, (64, len(merged)), False)
    log('Print: ID={}, width=64, height={}', print_id, len(merged))

    success, reason = t.print(merged)
    prints[print_id].done = True
    if not success:
        return 500, Response(error='failed to print: ' + reason)
    return 200, Response()


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
