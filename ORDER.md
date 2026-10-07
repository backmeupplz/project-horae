# Ordering Horae rev A (2 watches + 1 dock)

Prices were checked live on 2026-10-06 for delivery to Vancouver, BC.
- USD → CAD at 1.4254 (Bank of Canada, 2026-10-05).
- "+ tax" means GST 5 % + BC PST 7 %. Digi-Key.ca, Amazon.ca, AliExpress and Bambu CA add it at checkout; courier imports
  collect it at delivery.

Then build it with [ASSEMBLY.md](ASSEMBLY.md).

## Order this first
| When | What | Why |
|---|---|---|
| Today | LiPo cells (AliExpress) | 2–4 weeks on the battery shipping lines: the critical path |
| Today | 5–10 ESP32-S3FN8 into your JLC parts inventory | JLC has 602 and LCSC has 0 |
| By Oct 12 | Displays (buy-lcd) | the US$4.17 sale ends Oct 12; 64 in stock |
| This week | JLC boards | about 2 weeks door to door |
| This week | Digi-Key, Amazon.ca, magnets, filament | 1–10 days; enough for the test print |

## 1. The board: JLCPCB, Standard PCBA, top side only

Files, all in `hardware/out/`:

| Upload | File |
|---|---|
| Gerbers (the 70 × 70 mm frame with one board) | `panel-gerbers.zip` |
| BOM | `jlc-bom.csv` (33 lines, 65 parts) |
| CPL (rotation offsets already applied) | `jlc-cpl-panel.csv` |

Order-form settings:

| Setting | Choose |
|---|---|
| Base material / layers / thickness | FR-4, standard TG, **4 layers, 0.6 mm** |
| Delivery format | **Panel by Customer**: the frame holds one board. Quantity **5** (the minimum), and you assemble 2 or 5 of them. |
| Board size | 70 × 70 mm |
| Surface finish | **ENIG 1 µ"**, needed for the 0.4 mm-pitch WCSPs and the pogo pads |
| Copper | 1 oz outer, 0.5 oz inner |
| Impedance control | **No requirement**, but specify stack-up **JLC04061H-3313**. The RF line is only about 0.05 λ long; without a named stack-up JLC may use a thicker prepreg. |
| Via covering | **Plugged**: no vias sit in pads |
| Min via hole / diameter | 0.3 / (0.4/0.45): the free default. The board's vias are 0.45/0.2. |
| Mask / silkscreen | green / white |
| Mark on PCB | Remove Mark. The frame rail has a "JLCJLCJLCJLC" spot for the order number. |
| Confirm Production File | Yes ($1.05) |
| PCB Assembly | **Standard**, top side, quantity **2** (or 5) |
| Edge rails / fiducials / tooling holes | **Added by customer** |
| Confirm Parts Placement | **Yes** ($0.45). Check every pin-1 dot and cathode bar in the preview: U1–U4, U6, J1, Q1/Q2, D1–D4, MIC1, Y1. |
| Shipping | **DHL Express**. Global Standard is limited to orders of US$99 or less. |

**Cost (USD)** (`hardware/cost.py`; the bare PCB from JLC's live quote):

| | 2 boards | 5 boards |
|---|---|---|
| Bare PCB, 5 frames | 46.20 | 46.20 |
| PCBA fees: setup 25.56, stencil 8.21, 33 feeders × 1.53, fixtures 16.42, X-ray, placement confirmation and packing | 118.03 | 122.13 |
| Parts, with JLC's attrition and minimum quantities | 30.42 | 62.93 |
| Joints | ~0.75 | ~1.85 |
| DHL Express, 2–4 business days | 31.23 | 31.23 |
| **Total** | **≈ 226** | **≈ 264** |
| **Landed (CAD)**, with 12 % tax on the goods and DHL's CAD 18 clearance | **≈ 375** | **≈ 435** |

- Duty is 0 % (HS 8534.00.00). There is no DDP option for Canada.
- X-ray and fixture fees are confirmed only after the BOM/CPL upload.
- 5 boards cost about $13 more each than 2, and a spare saves a 2-week JLC round trip if one dies during assembly.

## 2. Everything else

Each item has an alternative in the [sourcing notes](#alternatives) below.

| # | Item | Buy | Qty | CAD (before tax) | Delivery |
|---|---|---|---|---|---|
| 1 | **Display** Good Display GDEM0097T61, "ePaper Only": 18-pin 0.5 mm FPC, matches J1 pin for pin | [buy-lcd.com](https://www.buy-lcd.com/products/gdem0097t61) | **4** (one spare, one for practising the U-bend) | 23.06 + shipping (Economy US$17.87, DHL US$41.91) | ships in 3 business days; Economy 12–30 days, DHL 2–5 |
| 2 | **LiPo cell** 301520 class with protection and bare red/black leads. **It must measure ≤ 21.4 × 16.0 × 3.25 mm including the PCM; buy ≤ 3.05 mm thick.** | [AliExpress EASYLANDER 5-pack](https://www.aliexpress.com/item/1005009277089856.html) (301520 option, drawing 3 × 15 × 20 ± 2 incl. PCM) | 1 pack of 5 | 16.68 | 2–4 weeks |
| 3 | **Motor** Vybronics VC0625B001L, 6 × 2.5 mm, 10 mm leads | [Digi-Key 1670-VC0625B001L-ND](https://www.digikey.ca/en/products/detail/vybronics-inc/VC0625B001L/1670-VC0625B001L-ND) | 4 | 19.00 | next day; Digi-Key is free from C$100, otherwise C$15; duties included |
| 4 | **Spring pins** Mill-Max 0955-0-15-20-71-14-11-0 | [Digi-Key ED11533-ND](https://www.digikey.ca/en/products/result?keywords=0955-0-15-20-71-14-11-0) | 10 | 15.76 | same Digi-Key order |
| 5 | **USB-C breakout** Adafruit 6050 (the dock is drawn for it) | [Digi-Key 1528-6050-ND](https://www.digikey.ca/en/products/result?keywords=1528-6050-ND) | 2 | 8.84 | same Digi-Key order |
| 6 | **Magnets** 3 × 1 mm N52, **metric** (2 per watch). Imperial 1/8" (3.175 mm) magnets don't fit the 3.05 mm wells. | [AliExpress SZYD, 50 pcs](https://www.aliexpress.com/item/1005010742498039.html) | 1 pack | 7.25 | Oct 15–18 |
| 7 | **Magnets** 3 × 3 mm N52, metric (4 per dock) | the same store, 50 pcs | 1 pack | 9.75 | Oct 15–18 |
| 8 | **30 AWG silicone wire**, red + black | [Amazon.ca BNTECHGO](https://www.amazon.ca/dp/B01M285AUG) | 1 | 8.90 | 1–2 days |
| 9 | **Strap**, 16 mm two-piece with quick-release bars. The ends must be ≤ 3.7 mm thick. | [Amazon.ca Anbeer silicone 16 mm](https://www.amazon.ca/dp/B0C9SRVT2D) | 2 | 33.90 | next day |
| 10 | Spare **spring bars**, 16 × 1.5 mm (optional: the straps include bars) | [Amazon.ca HARFINGTON, 12 pcs](https://www.amazon.ca/dp/B0F9W949YF) | 1 | 7.39 | 1–2 days |
| 11 | **Mic vent:** bare ePTFE film, about 0.25 mm thick, **no adhesive**. You cut a 1.4 × 1.0 mm patch per watch. | [AliExpress ePTFE film, 230 × 260 mm](https://www.aliexpress.com/item/1005001809765077.html) | 1 | 9.08 | 2–3 weeks; the first test print doesn't need it |
| 12 | **PETG** for the shells and dock | [Bambu PETG Basic](https://ca.store.bambulab.com/en/products/petg-basic) or [Matte](https://ca.store.bambulab.com/en/products/petg-matte) | 1 kg | 17.99 (refill) | 1–3 days to dispatch + 3–7 days |
| 13 | **TPU 90A** for the seals, cushions and grip pad. **Not 95A:** it is twice as stiff and overloads the snaps. | [Bambu TPU 90A](https://ca.store.bambulab.com/en/products/tpu-85a-tpu-90a): Black, White, Grape Jelly, Crystal Blue, Cocoa Brown or Quicksilver (or the Blaze/Frozen gradients) | 1 kg | 53.99 | same |
| 14 | PETG-CF + a hardened nozzle (carbon-fibre version only) | [Bambu PETG-CF](https://ca.store.bambulab.com/en/products/petg-cf) + [A1 mini hardened hotend](https://ca.store.bambulab.com/en/products/bambu-hotend-a1-a2) | 1 + 1 | 60.98 | same |
| 15 | Filament dryer, only if you don't have one (TPU must be dried: 70 °C for 8 h) | [SUNLU S2](https://www.amazon.ca/dp/B0FGV3WQ5X) | 1 | 59.49 | 2–8 days |

**Tools** (skip what you own). The full set is C$99 and the lean set C$83:
- Solder (63/37, 0.6 mm) and flux (Chip Quik SMD291).
- A pin vise with a 1.0 mm bit, for the pin bores.
- Nylon spudgers, 10 mm Kapton tape and fine tweezers.
- Isopropyl alcohol.

For bring-up you also need a bench supply with a current limit, in place of the cell (ASSEMBLY.md section 3).

## 3. Totals (CAD, landed)
| Plan | What | Total |
|---|---|---|
| **Cheapest sensible** | 2 boards + displays by Economy + AliExpress cells, magnets and vent + a minimal Digi-Key order + Amazon straps, wire and filament (Amazon SUNLU PETG and Polymaker TPU 90A) | **≈ C$ 640** |
| **Fastest sensible** | 5 boards + displays by DHL + the full Digi-Key order + Amazon.ca Prime for the rest | **≈ C$ 780** |

Add about C$ 90 for tools and C$ 60 for a dryer if needed. You need only about 6 g of PETG and 0.4 g of TPU, so any
spools you already own work.

## 4. Before you press "order"
1. **Rebuild** (`hardware/build.sh`) and check `hardware/out/drc.json` shows 0 / 0 / 0. Upload the panel files, not the
   single-board zip.
2. **Pre-buy the ESP32-S3FN8.**
3. **Placement preview:** JLC's preview must show every part on the board. If parts float off the board, the CPL frame is
   wrong; stop.
4. **Displays:** order them before the Oct 12 sale ends.
5. **On arrival:**
   - measure the cells (≤ 21.4 × 16.0 × 3.25 mm including the PCM, ≤ 3.05 thick is best);
   - measure the strap ends (≤ 3.7 mm);
   - test-fit one magnet in a printed well.

## Alternatives
- **Display:** [AliExpress GooDisplay Official Store](https://www.aliexpress.com/item/1005004146215543.html) (US$6.96), or
  [microhello](https://microhello.com/products/gdem0097t61,097-inch-small-e-ink-screen-mini-e-paper-display) (US$7.65).
- **Cell:** [Liter Energy 301520](https://www.aliexpress.com/item/1005009496624282.html) (C$5.22 each), or a
  [301518 4-pack](https://www.aliexpress.com/item/1005012116947474.html) (C$18.08). Measure whatever arrives.
- **Motor:** VC0625B002L, the same motor with adhesive.
- **Magnets:** [Amazon.ca GOOZADA, 400 pcs](https://www.amazon.ca/dp/B0F66ZNSV8) (3 × 1), or
  [magpross, 140 pcs](https://www.amazon.ca/dp/B09B34HFLP) (3 × 3). Both must be metric.
- **USB-C breakout:** [Adafruit direct](https://www.adafruit.com/product/6050), US$2.95 + DHL.
- **Strap:** [Barton silicone 16 mm](https://www.amazon.ca/dp/B01ASOGBYG).
- **Filament:** [SUNLU PETG](https://www.amazon.ca/dp/B0B99M3D9B) (C$17.09), or
  [Polymaker PolyFlex TPU90](https://www.amazon.ca/dp/B09KKXZCBR) (C$27.99).
- **USB ESD:** the board uses ST's own USBLC6-2P6 (C15999). The TECH PUBLIC copy (C2827693) also fits, but its CPL
  rotation differs (270° instead of 180°).
