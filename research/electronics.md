# Electronics: EDA, fabs, key ICs

_Researched 2026-10-03. Items marked "unverified" still need a check._

## Starting point: Watchy's KiCad files
Watchy's hardware lives in **[sqfmi/watchy-hardware](https://github.com/sqfmi/watchy-hardware)** (MIT), not in the firmware repo `sqfmi/Watchy`.
- **Format:** KiCad 7. KiCad 10 opens it fine.
- **Board:** 4 layers.
- **Contents:** STEP models, gerbers, BOM.
- **v3 BOM:**
  - Bare ESP32-S3 (QFN56), 32 kHz crystal, PCB antenna
  - BMA423 accelerometer, TP4054 charger, RT9080 LDO
  - Micro-USB, pager motor
  - No external RTC IC

## EDA tools an agent can drive
| Tool | License | Scriptable | Headless render | Maturity |
|---|---|---|---|---|
| **KiCad 10** + `kicad-cli` | GPL | Runs ERC/DRC (JSON), gerbers, drill, pick-and-place, BOM, STEP and SVG. Project files are plain-text S-expressions an agent can edit. | ✅ `kicad-cli pcb render` | Production |
| KiCad IPC API | GPL/MIT | Needs the GUI running. Headless use arrives in KiCad 11. | ❌ | Early |
| [atopile](https://pypi.org/p/atopile) | MIT | `.ato` language that picks JLC parts and generates the KiCad PCB | via KiCad | Pre-1.0 |
| [tscircuit](https://docs.tscircuit.com/) | MIT | React/TS with a built-in autorouter. Exports a KiCad project. | ✅ | Unstable |
| [SKiDL](https://pypi.org/project/skidl/) | MIT | Python netlists only. KiCad 10 support unverified. | ❌ | Stable, narrow |
| [Freerouting](https://github.com/freerouting/freerouting/) | GPL | `java -jar freerouting.jar -de board.dsn -do board.ses` | ❌ | Mature |
| Quilter | SaaS | Upload KiCad, get AI layout back. Web only. | ❌ | Unproven on RF |
| Flux.ai / EasyEDA Pro / JITX | SaaS / freeware / commercial | Browser-bound or unclear | ❌ | Wrong fit |

## Fabs that ship to Vancouver
| Fab | Thin rigid | Flex / rigid-flex | HDI / fine pitch | Assembly |
|---|---|---|---|---|
| **[JLCPCB](https://jlcpcb.com/capabilities/pcb-capabilities)** | 2-layer 0.4 mm. 4-layer: 0.8 mm listed, 0.6 mm reportedly possible (unverified). | Flex: 1–2 layers, from $2–25 per 5. No rigid-flex online. | 1–3 step HDI, via-in-pad, 01005, 0.35 mm pitch | Standard PCBA needs a 70×70 mm panel |
| **PCBWay** | 0.4 mm+ | Flex and **rigid-flex** | ✅ | ✅ |
| NextPCB | ✅ | Flex and rigid-flex | ✅ | Free PCBA promo for 1–10 pcs |
| Elecrow / Seeed Fusion | ✅ | Flex and rigid-flex | limited | Slower (7–25 days) |
| OSH Park (US) | 4-layer only at 1.6 mm | Flex suspended | ❌ | ❌ |
| Candor (Toronto) | ✅ | Rigid-flex, HDI | ✅ | Partners. Premium price |
| Bittele/7pcb (Markham) | partners | partners | ✅ | Turnkey, ~6 days |

**Estimated cost:** 5 assembled small 4-layer boards at JLC come to **≈ USD 60–150** before shipping. Shipping is DHL, 3–6 days, ~$20–35. (Estimate, not a quote.)

**Import costs into BC (2026):**
- Tax: PCBs aren't on Canada's China surtax list ([SOR/2024-187](https://laws-lois.justice.gc.ca/eng/regulations/SOR-2024-187/page-1.html)). Expect **GST 5% + PST 7%** plus brokerage.
- Brokerage: DHL charges about CAD $10–20.
- De minimis from China is only about CAD $20, so assume every order is taxed. JLC's DHL DDP option roughly breaks even.
- US shipments (OSH Park) are tax-free under CAD $40 thanks to CUSMA.

## Key ICs
| | ESP32-S3 | ESP32-C6 | nRF52840 | nRF54L15 |
|---|---|---|---|---|
| Sleep | ~7 µA deep sleep (14+ µA on real boards) | ~7 µA | 2.35 µA System ON | 2.9 µA ON / 0.7 µA OFF |
| Radio | Wi-Fi 4 + BLE 5 | Wi-Fi 6 + BLE 5 + 802.15.4 | BLE 5, Thread | BLE 6, Thread |
| Smallest module | S3-MINI-1 15.4×20.5×2.4 | C6-MINI-1 13.2×16.6×2.4 | MDBT50Q 10.5×15.5×2.05 | **Fanstel BC15P 6.0×6.5×2.0** |
| Watchy firmware | ✅ | mostly | ❌ rewrite | ❌ rewrite (Zephyr) |

- **RTC:** RV-3028-C7 (~45 nA), only if the internal RTC drifts too much.
- **Accelerometer:** BMA423 or BMA456 (both have a pedometer). LIS2DW12 draws less but has no pedometer.
- **Charger / PMIC:** TP4054 (simplest), BQ25125 (wearable PMIC), nPM1300 (pairs with nRF).
- **Haptics:** coin ERM motor plus a MOSFET, or DRV2605L plus an LRA.

## Recommendation
1. **EDA:** fork `watchy-hardware` into KiCad 10.
   - The agent edits the S-expression files directly.
   - A Makefile runs `kicad-cli` for ERC/DRC, renders, STEP and fab outputs.
   - Freerouting handles non-RF nets.
2. **Fab:** JLCPCB, 4-layer at 0.6–0.8 mm, Standard PCBA, panelized, shipped by DHL. Get rigid-flex quotes from PCBWay or NextPCB once the design settles.
3. **ICs:** v1 keeps the bare ESP32-S3, which is the lowest risk because it reuses the schematic, RF section and firmware. Evaluate an nRF54L15 module for v2.
