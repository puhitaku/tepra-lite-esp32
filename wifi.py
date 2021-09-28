import network
import utime

wifi = network.WLAN(network.STA_IF)


def up(ssid, psk):
    if wifi.isconnected():
        return True

    print('Connecting to an AP')
    print('SSID: {}, PSK: (hidden)'.format(ssid))

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
        print('Failed to connect: timed out')
        return False

    print('Successfully connected')
    return True


def show_ifconfig():
    print('Address: {}, Netmask: {}, GW: {}, DNS: {}'.format(*wifi.ifconfig()))
