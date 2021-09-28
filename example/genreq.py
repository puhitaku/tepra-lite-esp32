import binascii
import zlib

from PIL import Image, ImageDraw, ImageFont

width = 300
height = 64  # constant, cannot be changed

im = Image.new('RGB', (width, height), 'white')
draw = ImageDraw.Draw(im)
font = ImageFont.truetype('SFNS.ttf', 50)  # runs on macOS
draw.text((width // 2, height // 2), 'Hello World!', font=font, fill='black', anchor='mm')
im = im.convert("L")
im = im.rotate(-90, expand=True)

encoded = b''
for y in range(im.height):
    aggregated = 0
    for shift, x in enumerate(range(im.width - 1, -1, -1)):
        if im.getpixel((x, y)) <= 127:
            aggregated += 1 << shift
    line = aggregated.to_bytes(8, 'big')
    encoded += line
    print(binascii.hexlify(line))

with open('hello.bin', 'wb') as f:
    f.write(zlib.compress(encoded))

im.save('generated.png')
