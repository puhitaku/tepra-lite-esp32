import binascii
import json
from PIL import Image, ImageDraw, ImageFont

im = Image.new('RGB', (140, 64), 'white')
draw = ImageDraw.Draw(im)
font = ImageFont.truetype('SFNS.ttf', 20)
draw.text((140 // 2, 64 // 2), 'example.com', font=font, fill='black', anchor='mm')
im = im.convert("L")
im = im.rotate(-90, expand=True)

lines = []
for y in range(im.height):
    aggregated = 0
    for shift, x in enumerate(range(im.width-1, -1, -1)):
        if im.getpixel((x, y)) <= 127:
            aggregated += 1 << shift
    lines.append(binascii.hexlify(aggregated.to_bytes(8, 'big')).decode())

with open('hello.json', 'w') as f:
    parts = [
        {'type': 'qr', 'string': 'http://example.com/'},
        {'type': 'image', 'image': ''.join(lines)},
    ]
    json.dump({'parts': parts}, f)

im.save('out.png')
