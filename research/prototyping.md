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

### v0 bill of materials (hand-soldered, 2-layer 0.8 mm carrier)
| Block | Part | Package | Notes |
|---|---|---|---|
| MCU | Seeed [XIAO ESP32S3](https://www.seeedstudio.com/XIAO-ESP32S3-p-5627.html) / [XIAO ESP32C6](https://www.seeedstudio.com/Seeed-Studio-XIAO-ESP32C6-p-5884.html) | castellated 21×17.8 | Same footprint, both have Wi-Fi + BLE, so we test both |
| Display | Good Display [GDEM0097T61](https://www.good-display.com/product/486.html) | 30×14.15×1.0, FPC 18p **0.5 mm**, 0.30 mm with stiffener | [datasheet](https://v4.cecdn.yun300.cn/100001_1909185148/GDEM0097T61-V1.1%20new.pdf) |
| Display socket | Hirose **FH34SRJ-18S-0.5SH(50)** | 18p 0.5 mm ZIF, **1.0 mm tall**, top+bottom contact | The ribbon plugs in, so we never solder the ribbon itself |
| E-paper booster | Q1 AO3400A (Watchy) or Si1308EDL (GD ref), D1–D3 MBR0530, L1 47 µH ≤1.2 mm ([PNLS3012-470M](https://jlcpcb.com/partdetail/DMBJ-PNLS3012470/C2849443) or Murata LQH3NPN470NJ0L), R1 1 MΩ, R2 2.2 Ω, 7× 1 µF/25 V, 2× 4.7 µF/25 V | SOT-23, SOD-123, 3×3, 0603/0805 | Copied from the datasheet's typical circuit (p.20) |
| RTC | NXP PCF8563T + 32.768 kHz crystal (hand-solder) or RV-3028-C7 (better, needs hot air) | SO-8 / 3.2×1.5 | The XIAO's internal RC clock is too inaccurate for a watch (verify whether a 32 kHz crystal is fitted) |
| Accelerometer | Bosch BMA423 (same as Watchy) | LGA-12 2×2 | Can't be soldered with an iron: use hot air or a hot plate, or have JLC place just this part. Optional in v0 |
| Buttons | 4× Panasonic EVQ-PUC02K (same as Watchy) | side-push, 1.35 mm tall | – |
| Haptics | 8 mm coin ERM motor + AO3400A + diode | – | – |
| Battery | 3.7 V LiPo **301525** (~3×15×25, ~110 mAh) with PCM | soldered leads | 15 mm wide, narrower than the XIAO |
| Power | 47–100 µF bulk cap at the battery, 2× 1 MΩ divider for battery voltage | 1206 / 0603 | Wi-Fi bursts draw ~300 mA from a tiny cell |
| Power meter | [Nordic PPK2](https://www.nordicsemi.com/Products/Development-hardware/Power-Profiler-Kit-2) | – | Optional, ~$100 |

### Size estimates
| | L × W × T (mm) | What sets each dimension |
|---|---|---|
| [Fitbit Charge 6](https://store.google.com/product/fitbit_charge_6_specs) | 36.7 × 23.1 × 11.2 | target |
| **v0** XIAO carrier | **~40 × 21 × 10–11** | L: display + walls + USB-C. W: XIAO 17.8 + walls. T: 0.6 lip + 1.0 display + ~2.6 XIAO (USB-C end ~4.3, unverified) + 0.8 PCB + 3.3 battery + 1.0 floor |
| **v1** custom 4-layer, bare ESP32-S3/C6 | **~34 × 18 × 7** | L: 30 mm display + walls + antenna keep-out. T: 0.6 + 1.0 + 1.2 tallest part + 0.8 PCB + 2.6 battery (2.4 mm cell + swelling) + 0.8 |
| v1 with nRF54L15 (no Wi-Fi) | ~32 × 17 × 6 | same, with a ~1.5 mm, 50 mAh cell |

## Step 2–3: iterate
Revise the board and case together until everything works and fits on a wrist.

## Step 4: miniaturize
Make a custom 4-layer board with a bare chip and factory assembly. This is the expensive step, so it waits until v0 works.

## Charging
- **Prototype:** the XIAO's own USB-C.
- **Final watch:** a 4-pin magnetic pogo connector on the back (5V, GND, D+, D−). It gives charging *and* USB flashing at zero added height, and both chips have native USB.
- **Why not USB-C:** a USB-C socket is ~3.2 mm tall and ~9 mm wide, so it sets a floor on the case's edge thickness and is an ingress point.
