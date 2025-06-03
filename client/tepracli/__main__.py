import gzip
import importlib
import socket
import sys
import zlib
from io import BytesIO

import click
import qrcode
from PIL import Image, ImageDraw, ImageFont

from tepracli import Client, min_width, height


# Based on: https://stackoverflow.com/questions/65742330/preserving-the-order-of-user-provided-parameters-with-python-click
# Edited to pass options via the context.
class OrderedParamsCommand(click.Command):
    _options = []

    def parse_args(self, ctx, args):
        # run the parser for ourselves to preserve the passed order
        parser = self.make_parser(ctx)
        opts, _, param_order = parser.parse_args(args=list(args))
        for param in param_order:
            if param.name not in ('message', 'space', 'qr', 'image'):
                continue
            ctx.obj['parts'] = ctx.obj.get('parts', []) + [(param, opts[param.name].pop(0))]

        # return "normal" parse results
        return super().parse_args(ctx, args)


@click.group()
@click.pass_context
def cmd(ctx):
    ctx.obj = dict()


@cmd.command()
@click.option(
    '--address',
    '-a',
    default="tepra.local",
    help='The IP address or the URL of TEPRA Lite LR30. (default = tepra.local)',
)
@click.pass_context
def battery(ctx, address):
    actual_address = socket.gethostbyname(address)
    c = Client(actual_address)
    bat, err = c.get_battery()
    if err:
        print(f'Failed to get remaining battery: {err}')
    else:
        print(f'Remaining battery: {bat}%')


@cmd.command(name='print', cls=OrderedParamsCommand)
@click.option(
    '--address',
    '-a',
    default="tepra.local",
    help='The IP address or the URL of TEPRA Lite LR30. (default = tepra.local)',
)
@click.option('--preview', is_flag=True, help='Generate preview.png without printing.')
@click.option('--font', '-f', help='Path or name of font. (default = bundled Adobe Source Sans)')
@click.option(
    '--fontsize', '-S', default=30, type=click.IntRange(0), help='Font size. [px] (default = 30)'
)
@click.option(
    '--depth', '-d', default=0, type=click.IntRange(-3, 3), help='Depth of color. (default = 0)'
)
@click.option('--message', '-m', multiple=True, help='Print a text.')
@click.option('--space', '-s', multiple=True, help='Leave space between parts. [px]')
@click.option('--qr', '-q', multiple=True, help='Draw a QR code.')
@click.option('--image', '-i', multiple=True, help='Paste an image.')
@click.pass_context
def do_print(ctx, address, preview, font, fontsize, depth, **_):
    if ctx.obj.get('parts') is None:
        print(
            'Please specify at least one part with -m/--message, -s/--space, and -q/--qr',
            file=sys.stderr,
        )
        sys.exit(1)

    if not font:
        font = importlib.resources.files('tepracli.assets').joinpath('ss3.ttf.gz')

    if font.endswith('.gz'):
        with open(font, 'rb') as gz:
            font = BytesIO(gzip.decompress(gz.read()))

    font = ImageFont.truetype(font, fontsize)

    rendered = []

    for typ, content in ctx.obj['parts']:
        if typ.name == 'message':
            actual_width = font.getmask(content).getbbox()[2] + 2  # add 2px for safe anti-aliasing
            im = Image.new('L', (actual_width, height), 'white')
            draw = ImageDraw.Draw(im)
            draw.text(
                (actual_width // 2, height // 2), content, font=font, fill='black', anchor='mm'
            )
            rendered.append(im)
        elif typ.name == 'space':
            im = Image.new('L', (int(content), height), 'white')
            rendered.append(im)
        elif typ.name == 'qr':
            qr = qrcode.QRCode(error_correction=qrcode.ERROR_CORRECT_L, box_size=1, border=0)
            qr.add_data(content)
            qr.make()
            im = qr.make_image()
            # rendered.append(im)
            if im.height <= height // 2:
                im = im.resize((im.width * 2, im.height * 2), resample=Image.NEAREST)
            elif im.height > 64:
                print(
                    f'Generated QR code exceeds 64px ({im.height}px). Please try a shorter string.',
                    file=sys.stderr,
                )
                sys.exit(1)
            newim = Image.new('L', (im.width, 64), 'white')
            newim.paste(im, (0, 64 // 2 - im.height // 2))
            rendered.append(newim)
        elif typ.name == 'image':
            im = Image.open(content)
            new_width = height * int(im.size[0] / im.size[1])
            new_height = height
            rendered.append(im.resize((new_width, new_height)))

    merged = rendered[0]
    for im in rendered[1:]:
        new = Image.new('L', (merged.width + im.width, height))
        new.paste(merged, (0, 0))
        new.paste(im, (merged.width, 0))
        merged = new

    # Valid image
    # 1. The image must be more than 84px in width
    # 2. The image width must be aligned to multiple of 2
    assumed_width = max(min_width, merged.width)
    if assumed_width % 2:
        assumed_width += 1

    if merged.width != assumed_width:
        new = Image.new('L', (assumed_width, height), color='white')
        new.paste(merged, (assumed_width // 2 - merged.width // 2, 0))
        merged = new

    for x in range(merged.width):
        for y in range(merged.height):
            merged.putpixel((x, y), 255 if merged.getpixel((x, y)) >= 127 else 0)

    if preview:
        merged.save('preview.png')
        sys.exit(0)

    im = merged.rotate(-90, expand=True)
    encoded = b''
    for y in range(im.height):
        aggregated = 0
        for shift, x in enumerate(range(im.width - 1, -1, -1)):
            if im.getpixel((x, y)) <= 127:
                aggregated += 1 << shift
        line = aggregated.to_bytes(8, 'big')
        encoded += line

    actual_address = socket.gethostbyname(address)
    c = Client(actual_address)

    err = c.post_depth(depth)
    if err:
        print(f'Failed to POST depth: {err}', file=sys.stderr)

    err = c.post_print(zlib.compress(encoded))
    if err:
        print(f'Failed to POST print: {err}', file=sys.stderr)


cmd()
