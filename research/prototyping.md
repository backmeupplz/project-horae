# Prototype v0: no factory

_Planned 2026-10-03. Prices are approximate, in USD._

Goal: get every function working on the desk first, using off-the-shelf boards and hand wiring. We miniaturize the PCB once the behaviour is right.

## Step 0: the Watchy we already have
The Watchy is already a working ESP32 + e-paper + accelerometer board. Use it for firmware experiments while the parts ship.

## Step 1: breadboard kit
The two XIAO boards have the same footprint and pinout, so the same wiring can test **ESP32-S3 vs nRF52840** side by side.

| Part | Why | Link | ~Price |
|---|---|---|---|
| Seeed XIAO ESP32S3 | Watchy-compatible chip, LiPo charger, USB-C, 21×17.5 mm | [seeedstudio.com](https://www.seeedstudio.com/XIAO-ESP32S3-p-5627.html) | $7.50 |
| Seeed XIAO nRF52840 Sense | The low-power alternative, with a 6-axis IMU (step counter) and BQ25101 charger | [seeedstudio.com](https://www.seeedstudio.com/Seeed-XIAO-BLE-Sense-nRF52840-p-5253.html) | $16 |
| GDEM0097T61 0.97" 184×88 e-paper | Bar-shaped display candidate | [Good Display](https://www.good-display.com/product/486.html), [buy-lcd](https://www.buy-lcd.com/products/gdem0097t61) (out of stock 2026-10-03) | $4–5 |
| DESPI-C02-CV0097 adapter | Converts the display's 18-pin FPC to 2.54 mm header pins | [openelab](https://openelab.io/products/goodisplay-0-97-inch-epaper) | ? |
| 150 mAh LiPo (3.8×19.75×26) | Battery, soldered to the XIAO BAT pads | [Adafruit 1317](https://www.adafruit.com/product/1317) | $6 |
| Vibration motor disc | Haptics | [Adafruit 1201](https://www.adafruit.com/product/1201) | $2 |
| 4× tactile buttons, breadboard, jumpers | Watchy-style inputs | any | $5 |
| **Nordic PPK2** | Measures real µA, which decides the chip and battery size | [nordicsemi.com](https://www.nordicsemi.com/Products/Development-hardware/Power-Profiler-Kit-2) | ~$100 |

The kit is about $45 without the PPK2. The PPK2 is the one tool worth buying, because every battery-life number so far is an estimate.

## Step 2: chunky printed case
Print a build123d case around the breadboarded stack on the A1 mini, so we can wear it and test the band form factor early.

## Step 3: first custom board, hand-soldered
Order bare 2-layer PCBs from JLC (about $2 for 5 plus shipping) as a carrier for the XIAO and the display connector. Solder them by hand. Factory assembly isn't needed until Step 4.

## Step 4: miniaturize
Make a custom 4-layer board with a bare chip and factory assembly. This is the expensive step, so it waits until v0 works.

## Charging
- **Prototype:** the XIAO's own USB-C.
- **Final watch:** a 4-pin magnetic pogo connector on the back (5V, GND, D+, D−). It gives charging *and* USB flashing at zero added height, and both chips have native USB.
- **Why not USB-C:** a USB-C socket is ~3.2 mm tall and ~9 mm wide, so it sets a floor on the case's edge thickness and is an ingress point.
