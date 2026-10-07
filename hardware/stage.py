"""Staged routing: import a Freerouting session into horae.kicad_pcb as locked tracks, then re-export the DSN, so the next
Freerouting pass routes around them. Run: ./kicad python3 stage.py out/stage1.ses"""
import sys
import pcbnew
import zlib
from gen_pcb import export_dsn
pcbnew.KIID.SeedGenerator(zlib.crc32(sys.argv[1].encode()))   # reproducible, per-stage UUIDs
board = pcbnew.LoadBoard("horae.kicad_pcb")
from sesfix import fix_ses
fixed = sys.argv[1].replace(".ses", "-fixed.ses"); fix_ses(sys.argv[1], fixed)
if not pcbnew.ImportSpecctraSES(board, fixed):
    raise SystemExit("SES import failed")
for t in board.GetTracks():
    t.SetLocked(True)
board.Save("horae.kicad_pcb")
export_dsn(board, fat_touch=True)   # touch copper is final now: later passes keep 0.3 mm from it
print(f"stage locked: {sum(1 for t in board.GetTracks())} tracks/vias")
