"""openEMS FDTD model of the Horae rev A antenna end. Geometry from geom.json (rf/extract.py), case from spec.py + cad/horae.py.

Run (inside the horae-openems image, repo at /work):
  docker run --rm -v "$PWD/../..":/work -w /work/hardware/rf horae-openems python sim.py bare|env|wrist \
      [--trim MM] [--res MM] [--bar-dx MM | --no-bar] [--geom FILE] [--air MM] [--threads N] [--dry]   (or ./run_all.sh)

Model frame: x = KiCad x - 100 (+X = antenna end), y = KiCad y - 100, z = 0 at the PCB bottom (B.Cu), F.Cu at spec.PCB_T.
Stack (JLC 0.6 mm 4-layer, 3313): B.Cu 0 | prepreg 0.1 | In2 | core | In1 | prepreg 0.1 | F.Cu, zero-thickness copper.
Ground: one PEC block (full thickness) left of X_FULL; right of it, every GND fill polygon of every layer at its own z,
F.Cu GND tracks + C11/C12 GND pads, GND vias as through-board posts (In1 is the only plane that reaches the keep-out on
the board as built; --geom geom_pour.json = F/In2/B pours to the keep-out too). Antenna: meander.py trim of the
untrimmed SWRA117D, placed like AE1 (self-checked against the board copper at the lib trim).
Case (spec.py; cad/horae.py constants copied below): PETG shell with plan corner radii and the pebble edge rounds,
cavity, glass ledges / antenna-end block / upper walls, back blocks, glass slab, battery = floating PEC box, steel
spring bars (PEC) in the lugs with a silicone strap end looped round each. Not modelled: motor, mic duct, touch
windows, gaskets (= PETG), solder mask, non-GND copper; part/PCB gaps of 0.05 become 0.1 (mesh).
--trim MM: cut from the untrimmed open end (6.64 = the rev A lib footprint). --bar-dx: +X bar axis past the case end.
Mesh: 0.1 mm at the antenna (0.07 gives the same), AIR (32 mm) of air around everything before the 8 PML cells. The
2026-10-03 mesh had the PML ~4 mm off the case: fine for env (--air 4: same Z and efficiency, 30 % faster), but its
NF2FF box (x +-19.6) cut through the wrist slab, which ran into the PML: v1's on-wrist efficiency was too high.
Results: results/{case}_v2_trim{T}[_res][_bar][_nobar][_pour][_air].npz (v2 = the 0.6 mm board; no v2 = 0.8 mm board).
"""
import json, math, os, sys
import numpy as np
from CSXCAD import ContinuousStructure
from CSXCAD.SmoothMeshLines import SmoothMeshLines
from openEMS import openEMS
from openEMS.physical_constants import EPS0

sys.path.insert(0, "../.."); sys.path.insert(0, ".")
import spec as S
import meander

arg = lambda k, d: type(d)(sys.argv[sys.argv.index(k) + 1]) if k in sys.argv else d
case = sys.argv[1] if len(sys.argv) > 1 else "bare"
trim = arg("--trim", meander.LIB_TRIM)
RES = arg("--res", 0.1)                     # fine x/y cell (mm)
GEOM = arg("--geom", "geom.json")
AIR = arg("--air", 32.0)                    # air between every structure and the PML (~lambda/4 at 2.4 GHz)
# cad/horae.py (2026-10-04): BAR_D 1.5, STRAP_W 16, STRAP_R 1.85, BAR_DX = STRAP_R + 0.3, EAR_R 1.6, Z_BAR = FLOOR + BACK_GASKET + EAR_R
BAR_D, STRAP_W, STRAP_R, EAR_R, BACK_GASKET = 1.5, 16.0, 1.85, 1.6, 0.3
BAR_DX = arg("--bar-dx", STRAP_R + 0.3)
BAR = "--no-bar" not in sys.argv
tag = (f"{case}_v2_trim{trim:g}" + (f"_res{RES:g}" if RES != 0.1 else "") + (f"_bar{BAR_DX:g}" if "--bar-dx" in sys.argv else "")
       + ("" if BAR else "_nobar") + (f"_{os.path.basename(GEOM)[5:-5]}" if GEOM != "geom.json" else "") + (f"_air{AIR:g}" if AIR != 32 else ""))
OUT = os.path.abspath("results")              # FDTD.Run chdirs into the sim folder
F0, FC, FT = 2.5e9, 1.0e9, 2.44e9            # excitation centre, half-bandwidth, loss-tangent reference
FE = np.array([2.40e9, 2.44e9, 2.48e9])       # radiation efficiency at these
g = json.load(open(GEOM))
K = lambda p: (p[0] - 100.0, p[1] - 100.0)   # KiCad -> model

FDTD = openEMS(NrTS=600000, EndCriteria=1e-4)
FDTD.SetGaussExcite(F0, FC)
FDTD.SetBoundaryCond(["PML_8"] * 6)
CSX = ContinuousStructure(); FDTD.SetCSX(CSX)
mesh = CSX.GetGrid(); mesh.SetDeltaUnit(1e-3)
kap = lambda er, tand: 2 * np.pi * FT * EPS0 * er * tand

# ---------------- PCB
T = S.PCB_T
ZL = {"F.Cu": T, "In1.Cu": T - 0.1, "In2.Cu": 0.1, "B.Cu": 0.0}
X_KO = min(p[0] for p in g["keepout"][0]) - 100   # keep-out start (all GND stops here)
X_FULL = X_KO - 3.0                           # left of this the board is one PEC block
outline = np.array([K(p) for p in g["outline"][0]]).T
x0b, x1b, yb = outline[0].min(), outline[0].max(), outline[1].max()
pp = CSX.AddMaterial("prepreg", epsilon=4.1, kappa=kap(4.1, 0.02))
core = CSX.AddMaterial("core", epsilon=4.6, kappa=kap(4.6, 0.02))
pp.AddLinPoly(outline, "z", 0.0, 0.1, priority=5)
core.AddLinPoly(outline, "z", 0.1, T - 0.2, priority=5)
pp.AddLinPoly(outline, "z", T - 0.1, 0.1, priority=5)

# antenna: meander.trim() in footprint coords -> board via the AE1 placement (KiCad: y down, angle CCW)
ref, ax_, ay_, rot, pads = next(f for f in g["fps"] if f[0] == "AE1")
c, s = round(math.cos(math.radians(rot))), round(math.sin(math.radians(rot)))
fp2b = lambda x, y: (ax_ + x * c + y * s - 100, ay_ - x * s + y * c - 100)
def place(r):
    (xa, ya), (xb_, yb_) = fp2b(r[0], r[2]), fp2b(r[1], r[3])
    return [min(xa, xb_), min(ya, yb_), max(xa, xb_), max(ya, yb_)]
bbox = lambda ps: [min(p[0] for p in ps) - 100, min(p[1] for p in ps) - 100, max(p[0] for p in ps) - 100, max(p[1] for p in ps) - 100]
board_cu = sorted(np.round(bbox(p), 3).tolist() for p in g["ant"] + g["pads"]["1"] + g["pads"]["2"])
pad_rects = [place((x - w / 2, x + w / 2, y - h / 2, y + h / 2)) for x, y, w, h in ((14.47, 0.25, 0.5, 0.5), (16.57, 0.25, 0.9, 0.5))]
assert sorted(np.round(r, 3).tolist() for r in [place(r) for r in meander.trim(meander.LIB_TRIM)] + pad_rects) == board_cu, \
    "AE1 on the board is not meander.trim(LIB_TRIM): re-extract or update meander.py"
boxes = [place(r) for r in meander.trim(trim)] + pad_rects
ant = CSX.AddMetal("antenna")
for b in boxes:
    ant.AddBox([b[0], b[1], T], [b[2], b[3], T], priority=10)
px0, py0, px1, py1 = pad_rects[0]
port = FDTD.AddLumpedPort(1, 50, [px0, py0, T - 0.1], [px1, py1, T], "z", excite=1.0, priority=20)

bx = np.array(boxes + board_cu)              # fine mesh spans the board copper too: same grid for every trim
FY0, FY1 = bx[:, 1].min() - 0.45, bx[:, 3].max() + 0.45   # fine-mesh y span; modelled GND detail stays inside it
near = lambda x, y: x > X_FULL and FY0 < y < FY1
gnd = CSX.AddMetal("gnd")
gnd.AddBox([x0b, -yb, 0.0], [X_FULL, yb, T], priority=10)    # (square -X corners: far from the antenna)
for L, ps in g["fills"].items():
    for p in ps:
        if max(x for x, _ in p) - 100 > X_FULL:
            gnd.AddPolygon(np.array([K(q) for q in p]).T, "z", ZL[L], priority=10)
for t in g["tracks"]:
    (xa, ya), (xb_, yb_) = K(t["a"]), K(t["b"])
    if t["net"] != "GND" or not (near(xa, ya) or near(xb_, yb_)) or (xa, ya) == (xb_, yb_): continue
    d = np.array([xb_ - xa, yb_ - ya]); d /= np.linalg.norm(d); n = np.array([-d[1], d[0]]) * t["w"] / 2; e = d * t["w"] / 2
    q = np.array([[xa, ya] - e - n, [xb_, yb_] + e - n, [xb_, yb_] + e + n, [xa, ya] - e + n]).T
    gnd.AddPolygon(q, "z", ZL[t["layer"]], priority=10)
for f in g["fps"]:
    for num, net, x, y, w, h in f[4]:
        if net == "GND" and f[0] in ("C11", "C12"):
            x, y = K((x, y)); w, h = (h, w) if round(f[3]) % 180 else (w, h)
            gnd.AddBox([x - w / 2, y - h / 2, T], [x + w / 2, y + h / 2, T], priority=10)
for v in g["vias"]:
    x, y = K(v["a"])
    if v["net"] == "GND" and near(x, y):
        gnd.AddBox([x - 0.1, y - 0.1, 0.0], [x + 0.1, y + 0.1, T], priority=10)   # barrel (0.2 drill)
        gnd.AddBox([x - 0.2, y - 0.2, T], [x + 0.2, y + 0.2, T], priority=10)     # F.Cu ring

# ---------------- environment (spec.py, z re-referenced to the PCB bottom)
zr = lambda z_abs: z_abs - S.Z_PCB0
env = case in ("env", "wrist")
OL, OW, HL, HW = S.CASE_L / 2, S.CASE_W / 2, S.CAV_L / 2, S.CAV_W / 2
X_BAR, Z_BAR = OL + BAR_DX, zr(S.FLOOR + BACK_GASKET + EAR_R)
Z_FRAME0, Z_ROUND, Y_TOP = zr(S.FLOOR + BACK_GASKET), zr(S.CASE_T - 2.5), S.DISP_W / 2 + 0.15
TOP_R, BOT_R = (1.6, 2.5), 1.2                # pebble: elliptical top round (across, down), bottom fillet
def rrect(l, w, r, n=8):                      # plan-view rounded rectangle
    pts = []
    for cx, cy, a0 in ((l / 2 - r, w / 2 - r, 0), (-l / 2 + r, w / 2 - r, 90), (-l / 2 + r, -w / 2 + r, 180), (l / 2 - r, -w / 2 + r, 270)):
        pts += [(cx + r * np.cos(np.radians(a0 + 90 * k / n)), cy + r * np.sin(np.radians(a0 + 90 * k / n))) for k in range(n + 1)]
    return np.array(pts).T
def spandrel(a, b, top):                      # between a corner (at the origin) and its elliptical round (a across, b in z)
    ph = np.linspace(0, np.pi / 2, 9)
    return np.r_[-a + a * np.cos(ph), 0], np.r_[(b * np.sin(ph) - b) if top else (b - b * np.sin(ph)), 0]
if env:
    petg = CSX.AddMaterial("petg", epsilon=2.6, kappa=kap(2.6, 0.02))
    air = CSX.AddMaterial("air", epsilon=1.0)
    glass = CSX.AddMaterial("glass", epsilon=6.0, kappa=kap(6.0, 0.005))
    zf, zt = zr(0.0), zr(S.CASE_T)
    petg.AddLinPoly(rrect(S.CASE_L, S.CASE_W, S.CORNER_R), "z", zf, zt - zf, priority=1)          # shell
    air.AddLinPoly(rrect(S.CAV_L, S.CAV_W, S.PCB_CORNER_R + 0.1), "z", zr(S.FLOOR), zr(S.Z_DISP1) - zr(S.FLOOR), priority=2)
    aa_x1 = S.DISP_X1 - S.DISP_AA_MARGIN_FAR; m = S.DISP_AA_MARGIN_FAR - S.LIP_OVERLAP
    air.AddBox([aa_x1 - S.DISP_AA_L - m, -S.DISP_AA_W / 2 - m, zr(S.Z_DISP1)],  # bezel window
               [aa_x1 + m, S.DISP_AA_W / 2 + m, zt], priority=2)
    zp = T + 0.1                                                                # case parts resting on the PCB top
    petg.AddBox([S.DISP_X1 + 0.15, -HW, zp], [HL, HW, zr(S.Z_DISP1)], priority=3)    # antenna-end block, full width
    for sx in (-1, 1):
        for sy in (-1, 1):
            xa, xb_ = (S.DISP_X1 - S.LEDGE, HL) if sx > 0 else (-HL, S.DISP_X0 + S.LEDGE)
            petg.AddBox([xa, sy * S.LEDGE_Y, zp], [xb_, sy * HW, zr(S.Z_DISP1)], priority=3)  # glass-end ledges
        petg.AddBox([-HL, sx * Y_TOP, zr(S.Z_DISP0 - 0.1)], [HL, sx * HW, zr(S.Z_DISP1)], priority=3)  # upper walls
    petg.AddBox([S.BAT_X1 + 0.25, -HW, zr(S.FLOOR)], [HL, HW, -0.1], priority=3)      # back blocks (gap 0.05 -> 0.1)
    petg.AddBox([-HL, -HW, zr(S.FLOOR)], [S.BAT_X0 - 0.25, HW, -0.1], priority=3)
    glass.AddBox([S.DISP_X0, -S.DISP_W / 2, zr(S.Z_DISP0)], [S.DISP_X1, S.DISP_W / 2, zr(S.Z_DISP1)], priority=4)
    bat = CSX.AddMetal("battery")
    bat.AddBox([S.BAT_X0, -S.BAT_W / 2, zr(S.Z_BAT0)], [S.BAT_X1, S.BAT_W / 2, zr(S.Z_BAT0 + S.BAT_T)], priority=6)
    for top, (a, b) in ((True, TOP_R), (False, (BOT_R, BOT_R))):               # edge rounds, cut from every PETG part
        u, v = spandrel(a, b, top); zc = zt if top else zf
        for sx in (-1, 1):
            air.AddLinPoly(np.array([zc + v, sx * (OL + u)]), "y", -OW, 2 * OW, priority=5)
            air.AddLinPoly(np.array([sx * (OW + u), zc + v]), "x", -OL, 2 * OL, priority=5)
    if BAR:
        steel, sil = CSX.AddMetal("spring_bar"), CSX.AddMaterial("strap", epsilon=3.0, kappa=kap(3.0, 0.02))
        c0 = np.array([X_BAR, Z_BAR]); p0 = np.array([OL, Z_ROUND]); dd = p0 - c0
        th = math.atan2(dd[1], dd[0]) - math.acos(EAR_R / np.hypot(*dd)); tp = c0 + EAR_R * np.array([math.cos(th), math.sin(th)])
        for sx in (-1, 1):
            xb = sx * X_BAR
            steel.AddCylinder([xb, -STRAP_W / 2 + 0.05, Z_BAR], [xb, STRAP_W / 2 - 0.05, Z_BAR], BAR_D / 2, priority=7)
            steel.AddCylinder([xb, -OW + 0.05, Z_BAR], [xb, OW - 0.05, Z_BAR], 0.4, priority=7)        # tips in the ears
            w = STRAP_W / 2 - 0.1
            sil.AddCylinder([xb, -w, Z_BAR], [xb, w, Z_BAR], STRAP_R, priority=3)                      # strap loop
            sil.AddBox([xb, -w, Z_BAR + 0.05], [sx * (X_BAR + 12), w, Z_BAR + STRAP_R], priority=3)    # 12 mm of strap
            ear = np.array([[Z_FRAME0, Z_FRAME0, Z_BAR, tp[1], Z_ROUND, Z_ROUND],
                            sx * np.array([OL - S.CORNER_R - 0.5, X_BAR, X_BAR, tp[0], OL, OL - S.CORNER_R - 0.5])])
            for sy in (-1, 1):
                petg.AddLinPoly(ear, "y", min(sy * OW, sy * STRAP_W / 2), OW - STRAP_W / 2, priority=3)   # lugs
                petg.AddCylinder([xb, sy * STRAP_W / 2, Z_BAR], [xb, sy * OW, Z_BAR], EAR_R, priority=3)
    if case == "wrist":   # crude flat skin-equivalent slab (2.45 GHz dry skin: er 38, sigma 1.46 S/m) under the floor
        skin = CSX.AddMaterial("skin", epsilon=38.0, kappa=1.46)
        skin.AddBox([-30, -25, zf - 12.0], [30, 25, zf], priority=1)

# ---------------- mesh: 0.1 (RES) at the antenna, 0.6 (z 0.5) over the case, 2 over strap/skin, 4 in the air
def lines(tiers):
    a = np.unique(np.round(tiers[0][0], 4))
    for edges, res in tiers:
        for e in sorted(edges):   # drop edges that would make sub-0.09 mm cells (the geometry snaps instead)
            if np.min(abs(a - e)) > 0.09: a = np.r_[a, e]
        a = SmoothMeshLines(np.unique(np.round(a, 4)), res, 1.4)
    return a

# uniform RES grid (min cell sets the timestep) aligned to the port pad; other edges snap +-RES/2
fx = px0 + RES * np.arange(np.floor((X_FULL - 0.05 - px0) / RES), np.ceil((bx[:, 2].max() + 0.2 - px0) / RES) + 1)
fy = py0 + RES * np.arange(np.floor((FY0 - py0) / RES), np.ceil((FY1 - py0) / RES) + 1)
fz = np.arange(0, T + 0.01, 0.1)
midx, midy, midz = [x0b, x1b], [-yb, yb], []
far = [[], [], []]
if env:
    for sx in (-1, 1):
        midx += [sx * v for v in (OL, HL, OL - TOP_R[0], OL - BOT_R, S.DISP_X1 + 0.15, S.DISP_X1 - S.LEDGE)]
        midy += [sx * v for v in (OW, HW, OW - TOP_R[0], OW - BOT_R, S.DISP_W / 2, Y_TOP, S.LEDGE_Y, S.BAT_W / 2)]
    midx += [S.BAT_X0, S.BAT_X1, S.BAT_X1 + 0.25, S.BAT_X0 - 0.25, S.DISP_X0, S.DISP_X1]
    midz += [zr(0.0), zr(S.FLOOR), zr(S.Z_BAT0 + S.BAT_T), -0.1, T + 0.1, zr(S.Z_DISP0), zr(S.Z_DISP1), zr(S.CASE_T),
             zr(S.Z_DISP0 - 0.1), Z_ROUND, zr(BOT_R)]
    if BAR:
        for sx in (-1, 1):
            midx += [sx * (X_BAR + d) for d in (-STRAP_R, -0.75, -0.375, 0, 0.375, 0.75, STRAP_R)]
            far[0] += [sx * (X_BAR + 12)]
        midy += [sx * v for sx in (-1, 1) for v in (STRAP_W / 2 - 0.1, OW - 0.05)]
        midz += [Z_BAR + d for d in (-STRAP_R, -0.75, -0.375, 0, 0.375, 0.75, STRAP_R)] + [Z_FRAME0]
    if case == "wrist":
        far[0] += [-30, 30]; far[1] += [-25, 25]; far[2] += [zr(0.0) - 12]
ax = [lines([(fx, RES), (midx, 0.6), (far[0], 2.0)]), lines([(fy, RES), (midy, 0.6), (far[1], 2.0)]),
      lines([(fz, 0.1), (midz, 0.5), (far[2], 2.0)])]
for d, a in zip("xyz", ax):   # AIR of air past every structure, then 8 PML cells of 4 mm
    mesh.AddLine(d, SmoothMeshLines(np.unique(np.r_[a, a[0] - AIR - 32, a[-1] + AIR + 32]), 4.0, 1.4))
nf2ff = FDTD.CreateNF2FFBox()

sim = f"/tmp/horae_{tag}"
nl = [len(mesh.GetLines(d)) for d in "xyz"]
print(tag, "cells:", nl, np.prod(nl) / 1e6, "M; nf2ff box", [np.round(mesh.GetLines(d)[[11, -12]], 1).tolist() for d in "xyz"])
if "--dry" in sys.argv:
    CSX.Write2XML(f"/tmp/model_{tag}.xml"); sys.exit()
FDTD.Run(sim, cleanup=True, numThreads=arg("--threads", os.cpu_count()))

f = np.linspace(1.6e9, 3.2e9, 641)
port.CalcPort(sim, f)
s11 = port.uf_ref / port.uf_inc
zin = port.uf_tot / port.if_tot
res = nf2ff.CalcNF2FF(sim, FE, np.array([90.0]), np.array([0.0]))
port.CalcPort(sim, FE)
eff = np.real(res.Prad) / np.real(port.P_acc)
os.makedirs(OUT, exist_ok=True)
np.savez(f"{OUT}/{tag}.npz", f=f, s11=s11, zin=zin, rad_eff_2g44=float(eff[1]), rad_eff=eff, f_eff=FE)
print(tag, "rad. efficiency @2.40/2.44/2.48 GHz:", np.round(eff, 3), "fmin:", f[np.argmin(abs(s11))] / 1e9)
