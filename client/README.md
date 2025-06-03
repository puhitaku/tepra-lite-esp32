tepracli - reference impl. of tepra-lite-esp32 client
=====================================================

## Install with pip

```
$ pip install tepracli
$ tepracli
```

## Install with uvx

```
$ uvx tepracli
```

## Install from source

It's recommended to enable editable mode `-e`; pull this repository from remote and tepracli will be updated automatically.

```
$ cd tepra-lite-esp32/client
$ pip install -e .
$ python -m tepracli
```

## Usage

Subcommands:

 - print: print strings and QR code
 - battery: get remaining battery

### Print

```
Usage: tepracli print [OPTIONS]

Options:
  -a, --address TEXT            The IP address or the URL of TEPRA Lite LR30. (default = tepra.local)
  --preview                     Generate preview.png without printing.
  -f, --font TEXT               Path or name of font. (default = bundled Adobe
                                Source Sans)
  -S, --fontsize INTEGER RANGE  Font size. [px] (default = 30)  [x>=0]
  -d, --depth INTEGER RANGE     Depth of color. (default = 0)  [-3<=x<=3]
  -m, --message TEXT            Print a text.
  -s, --space TEXT              Leave space between parts. [px]
  -q, --qr TEXT                 Draw a QR code.
  --help                        Show this message and exit.
```

### Print examples

|Options|Output|
|:-|:-:|
|`-m Hello`|<img src="example1.png" height=80px>|
|`-S 15 -m Hello`|<img src="example2.png" height=80px>|
|`-S 50 -m Hello`|<img src="example3.png" height=80px>|
|`-m Hello -m World`|<img src="example4.png" height=80px>|
|`-m Hello -s 10 -m World`|<img src="example5.png" height=80px>|
|`-q "http://example.com" -s 20 -m "http://example.com"`|<img src="example6.png" height=80px>|

### Get Remaining Battery

It's not really useful: LR30 replies 99% as the percentage of remaining battery every time.

```
Usage: tepracli battery [OPTIONS]

Options:
  -a, --address TEXT  The IP address or the URL of TEPRA Lite LR30. (default = tepra.local)
  --help              Show this message and exit.

```

```
$ tepracli battery -a ${TEPRA_ADDRESS}
99%
```
