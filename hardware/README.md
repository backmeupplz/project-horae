# Horae rev A hardware

ESP32-S3 band watch board, **33.8 × 16.2 × 0.6 mm, 4 layers**, assembled by JLCPCB (Standard PCBA, top side only).
The case around it is **35.6 × 18.0 × 7.05 mm**, smaller than a Fitbit Charge 3 (38 × 18.3 × 11.8) in every direction.

**Status (2026-10-04):** second ("slim") pass, ready for review, **not ordered**.
- ERC: 0. DRC: 0 errors, 0 warnings, 0 unconnected.
- RF: re-simulated in openEMS for this board, the case, both steel spring bars and the strap (`rf/results/report_v2_trim6.64.txt`).

Everything here is generated from two files:
- [`design.py`](design.py), the netlist
- [`../spec.py`](../spec.py), the shared dimensions

## Rebuild
```sh
./build.sh      # ~15 min: schematic, ERC, placement, best-of-5 Freerouting, pours, DRC, STEP, gerbers, BOM/CPL, renders
python3 cost.py # live JLC prices for the BOM -> out/cost.json
```
It needs Docker (it runs KiCad 10 from the official `kicad/kicad:10.0` image through `./kicad`), a Java 25 runtime and the Freerouting 2.4.1 jar in `~/.local`.

| File | What |
|---|---|
| `design.py` | parts, LCSC numbers, pin-to-net map |
| `gen_sch.py` | writes `horae.kicad_sch` (symbols joined by net labels) |
| `gen_pcb.py` | outline, stack, pinned and legalized placement, nets, keep-outs; exports the Specctra DSN |
| `route.py` | imports the Freerouting session, pours GND, adds stitching vias |
| `fab.py` | `out/jlc-bom.csv` and `out/jlc-cpl.csv` |
| `cost.py` | JLC cost estimate from the BOM |
| `lib/` | LCSC-imported symbols, footprints and 3D models (easyeda2kicad), plus Watchy's antenna footprint |
| `out/` | schematic PDF, STEP, gerber zip, BOM, CPL, ERC/DRC reports |

## Design summary
- **MCU:** ESP32-S3FN8 (8 MB in-package flash) with a 40 MHz crystal and Espressif's 24 nH series L on XTAL_P.
  - **Timekeeping:** a 32.768 kHz crystal on GPIO15/16 drives the ESP32's own RTC, as on Watchy v3 and Yatchy. No RTC chip (saves $3.44 and an I²C device). ±20 ppm is ~1 min/month before the phone sync corrects it.
  - **Antenna:** Watchy's meander IFA, trimmed 6.64 mm, ending 0.35 mm from the board edge. Match **C11 0.3 pF / L3 1.2 nH**, C12 not fitted (spare tuning spot). Simulated S11 across 2.40–2.48 GHz: −9.2 to −14.7 dB in the case, −9.1 to −13.7 dB on the wrist; radiation efficiency ~0.74 in the case including the match (on a wrist the body absorbs most of it, ~6%, as for any wrist wearable).
- **Power:**
  - 4 pogo pads on the bottom: VBUS + D− on one side, GND + D+ on the other; USBLC6 for ESD.
  - **TI BQ25101** linear charger (1.6 × 0.9 mm WCSP): 24 mA (~0.5C for the 40–55 mAh cell), input tolerates 28 V, 75 nA battery drain (the TP4054 it replaces drew µA).
  - **TI TPS62840** buck (60 nA quiescent, 750 mA, 3.3 V set by a 267 kΩ VSET resistor) replaces the RT9080 LDO (2 µA, and ~10% less efficient at Wi-Fi currents).
  - Battery voltage through a 10 MΩ / 10 MΩ divider (0.2 µA) with 100 nF at the ADC.
  - Battery and motor are **soldered** to 2 × 2 mm and 1.5 mm pads on the bottom (polarity printed on the silkscreen).
- **Sensors:** ST LIS2DUX12 accelerometer (pedometer at 2.7 µA, tap, wake-up, 6D, ML core) on I²C at GPIO10/11 with the ESP32's internal pull-ups; INT1/INT2 on GPIO9/8.
- **Display:** GDEM0097T61 into a Hirose FH34SRJ-18S. The booster follows Solomon's SSD1681 reference values in tiny packages: 47 µH 3 × 3 × 1.0 mm inductor (520 mA), Nexperia PMZ390UN MOSFET (30 V, Vgs(th) 0.95 V), 3× Nexperia PMEG3005EL Schottky (30 V 0.5 A, 1.0 × 0.6 mm), 2.2 Ω sense, 1 µF/25 V rail caps.
- **Touch:** 4 capacitive electrodes (4.0 × 1.6 mm) along the long edges, on touch channels GPIO1–4; no buttons.
- **Haptics:** 6 mm coin ERM (Vybronics VC0625B001L, 2.5 mm, 10 mm leads) on a PMZ390UN low-side switch with a PMEG3005EL flyback diode.
- **Mic:** LMD2718T261 top-port PDM mic on GPIO38–40, powered from GPIO38 (0 µA when off).
- **Height:** the tallest part is 1.0 mm (FH34SRJ and the booster inductor); everything else is ≤ 0.9 mm, so the display sits 1.05 mm above the board.

### GPIO plan
| Side of U1 | GPIO | Use |
|---|---|---|
| facing the antenna (pins 6–14) | 1, 2, 3, 4 | touch DOWN, BACK, MENU, UP |
| | 5 | vibration motor |
| | 6 | charger CHG (low = charging: wakes the watch on the dock) |
| | 7 | battery ADC |
| | 8, 9 | accelerometer INT2, INT1 |
| facing the display connector (pins 15–27) | 10, 11 | I²C SDA, SCL |
| | 12, 13, 14, 17, 18, 21 | display BUSY, RES, DC, CS, SCK, MOSI |
| | 15, 16 | 32.768 kHz crystal |
| | 19, 20 | USB D−, D+ (pogo pads) |
| bottom (pins 43–45) | 38, 39, 40 | mic power, PDM clock, PDM data |

Every display, I²C, touch and wake line is on an RTC GPIO (0–21), so the ULP core can redraw the minutes without waking the main CPU (Yatchy's biggest battery win). The display and I²C pins sit on the side of the chip that faces the display connector, which is what made the board routable at this size.

## Review checklist: decide or verify before ordering
1. **Display ribbon orientation: verified (2026-10-04).**
   - **Datasheet:** in the BACK view of the GDEM0097T61 drawing (p.7), pin 1 is the rightmost finger and pin 18 the leftmost, and the contacts are on the back face.
   - **Seen from the display face:** pin 1 is on the left with the tail pointing down. On the board (KiCad top view, tail toward −X) that puts pin 1 at **−Y (KiCad)**.
   - **Through the U-bend:** the bend folds about an axis parallel to Y, so every finger keeps its Y position. The contacts end up facing up, and the FH34SRJ has top and bottom contacts.
   - **Connector:** J1 pad 1 is at −Y and carries GDR (display pin 1). Pads 1–18 run along the −X side (the ribbon entry), and the back-flip actuator is on +X.
   - **Assembly:** display face up with the ribbon toward −X; fold the ribbon under, flip the actuator up, push the ribbon straight in, contacts facing up, and close the actuator.
2. **JLC Standard PCBA is required.** Economic PCBA stops at 0402 parts and 0.5 mm BGA pitch; this board has 0201 passives and two 0.4 mm-pitch WCSPs (BQ25101, TPS62840). Standard also allows the 0.6 mm board. It needs a ≥ 70 × 70 mm panel: order with JLC panelization (e.g. 2 × 4) or a 2 × 2 panel with wide rails.
3. **Board stack-up:** 4 layers, 0.6 mm, In1 solid GND. Pick JLC's 0.6 mm 4-layer impedance stack with 3313 prepreg on the outer layers (~0.1 mm to In1); the 50 Ω feed (0.20 mm track, 0.15 mm gap) assumes that.
4. **RF:** the in-case and on-wrist responses sit ~100 MHz apart, so a ±3% resonance error costs ~4 dB at one band edge. The steel spring bar is part of the antenna's environment: keep it within ±1 mm of 2.15 mm past the case end (or re-run `rf/`). Verify on the first boards with a VNA through a pigtail at the C11 pad (trace to U1 cut), case closed with the strap on, off and on a wrist, then retune C11/L3 (C12 is the spare). A bare board always reads high; test it in the case.
5. **32 kHz crystal:** 12.5 pF, ESR 70 kΩ (Espressif's limit), 20 pF load caps. Check that it starts (firmware falls back to the internal RC clock if not) and trim the load caps after measuring.
6. **Charger:** BQ25101 TS has a 10 kΩ resistor to GND (no thermistor), ISET 5.6 kΩ = 24 mA. Raise the current (lower ISET) only if the chosen cell allows it.
7. **Buck:** VSET 267 kΩ (1%) selects 3.3 V; confirm against TI's table before ordering.
8. **Battery:** a 3.0 × 15 × 18–19 mm cell with protection (301518 / 301519 class, 40–55 mAh, ≤ 21 mm with the PCM). Solder it to TP5 (+, KiCad +Y) and TP6 (−). Check the cell's polarity before soldering.
9. **No load-sharing power path.** While docked, the charger charges the battery while the ESP32 runs from it.
10. **JLC CPL rotations:** LCSC-imported footprints sometimes need rotation offsets. Check JLC's placement preview, especially the WCSPs, SOT-883 and SOD-882 parts.
11. **Recovery without buttons:** EN, BOOT (GPIO0), TXD0/RXD0 and 3.3 V are on bottom test pads; USB is on the dock pads.

## Cost breakdown (JLC Standard PCBA, live prices 2026-10-04; `python3 cost.py`)
| Item | 2 boards assembled | 5 boards assembled |
|---|---|---|
| Bare PCB: 4-layer, 0.6 mm, ENIG, 0.4/0.2 vias, impedance stack-up, panelized | ~$15–30 | ~$15–30 |
| Standard PCBA setup $25 + stencil $7.86 + panel $7.81 | $40.67 | $40.67 |
| Extended-part loading: 28 lines × $3 | $84 | $84 |
| Parts at $11.71 per board (biggest: LIS2DUX12 $4.03, ESP32-S3 $3.33, TPS62840 $1.20, BQ25101 $0.73) | $23 | $59 |
| Solder joints ($0.0016 each) | ~$0.5 | ~$1 |
| **Subtotal (USD)** | **≈ $163–178** | **≈ $198–213** |
| Shipping: DHL Express ~$25, or Global Standard ~$10 (1–2 weeks) | $10–25 | $10–25 |
| GST+PST 12% + brokerage (CAD) | ~$30–40 | ~$35–45 |

**Correction (2026-10-04):** the Day-0 estimate (~$120–130) assumed Economic PCBA, which JLC does not offer for 0201 parts. Standard PCBA was always required for this board; its setup is ~$31 more.

**Where the money goes:**
- **Loading fees** are $84 of it: JLC has no basic or preferred 0201 parts, and every unique extended part costs $3 per order. Swapping 0201s for basic 0402s would need board area this board doesn't have.
- **Parts** dropped from $14.61 to $11.71 per board: the $3.44 RTC chip is gone (32 kHz crystal instead), while the better charger (+$0.60) and buck (+$1.08) cost a little more.

**Options:**
1. **5 boards instead of 2:** fees are per order, so each extra assembled board costs only ~$12 in parts.
2. **Global Standard shipping** instead of DHL: saves ~$15, costs about a week.
3. **DHL with DDP** (taxes prepaid at checkout): avoids DHL's separate brokerage bill.

## Battery and motor (bought separately, soldered: 4 joints)
- **Cell:** 3.0 × 15 × 18–19 mm LiPo with protection (PCM), ≤ 21 mm long including the PCM. Real capacity in this pocket is **40–55 mAh** (tiny cells reach only ~50–65 mAh per 1000 mm³; the Day-0 "~100 mAh" figure was too optimistic). Examples: LiPol LP301518 (40 mAh) / LP301519 (55 mAh), AliExpress 301518 packs. A 2.5 mm cell (LiPol LP251320, 40 mAh, factory order) would make the case 6.55 mm.
- **Motor:** Vybronics VC0625B001L, 6 × 2.5 mm brushed coin ERM with 10 mm leads (Digi-Key 1670-VC0625B001L-ND). No 6 mm motor with spring contacts exists off the shelf; the zero-solder options (7–8 mm motors with pads or springs) don't fit this zone.
- **Why not a plug:** a JST SH socket plus the plug and its lead slack needs ~2 mm more case length and a custom short-lead cell, and it would need JLC to assemble the board's bottom side too (+~$33). Two 2 × 2 mm pads take seconds to solder.
