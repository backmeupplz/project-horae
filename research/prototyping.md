# Prototype v0: no factory

_Planned 2026-10-03. Prices are approximate, in USD._

Goal: get every function working on the desk first, using off-the-shelf boards and hand wiring. We miniaturize the PCB once the behaviour is right.

## Step 0: the Watchy we already have
The Watchy is already a working ESP32 + e-paper + accelerometer board. Use it for firmware experiments while the parts ship.

## Step 1: XIAO carrier PCB, hand-soldered
Skip the breadboard. Design a small 2-layer carrier board in KiCad, about 25×40 mm, with:
- castellated pads for a XIAO module. ESP32S3 and nRF52840 Sense share a footprint, so the chip decision becomes a module swap.
- the 0.97" display's FPC connector plus its booster circuit, using the Watchy / Good Display reference design.
- 4 buttons, a motor MOSFET, and LiPo pads.

Every part is hand-solderable: 0603/0805 passives, SOT-23, a 0.5 mm FPC connector (drag-solder with flux), and the castellated module. The Sense's onboard IMU avoids hand-placing a 2×2 mm LGA accelerometer.

Order bare boards from OSH Park (no duty, slow) or JLC (fast). Print a build123d case around the board.

### Parts
| Part | Link | ~Price |
|---|---|---|
| Seeed XIAO ESP32S3 | [seeedstudio.com](https://www.seeedstudio.com/XIAO-ESP32S3-p-5627.html) | $7.50 |
| Seeed XIAO nRF52840 Sense | [seeedstudio.com](https://www.seeedstudio.com/Seeed-XIAO-BLE-Sense-nRF52840-p-5253.html) | $16 |
| GDEM0097T61 0.97" e-paper | [Good Display](https://www.good-display.com/product/486.html), [buy-lcd](https://www.buy-lcd.com/products/gdem0097t61) | $4–5 |
| DESPI-C02-CV0097 adapter (bench testing the panel before our board arrives) | [openelab](https://openelab.io/products/goodisplay-0-97-inch-epaper) | ? |
| 150 mAh LiPo | [Adafruit 1317](https://www.adafruit.com/product/1317) | $6 |
| Vibration motor disc | [Adafruit 1201](https://www.adafruit.com/product/1201) | $2 |
| **Nordic PPK2** (real µA numbers) | [nordicsemi.com](https://www.nordicsemi.com/Products/Development-hardware/Power-Profiler-Kit-2) | ~$100 |

## Step 2–3: iterate
Revise the board and case together until everything works and fits on a wrist.

## Step 4: miniaturize
Make a custom 4-layer board with a bare chip and factory assembly. This is the expensive step, so it waits until v0 works.

## Charging
- **Prototype:** the XIAO's own USB-C.
- **Final watch:** a 4-pin magnetic pogo connector on the back (5V, GND, D+, D−). It gives charging *and* USB flashing at zero added height, and both chips have native USB.
- **Why not USB-C:** a USB-C socket is ~3.2 mm tall and ~9 mm wide, so it sets a floor on the case's edge thickness and is an ingress point.
