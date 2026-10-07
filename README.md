# Project Horae

A miniaturized successor to [Watchy](https://watchy.sqfmi.com/), the open-source ESP32 e-paper watch. It's rebuilt as thin as possible, in a slim band form factor (think Fitbit Charge, not a square).

Build log: **[projecthorae.com](https://projecthorae.com)**

## Build one
- [ORDER.md](ORDER.md): the JLCPCB order (files and every order-form setting), the shopping list with Canadian sources, and the totals
- [ASSEMBLY.md](ASSEMBLY.md): printing, a test-print checklist, bench bring-up, assembly, the dock wiring, and the firmware rules the hardware depends on
- [hardware/README.md](hardware/README.md): the board design, the pre-order review, what to verify at bring-up, and the cost

## Research
- [Displays](research/displays.md): bar-shaped e-paper and memory LCD panels
- [Batteries](research/batteries.md): thin LiPo, sodium-ion reality check, power budget
- [Electronics](research/electronics.md): EDA tools, fabs shipping to Vancouver, key ICs
- [CAD & printing](research/cad-tools.md): code-CAD and the headless Bambu A1 mini pipeline
- [Prototype v0](research/prototyping.md): breadboard kit, steps, charging
- [Build plan, rev A](research/build-plan.md): custom board straight away, order → solder → firmware → case → wear

## 3D explorer
The landing page's interactive model (`explorer/`) is generated from the case CAD and the KiCad board:
`.venv/bin/python cad/web.py` (needs Docker for KiCad and `npx` for gltf-transform). Re-run it after changing the CAD or the board.

## Printing (Bambu A1 mini, 0.4 nozzle, one filament per job)
- `cad/out/plates/petg.3mf`: both shells plus the dock's tray and lid, in PETG Basic or Matte. Use 0.1 mm layers **and a 0.1 mm first layer** (it is the skin over the watch's magnets), no supports.
- `cad/out/plates/tpu.3mf`: every seal and cushion plus the dock's grip pad, in TPU 90A (not 95A: twice as stiff) from the external spool, printed slowly. Give the bezel gasket 0.08 mm layers.
- Carbon-fibre version: print `petg-cf.3mf` (PETG-CF, hardened nozzle) and `petg-cf-set.3mf` (the colour-matched PETG parts) instead of `petg.3mf`.
- Per-part notes (orientation, layer heights, squeeze) are in `PRINT` in `cad/horae.py`, and a full `.venv/bin/python cad/horae.py` run prints them.

## Adding a timeline entry
The timeline is newest first. Add a new `<li class="entry">` block at the top of the `<ol class="timeline">` in `index.html`, and put its photos in `media/YYYY-MM-DD/`.
