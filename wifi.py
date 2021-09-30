import network
import utime

from tepra import new_logger

log = new_logger('Wi-Fi  :')
wifi = network.WLAN(network.STA_IF)


def up(ssid, psk):
    if wifi.isconnected():
        return True

    log('Connecting to an AP')
    log('SSID: {}, PSK: (hidden)', ssid)

    wifi.active(True)
    wifi.connect(ssid, psk)

    elapsed = 0
    while not wifi.isconnected() and elapsed < 10:
        utime.sleep(1)
        elapsed += 1

    for _ in range(10):
        if wifi.isconnected():
            break
        utime.sleep(1)
    else:
        log('Failed to connect: timed out')
        return False

    log('Successfully connected')
    return True


def show_ifconfig():
    log('Address: {}, Netmask: {}, GW: {}, DNS: {}', *wifi.ifconfig())
