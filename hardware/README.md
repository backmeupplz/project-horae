# Horae rev A hardware

ESP32-S3 band watch board: **33.6 × 16.0 × 0.6 mm, 4 layers**. JLCPCB assembles it (Standard PCBA, top side only) in a
1-up 70 × 70 mm frame.
- **Case:** 35.6 × 18.0 × 6.80 mm, smaller than a Fitbit Charge 3 (38 × 18.3 × 11.8) in every direction. Two PETG shells
  click together with no glue (see `../cad/horae.py`).
- **Board fit:** the board sits 0.2 mm off every cavity wall, because JLC routes outlines to ±0.2 mm. Six crush ribs in the
  case centre it.

**Status (2026-10-06): pre-order review done, not ordered.**
- **Review:** four parallel reviews (schematic and parts, layout and fab files, size, sourcing) found 7 blockers. All are
  fixed and listed below.
- **Checks:** ERC 0. DRC 0 errors, 0 warnings, 0 unconnected. A probe of JLC's multilayer limits is clean: minimum
  clearance 0.110, track 0.100, hole-to-copper 0.235, copper-to-edge 0.201 mm.
- **Reproducible:** a fresh build gives the same board and CPL byte for byte.
- **Ordering:** [../ORDER.md](../ORDER.md). **Assembly and bring-up:** [../ASSEMBLY.md](../ASSEMBLY.md).

Everything here is generated from two files:
- [`design.py`](design.py), the netlist
- [`../spec.py`](../spec.py), the shared dimensions

## Rebuild
```sh
./build.sh       # ~6 min: schematic, ERC, placement, staged Freerouting, pours, DRC, STEP, gerbers, BOM/CPL, panel, renders
python3 cost.py  # live JLC parts (with JLC's attrition/minimums) + Standard PCBA fees -> out/cost.json; `cost.py 5` for 5 boards
```
It needs:
- Docker: it runs KiCad 10 from the official `kicad/kicad:10.0` image through `./kicad`.
- A Java 25 runtime.
- The Freerouting 2.4.1 jar in `~/.local`.

| File | What |
|---|---|
| `design.py` | parts, LCSC numbers, pin-to-net map |
| `gen_sch.py` | writes `horae.kicad_sch` (symbols joined by net labels) |
| `gen_pcb.py` | outline, stack, pinned and legalized placement (the build fails on any drift over 1 mm), net classes, keep-outs; exports the Specctra DSN |
| `stage.py`, `dsn_only.py`, `sesfix.py` | staged routing: touch first, then the e-paper bus, then the rest; deterministic (seeded UUIDs, one router thread) |
| `route.py` | imports the Freerouting session, pours GND, adds stitching and the RF via fence, removes unused escape vias |
| `fab.py` | `out/jlc-bom.csv` and `out/jlc-cpl.csv` (gerber coordinates, JLC rotation offsets) |
| `panel.py` | the 70 × 70 mm frame: `out/panel-gerbers.zip`, `out/jlc-cpl-panel.csv`, `out/panel-top.png` |
| `cost.py` | JLC cost estimate from the BOM |
| `lib/` | symbols, footprints and 3D models: LCSC-imported, TI/Espressif land patterns, Watchy's antenna |
| `rf/` | openEMS antenna model and match fitting |
| `out/` | schematic PDF, STEP, gerbers, BOM, CPL, panel, ERC/DRC reports, renders |

## Design summary
- **MCU:** ESP32-S3FN8 (8 MB in-package flash).
  - 40 MHz KYX crystal (12 pF, ±10 ppm) with Espressif's 24 nH series L on XTAL_P.
  - The exposed pad follows Espressif's land pattern: solid copper, nine 1.0 mm mask windows, 12 vias in the mask webs,
    and no vias in the paste.
  - **Timekeeping:** a 32.768 kHz crystal on GPIO15/16 drives the ESP32's own RTC, as on Watchy v3 and Yatchy, so there's
    no RTC chip. ±20 ppm is about 1 min/month before the phone sync corrects it. All four crystal load caps are 18 pF C0G.
  - **Antenna:** Watchy's meander IFA, trimmed 6.64 mm, ending 0.35 mm from the board edge. It is fed by a 50 Ω GCPW
    (0.15 mm track, 0.15 mm gap). Match **C11 0.5 pF / L3 0.8 nH**; C12 is not fitted and is the spare tuning spot.
  - **Antenna simulation (v4, this board):** S11 across 2.40–2.48 GHz is −8.8 to −14.2 dB in the case and −8.6 to
    −13.6 dB on the wrist, with a worst in-band loss of 0.78 dB.
  - The re-layout put ground closer to the feed, which lowered the resonance 0.6–0.8 %. So L3 went from 1.2 to 0.8 nH,
    the most robust match across JLC's parts. `rf/results/report_v4_trim6.64.txt` has the details.
- **Power:**
  - **Pogo pads:** 4 on the bottom for the charging/USB dock, whose spring pins reach them through the case floor. They are
    VBUS + D− on one side and GND + D+ on the other. ST's USBLC6-2P6 sits flow-through between the pads and the ESP32.
  - **TI BQ25101** linear charger (1.6 × 0.9 mm WCSP):
    - charges at 20 mA (6.8 kΩ ISET, 0.5C for a 40 mAh cell), with TI's ISET RC (2.7 kΩ + 10 nF) for currents under
      50 mA;
    - 4.7 µF/25 V on IN and 1 µF on OUT, both at the chip;
    - ≤ 75 nA battery drain.
    - The IN pin is rated 30 V, but the USBLC6 clamps VBUS from about 6 V, so the input is 5 V only.
  - **TI TPS62840** buck:
    - 60 nA quiescent, 3.3 V set by a 267 kΩ VSET resistor (TI's window is 256–278 kΩ);
    - 2.2 µH LSCND1608 inductor (1.3 A saturation, 0.2 Ω, 0.8 mm).
  - **Battery voltage:** a 10 MΩ / 10 MΩ ±1 % divider (0.2 µA) with 100 nF at the ADC. Calibrate each board at the
    4.20 V end of charge.
  - **Soldered parts:** the battery goes to a **square + pad (TP5)** and a **round − pad (TP6)** on the bottom; the motor
    to 1.5 mm pads.
- **Sensors:** ST LIS2DUX12 accelerometer (pedometer at 2.7 µA, tap, wake-up, 6D, ML core).
  - **I²C:** address **0x19**, on GPIO8 (SDA) / GPIO9 (SCL) with the ESP32's internal pull-ups, so 100 kHz.
  - **Interrupts:** INT1/INT2 on GPIO10/11.
  - **Layout:** nothing on any layer under it (ST TN0018).
- **Display:** GDEM0097T61 into a Hirose FH34SRJ-18S.
  - **Connector:** its slot and fitting nails face the ribbon's U-bend at −X, and **pad = 19 − display pin**.
  - **Booster:** Good Display's reference (p.20) in tiny packages:
    - 47 µH Sunlord SWPA3010S (3 × 3 × 1.0 mm) with 10 µF at its input;
    - Nexperia PMZ390UN switch (30 V);
    - 3× Nexperia PMEG3002AEL Schottky (30 V, about 6× less leakage than the PMEG3005EL);
    - 2.2 Ω sense;
    - 2.2 µF/25 V on the ±15–20 V rails (0402 parts lose about 90 % of their capacitance there) and 1 µF/25 V on the rest.
- **Touch:** 4 capacitive electrodes (4.0 × 1.6 mm) along the long edges, on touch channels GPIO1–4, each through a
  510 Ω series resistor at the chip. No buttons.
  - On every layer, no other trace and no ground pour come within 0.5 mm of an electrode.
  - The electrodes are well below Espressif's recommended size (8 mm+), so measure raw counts in the closed case first
    (bring-up checks).
- **Haptics:** 6 mm coin ERM (Vybronics VC0625B001L, 2.5 mm, 10 mm leads) on a PMZ390UN low-side switch, with a
  PMEG3002AEL flyback diode. It is rated 2.5 V, so firmware drives it with PWM.
- **Mic:** LMD2718T261 top-port PDM mic: DATA on GPIO38, CLK on GPIO39, and powered from GPIO40 (0 µA when off).
  - The ROM drives GPIO40 high in USB-OTG download mode, so it may only be the mic's supply.
  - Burn `DIS_USB_OTG_DOWNLOAD_MODE` at the first flash.
- **Height:** the tallest parts are J1 (1.0 mm, 1.1 max) and L4 (1.0 mm). Then come the mic (0.9, 1.0 max), the ESP32
  (0.885), L5 (0.8) and the accelerometer (0.74). The display sits 1.05 mm above the board.

### GPIO plan
| Side of U1 | GPIO | Use |
|---|---|---|
| facing the antenna (pins 6–14) | 1, 2, 3, 4 | touch DOWN, BACK, MENU, UP (each through 510 Ω) |
| | 5 | vibration motor (PWM) |
| | 6 | charger CHG (open drain, low = charging: wakes the watch on the dock) |
| | 7 | battery ADC (ADC1 channel 6) |
| | 8, 9 | I²C SDA, SCL (accelerometer, 0x19) |
| facing the display connector (pins 15–27) | 10, 11 | accelerometer INT1, INT2 |
| | 12, 13, 14, 17, 18, 21 | display BUSY, RES, DC, CS, SCK, MOSI |
| | 15, 16 | 32.768 kHz crystal |
| | 19, 20 | USB D−, D+ (dock pads, through the USBLC6) |
| bottom (pins 43–45) | 38, 39, 40 | mic DATA, CLK, power |
| test pads (bottom) | 0, 43, 44, EN, 3.3 V | BOOT, TXD0, RXD0, reset, supply |

Every display, I²C, touch and wake line is on an RTC GPIO (0–21), so the ULP core can redraw the minutes without waking
the main CPU (Yatchy's biggest battery win). The ULP bit-bangs I²C: its hardware I²C pins are GPIO0–3.

## Pre-order review (2026-10-06): what changed
- **Blockers fixed:**
  - **J1 faced the wrong way.** The FH34SRJ's slot is on the fitting-nail side, so the ribbon couldn't reach it. J1 is
    turned around with its pins remapped. It also moved 1.7 mm toward +X, because Good Display's bend rule (R > 0.5 mm)
    with the 11.18 mm tail needs that much room.
  - **CPL:** it was relative to the board centre, while the gerbers use absolute coordinates, so every part would have
    landed about 141 mm off. U4 also needed a rotation offset; the CPL now has offsets for U4 and L4.
  - **WCSP lands:** the U2/U3 ball pads (0.185–0.2 mm, mask = pad) were below JLC's minimum. They are now TI's 0.23 mm
    NSMD lands with 0.25 mm square paste.
  - **Touch:** foreign traces ran under the electrodes on the inner and bottom layers.
  - **RF:** the RF match pads were 0.07 mm apart, which would merge the solder mask and tombstone L3.
  - **Thermal vias:** the ESP32's exposed pad had open vias inside the paste.
  - **Panel:** JLC Standard PCBA needs a panel of at least 70 × 70 mm. JLC's own 2 × 4 panel would have meant paying for
    16 assembled boards, so `panel.py` makes a 1-up frame.
- **Should-fix items done:**
  - **Vias:** all are now 0.45/0.2 mm. 0.4 mm pads cost about $36 more per order and triggered 4-wire testing.
  - **Supplies:** 0.2–0.3 mm traces; VDD3P3 on the top layer with no vias.
  - **Decoupling:** every cap within 1 mm of its pin, with new caps at VDD3P3_CPU, VDDA, the booster input and the charger
    output.
  - **Crystals:** on the top layer at their pins, with nothing underneath.
  - **USB ESD:** flow-through.
  - **Mic:** its pins are swapped so the ROM can't back-drive it during flashing.
  - **Lower-leakage diodes, and rail caps that keep their value at 20 V.**
  - **Genuine ST USBLC6.**
  - **Parts with better stock:** the original Sunlord inductor, plus ±1 % 10 MΩ and 510 Ω resistors with no 6,000-piece
    minimums.
  - **Silkscreen:** pin-1 and cathode marks for JLC's placement check.
  - **Paste:** reduced on the FPC connector. Thermal spokes on the non-critical 0201s against tombstoning.

## Verify at bring-up
1. **RF:** the in-case and on-wrist responses sit about 100 MHz apart, so a ±3 % resonance error costs about 4 dB at one
   band edge.
   - The steel spring bar is part of the antenna's environment. Keep it within ±1 mm of 2.15 mm past the case end, or
     re-run `rf/`.
   - Verify on the first boards with a VNA through a pigtail at the C11 pad (cut the trace to U1). Close the case and
     measure with the strap on, off and on a wrist, then retune C11/L3; C12 is the spare.
   - A bare board always reads high, so test it in the case.
2. **Touch:** read raw counts and noise in the closed case before relying on touch as the only input.
3. **Booster:** SSD1680's current-sense trip on RESE isn't published, so L4's saturation margin (0.22 A rated, 0.35 A
   typical) is unknown. Probe RESE (current = V / 2.2 Ω) and watch the VGH ramp.
4. **Crystals:**
   - The 40 MHz must be within ±10 ppm: trim C1/C2 with a TX tone if not.
   - Check that the 32 kHz crystal starts. Its 70 kΩ resistance is at Espressif's limit, and the firmware falls back to
     the internal RC clock.
5. **Charger:** it can't run the board without a cell, and its 10-hour timer stops charging if the watch stays awake on
   the dock. Bring the board up from a bench supply on TP5/TP6, and deep-sleep while docked.
6. **JLC preview:** order with "Confirm Parts Placement" and check every pin-1 dot and cathode bar against the
   silkscreen, especially U1–U4, U6, J1, Q1/Q2, D1–D4, MIC1 and Y1.
7. **Recovery without buttons:** EN, BOOT (GPIO0), TXD0/RXD0 and 3.3 V are on bottom test pads, and USB is on the dock
   pads.

## Cost (JLC Standard PCBA, live 2026-10-06; `python3 cost.py`)
| Item (USD) | 2 boards | 5 boards |
|---|---|---|
| Bare PCB: 5 frames, 4 layers, 0.6 mm, ENIG, JLC04061H-3313 stack-up (impedance control not needed), 0.45/0.2 vias, plugged | 46.20 | 46.20 |
| PCBA setup 25.56 + stencil 8.21 + 33 feeders × 1.53 + fixtures 16.42 + X-ray + placement confirmation and packing | 118.03 | 122.13 |
| Parts, with JLC's attrition and minimum quantities | 30.42 | 62.93 |
| Joints (about 230 per board × $0.0016) | ~0.75 | ~1.85 |
| **Subtotal** | **≈ 195** | **≈ 233** |
| DHL Express (2–4 business days); Global Standard is capped at $99 orders | 31.23 | 31.23 |

- **Import:** duty 0 % (HS 8534.00.00). GST + BC PST 12 % is collected at delivery, plus DHL's CAD 18 clearance fee.
  There is no DDP option for Canada.
- **Fees:** on Standard PCBA every BOM line pays the $1.53 feeder fee, basic or extended alike. JLC has no basic or
  preferred 0201 parts, so swapping parts for basic ones saves nothing here; only fewer lines do.
- **Pre-buy the ESP32-S3FN8:** JLC has 602 in stock and 0 at LCSC. Buy 5–10 into your JLC parts inventory before
  ordering.

## Battery and motor (bought separately, soldered: 4 joints)
- **Cell:** a 3.0 mm LiPo with protection (PCM), at most 21.4 × 16.0 × 3.25 mm including the PCM. The PCM end may be up
  to 3.5 thick and 2.5 long.
  - Buy cells no thicker than 3.05 mm, and measure them on arrival: thickness tolerance is often ±0.3.
  - Real capacity in this pocket is **40–55 mAh** (301518 / 301519 / 301520 class).
  - They ship with two bare wire leads (no plug): trim them, then red to + and black to −.
  - **Thinner option:** a bare 2.5 mm cell (LP251320, 40 mAh, buyable at quantity 1) would make the case 6.30 mm. It would
    need cell protection on the board and an RF retune.
- **Motor:** Vybronics VC0625B001L, a 6 × 2.5 mm brushed coin ERM with 10 mm leads (Digi-Key 1670-VC0625B001L-ND). No
  6 mm motor with spring contacts exists off the shelf.
- **Why not a plug:** a JST SH socket, the plug and its lead slack need about 2 mm more case length, and the board's bottom
  side would need assembly too. Two pads take seconds to solder.

## Charging dock (bought parts; the tray, lid and grip pad print with the case)
- **Spring pins:** 4 Mill-Max 0955-0-15-20-71-14-11-0 (plus 2 spares). Docked, each presses about 42 g on its pad.
- **Magnets:** 4 × 3 × 3 mm N52 in the dock; the case holds 2 × 3 × 1 mm N52.
  - Placed end for end, the watch is pushed off, so VBUS never lands on GND.
  - They hold 1.9× the pins' spring force.
  - The case's magnets click into the bottom shell from the inside, behind a 0.1 mm skin, so lifting the watch off can't
    pull them out.
- **USB-C:** [Adafruit 6050](https://www.adafruit.com/product/6050) sunken breakout. Its 5.1 kΩ CC pull-downs make any
  USB-C charger give 5 V, and D+/D− are broken out for flashing.
- **Wire:** 2–3 cm each of 30 AWG for VBUS, GND, D+ and D− (twist D+ with D−). These 4 wires are the dock's only soldering.
  Wiring table: [../ASSEMBLY.md](../ASSEMBLY.md).
