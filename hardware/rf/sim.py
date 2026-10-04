"""openEMS FDTD model of the Horae rev A antenna end. Geometry from geom.json (rf/extract.py), case from spec.py.

Run (inside the horae-openems image, repo at /work):
  docker run --rm -v "$PWD/../..":/work -w /work/hardware/rf horae-openems python sim.py bare|env|wrist [--trim MM] [--res MM]   (or ./run_all.sh)

Model frame: x = KiCad x - 100 (+X = antenna end), y = KiCad y - 100, z = 0 at the PCB bottom (B.Cu), F.Cu at 0.8.
Simplifications: zero-thickness copper; In1/In2/B.Cu GND (+ the F.Cu pour away from the feed) merged into one PEC
block that ends at the keep-out; F.Cu pour polygons near the feed taken from the real fill; case as rectangular PETG
(no corner radii, lugs or PETG-CF); battery = floating PEC box; display = plain glass slab.
--trim MM shortens the meander from its open end by MM of conductor path (centre-line), for tuning studies.
"""
import json, os, sys
import numpy as np
from CSXCAD import ContinuousStructure
from CSXCAD.SmoothMeshLines import SmoothMeshLines
from openEMS import openEMS
from openEMS.physical_constants import EPS0

sys.path.insert(0, "../..")
import spec as S

case = sys.argv[1] if len(sys.argv) > 1 else "bare"
trim = float(sys.argv[sys.argv.index("--trim") + 1]) if "--trim" in sys.argv else 0.0
RES = float(sys.argv[sys.argv.index("--res") + 1]) if "--res" in sys.argv else 0.1   # fine x/y cell (mm)
tag = case + (f"_trim{trim:g}" if trim else "") + (f"_res{RES:g}" if RES != 0.1 else "")
OUT = os.path.abspath("results")              # FDTD.Run chdirs into the sim folder
F0, FC, FT = 2.5e9, 1.0e9, 2.44e9            # excitation centre, half-bandwidth, loss-tangent reference
g = json.load(open("geom.json"))
K = lambda p: (p[0] - 100.0, p[1] - 100.0)   # KiCad -> model

FDTD = openEMS(NrTS=400000, EndCriteria=1e-4)
FDTD.SetGaussExcite(F0, FC)
FDTD.SetBoundaryCond(["PML_8"] * 6)
CSX = ContinuousStructure(); FDTD.SetCSX(CSX)
mesh = CSX.GetGrid(); mesh.SetDeltaUnit(1e-3)
kap = lambda er, tand: 2 * np.pi * FT * EPS0 * er * tand

# ---------------- PCB
X_KO = min(p[0] for p in g["keepout"][0]) - 100   # keep-out start (all GND stops here)
X_FULL = X_KO - 1.65                          # left of this the F.Cu pour is merged into the GND block
outline = np.array([K(p) for p in g["outline"][0]]).T
x0b, x1b, yb = outline[0].min(), outline[0].max(), outline[1].max()
pp = CSX.AddMaterial("prepreg", epsilon=4.1, kappa=kap(4.1, 0.02))
core = CSX.AddMaterial("core", epsilon=4.6, kappa=kap(4.6, 0.02))
pp.AddLinPoly(outline, "z", 0.0, 0.1, priority=5)
core.AddLinPoly(outline, "z", 0.1, 0.6, priority=5)
pp.AddLinPoly(outline, "z", 0.7, 0.1, priority=5)
gnd = CSX.AddMetal("gnd")
gnd.AddBox([x0b, -yb, 0.0], [X_FULL, yb, 0.8], priority=10)    # (square -X corners: far from the antenna)
gnd.AddBox([X_FULL, -yb, 0.0], [X_KO, yb, 0.7], priority=10)   # In1/In2/B.Cu to the keep-out
for p in g["fills"]["F.Cu"]:
    if max(x for x, _ in p) - 100 > X_FULL:
        pts = np.array([K(q) for q in p]).T
        gnd.AddPolygon(pts, "z", 0.8, priority=10)
for v in g["vias"]:
    x, y = K(v["a"])
    if v["net"] == "GND" and x > X_FULL:
        gnd.AddBox([x - 0.1, y - 0.1, 0.7], [x + 0.1, y + 0.1, 0.8], priority=10)
ant = CSX.AddMetal("antenna")
boxes = []
for p in g["ant"] + g["pads"]["1"] + g["pads"]["2"]:
    q = np.array([K(r) for r in p]); boxes.append([q[:, 0].min(), q[:, 1].min(), q[:, 0].max(), q[:, 1].max()])
if trim:  # cut the meander back from its open end, following the copper path (template relative to the antenna bbox)
    X1, Y0 = max(b[2] for b in boxes), min(b[1] for b in boxes)
    path = [((X1 - 4.44, X1 - 0.5, Y0, Y0 + 0.5), 0, 0),          # open-end arm, free end at -x
            ((X1 - 0.5, X1, Y0, Y0 + 2.7), 1, 0),                 # top bar piece, path runs +y
            ((X1 - 3.14, X1 - 0.5, Y0 + 2.2, Y0 + 2.7), 0, 1),    # arm, path runs -x
            ((X1 - 3.14, X1 - 2.64, Y0 + 2.7, Y0 + 4.7), 1, 0),   # inner bend, +y
            ((X1 - 3.14, X1 - 0.5, Y0 + 4.7, Y0 + 5.2), 0, 0),    # arm, +x
            ((X1 - 0.5, X1, Y0 + 4.7, Y0 + 7.4), 1, 0)]           # top bar piece, +y
    left = trim
    for (x0, x1, y0, y1), ax, side in path:
        c = ((x0 + x1) / 2, (y0 + y1) / 2)
        b = min(boxes, key=lambda b: np.hypot((b[0] + b[2]) / 2 - c[0], (b[1] + b[3]) / 2 - c[1]))
        assert np.hypot((b[0] + b[2]) / 2 - c[0], (b[1] + b[3]) / 2 - c[1]) < 0.3, "meander template mismatch"
        lo, hi = (0, 2) if ax == 0 else (1, 3)
        n = b[hi] - b[lo]
        if left >= n:
            boxes.remove(b); left -= n
        else:
            if side == 0: b[lo] += left
            else: b[hi] -= left
            left = 0
        if left <= 0: break
for b in boxes:
    ant.AddBox([b[0], b[1], 0.8], [b[2], b[3], 0.8], priority=10)
pad1 = [K(q) for q in g["pads"]["1"][0]]
px0, px1 = min(p[0] for p in pad1), max(p[0] for p in pad1)
py0, py1 = min(p[1] for p in pad1), max(p[1] for p in pad1)
port = FDTD.AddLumpedPort(1, 50, [px0, py0, 0.7], [px1, py1, 0.8], "z", excite=1.0, priority=20)

# ---------------- environment (spec.py, z re-referenced to the PCB bottom)
zr = lambda z_abs: z_abs - S.Z_PCB0
env = case in ("env", "wrist")
if env:
    petg = CSX.AddMaterial("petg", epsilon=2.6, kappa=kap(2.6, 0.02))
    air = CSX.AddMaterial("air", epsilon=1.0)
    glass = CSX.AddMaterial("glass", epsilon=6.0, kappa=kap(6.0, 0.005))
    OL, OW, HL, HW = S.CASE_L / 2, S.CASE_W / 2, S.CAV_L / 2, S.CAV_W / 2
    zf, zt = zr(0.0), zr(S.CASE_T)
    petg.AddBox([-OL, -OW, zf], [OL, OW, zt], priority=1)                       # shell
    air.AddBox([-HL, -HW, zr(S.FLOOR)], [HL, HW, zr(S.Z_DISP1)], priority=2)    # cavity
    aa_x1 = S.DISP_X1 - S.DISP_AA_MARGIN_FAR; m = S.DISP_AA_MARGIN_FAR - S.LIP_OVERLAP
    air.AddBox([aa_x1 - S.DISP_AA_L - m, -S.DISP_AA_W / 2 - m, zr(S.Z_DISP1)],  # bezel window
               [aa_x1 + m, S.DISP_AA_W / 2 + m, zt], priority=2)
    petg.AddBox([S.DISP_X1 - S.LEDGE, -HW, 0.9], [HL, HW, zr(S.Z_DISP1)], priority=3)  # +X ledge
    petg.AddBox([S.BAT_X1 + 0.25, -HW, zr(S.FLOOR)], [HL, HW, -0.1], priority=3)      # back block (gaps 0.05 -> 0.1)
    petg.AddBox([-HL, -HW, zr(S.FLOOR)], [S.BAT_X0 - 0.25, HW, -0.1], priority=3)
    glass.AddBox([S.DISP_X0, -S.DISP_W / 2, zr(S.Z_DISP0)], [S.DISP_X1, S.DISP_W / 2, zr(S.Z_DISP1)], priority=4)
    bat = CSX.AddMetal("battery")
    bat.AddBox([S.BAT_X0, -S.BAT_W / 2, zr(S.Z_BAT0)], [S.BAT_X1, S.BAT_W / 2, -0.1], priority=6)  # 0.05 gap -> 0.1
    if case == "wrist":   # crude flat skin-equivalent slab (2.45 GHz dry skin: er 38, sigma 1.46 S/m) under the floor
        skin = CSX.AddMaterial("skin", epsilon=38.0, kappa=1.46)
        skin.AddBox([-30, -25, zf - 12.0], [30, 25, zf], priority=1)

# ---------------- mesh
def lines(fine_edges, fine_res, mid_edges, mid_res, outer, out_res):
    a = SmoothMeshLines(np.unique(np.round(fine_edges, 3)), fine_res, 1.4)
    for e in sorted(mid_edges):   # drop edges that would make sub-0.09 mm cells (the geometry snaps instead)
        if np.min(abs(a - e)) > 0.09: a = np.r_[a, e]
    a = SmoothMeshLines(np.unique(a), mid_res, 1.4)
    return SmoothMeshLines(np.unique(np.r_[a, outer]), out_res, 1.4)

bx = np.array(boxes)
air_m = 32.0
ext_x = (S.CASE_L / 2 if env else x1b) + air_m
ext_y = (S.CASE_W / 2 if env else yb) + air_m
# uniform RES (0.1 mm) grid (min cell sets the timestep) aligned to the port pad and keep-out edges; other edges snap +-0.05
fx = px0 + RES * np.arange(np.floor((X_FULL - 0.05 - px0) / RES), np.ceil((bx[:, 2].max() + 0.2 - px0) / RES) + 1)
fy = py0 + RES * np.arange(np.floor((bx[:, 1].min() - 0.45 - py0) / RES), np.ceil((bx[:, 3].max() + 0.45 - py0) / RES) + 1)
midx = [x0b, x1b] + ([-S.CASE_L / 2, S.CASE_L / 2, -S.CAV_L / 2, S.CAV_L / 2, S.BAT_X0, S.BAT_X1,
                                 S.BAT_X1 + 0.25, S.DISP_X0, S.DISP_X1 - S.LEDGE] if env else [])
midy = [-yb, yb] + ([-S.CASE_W / 2, S.CASE_W / 2, -S.CAV_W / 2, S.CAV_W / 2, -S.DISP_W / 2, S.DISP_W / 2,
                         -S.BAT_W / 2, S.BAT_W / 2] if env else [])
mesh.AddLine("x", lines(fx, RES, midx, 0.6, [-ext_x, ext_x], 4.0))
mesh.AddLine("y", lines(fy, RES, midy, 0.6, [-ext_y, ext_y], 4.0))
zl = [0.0, 0.1, 0.4, 0.7, 0.8]
if env:
    zl += [zr(0.0), zr(S.FLOOR), zr(S.Z_BAT0), -0.1, 0.9, zr(S.Z_DISP0), zr(S.Z_DISP1), zr(S.CASE_T)]
zb = (zr(0.0) - (12 if case == "wrist" else 0)) if env else 0.0
zt_ = zr(S.CASE_T) if env else 0.8
mesh.AddLine("z", lines(np.array([0, 0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8]), 0.1, zl, 0.5,
                        [zb - air_m, zt_ + air_m], 4.0))
nf2ff = FDTD.CreateNF2FFBox()

sim = f"/tmp/horae_{tag}"
print(tag, "cells:", [len(mesh.GetLines(d)) for d in "xyz"], np.prod([len(mesh.GetLines(d)) for d in "xyz"]) / 1e6, "M")
if "--dry" in sys.argv:
    CSX.Write2XML(f"model_{tag}.xml"); sys.exit()
FDTD.Run(sim, cleanup=True, numThreads=os.cpu_count())

f = np.linspace(1.6e9, 3.2e9, 641)
port.CalcPort(sim, f)
s11 = port.uf_ref / port.uf_inc
zin = port.uf_tot / port.if_tot
res = nf2ff.CalcNF2FF(sim, FT, np.array([90.0]), np.array([0.0]))
port.CalcPort(sim, np.array([FT]))
eff = float(res.Prad[0] / np.real(port.P_acc[0]))
os.makedirs(OUT, exist_ok=True)
np.savez(f"{OUT}/{tag}.npz", f=f, s11=s11, zin=zin, rad_eff_2g44=eff)
print(tag, "rad. efficiency @2.44 GHz:", round(eff, 3), "fmin:", f[np.argmin(abs(s11))] / 1e9)
