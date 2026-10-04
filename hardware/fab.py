"""JLCPCB assembly files from design.py + the placed board: BOM (LCSC numbers) and CPL. Run: ./kicad python3 fab.py"""
import csv, collections, sys, pcbnew
from design import PARTS

board = pcbnew.LoadBoard("horae.kicad_pcb")
OX, OY = 100.0, 100.0
groups = collections.OrderedDict()
for ref, sym, val, fp, lcsc, pins, block in PARTS:
    if lcsc:
        groups.setdefault((lcsc, fp.split(":")[1]), {"vals": [], "refs": []})
        g = groups[(lcsc, fp.split(":")[1])]; g["refs"].append(ref); g["vals"].append(val)
with open("out/jlc-bom.csv", "w", newline="") as f:
    w = csv.writer(f); w.writerow(["Comment", "Designator", "Footprint", "LCSC Part #"])
    for (lcsc, fp), g in groups.items():
        w.writerow([g["vals"][0].split("/")[0] if len(set(g["vals"])) > 1 else g["vals"][0], ",".join(g["refs"]), fp, lcsc])
with open("out/jlc-cpl.csv", "w", newline="") as f:
    w = csv.writer(f); w.writerow(["Designator", "Mid X", "Mid Y", "Layer", "Rotation"])
    for fp in board.GetFootprints():
        ref = fp.GetReference()
        if not any(p[0] == ref and p[4] for p in PARTS):
            continue
        pos = fp.GetPosition()
        # KiCad Y grows down; JLC CPL expects Y up. Rotations may need per-part offsets (check JLC's preview).
        w.writerow([ref, f"{pcbnew.ToMM(pos.x) - OX:.3f}mm", f"{OY - pcbnew.ToMM(pos.y):.3f}mm",
                    "Bottom" if fp.IsFlipped() else "Top", f"{fp.GetOrientationDegrees() % 360:.1f}"])
print(f"BOM: {len(groups)} lines, {sum(len(g['refs']) for g in groups.values())} parts")
