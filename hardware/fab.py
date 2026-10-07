"""JLCPCB assembly files from design.py + a placed board: BOM (LCSC numbers) and CPL in that board's gerber frame.
Run: ./kicad python3 fab.py [board.kicad_pcb cpl.csv]   (default: horae.kicad_pcb -> out/jlc-bom.csv + out/jlc-cpl.csv)"""
import csv, collections, sys, pcbnew
from design import PARTS

# CPL rotation = KiCad rotation + this offset. Measured pad by pad against JLC's EasyEDA footprint for each LCSC part:
# KiCad's SOT-666 has pin 1 where EasyEDA's has pin 4, the SWPA3010S land is numbered the other way round; all other
# parts (both crystals, the WCSPs, J1, the mic, the diodes, the passives) match at 0 with no origin offset.
ROT_OFFSET = {"U4": 180, "L4": 180}

board_path, cpl_path = (sys.argv[1], sys.argv[2]) if len(sys.argv) > 2 else ("horae.kicad_pcb", "out/jlc-cpl.csv")
board = pcbnew.LoadBoard(board_path)
fitted = {p[0] for p in PARTS if p[4]}      # no LCSC number = not assembled (C12 DNP, antenna, pads, electrodes)

if board_path == "horae.kicad_pcb":
    groups = collections.OrderedDict()
    for ref, sym, val, fp, lcsc, pins, block in PARTS:
        if lcsc:
            g = groups.setdefault((lcsc, fp.split(":")[1]), {"vals": [], "refs": []})
            g["refs"].append(ref); g["vals"].append(val)
    with open("out/jlc-bom.csv", "w", newline="") as f:
        w = csv.writer(f); w.writerow(["Comment", "Designator", "Footprint", "LCSC Part #"])
        for (lcsc, fp), g in groups.items():
            w.writerow([g["vals"][0], ",".join(g["refs"]), fp, lcsc])
    print(f"BOM: {len(groups)} lines, {sum(len(g['refs']) for g in groups.values())} parts")

# Gerber frame: kicad-cli plots absolute coordinates with Y up, so X = x, Y = -y (no origin shift, no manual alignment)
rows = []
for fp in board.GetFootprints():
    ref = fp.GetReference()
    if ref not in fitted:
        continue
    assert not fp.IsFlipped(), f"{ref} on the bottom: top-side assembly only"
    pos = fp.GetPosition()
    rows.append([ref, f"{pcbnew.ToMM(pos.x):.3f}mm", f"{-pcbnew.ToMM(pos.y):.3f}mm", "Top",
                 f"{(fp.GetOrientationDegrees() + ROT_OFFSET.get(ref, 0)) % 360:g}"])
assert {r[0] for r in rows} == fitted, f"CPL misses {fitted - {r[0] for r in rows}}"
with open(cpl_path, "w", newline="") as f:
    w = csv.writer(f); w.writerow(["Designator", "Mid X", "Mid Y", "Layer", "Rotation"])
    w.writerows(sorted(rows, key=lambda r: (r[0][0], int("".join(c for c in r[0] if c.isdigit()) or 0))))
print(f"CPL: {len(rows)} placements -> {cpl_path}")
