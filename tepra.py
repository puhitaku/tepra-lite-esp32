# This example finds and connects to a peripheral running the
# UART service (e.g. ble_simple_peripheral.py)

import binascii
import bluetooth
import gc
import time
from ble_advertising import decode_name
from micropython import const

# Silence type checkers
try:
    from typing import Optional
except ImportError:
    from typ1ng import Optional

_IRQ_CENTRAL_CONNECT = const(1)
_IRQ_CENTRAL_DISCONNECT = const(2)
_IRQ_GATTS_WRITE = const(3)
_IRQ_GATTS_READ_REQUEST = const(4)
_IRQ_SCAN_RESULT = const(5)
_IRQ_SCAN_DONE = const(6)
_IRQ_PERIPHERAL_CONNECT = const(7)
_IRQ_PERIPHERAL_DISCONNECT = const(8)
_IRQ_GATTC_SERVICE_RESULT = const(9)
_IRQ_GATTC_SERVICE_DONE = const(10)
_IRQ_GATTC_CHARACTERISTIC_RESULT = const(11)
_IRQ_GATTC_CHARACTERISTIC_DONE = const(12)
_IRQ_GATTC_DESCRIPTOR_RESULT = const(13)
_IRQ_GATTC_DESCRIPTOR_DONE = const(14)
_IRQ_GATTC_READ_RESULT = const(15)
_IRQ_GATTC_READ_DONE = const(16)
_IRQ_GATTC_WRITE_DONE = const(17)
_IRQ_GATTC_NOTIFY = const(18)
_IRQ_GATTC_INDICATE = const(19)

LR30_DEVICE_NAME = 'LR30'


class Service:
    start_handle: int
    end_handle: int
    uuid: bluetooth.UUID

    def __init__(self, start_handle, end_handle, uuid):
        self.start_handle, self.end_handle = start_handle, end_handle
        self.uuid = bluetooth.UUID(bytes(uuid))  # Copy the UUID instance as it's mutable

    def __str__(self):
        return '<Service start={:#04x} end={:#04x} uuid={}>'.format(
            self.start_handle, self.end_handle, self.uuid
        )

    def __repr__(self):
        return self.__str__()


class Characteristic:
    handle: int
    value_handle: int
    properties: int
    uuid: bluetooth.UUID

    def __init__(self, handle, value_handle, properties, uuid):
        self.handle, self.value_handle, self.properties, self.uuid = (
            handle,
            value_handle,
            properties,
            bluetooth.UUID(bytes(uuid)),  # Copy the UUID instance as it's mutable
        )

    def __str__(self):
        return '<Chr handle={:#x} vhandle={:#x}, prop={:#02x}, uuid={}>'.format(
            self.handle, self.value_handle, self.properties, self.uuid
        )

    def __repr__(self):
        return self.__str__()

    def prop_extended_properties(self):
        return self.properties & 0x80 > 0

    def prop_authenticated_signed_writes(self):
        return self.properties & 0x40 > 0

    def prop_indicate(self):
        return self.properties & 0x20 > 0

    def prop_notify(self):
        return self.properties & 0x10 > 0

    def prop_write(self):
        return self.properties & 0x08 > 0

    def prop_write_without_response(self):
        return self.properties & 0x04 > 0

    def prop_read(self):
        return self.properties & 0x02 > 0

    def prop_broadcast(self):
        return self.properties & 0x01 > 0


class Descriptor:
    handle: int
    uuid: bluetooth.UUID

    def __init__(self, handle, uuid):
        self.handle, self.uuid = (
            handle,
            bluetooth.UUID(bytes(uuid)),  # Copy the UUID instance as it's mutable
        )

    def __str__(self):
        return '<Dsc handle={:#x} uuid={}>'.format(self.handle, self.uuid)

    def __repr__(self):
        return self.__str__()


class BLESimpleCentral:
    # Scan result
    _name = None
    _addr_type = None
    _addr = None

    # Callbacks for completion of various operations
    # These reset back to None after being invoked
    _scan_callback = None
    _svc_scan_callback = None
    _svc_done_callback = None
    _chr_scan_callback = None
    _chr_done_callback = None
    _desc_scan_callback = None
    _desc_done_callback = None
    _read_callback = None
    _read_done_callback = None
    _write_done_callback = None
    _conn_callback = None

    # Persistent callback for when new data is notified from the device
    _notify_callback = None

    # Connected device
    _conn_handle = None

    _debug = False

    def __init__(self, ble, debug=False):
        self._ble = ble
        self._ble.active(True)
        self._ble.irq(self._irq)

        self._reset()
        self._debug = debug

    def _reset(self):
        self._name = None
        self._addr_type = None
        self._addr = None

        self._scan_callback = None
        self._svc_scan_callback = None
        self._svc_done_callback = None
        self._chr_scan_callback = None
        self._chr_done_callback = None
        self._desc_scan_callback = None
        self._desc_done_callback = None
        self._conn_callback = None
        self._read_callback = None
        self._read_done_callback = None
        self._write_done_callback = None
        self._notify_callback = None

        self._conn_handle = None

    def _irq(self, event, data):
        if event == _IRQ_SCAN_RESULT:
            addr_type, addr, adv_type, rssi, adv_data = data
            if adv_type != 0x04:
                return

            addr_hex = ':'.join('{:02x}'.format(x) for x in addr)
            name = decode_name(adv_data) or '?'
            name = name.strip('\x00')
            self._log(
                'adv_type={} addr={} name={} {} rssi={} adv_data={}'.format(
                    adv_type, addr_hex, name, len(name), rssi, str(bytes(adv_data))
                )
            )

            if name == LR30_DEVICE_NAME:
                # Found a potential device, remember it and stop scanning
                self._addr_type = addr_type
                self._addr = bytes(addr)  # Note: addr buffer is owned by caller so need to copy it
                self._name = name
                self._ble.gap_scan(None)  # Stop scanning

        elif event == _IRQ_SCAN_DONE:
            self._log('Scanning done')
            if self._scan_callback:
                self._scan_callback(self._addr is not None)

        elif event == _IRQ_PERIPHERAL_CONNECT:
            # Connected successfully
            conn_handle, addr_type, addr = data
            if addr_type == self._addr_type and addr == self._addr:
                self._log('Connected')
                self._conn_handle = conn_handle

        elif event == _IRQ_PERIPHERAL_DISCONNECT:
            self._log('Disconnected')
            # Disconnected (either initiated by us or the remote end)
            conn_handle, _, _ = data
            if conn_handle == self._conn_handle:
                # If it was initiated by us, it'll already be reset
                self._reset()

        elif event == _IRQ_GATTC_SERVICE_RESULT:
            # Connected device returned a service
            conn_handle, start_handle, end_handle, uuid = data
            if conn_handle == self._conn_handle and self._svc_scan_callback is not None:
                self._svc_scan_callback(start_handle, end_handle, uuid)

        elif event == _IRQ_GATTC_SERVICE_DONE:
            self._log('Discovering service done')
            # Service query complete
            if self._svc_done_callback is not None:
                self._svc_done_callback()

        elif event == _IRQ_GATTC_CHARACTERISTIC_RESULT:
            # Connected device returned a characteristic
            conn_handle, def_handle, value_handle, properties, uuid = data
            if conn_handle == self._conn_handle and self._chr_scan_callback is not None:
                self._chr_scan_callback(Characteristic(def_handle, value_handle, properties, uuid))

        elif event == _IRQ_GATTC_CHARACTERISTIC_DONE:
            self._log('Discovering characteristics done')
            # Characteristic query complete
            if self._chr_done_callback is not None:
                self._chr_done_callback()

        elif event == _IRQ_GATTC_DESCRIPTOR_RESULT:
            # Connected device returned a descriptor
            conn_handle, dsc_handle, uuid = data
            if conn_handle == self._conn_handle and self._desc_scan_callback is not None:
                self._desc_scan_callback(dsc_handle, uuid)

        elif event == _IRQ_GATTC_DESCRIPTOR_DONE:
            self._log('Discovering descriptor done')
            # Descriptor query complete
            if self._desc_done_callback is not None:
                self._desc_done_callback()

        elif event == _IRQ_GATTC_READ_RESULT:
            conn_handle, value_handle, char_data = data
            if conn_handle == self._conn_handle:
                self._read_callback(char_data)

        elif event == _IRQ_GATTC_READ_DONE:
            self._log('Reading characteristics done')
            conn_handle, value_handle, status = data
            if conn_handle == self._conn_handle:
                self._read_done_callback()

        elif event == _IRQ_GATTC_WRITE_DONE:
            self._log('Writing characteristics done')
            conn_handle, value_handle, status = data
            if conn_handle == self._conn_handle:
                self._write_done_callback(value_handle, status)

        elif event == _IRQ_GATTC_NOTIFY:
            self._log('Notification received')
            conn_handle, value_handle, data = data
            if conn_handle == self._conn_handle:
                if self._notify_callback is not None:
                    self._notify_callback(value_handle, data)

    def _log(self, *o):
        if not self._debug:
            return
        print('BT:', *o)

    def scan(self) -> bool:
        """Find a device advertising the environmental sensor service."""
        found = None

        def callback(_found):
            nonlocal found
            found = _found

        self._addr_type = None
        self._addr = None
        self._scan_callback = callback
        self._ble.gap_scan(5000, 100000, 10000, True)

        while found is None:
            time.sleep_ms(10)

        self._scan_callback = None
        return found

    def connect(self):
        """Connect to the specified device (otherwise use cached address from a scan)."""
        if self._addr_type is None or self._addr is None:
            return False

        self._ble.gap_connect(self._addr_type, self._addr)

        while self._conn_handle is None:
            time.sleep_ms(10)

        return True

    def disconnect(self):
        """Disconnect from current device."""
        if not self._conn_handle:
            return
        self._ble.gap_disconnect(self._conn_handle)
        self._reset()

    def discover_services(self):
        svcs = []
        done = False

        if self._conn_handle is None:
            return []

        def callback_scan(start_handle, end_handle, uuid):
            nonlocal svcs
            svcs.append(Service(start_handle, end_handle, uuid))

        def callback_done():
            nonlocal self, done
            done = True

        self._svc_scan_callback = callback_scan
        self._svc_done_callback = callback_done
        self._ble.gattc_discover_services(self._conn_handle)

        while not done:
            time.sleep_ms(10)

        self._svc_scan_callback = None
        self._svc_done_callback = None

        return svcs

    def discover_characteristics(self, service: Service):
        chrs = []
        done = False

        if self._conn_handle is None:
            return []

        def callback_scan(c):
            nonlocal chrs
            chrs.append(c)

        def callback_done():
            nonlocal done
            done = True

        self._chr_scan_callback = callback_scan
        self._chr_done_callback = callback_done
        self._ble.gattc_discover_characteristics(
            self._conn_handle, service.start_handle, service.end_handle
        )

        while not done:
            time.sleep_ms(10)

        self._chr_scan_callback = None
        self._chr_done_callback = None

        return chrs

    def discover_descriptors(self, service: Service):
        descs = []
        done = False

        if self._conn_handle is None:
            return []

        def callback_scan(handle, uuid):
            nonlocal descs
            descs.append(Descriptor(handle, uuid))

        def callback_done():
            nonlocal done
            done = True

        self._desc_scan_callback = callback_scan
        self._desc_done_callback = callback_done
        self._ble.gattc_discover_descriptors(
            self._conn_handle, service.start_handle, service.end_handle
        )

        while not done:
            time.sleep_ms(10)

        self._desc_scan_callback = None
        self._desc_done_callback = None

        return descs

    def _read(self, handle: int) -> Optional[bytes]:
        data = None
        done = False

        if self._conn_handle is None:
            return data

        def callback_read(d: memoryview):
            nonlocal data
            data = bytes(d)  # Copy the value from the memoryview

        def callback_done():
            nonlocal done
            done = True

        self._read_callback = callback_read
        self._read_done_callback = callback_done
        self._ble.gattc_read(self._conn_handle, handle)

        while not done:
            time.sleep_ms(10)

        self._read_callback = None
        self._read_done_callback = None

        return data

    def read(self, c: Characteristic):
        return self._read(c.value_handle)

    def write(self, c: Characteristic, data: bytes):
        """Send data without response."""
        if not c.prop_write_without_response():
            return

        if self._conn_handle is None:
            return

        self._log('Writing without response: {}'.format(hexstr(data)))
        self._ble.gattc_write(self._conn_handle, c.value_handle, data, 0)
        return

    def write_request(self, c: Characteristic, data: bytes, callback):
        """Send data with response."""
        done = False

        if not c.prop_write():
            return

        if self._conn_handle is None:
            return

        def callback_done(handle, status):
            nonlocal done
            done = True
            callback(handle, status)

        self._write_done_callback = callback_done

        self._log('Writing with response')
        self._ble.gattc_write(self._conn_handle, c.value_handle, data, 1)

        while not done:
            time.sleep_ms(10)

        self._write_done_callback = None

        return

    def write_cccd(self, c: Characteristic, indication=False, notification=False):
        """Write the Client Characteristic Configuration Descriptor of a characteristic."""
        done = False

        if not c.prop_indicate() and not c.prop_notify():
            return

        if self._conn_handle is None:
            return

        def callback_done(*_):
            nonlocal done
            done = True

        self._write_done_callback = callback_done
        value = (0b10 if indication else 0b00) + (0b01 if notification else 0b00)

        # FIXME: it should lookup the actual handle of CCCD from descriptors, not adding 1 to the value handle
        self._ble.gattc_write(self._conn_handle, c.value_handle + 1, bytes([value]), 1)

        while not done:
            time.sleep_ms(10)

        self._write_done_callback = None
        return

    def write_wait_notification(self, tx: Characteristic, tx_data: bytes, rx: Characteristic) -> Optional[bytes]:
        """Write without response and wait for a notification"""
        rx_data = None

        if not tx.prop_write_without_response() or not rx.prop_notify():
            return rx_data

        if self._conn_handle is None:
            return rx_data

        def callback(handle, d):
            nonlocal rx_data
            if handle == rx.value_handle:
                rx_data = d

        self._notify_callback = callback
        self.write(tx, tx_data)

        while rx_data is None:
            time.sleep_ms(10)

        self._notify_callback = None
        return rx_data

    def wait_notification(self, rx: Characteristic) -> Optional[bytes]:
        """Wait for a notification from the characteristic"""
        rx_data = None

        if not rx.prop_notify():
            return

        if self._conn_handle is None:
            return

        def callback(handle, d):
            nonlocal rx_data
            if handle == rx.value_handle:
                rx_data = d

        self._notify_callback = callback

        while rx_data is None:
            time.sleep_ms(10)

        self._notify_callback = None
        return rx_data


def hexstr(b: bytes):
    return str(binascii.hexlify(bytes(b)))


def p(*b):
    return bytes(b)


def lookup_characteristic(chrs: list[list[Characteristic]], uuid: bluetooth.UUID):
    for cl in chrs:
        for c in cl:
            if c.uuid == uuid:
                return c


class Tepra:
    _battery_svc: Service
    _print_svc: Service

    _battery_chr: Characteristic
    _tx: Characteristic
    _rx: Characteristic

    _ble = bluetooth.BLE
    _central = BLESimpleCentral
    _debug = False

    def __init__(self, debug=False):
        self._ble = bluetooth.BLE()
        self._central = BLESimpleCentral(self._ble, debug=debug)
        self._debug = debug

    def _log(self, *o):
        if not self._debug:
            return
        print('Tepra:', *o)

    def connect(self) -> bool:
        # Scan and find a TEPRA Lite
        success = self._central.scan()
        if not success:
            self._log('TEPRA Lite was not found')
            return False

        # Connect to it
        success = self._central.connect()
        if not success:
            self._log('Failed to connect to the TEPRA Lite, resetting...')
            return False

        # Discover all services
        svcs = self._central.discover_services()
        if not svcs:
            self._log('Failed to discover any service of TEPRA Lite, resetting...')
            return False

        # Discover all characteristics in all services
        chrs = []
        for svc in svcs:
            chrs.append(self._central.discover_characteristics(svc))

        if not chrs:
            self._log('Failed to discover any characteristic of the service, resetting...')
            return False

        # Discover all descriptors in all services
        descs = []
        for svc in svcs:
            descs.append(self._central.discover_descriptors(svc))

        if len(chrs) < 2:
            self._log('Insufficient number of characteristics, resetting...')
            return False

        # Look for characteristics
        self._battery_chr = lookup_characteristic(chrs, bluetooth.UUID(0x2a19))
        self._tx = lookup_characteristic(chrs, bluetooth.UUID(0xfff2))
        self._rx = lookup_characteristic(chrs, bluetooth.UUID(0xfff1))

        if self._tx is None or self._rx is None:
            self._log('Failed to lookup the printer status characteristic, resetting...')
            return False

        # Set CCCD of RX characteristics
        self._central.write_cccd(self._rx, indication=False, notification=True)
        return True

    def disconnect(self):
        raise NotImplementedError

    def fetch_remaining_battery(self) -> (bool, int):
        recv = self._central.read(self._battery_chr)
        if recv is None or len(recv) < 1:
            self._log('Failed to read the battery information')
            return False, 0
        return True, recv[0]

    def get_ready(self, depth=0) -> bool:
        recv = self._central.write_wait_notification(self._tx, b'\xf0\x5a', self._rx)
        if not recv:
            return False
        self._log('Recv:', hexstr(recv))

        if depth < -3 or depth > 3:
            raise ValueError('invalid depth: {}'.format(depth))

        d = 0x10 - depth if depth < 0 else 0x00 + depth
        self._log('Depth: {} ({:02x})'.format(depth, d))

        recv = self._central.write_wait_notification(self._tx, p(0xf0, 0x5b, d, 0x06), self._rx)
        if not recv:
            return False
        self._log('Recv:', hexstr(recv))

        return True

    def print(self, b: bytes, d: int) -> (bool, str):
        ret = self._print(b, d)
        gc.collect()
        return ret

    def _print(self, b: bytes, d: int) -> (bool, str):
        if len(b) % 16 != 0:
            return False, "insufficient length, image data length must be aligned to 16"

        # Get ready
        recv = self.get_ready(depth=d)
        self._log('Get ready:', recv)
        if not recv:
            return False, 'failed to get ready'

        i = 1
        err = ""

        for ofs in range(0, len(b)-1, 16):
            # Print until EOF
            # The stream returns 16 bytes or shorter bytes if there are no body to read

            buf = bytes((
                0xf0,
                0x5c,
                b[ofs+6], b[ofs+7], b[ofs+4], b[ofs+5], b[ofs+2], b[ofs+3], b[ofs+0], b[ofs+1],
                b[ofs+14], b[ofs+15], b[ofs+12], b[ofs+13], b[ofs+10], b[ofs+11], b[ofs+8], b[ofs+9],
            ))

            self._central.write(self._tx, buf)

            if i % 6 == 0:
                self._log('Wait for a notification...')
                self._central.wait_notification(self._rx)
            else:
                time.sleep_ms(20)

            i += 1

        # End sending lines
        recv = self._central.write_wait_notification(self._tx, p(0xf0, 0x5d, 0x00), self._rx)
        self._log('End sending lines:', hexstr(recv))

        self._log('Waiting for the print to finish...')
        done = False
        while not done:
            recv = self._central.write_wait_notification(self._tx, p(0xf0, 0x5e), self._rx)
            if len(recv) < 4:
                self._log('Received an invalid reply:', hexstr(recv))
                return False, 'received an invalid reply: ' + hexstr(recv)
            done = recv[2] == 0x01

        self._log('Done!')
        return True, err

    @staticmethod
    def validate(pixels: list[bytes]) -> tuple[bool, str]:
        """Validates the image if ...
        1. it has at least one pixel
        2. all lines are the same length
        """

        if len(pixels) == 0:
            return False, 'has no pixels'

        width = len(pixels[0])
        for line in pixels:
            if len(line) != width:
                return False, 'line lengths are not uniform'

        return True, ''

    @staticmethod
    def validate_for_printing(pixels: list[bytes]) -> (bool, str):
        """Validates the image if ...
        1. it has at least 84 lines
        2. all lines are 64 pixel length
        """

        if len(pixels) < 84:
            return False, 'has no enough lines'

        for line in pixels:
            if len(line) != 8:  # 8 Bytes = 64 bits (one line)
                return False, 'line lengths are not uniform'

        return True, ''
