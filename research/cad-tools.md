# CAD tools & print pipeline

_Researched 2026-10-03. Items marked "verify" are unconfirmed._

**Primary stack: [build123d](https://build123d.readthedocs.io/).** It's Python and B-rep, so we get real fillets and STEP output. It imports the KiCad board STEP for interference checks and installs with plain pip. **Fallback: OpenSCAD snapshot (Manifold)** for quick mesh parts and one-line PNG renders.

| Tool | License | Lang | STEP | STL/3MF | KiCad STEP import | Headless PNG | Verdict |
|---|---|---|---|---|---|---|---|
| **build123d** | Apache-2.0 | Python (OCCT) | ✅ | ✅/✅ | ✅ `import_step()` | via pyvista | **Primary** |
| CadQuery 2.5 | Apache-2.0 | Python (OCCT) | ✅ | ✅/✅ | ✅ | via pyvista | Fine, slower releases |
| OpenSCAD snapshot | GPL-2 | DSL | ❌ | ✅/✅ | ❌ (convert to STL) | ✅ built-in | **Fallback** |
| FreeCAD 1.x | LGPL | Python | ✅ | ✅ | ✅ | hard headless | Heavy |
| Zoo / KCL | proprietary, metered | KCL | ✅ | ✅ | verify | cloud | Ideation only |
| Onshape | free = public docs | FeatureScript | ✅ | ✅ | ✅ | API | Cloud-only |
| Fusion 360 | free personal | Python | ✅ | ✅ | ✅ | ❌ no headless | Unsuitable |

Agent tooling worth borrowing: [earthtojake/text-to-cad](https://github.com/earthtojake/text-to-cad) (build123d skills for Claude Code), [build123d-mcp](https://pypi.org/project/build123d-mcp/).

## Install
```sh
python3 -m venv ~/horae-venv && source ~/horae-venv/bin/activate
pip install build123d pyvista
brew install --cask openscad@snapshot kicad bambu-studio
```

## PCB → CAD
```sh
kicad-cli pcb export step --subst-models -o board.step board.kicad_pcb   # --subst-models or bodies go missing
```

## Screenshots of progress
- pyvista: `pv.Plotter(off_screen=True)` → `add_mesh(pv.read("case.stl"))` → `screenshot("view.png")`
- or `openscad -o view.png --render --imgsize=1200,800 view.scad` with `import("case.stl");`

## Slice + print on the A1 mini, headless
```sh
/Applications/BambuStudio.app/Contents/MacOS/BambuStudio --slice 1 --allow-newer-file \
  --load-settings "machine.json;process.json" --load-filaments "pla.json" \
  --export-3mf out.gcode.3mf case.3mf
```
Export the A1 mini preset JSONs from the app once. ([CLI wiki](https://github.com/bambulab/BambuStudio/wiki/Command-Line-Usage))

Send it over LAN with [`bambulabs_api`](https://pypi.org/project/bambulabs-api/): `upload_file()` then `start_print(..., use_ams=False)`. Third-party print commands need **LAN Only Mode + Developer Mode** turned on at the printer ([Bambu wiki](https://wiki.bambulab.com/en/knowledge-sharing/enable-developer-mode)). Developer Mode turns off cloud and the Handy app. Firmware support for the A1 series needs a verify.

## FDM rules for a thin wearable
- **Walls:** 0.8 mm minimum, 1.2–1.6 mm for the case, ≥1.5 mm around snaps. With the 0.2 mm nozzle, ~0.6–0.8 mm walls are possible for the final shell.
- **Tolerances:** 0.2–0.3 mm/side for slip and snap fits, ~0.15 mm for press fits. Print a calibration coupon first.
- **Snaps:** cantilever length ≥5× thickness, with layers along the beam.
- **Orientation:** print flat, display window up.
- **Materials:** PLA for prototypes (softens at ~60 °C), PETG for daily wear, TPU 95A for straps. Skip ASA/ABS on the open A1 mini.
- **Skin contact:** no FDM filament is certified skin-safe. Smooth or coat the back, or add a TPU pad.
- **Clearance:** 0.3–0.5 mm around the PCB envelope, extra around the LiPo for swelling. Support the e-paper glass on a ledge and never clamp its edges.
