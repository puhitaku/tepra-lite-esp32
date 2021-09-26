## Sniffed packets

See [sniffed_packets.pcapng](sniffed_packets.pcapng) for a reference.


## Service UUIDs

 - `0x180f` Battery Service
 - `0xfff0` TEPRA Lite Specific Service


## Characteristic UUIDs

 - `0x2a19` Battery Level
 - `0xfff1` TEPRA Lite Specific (Notify only)
   - Behaves as RX
 - `0xfff2` TEPRA Lite Specific (Write Without Response only)
   - Beahves as TX


## Progress of communication (setup)

 1. Discover services and characteristics

 1. Write CCCD to enable Notification of Characteristic `0xfff1`


## Progress of communication (print)

Note: All "send" mean Write Without Response via TX characteristic `0xfff2` and all "receive" mean Notification via RX characteristic `0xfff1`.

 1. Send `f0 5a`

 1. Receive `f1 5a 00 02 00 54 45 50 52 41` (`\xf1 Z \0 \x02 \0 T E P R A`)

 1. Send `f0 5b {depth} 06`

    - `depth[4:4]` is sign (0 = positive, 1 = negative)
    - `depth[1:0]` is abs(depth) 0 <= x <= 3
    - Example 1: 0x13 means depth = -3
    - Example 2: 0x00 means depth = 0
    - Example 3: 0x03 means depth = 3

 1. Send `f0 5c` + 8 Bytes (a line of the image) + 8 Bytes (another line of the image) 6 times

    - (2 + 8 + 8) * 6 = 108 Bytes

 1. Wait until `f1 5c` + 4 Bytes are received

    - Meaning of last 4 Bytes are unknown

 1. Repeat sending lines at least 84 lines (2 lines * 6 * 7)

 1. Send `f0 5d 00` (indication of the end of lines?)

 1. Receive `f1 5d 00`

 1. Send `f0 5e`

 1. Receive `f1 5d 01 00`

 1. Repeat sending `f0 5e` and receiving `f1 5d 01 00` until it receives `f1 5d 00 00`
