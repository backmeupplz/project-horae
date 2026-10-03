# Build plan: custom board rev A

_Drafted 2026-10-03. This replaces the XIAO carrier from [prototyping.md](prototyping.md) if we go straight to a custom board. Costs are estimates; get real quotes at order time._

Target: **~34 × 18 × 7 mm**, ESP32-S3 with Wi-Fi + BLE, 0.97" e-paper, hand-assembled at home.

## 0. Rev A at a glance
- **Board:** 4-layer, 0.8 mm. **Every part on one side**, so a hot plate can reflow the whole board in one pass.
- **Layout:** display on top of the board, parts under it (≤1.2 mm tall), battery below.
- **Reused from Watchy (proven blocks):**
  - ESP32-S3 core with in-package flash, crystal and antenna section
  - e-paper booster (cross-checked against the display datasheet's reference circuit)
  - BMA423 accelerometer, buttons, motor driver
- **New:**
  - 18-pin display socket (Hirose FH34SRJ-18S-0.5SH)
  - RV-3028-C7 RTC (Watchy v3 relies on the ESP32's own RTC)
  - 4 gold **pogo pads** on the back for charging and USB flashing. No USB socket: it would be 3.2 mm tall
  - test pads for serial, boot, enable and power
- **Battery:** LiPo with protection board, ~2.4–3.0 mm thick, ~100 mAh, soldered to pads.
- **Charging dock:** printed on the A1 mini, with spring pogo pins and magnets, wired to a USB-C breakout.

## 1. Design (Claude, ~2–4 days with your reviews)
1. Fork [sqfmi/watchy-hardware](https://github.com/sqfmi/watchy-hardware) into this repo (`hardware/`) and upgrade it to KiCad 10.
2. Schematic: trim Watchy down, swap in the parts listed above, and add the new connector, RTC, pogo pads and test pads.
3. Place and route on a ~34×18 mm outline, with the antenna at one end and a ground-free keep-out under it.
4. Check it with `kicad-cli` (ERC/DRC). Export renders, STEP, gerbers, BOM and placement files. Each milestone gets a screenshot on the timeline.
5. Design the case in build123d around the board STEP: shell, display window, button caps, strap lugs, plus the dock.
6. **Review gate:** you look over the renders and the case before we pay for anything.

## 2. Order (one day; parts arrive in 1–2 weeks)
| What | Where | Lead | ~Cost |
|---|---|---|---|
| 5× bare boards, 4-layer 0.8 mm + steel stencil | JLCPCB, by DHL | 3–4 days to make + 3–5 days to ship | $15–25 + ~$20 shipping + CAD ~$15–20 tax/brokerage |
| Parts for 3 boards (ESP32-S3, crystal, RTC, BMA423, regulator, charger, booster, socket, buttons, motor, passives + spares) | LCSC (same group as JLC) or Digi-Key CA | 3–7 days | ~$50–70 |
| 4× GDEM0097T61 displays | Good Display on AliExpress / buy-lcd | 1–3 weeks (**order first**) | ~$20–50 |
| 3× LiPo ~100 mAh | AliExpress / Adafruit | 1–3 weeks | ~$15 |
| Dock: spring pogo pins, 6×2 mm magnets, USB-C breakout | AliExpress / Amazon.ca | 1–2 weeks | ~$15 |
| **Firmware dev kit (optional, recommended):** XIAO ESP32S3 + DESPI-C02-CV0097 adapter | Seeed / openelab | ~1 week | ~$20 |

The dev kit lets firmware work start on a real panel before our boards arrive.

### Tools, if you don't have them
- **Hot plate:** a small PTC plate (~$30–40) or Miniware MHP30 (~$80)
- **Solder paste** (Sn63/37 or SAC305 syringe) and **tacky flux**: ~$25
- **Tweezers + magnifier** (a USB microscope or 10× loupe): ~$30
- **Hot-air station** (~$60–100): strongly recommended for fixing a bridged QFN or reworking the display socket
- **Nordic PPK2** (~$100): optional, but the only way to get real battery numbers

### Lower-risk alternative
Have JLC assemble just the hard parts: ESP32-S3, crystal, BMA423, RTC, regulator and charger. This costs roughly +$30–70 for 5 boards and +2–4 days, and removes most of the tools and most of the risk. You'd still solder the socket, buttons, motor and battery.

## 3. Assemble (you, one evening per board)
1. Tape the stencil over the board, then spread paste with a card.
2. Place the parts with tweezers: the chip and module, then the small passives.
3. Reflow on the hot plate. Inspect under magnification, then fix bridges with flux and wick or hot air.
4. Hand-solder the display socket if the hot plate disturbed it, then the motor and battery leads (**battery last**).
5. Bring it up in steps:
   1. Check the power rails on USB with no battery fitted.
   2. Flash over the pogo pads, using the ESP32-S3's native USB.
   3. Test serial output, the display, RTC, buttons, accelerometer, motor and battery voltage, one at a time.

## 4. Firmware (Claude, in parallel)
- PlatformIO + Arduino-ESP32, forked from the [Watchy firmware](https://github.com/sqfmi/Watchy).
- A GxEPD2 class for the 184×88 SSD1680 panel.
- A first watch face designed for a narrow portrait bar.
- Power: deep sleep, woken every minute by the RTC, with partial refresh. Wi-Fi only on demand (daily NTP time and weather, OTA updates). Bluetooth comes later.
- Bring-up sketches for each component, so a dead board can be narrowed down to one part.

## 5. Print and wear
- **Case:** PLA for fit checks, PETG for wearing. Use the 0.2 mm nozzle for the thin walls.
- **Strap:** TPU, or standard spring-bar lugs.
- **Dock:** printed with the pogo pins and magnets pressed in.
- **Wear test:** a week on the wrist. Log battery voltage over time and measure sleep current.
- **Rev B:** collect every problem into one list for the next board.

## 6. Timeline, if everything goes right
| Week | |
|---|---|
| 1 | Design + review; order displays and batteries on day 1 |
| 2 | Order boards + parts; firmware on the dev kit |
| 3 | Boards arrive; assemble + bring-up; print the case |
| 4 | Wear test; rev B list |

## Risks
- **First custom RF board.** The antenna may need tuning. We reduce the risk by copying Watchy's proven antenna and RF layout as closely as the new shape allows.
- **QFN56 at 0.4 mm pitch** is the hardest part to solder by hand-reflow. Mitigations: buy spare chips and boards, or use the JLC alternative above.
- **Display stock:** GDEM0097T61 is out of stock at buy-lcd today. Order early from AliExpress.
- **Rev A will have mistakes.** Budget for a rev B (another ~$40 of boards).
