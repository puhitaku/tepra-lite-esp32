# tepra-lite-esp32

*MicroPython module to communicate with KING JIM TEPRA Lite LR30 as a result of reverse engineering.*

Print anything you want to. Print via any interface you have. It's also capable of printing automatically-generated images on your ESP32.


## Prerequisites

 - ESP32
   - Developed on ESP-WROOM-32
   - Any ESP32 modules should be capable of running this
 - Latest stable MicroPython
   - Developed on esp32-20210418-v1.15.bin


## Installing

TODO


## Why?

Why I wrote this module in MicroPython is because it enriches the time of coding on microcontrollers. The simple and easy-to-use API of `ubluetooth` is also a prominently good point. It let me focus on high-level behavior of BLE stack and may help people who are interested in reverse engineering and re-implementing BLE communication.

The nature of `import` will also work nicely when you prototype your project that connects something and TEPRA Lite. Import `tepra` on the REPL and try communicating with it step-by-step.

And here's another reason: preventing nightmares of Bluetooth stacks on PC, for example, Bluez. Bluez has a Python binding that is prone to crash and raise exceptions everywhere. While there are some choices like Bleak that works multi-OS, I didn't choose this. Resetting entire stack including the physical BT module is hard without rebooting. When it comes to ESP32, it's super easy; you just have to push the RESET button on the module. This literally resets everything on ESP32 and removes any side effects until then.

Simple and easy-to-use, well-documented, ease of resetting and removing environmental dependencies, and extreme extendability including electronic circuits. ESP32 is a great environment to get started with Bluetooth.

