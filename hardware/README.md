# Horae rev A hardware

ESP32-S3 band watch board, **36.3 × 16.5 × 0.8 mm, 4 layers**, fully assembled by JLCPCB.

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
  - **Antenna:** Watchy's meander IFA with its 3 pF / 7.5 nH / 3 pF pi match.
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
2. **RF.** Watchy's antenna sits on a much smaller ground plane here, the RF trace was autorouted (not impedance-controlled), and the match values are Watchy's.
   - Expect to retune the C/L/C values. Hand-routing the RF path is a good idea before ordering.
3. **Via-in-pad** at C5.2, C15.2 and U6.9 (BMA400 GND), where no via fit beside the pad. This needs JLC's filled + capped via option (possibly a fee).
4. **0.3 mm vias with 0.15 mm holes** cost extra at JLC. 0.2 mm holes would need a looser placement or a reroute.
5. **Crystal load caps** are 22 pF (basic part) against the crystal's 15 pF load spec, so the clock runs a few ppm fast. 24 pF is the exact value.
6. **RV-3032 VBACKUP and EVI are tied to GND** (backup unused). Confirm against the datasheet.
7. **No vibration motor in rev A.** There's no room in the 7 mm stack. GPIO17 is reserved.
8. **No load-sharing power path.** While docked, the TP4054 charges the battery while the ESP32 runs from it.
9. **JLC CPL rotations:** LCSC-imported footprints sometimes need rotation offsets. Check JLC's placement preview.
10. **Battery** is a placeholder envelope (27 × 15 × 2.5 mm with PCM). Pick the real cell.

## Cost (JLC Economic PCBA, 2026-10-03 prices)
- **BOM:** 30 lines, about 24 of them extended parts at a $3 loading fee each, so ~$72 per order.
- **Parts:** ~$25.40 per board. The BMA400 alone is $14.91 at JLC; LCSC lists it at $2–3.
- **2 assembled boards (of 5):**

| Item | Cost |
|---|---|
| Boards | ~$10–25 (fine vias and via-in-pad may add) |
| Setup + stencil | $9.50 |
| Loading fees | ~$72 |
| Parts | ~$51 |
| **Subtotal** | **≈ USD 145–160** |
| DHL | +$25 |
| Tax and brokerage | +~CAD 40 |
| **Landed** | **≈ CAD 280** |

Cheaper options: BMA456 instead of BMA400 (−$10/board), basic-library swaps for some 0201 parts, or assembling only the hard parts at JLC.
