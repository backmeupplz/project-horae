"""openEMS FDTD model of the Horae rev A antenna end. Board from geom.json (rf/extract.py), case from cad/horae.py.

Run (inside the horae-openems image, repo at /work):
  docker run --rm -v "$PWD/../..":/work -w /work/hardware/rf horae-openems python sim.py bare|env|wrist \
      [--trim MM] [--res MM] [--geom FILE] [--air MM] [--threads N] [--dry]   (or ./run_all.sh)
env/wrist read the case meshes in case/ (case_stl.py: run it on the host after any change to cad/horae.py or spec.py).

Model frame: x = KiCad x - 100 (+X = antenna end), y = KiCad y - 100, z = 0 at the PCB bottom (B.Cu), F.Cu at spec.PCB_T.
Stack (JLC 0.6 mm 4-layer, 3313): B.Cu 0 | prepreg 0.1 | In2 | core | In1 | prepreg 0.1 | F.Cu, zero-thickness copper.
Ground: one PEC block (full thickness) left of X_FULL; right of it, every GND fill polygon of every layer at its own z,
F.Cu GND tracks + C11/C12 GND pads, GND vias as through-board posts. Antenna: meander.py trim of the untrimmed SWRA117D,
placed like AE1 (self-checked against the board copper at the lib trim).
Case = the CAD's own solids (case_stl.py): PETG top shell (walls, lip, inner blocks, ears) + bottom shell, TPU 90A seal
ring / bezel gasket / cushions / small seals, strap stubs (er 3), steel spring bars + battery + magnets + motor (PEC);
display = er 6 glass slab. The shells' 0.05 mm gaps over and under the PCB are kept 0.1 of air (mesh). Not modelled:
solder mask, non-GND copper, FPC, components. wrist: flat dry-skin slab under the case.
--trim MM: cut from the untrimmed open end (6.64 = the rev A lib footprint).
Mesh: 0.1 mm at the antenna (0.07 gives the same), AIR (32 mm) of air around everything before the 8 PML cells.
Results: results/{case}_{V}_trim{T}[_res][_pour][_air].npz, with the feed as built (pour, trace width, line lengths for
match.py). V: v4 = final board (33.6 x 16.0, 0.15/0.15 GCPW feed) + case with crush ribs, 2026-10-06; v3 = CAD case of
2026-10-05; v2 = the analytic case of 2026-10-04; no V = the 0.8 mm board of 2026-10-03.
"""
import heapq, json, math, os, sys
import numpy as np
from CSXCAD import ContinuousStructure
from CSXCAD.SmoothMeshLines import SmoothMeshLines
from openEMS import openEMS
from openEMS.physical_constants import EPS0

sys.path.insert(0, "../.."); sys.path.insert(0, ".")
import spec as S
import meander

V = "v4"
arg = lambda k, d: type(d)(sys.argv[sys.argv.index(k) + 1]) if k in sys.argv else d
case = sys.argv[1] if len(sys.argv) > 1 else "bare"
trim = arg("--trim", meander.LIB_TRIM)
RES = arg("--res", 0.1)                     # fine x/y cell (mm)
GEOM = arg("--geom", "geom.json")
AIR = arg("--air", 32.0)                    # air between every structure and the PML (~lambda/4 at 2.4 GHz)
tag = (f"{case}_{V}_trim{trim:g}" + (f"_res{RES:g}" if RES != 0.1 else "")
       + (f"_{os.path.basename(GEOM)[5:-5]}" if GEOM != "geom.json" else "") + (f"_air{AIR:g}" if AIR != 32 else ""))
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
        r = v["w"] / 2
        gnd.AddBox([x - 0.1, y - 0.1, 0.0], [x + 0.1, y + 0.1, T], priority=10)   # barrel (0.2 drill)
        gnd.AddBox([x - r, y - r, T], [x + r, y + r, T], priority=10)             # F.Cu ring

# ---------------- feed as built, for match.py (the FDTD port is at pad 1; the line and the parts are its circuit model)
POUR = any(max(x for x, _ in p) - 100 > X_FULL for p in g["fills"].get("F.Cu", []))   # F.Cu GND along the feed: GCPW
def feed(g):
    """Trace width and the line lengths chip-C11, C11-L3, L3-C12, C12-pad 1 edge (mm), along the RF tracks."""
    key = lambda p: (round(p[0], 3), round(p[1], 3))
    pad = {(f[0], p[0]): (key(p[2:4]), p[4]) for f in g["fps"] for p in f[4] if p[0]}
    def path(net, a, b):   # Dijkstra over the net's track segments
        adj = {}
        for t in g["tracks"]:
            if t["net"] == net:
                u, v = key(t["a"]), key(t["b"])
                adj.setdefault(u, []).append((v, math.dist(u, v))); adj.setdefault(v, []).append((u, math.dist(u, v)))
        dist, todo = {a: 0.0}, [(0.0, a)]
        while todo:
            d, u = heapq.heappop(todo)
            if u == b: return d
            for v, w in adj.get(u, []):
                if d + w < dist.get(v, 1e9): dist[v] = d + w; heapq.heappush(todo, (d + w, v))
        raise SystemExit(f"no {net} track from {a} to {b}")
    ends = [k for t in g["tracks"] if t["net"] == "RF_CHIP" for k in (key(t["a"]), key(t["b"]))]
    chip = next(k for k in ends if ends.count(k) == 1 and k != pad["L3", "1"][0])     # the LNA_IN pin
    p = lambda r, n: pad[r, n][0]
    seg = [path("RF_CHIP", chip, p("C11", "1")), path("RF_CHIP", p("C11", "1"), p("L3", "1")),
           path("RF_ANT", p("L3", "2"), p("C12", "1")), path("RF_ANT", p("C12", "1"), p("AE1", "1")) - pad["AE1", "1"][1] / 2]
    return min(t["w"] for t in g["tracks"] if t["net"] in ("RF_CHIP", "RF_ANT")), np.round(seg, 3)
print("feed:", "GCPW" if POUR else "microstrip", *feed(g))

# ---------------- environment: the CAD case (case_stl.py), glass slab, wrist slab
env = case in ("env", "wrist")
zr = lambda z_abs: z_abs - S.Z_PCB0
OL, OW, HL, HW = S.CASE_L / 2, S.CASE_W / 2, S.CAV_L / 2, S.CAV_W / 2
if env:
    cad = json.load(open("case/case.json"))
    mat = {"petg": (CSX.AddMaterial("petg", epsilon=2.6, kappa=kap(2.6, 0.02)), 3),
           "tpu": (CSX.AddMaterial("tpu", epsilon=3.0, kappa=kap(3.0, 0.05)), 5),          # TPU 90A
           "strap": (CSX.AddMaterial("strap", epsilon=3.0, kappa=kap(3.0, 0.02)), 3),      # silicone / FKM
           "pec": (CSX.AddMetal("case_metal"), 7)}
    for name, m in cad["materials"].items():
        p = mat[m][0].AddPolyhedronReader(os.path.abspath(f"case/{name}.stl"), priority=mat[m][1])
        assert p.ReadFile(), f"case/{name}.stl: run case_stl.py"
    air = CSX.AddMaterial("air", epsilon=1.0)
    for z0, z1 in ((T + 0.001, T + 0.099), (-0.099, -0.001)):   # 0.05 shell-to-PCB gaps -> one 0.1 air cell (board only:
        air.AddLinPoly(outline, "z", z0, z1 - z0, priority=4)    # the crush ribs at its edge stay)
    glass = CSX.AddMaterial("glass", epsilon=6.0, kappa=kap(6.0, 0.005))
    glass.AddBox([S.DISP_X0, -S.DISP_W / 2, zr(S.Z_DISP0)], [S.DISP_X1, S.DISP_W / 2, zr(S.Z_DISP1)], priority=4)
    if case == "wrist":   # crude flat skin-equivalent slab (2.45 GHz dry skin: er 38, sigma 1.46 S/m) under the case
        skin = CSX.AddMaterial("skin", epsilon=38.0, kappa=1.46)
        skin.AddBox([-30, -25, zr(0.0) - 12.0], [30, 25, zr(0.0)], priority=1)

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
    xb, zb, sr = cad["X_BAR"], cad["Z_BAR"], cad["STRAP_R"]
    for sx in (-1, 1):
        midx += [sx * v for v in (OL, HL, HL - cad["SEAL_GAP"], OL - 1.6, OL - 0.6, S.DISP_X1 + 0.15, S.DISP_X1 - S.LEDGE,
                                  xb + cad["EAR_R"])]
        midx += [sx * (xb + d) for d in (-sr, -0.75, -0.375, 0, 0.375, 0.75, sr)]
        midy += [sx * v for v in (OW, HW, HW - cad["SEAL_GAP"], OW - 1.6, OW - 0.6, S.DISP_W / 2, S.DISP_W / 2 + 0.15,
                                  S.LEDGE_Y, S.BAT_W / 2, cad["STRAP_W"] / 2, cad["STRAP_W"] / 2 - 0.1, OW - 0.05)]
        far[0] += [sx * (xb + 14)]
    midx += [S.BAT_X0, S.BAT_X1, S.BAT_X1 + 0.25, S.BAT_X0 - 0.25, S.DISP_X0, S.DISP_X1]
    midz += [zr(0.0), zr(S.FLOOR), zr(S.Z_BAT0 + S.BAT_T), -0.1, T + 0.1, zr(S.Z_DISP0), zr(S.Z_DISP1), cad["Z_LIP0"],
             zr(S.CASE_T), cad["Z_STEP"], cad["Z_ROUND"], zr(1.2), zr(0.1), zr(2.1)] + [zb + d for d in (-sr, -0.75, -0.375, 0, 0.375, 0.75, sr)]
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
w_feed, seg = feed(g)
np.savez(f"{OUT}/{tag}.npz", f=f, s11=s11, zin=zin, rad_eff_2g44=float(eff[1]), rad_eff=eff, f_eff=FE, pour=POUR,
         feed_w=w_feed, feed_seg=seg)
print(tag, "rad. efficiency @2.40/2.44/2.48 GHz:", np.round(eff, 3), "fmin:", f[np.argmin(abs(s11))] / 1e9)
