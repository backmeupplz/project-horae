# Build plan: custom board rev A

_Drafted 2026-10-03. This replaces the XIAO carrier from [prototyping.md](prototyping.md) if we go straight to a custom board. Costs are estimates; get real quotes at order time._

Target: **~36 × 17.5 × 6.6 mm** (see optimizations below), ESP32-S3 with Wi-Fi + BLE, 0.97" e-paper, hand-assembled at home.

## 0. Rev A, optimized for parts count, thickness and battery

### Fewer parts: ~44 placed vs Watchy's ~75
| Change | Saves |
|---|---|
| **[ESP32-S3-PICO-1](https://documentation.espressif.com/esp32-s3-pico-1_datasheet_en.html)** SiP instead of a bare ESP32-S3. It's 7×7×≤1.06 mm and contains the crystal, 8 MB flash, PSRAM, decoupling and RF matching. Externally it needs only 22 µF, 100 nF, an EN RC pair and a pi-match footprint (start it as a 0 Ω + 2 unfitted parts). Same chip, same Wi-Fi + BLE | ~15 parts |
| PCB trace antenna (Watchy's inverted-F) | 0 antenna parts |
| One user button wired to GPIO0, doubling as BOOT. EN on a test pad. Buttons use the chip's internal RTC pull-ups | 1 button + pull-ups |
| RV-3028-C7 RTC (crystal built in) replaces the 32 kHz crystal + 2 caps | 1 part, and ±1–3 ppm accuracy |
| Native USB over pogo pads instead of a USB socket | the socket |
| Vibration motor footprint left **unfitted** in rev A | 4 parts (optional) |

**Soldering:** everything sits on one side and goes through **one hot-plate pass**. The only hand-soldering is the 2 battery wires, plus 2 motor wires if fitted. The display ribbon plugs into its socket.

**Kept on purpose:**
- The charger (TP4054). If the battery connected straight to the pogo pads, they'd sit at 3.7 V against sweaty skin and corrode.
- One ESD part (USBLC6-2P6) on the exposed USB pads.

### Thinnest stack (display on top, parts under it, battery below)
| Layer | mm |
|---|---|
| Printed lip over the display edge (0.2 mm nozzle) | 0.5 |
| GDEM0097T61 | 1.0 |
| Adhesive/gap | 0.1 |
| Tallest parts (PICO-1 1.06, FH34SRJ 1.0, booster inductor ≤1.0) | 1.06 |
| PCB, 4-layer **0.6 mm** (confirm with JLC, else 0.8) | 0.6 |
| Battery ~2.4–2.5 mm + swelling | 2.75 |
| Case floor with pogo windows | 0.6 |
| **Total** | **~6.6** |

- **Footprint:** ~36 × 17.5 mm, compared with the [Charge 6](https://store.google.com/product/fitbit_charge_6_specs) at 36.7 × 23.1 × 11.2. Length is the 30 mm display plus an antenna end that sits past the display glass. Width is the 14.15 mm display + 0.8 mm walls + side buttons.
- **Height budget:** every part under the display must be ≤1.06 mm. That means 0402 passives, SOD-323/523 diodes, an SOT-323 MOSFET, and a 47 µH inductor in a 2520 or 3×3×1.0 package.
- **Alternative layout (~5.5 mm):** put the board and battery side by side under the display instead of stacked. The catch is that the battery shrinks to ~15×15×3 mm, about 50 mAh. Consider it for rev B once real current draw is measured.
- **Carbon fiber later:** a CNC-cut 0.3–0.5 mm CF back or shell (PCBWay/JLC CNC) allows thinner walls. **CF is conductive and blocks Wi-Fi/BLE**, so the antenna end has to stay plastic or glass. Printing CF-filled filament on the A1 mini needs the hardened steel nozzle.

### Battery life
| Item | ~µA |
|---|---|
| ESP32-S3 deep sleep, RTC peripherals off (datasheet) | 7–10 |
| RT9080 LDO (600 mA for Wi-Fi bursts, [2 µA Iq](https://www.richtek.com/assets/product_file/RT9080/DS9080-09.pdf)) | 2 |
| RV-3028-C7 | 0.05 |
| **BMA400** step counter ([4 µA](https://www.bosch-sensortec.com/media/boschsensortec/downloads/product_flyer/bst-bma400-fl000.pdf)) instead of BMA423 (its sibling BMA422 is listed at 25 µA). Needs a new driver | 4 |
| Battery divider (10 MΩ total) + e-paper deep sleep | ~1.3 |
| Wake every minute, fast boot (~40–60 ms at ~35 mA) | 25–35 |
| Partial refresh, 6 mW × 0.3 s per minute | ~8 |
| Wi-Fi sync once a day | ~4 |
| **Total** | **~50–65 µA ≈ 1.2–1.6 mAh/day** |

- **Estimate:** on a ~90–100 mAh cell that's **~4–8 weeks on paper**. Treat it as 2–6 weeks until a PPK2 measures the real board.
- **Wiring for later savings:** connect the display, RTC INT and buttons to **RTC-capable GPIOs** (GPIO0–21). Later firmware can then use the ULP core or a deep-sleep wake stub to update the minute digits without a full boot, cutting the biggest line in the table. This costs nothing in hardware.

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

## JLC full assembly: estimate (checked 2026-10-03)
Live JLC parts-library stock on 2026-10-03:

| Part | JLC/LCSC | Stock | ~$ each |
|---|---|---|---|
| ESP32-S3-PICO-1-N8R2 | C7558093 | **0** (would need Global Sourcing from Digi-Key) | 5.0 |
| **ESP32-S3FN8** (bare chip, Watchy's) | C2913196 | 660 | 3.33 |
| RV-3028-C7 | C2829066 | **0** | – |
| **RV-3032-C7** (2.5 ppm, crystal inside) | C5127802 | 4572 | 3.44 |
| BMA400 | C437655 | 226 | listed 14.9 at JLC (LCSC lists ~$2–3) |
| BMA456 (same BMA4 API as Watchy's BMA423) | C189518 | 2540 | 4.88 |
| FH34SRJ-18S-0.5SH(50) | C3169386 | 26512 | 0.28 |
| EVQ-PUC02K / EVQ-P7M01P buttons | C79174 / C7275646 | 6 / 265 | 0.17 / 0.58 |
| RT9080-33GJ5 | C841192 | 39625 | 0.12 |
| TP4054 | C32574 | 26354 | 0.13 |

**Decision:** because JLC places every part, part count no longer costs soldering time. So use the in-stock **ESP32-S3FN8 + crystal**, exactly as Watchy does, and copy Watchy's proven RF layout. That adds ~14 robot-placed parts and no Global Sourcing delay.

| Line (Economic PCBA, 4-layer **0.8 mm**, the minimum for Economic) | 2 boards assembled | 5 boards assembled |
|---|---|---|
| 5 bare boards | ~$8 | ~$8 |
| Setup + stencil | $9.50 | $9.50 |
| Extended-part loading, ~10 lines × $3 | ~$30 | ~$30 |
| Parts, ~$15–18 per board | ~$34 | ~$85 |
| Joints, ~250 × $0.0016 | ~$1 | ~$2 |
| **Subtotal (USD)** | **~$83** | **~$135** |
| DHL to Vancouver | ~$20–25 | ~$20–25 |
| GST+PST 12% + brokerage (CAD) | ~$30 | ~$40 |
| **Landed (CAD)** | **~$170** | **~$260** |

**Lead time:** ~3–4 days for the boards, +1–2 days for assembly, +3–5 days DHL, so **~1.5–2 weeks**.

**Cost compared with DIY:** self-assembly saves only ~$40–60 in fees, but needs ~$60–100 of tools and carries real risk on the QFN.

**Left for us:** plug in the display ribbon, solder 2 battery wires, and assemble the case.
