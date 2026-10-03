# Bar-shaped displays

_Researched 2026-10-03. Items marked "unverified" need a datasheet check before PCB work._

The Fitbit Charge screen is about 1.04". A band about 23 mm wide fits an outline of roughly **30–35 × 14–19 mm**. Anything 2.13" or larger is 59 mm or more long, which is too long.

## Shortlist
1. **[Good Display GDEM0097T61](https://www.good-display.com/product/486.html)**: 0.97" e-paper, 184×88 (2.1:1), 210 ppi, 30.0×14.15×**1.0 mm**, SSD1680, partial refresh in about 0.3 s. **$4.17, in stock** ([buy-lcd](https://www.buy-lcd.com/products/gdem0097t61)). This is the most direct Watchy successor: the same vendor, and a controller family close to Watchy's SSD1681. Downsides: an 18-pin FPC instead of 24 pins, glass, and a small 22×10.6 mm active area.
2. **[Sharp LS011B7DH03](https://www.digikey.com/en/products/detail/sharp-microelectronics/LS011B7DH03/25953418)**: 1.08" memory LCD, 160×68 (2.35:1), 32×14×**0.745 mm**, µW power and fast refresh, so it can animate. This is the most Fitbit-like option. Downsides: sourcing (non-stock, 28-week lead), lower contrast, it needs a VCOM toggle, and it has no GxEPD2 driver.
3. **[GDEW0102I4FC](https://www.good-display.com/product/341.html)**: 1.02" **flexible** e-paper, 128×80 (1.6:1), **0.3 mm** thick and unbreakable, and the GxEPD2_102 driver works with it. Downsides: it is a squatter shape, the 30-pin FPC likely needs ACF bonding (unverified), and its rigid sibling is EOL.

## Comparison
| Part | Type | Res | Outline mm (T) | IC | FPC | Driver | Status |
|---|---|---|---|---|---|---|---|
| **GDEM0097T61** 0.97" | e-paper glass | 184×88 | 30.0×14.15×1.0 | SSD1680 | 18p | adapt GxEPD2 (unverified) | $4.17 in stock |
| GDEW0102T4 1.02" | e-paper glass | 128×80 | 32.57×18.6×0.98 | UC8175 | 30p | GxEPD2_102 | **EOL** |
| **GDEW0102I4FC** 1.02" | e-paper flex | 128×80 | 32.57×18.6×0.3 | UC8175 | 30p ACF? | GxEPD2_102 | active |
| GDEM0213I61 2.13" | e-paper flex | 212×104 | 59.2×29.2×0.44 | SSD1680 | 24p | B74-ish | $8.46, too long |
| **Sharp LS011B7DH03** 1.08" | memory LCD | 160×68 | 32.0×14.0×0.745 | SPI | ~10p? | Adafruit_SharpMem port | 28-wk lead |
| Sharp LS013B7DH05 1.26" | memory LCD | 144×168 | 24.68×30×0.745 | SPI | – | Adafruit | near-square |
| JDI LPM013M126 1.28" | colour MIP | 176×176 | – | SPI | – | Zephyr | square (Bangle.js 2) |
| JDI 0.96" (LPM009M349A?) | colour MIP | 144×72 | ? | SPI | – | hobby | [Tindie](https://www.tindie.com/products/questwise-ventures/ultra-low-power-jdi-096-144x72-color-memory-lcd/), grey market |

Ruled out: GDEM0122T61 and GDEM0189T61 are near-square, and the 1.54" flexible is square. Waveshare, Pervasive, WeAct and Seeed have no bar part under 2".

## E-paper vs memory LCD
- **Power:** both are near zero when static. E-paper holds its image with the power cut. MLCD needs power and a VCOM toggle at about 1 Hz.
- **Thickness:** flexible e-paper is 0.3 mm, MLCD 0.745 mm, glass e-paper 1.0 mm.
- **Contrast:** e-paper is better. MLCD is grey on silver, but still readable in sunlight.
- **Refresh:** MLCD wins clearly, with animation, no ghosting and a better low-temperature range. E-paper takes about 0.3 s to partial-refresh and is rated 0–50 °C.
- **Verdict:** e-paper for a Watchy-style minute tick. MLCD if we want wrist-raise animations and scrolling notifications.

## Front light and touch
Front-lit e-paper only exists at 1.54" and 2.13" (adding about 0.7–0.9 mm). Touch only exists at 1.54" (GDEY0154D67-T03). For a bar, plan side-firing LEDs and a capacitive pad or buttons on the case.
