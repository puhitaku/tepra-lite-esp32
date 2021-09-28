import sys
import binascii
import zlib
import cv2
import numpy as np

ENTER_KEY_WIN = 13
ENTER_KEY_LINUX = 10
ESC_KEY = 27


def nothing(x):
    pass


if len(sys.argv) <= 1:
    print("usage: pic2bin.py <imagefile>")
    sys.exit()

windowname = sys.argv[1] + '    Enter : save    Esc : quit'

img = cv2.imread(sys.argv[1], cv2.IMREAD_COLOR)
if img is None:
    print("Image open error")
    sys.exit()
gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

height, width = gray.shape
if height != 64:
    print("Image height is invalid")
    sys.exit()

cv2.namedWindow(windowname, cv2.WINDOW_AUTOSIZE | cv2.WINDOW_GUI_NORMAL)

lut = np.arange(256, dtype='float32')
lut = pow((lut / 255), 2.2)

binalized = np.zeros((height, width, 1), np.uint8)

cumulative_err = 0
calc_done = 0
while True:
    if not calc_done:
        for y in range(height):
            for x in range(width):
                linear_val = lut[gray[y, x]]
                if linear_val + cumulative_err < 0.5:
                    cumulative_err += linear_val
                    binalized[y, x] = 0
                else:
                    cumulative_err -= 1.0 - linear_val
                    binalized[y, x] = 255
        calc_done = 1

    frame = cv2.cvtColor(binalized, cv2.COLOR_GRAY2BGR)
    frame = cv2.vconcat([img, frame])
    cv2.imshow(windowname, frame)

    key = cv2.waitKey(100)
    if (key == ENTER_KEY_WIN) | (key == ENTER_KEY_LINUX):
        cv2.destroyAllWindows()
        break
    elif key == ESC_KEY:
        sys.exit()

img_out = cv2.rotate(binalized, cv2.ROTATE_90_CLOCKWISE)
height, width = img_out.shape

encoded = b''
for y in range(height):
    aggregated = 0
    for shift, x in enumerate(range(width - 1, -1, -1)):
        if img_out[y, x] <= 127:
            aggregated += 1 << shift
    line = aggregated.to_bytes(8, 'big')
    encoded += line
    print(binascii.hexlify(line))

with open('hello.bin', 'wb') as f:
    f.write(zlib.compress(encoded))
# cv2.imwrite('hello_binalized.png', binalized)
