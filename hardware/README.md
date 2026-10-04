# Horae rev A hardware

ESP32-S3 band watch board, **37.3 × 16.5 × 0.8 mm, 4 layers**, fully assembled by JLCPCB.

**Status (2026-10-03):** first complete pass, ready for review, **not ordered**.
- ERC: 0 errors and warnings.
- DRC: 0 errors, 0 unconnected; 20 warnings, all silkscreen.

Everything here is generated from two files:
- [`design.py`](design.py), the netlist
- [`../spec.py`](../spec.py), the shared dimensions

## Rebuild
```sh
./build.sh   # ~3 min: schematic, ERC, placement, Freerouting, pours, DRC, STEP, gerbers, BOM/CPL, renders
```
It needs Docker (it runs KiCad 10 from the official `kicad/kicad:10.0` image through `./kicad`), a Java 25 runtime and the Freerouting 2.4.1 jar in `~/.local`.

| File | What |
|---|---|
| `design.py` | parts, LCSC numbers, pin-to-net map |
| `gen_sch.py` | writes `horae.kicad_sch` (symbols joined by net labels) |
| `gen_pcb.py` | outline, stack, pinned and legalized placement, nets, keep-outs; exports the Specctra DSN |
| `route.py` | imports the Freerouting session, pours GND, adds stitching vias |
| `fab.py` | `out/jlc-bom.csv` and `out/jlc-cpl.csv` |
| `lib/` | LCSC-imported symbols, footprints and 3D models (easyeda2kicad), plus Watchy's antenna footprint |
| `out/` | schematic PDF, STEP, gerber zip, BOM, CPL, ERC/DRC reports |

## Design summary
- **MCU:** ESP32-S3FN8 (Watchy's chip, 8 MB in-package flash) with a 40 MHz crystal and a 24 nH series L on XTAL_P (per Espressif).
  - **Antenna:** Watchy's meander IFA, **trimmed 6.64 mm** after an openEMS simulation (`rf/`). As drawn it resonated at ~1.99 GHz in the case and would barely radiate.
  - **Match:** C11 0.9 pF, L3 0.6 nH; C12 is a not-fitted tuning spot.
- **Power:**
  - Charging and USB data come in through 4 pogo pads on the bottom (VBUS, D−, D+, GND), with a USBLC6 for ESD.
  - TP4054 charger at 50 mA, RT9080 LDO (2 µA quiescent).
  - Battery voltage is read through a 10 MΩ / 10 MΩ divider (0.2 µA).
- **Sensors:** RV-3032-C7 RTC (INT wakes the ESP32) and BMA400 accelerometer (4 µA while step counting). I²C uses the ESP32's internal pull-ups.
- **Display:** GDEM0097T61 into a Hirose FH34SRJ-18S, with the booster circuit from the Good Display datasheet.
- **Buttons:** 4 Panasonic EVQ-P7M01P side switches on Watchy's button GPIOs (0, 6, 7, 8).
- **GPIO plan:** the display, RTC INT and buttons are on RTC-capable GPIOs (0–21), so later firmware can use the ULP core or a wake stub for minute updates.

## Review checklist: decide or verify before ordering
1. **Display pin 1 orientation.** The ribbon makes a U-bend into the FH34SRJ, which flips it.
   - The connector takes either contact side, but pin order still has to match.
   - Check with a real panel, using the DESPI adapter, before ordering.
2. **RF.**
   - Done: the feed is hand-routed as a 50 Ω GCPW (0.20 mm track, 0.15 mm gap, In1 ground below, JLC 0.8 mm 4-layer stack-up). The pi match sits in a straight line at the RF pin, and the shunt capacitors have their own ground vias. The antenna now sits entirely past the display glass.
   - Simulated in openEMS (FDTD) with the case, glass, battery and a wrist phantom: see `rf/results/report_trim6.64.txt`.
     - In case: S11 between −8.3 and −15.7 dB across 2.40–2.48 GHz.
     - On the wrist: −8.8 to −14.1 dB.
   - Confidence on the absolute frequency is about ±3–5% (PETG εr and infill, simplified case).
   - **Verify on hardware:**
     - **Preferred:** VNA through a pigtail on the AE1 feed, with L3 lifted, inside the assembled case.
     - **Without a VNA:** RSSI and throughput A/B tests. Swap values from the tuning kit listed in the report.
     - A bare board reads ~2.9 GHz; always test it inside the case.
3. **Via-in-pad:** removed. No POFV fee.
4. **Vias:** standard 0.4/0.2 mm, so no small-hole fee. Routing clearance is 0.11 mm and JLC's minimum is 0.09 mm.
5. **Crystal load caps:** 24 pF C0G, matching the crystal's 15 pF load spec plus ~3 pF of board stray. Trim ±2 pF after measuring the clock offset.
6. **RV-3032 VBACKUP and EVI are tied to GND** (backup unused). Confirm against the datasheet.
7. **No vibration motor in rev A.** There's no room in the 7 mm stack. GPIO17 is reserved.
8. **No load-sharing power path.** While docked, the TP4054 charges the battery while the ESP32 runs from it.
9. **JLC CPL rotations:** LCSC-imported footprints sometimes need rotation offsets. Check JLC's placement preview.
10. **Battery** is a placeholder envelope (27 × 15 × 2.5 mm with PCM). Pick the real cell.

## Cost breakdown (JLC Economic PCBA, live prices 2026-10-03)
| Item | 2 boards assembled (of 5 made) | 5 boards assembled |
|---|---|---|
| Bare PCB: 4-layer, 0.8 mm, ENIG, standard 0.4/0.2 vias, impedance stack-up | ~$10–20 | ~$10–20 |
| Assembly setup + stencil | $9.50 | $9.50 |
| Loading fees: 23 extended lines × $3 | $69 | $69 |
| Parts at $25.44 per board (BMA400 is $14.91 of that) | $51 | $127 |
| Solder joints | ~$1 | ~$2 |
| **Subtotal (USD)** | **≈ $140–150** | **≈ $220–230** |
| Shipping: DHL Express ~$25, or Global Standard ~$10 (1–2 weeks) | $10–25 | $10–25 |
| GST+PST 12% + brokerage (CAD) | ~$30–40 | ~$40–50 |

**Where the money goes:**
- **BMA400:** $15 at both JLC and LCSC; it's scarce. That's ~60% of per-board parts cost.
- **Loading fees:** $45 of the $69 is for 15 lines of tiny passives that cost under a cent each.
- JLC has essentially no basic or preferred 0201 parts. Swapping them for same-spec basic 0402 parts would need more board area than this board has.

**Already applied, with no component downgrade:**
- 1N5819WS → B5819WS diodes: same spec, preferred, so no fee.
- Standard 0.4/0.2 mm vias instead of 0.3/0.15: avoids the small-hole fee.
- Via-in-pad removed: avoids the 4-layer POFV fee.

**Further options, none of them downgrades:**
1. **Global Standard shipping** instead of DHL: saves ~$15, costs about a week.
2. **DHL with DDP** (taxes prepaid at checkout): avoids DHL's separate brokerage bill.
3. **Merge two values onto existing lines:**
   - R11 1 MΩ → 10 MΩ: gate pull-down, works the same.
   - R1 10 kΩ → 20 kΩ: EN pull-up, 20 ms RC instead of 10 ms.

   That's −$6, but it moves away from the reference values.
4. **More boards per order:** fees are per order. Each extra assembled board costs ~$25 more, so 5 boards instead of 2 gives you spares for experiments.
5. **JLC Global Sourcing** for the BMA400: check Digi-Key/Mouser pricing at order time.
