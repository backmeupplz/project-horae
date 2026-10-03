# Slim batteries

_Researched 2026-10-03. Power numbers are estimates. Measure them with a PPK2 on the first prototype._

**Bottom line:** use a stock **2.4–3.0 × 20 × 30 mm LiPo pouch, 100–130 mAh**. The MCU choice matters more than the chemistry. **Sodium-ion is not an option yet** (see below).

## Power budget (estimates)
The original Watchy gets 5–7 days on 200 mAh ([docs](https://watchy.sqfmi.com/docs/battery-life)), which works out to about 1.2–1.7 mA average. There is a lot of room to improve.

| | ESP32-S3 | nRF52840 |
|---|---|---|
| Sleep floor (board) | ~15–25 µA | ~5–15 µA |
| Wake every minute | reboots from deep sleep: ~75 µA avg | no reboot: ~2 µA |
| E-paper partial refresh | ~5 µA avg | same |
| BLE sync now and then | ~20–60 µA | ~10–30 µA |
| **Total** | **~3–4 mAh/day** | **~0.6–1.2 mAh/day** |
| 1 week (×1.5–2 margin) | 35–50 mAh | 10–15 mAh |
| 2 weeks | 70–100 mAh | 20–35 mAh |

The ESP32-S3 column assumes well-optimized firmware. Stock Watchy-style firmware draws about 10× more. On the nRF52840, the VDDH pin takes LiPo voltage directly, so no LDO is needed.

## Options
Wh/L is our own calculation: nominal V × mAh ÷ volume.

| Chemistry | Example | mm | mAh | Wh/L | Where | Price |
|---|---|---|---|---|---|---|
| LiPo + PCM | [Adafruit 1317](https://www.adafruit.com/products/1317) | 3.8×19.75×26 | 150 | ~285 | Adafruit / Digi-Key CA | US$5.95 |
| LiPo + PCM | [Adafruit 1570](https://www.adafruit.com/product/1570) | 3.8×11.5×31 | 100 | ~275 | Adafruit | US$5.95 |
| LiPo cell | [EEMB LP302030 / LP242030](https://www.sos.sk/novinky/pdf/2587_eemb-lipol-overview-en-1.pdf) | 3.0 / 2.4×20×30 | 130 / 100 | ~260 | EEMB, Amazon | ~$2–6? |
| Generic LiPo | AliExpress 302030 / 402030 | 3–4×20×30 | 130–200 | ~250–300 | AliExpress | $2–5 |
| Ultra-thin LiPo | [Grepow GRP0849049](https://grepow.com/shaped-battery/ultra-thin-battery.html) | 0.85×49×49 | 140 | ~260 | Grepow samples | ask |
| Ultra-thin LiPo | PowerStream | 0.5–2 thick | ~2 mAh/cm² @0.5 mm | ~150 | powerstream.com | from ~$8 |
| Ceramic Li-ion | NGK EnerCera EC382704P-T | 0.45×38×27 | 27 | ~220 | Japan only | ? |
| Curved LiPo | [Grepow 3020035](https://grepow.com/battery-news/grepow-curve-shaped-lipo-battery-3-8V-200mah-3020035.html) | ~3×20×35 | 200 | ~300 | custom, MOQ | ? |
| Li-ion coin | LIR2032 | Ø20×3.2 | 40 | ~150 | Amazon.ca | ~$2 |
| Thin-film / solid state | TDK CeraCharge, Ilika, ITEN | ~1 thick | 0.1–0.25 | ~10 | samples | only fits RTC backup |
| **Sodium-ion** | 18650 (smallest retail size) | Ø18×65 | ~1500 | 250–375 | B2B | **no wearable cells** |
| Si-C anode | LeydenJar Silyte | ? | ? | 800+ claimed | OEM eval only | n/a |

## Sodium-ion: an honest no
- No thin pouch or coin Na-ion cells are commercially available. Retail starts at 18650 size ([overview](https://en.wikipedia.org/wiki/Sodium-ion_battery)).
- Energy density is lower than LiPo, and packaging overhead would hurt small cells even more.
- Voltage swings from about 4.0 V down to 1.5 V. The ESP32 needs ≥3.0 V, so we'd need a buck-boost converter, which costs quiescent current and board area.
- It needs a charger with a Na-specific 3.9–4.0 V limit, because a 4.2 V Li charger overcharges it.
- Its strengths (cold performance, 0 V storage, grid-scale cost) don't matter on a wrist. Revisit around 2028.

## Other categories
- **Ultra-thin under 1 mm:** real cells, about 260 Wh/L at 0.85 mm. Stock sizes don't fit a band, so it's a custom Grepow order by email.
- **Curved / flexible:** Jenax J.Flex is still at demo stage and Panasonic's flexible cell was never sold at retail. Grepow curved cells are custom-only. Not for v1.
- **Coin cells:** 3.2 mm thick and low capacity, worse than a pouch on every axis.
- **Silicon-carbon:** expect +10–15% capacity per volume once hobby sizes appear.

## Mechanical and charging
- **Swelling:** leave 8–10% of the cell thickness as clearance, about 0.3 mm on a 3 mm cell.
- **PCM:** adds 3–5 mm of length and 1–3 mm of local thickness. We can buy a bare cell instead and put the protector (DW01 / FS312 class) on our PCB. That's thinner, but needs a fuse and careful testing.
- **Charging:** magnetic pogo pins plus a linear charger at ≤0.5C (MCP73831 / BQ25101). Qi adds a coil and ferrite (~1 mm) plus heat, and is oversized at this power level.
- **Shipping:** LiPo ships by ground. Digi-Key CA and Adafruit ship to Vancouver.

## Recommendation
1. **nRF52840 + 100–130 mAh 2.4–3.0 mm cell:** about 3–6 weeks. A ~50 mAh cell 1.5 mm thick would still give about 2 weeks.
2. **ESP32-S3 + the same cell:** about 1–2 weeks, and only with optimized firmware.
3. **Later revision:** a custom Grepow 1.0–1.5 × 22 × 40 mm cell once the enclosure is frozen.
