#!/usr/bin/env python3
"""Project Horae rev A mechanics: two snap-together shells, captured soft parts, magnetic charging head, checks,
exports, renders.

    .venv/bin/python cad/horae.py              # everything (cad/out/*, media/2026-10-05/cad-*.png)
    .venv/bin/python cad/horae.py --no-render
    .venv/bin/python cad/horae.py --thin       # spec with the 2.5 mm cell -> cad/out/variant-thin/, no renders

All shared dimensions come from spec.py. One filament per print (A1 mini, no AMS), no glue anywhere:
  top_shell     PETG, printed lip-face-down: bezel lip + window, walls, glass pocket, PCB bearing blocks, mic duct,
                and the strap ears swept out of the side walls (drilled for 16 mm spring bars)
  bottom_shell  PETG, printed floor-down: floor plate + motor/pogo/magnet block + antenna-end support block, 4 snap
                bumps that click into recesses in the top shell's end walls
  TPU 90A       captured by the closed case: bottom_seal (radial ring between the shells), bezel_gasket, cushions
                (glass corners), pogo_seals, motor_pad, mic_seal; the mic vent membrane sits in the gasket layer
  variant-cf/   PETG-CF top shell with PETG antenna window + 4 touch windows (captured inserts), PETG bottom shell
  charger/      magnetic cable head: puck_top + puck_base (PETG) holding 4 spring pins + 2 magnets, TPU cable boot
If hardware/out/horae.step exists it replaces the placeholder PCB.
"""
import math
import sys
from pathlib import Path

import numpy as np
from build123d import (Align, AngularDirection, Axis, Box, Color, Compound, Cone, Cylinder, Edge, Face, Plane,
                       Polyline, Pos, Rectangle, RectangleRounded, Rot, Solid, Vertex, Wire, export_step, export_stl,
                       extrude, fillet, import_step, make_face, mirror)

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import spec as S  # noqa: E402

THIN = "--thin" in sys.argv
if THIN:                  # re-run spec.py with the 2.5 mm cell so every derived dimension follows
    import re
    import types
    S = types.ModuleType("spec")
    src, n = re.subn(r"^(BAT_W, BAT_T = [\d.]+, )[\d.]+", r"\g<1>2.5", (ROOT / "spec.py").read_text(), flags=re.M)
    assert n == 1, "spec.py BAT_T line not found"
    exec(compile(src, str(ROOT / "spec.py"), "exec"), S.__dict__)

OUT = ROOT / "cad" / "out" / ("variant-thin" if THIN else "")
MEDIA = ROOT / "media" / "2026-10-05"
BOARD_STEP = ROOT / "hardware" / "out" / "horae.step"

# --- cad-only dimensions (nothing here touches the PCB) ---
FIT = 0.1             # per-side clearance of the bottom shell's blocks in the top shell's bore
GLASS_FIT = 0.15      # per-side clearance around the display glass
POCKET_CHAMFER = 0.25 # glass pocket's vertical corners (a sharp glass corner still clears by 0.035); gasket layer R1
WIN_M = S.DISP_AA_MARGIN_FAR - S.LIP_OVERLAP   # window = active area + this (0.75) -> 1.0 overlap on 3 sides
WIN_CHAMFER = 0.15    # 45 deg chamfer on the window's top edge (first layers on the bed)
GASKET_REVEAL = 0.3   # the TPU bezel gasket shows this far inside the window: a coloured ring around the display
Z_LIP0 = S.Z_DISP1 + S.BEZEL_GASKET           # underside of the lip
POGO = [(x, -y, net) for x, y, net in S.POGO_PADS]   # physical (spec Y is KiCad, down): charger pins are wired by these
POGO_XY = [(x, y) for x, y, _ in POGO]
POGO_PAD_D = 1.0
# straps and ears
STRAP_W = 16.0        # two-piece quick-release strap on standard spring bars; lug gap = STRAP_W -> 1.0 mm ears
BAR_D = 1.5           # spring-bar body (quick-release 1.5 bars, 0.8 tips)
BAR_TIP_HOLE = 1.1    # drilled lugs: straight through the ears (tips bear on the full ear width; 1.78 bars fit too)
STRAP_R = 1.85        # strap end loop around the bar (3.7 mm thick end): clearance envelope
BAR_DX = STRAP_R + 0.3   # bar axis past the case end face: the loop swings 0.3 clear of the end face
EAR_R = 1.6           # ear boss radius around the bar: 1.05 mm of PETG around the tip hole
EAR_SLOPE = 45.0      # ear tops fall at this angle onto the boss's outer side: covers its crown, so nothing flatter
                      # than 45 deg faces the bed when the top shell prints lip-down
EAR_KNEE = 0.5        # the ear's top starts to fall this far inside the end face
EAR_INNER_R = 0.25    # round on the ears' inner top edge (in the loft sections; fades out onto the boss)
# the two shells
SEAL_GAP = 0.45       # radial gap between the bottom shell's floor plate and the top shell's bore = bottom_seal width
SEAL_SQUEEZE = 0.05   # per side: bottom_seal is printed SEAL_GAP + 2 x this wide (grips the plate, presses the bore)
SNAP_W, SNAP_DEPTH = 3.0, 0.2       # snap bump width (Y) and engagement into the end wall (X)
SNAP_Z = min(1.0, S.Z_PCB1 + S.GAP - 3.12)  # bump tip height: low on the end wall, where it is most flexible; the
                      # +X wall keeps >= 3.1 free above it (PETG-CF strain <= 2.5 % also with the thin cell)
SNAP_RAMP, SNAP_RET = 30.0, 55.0    # lead-in / retention face angles from the closing axis (deg)
SNAP_Y = {-1: 3.3, 1: 4.0}          # bump centres |y|: -X beside the motor pocket, +X on the support block
PRY_W, PRY_L, PRY_DEPTH = 3.0, 0.6, 0.25   # pry notch in the floor plate's bottom edge at each end (under the strap)
# captured soft parts (installed size in the model; printed thickness in PRINT_T)
CUSHION_T = S.Z_DISP0 - S.Z_PCB1    # TPU blocks under the glass corners, on the PCB's part-free ledge zones
POGO_GASKET = 0.45    # TPU rings under the PCB around each pogo pad (installed)
POGO_RING_D, POGO_SEAL_D = 1.9, 0.7   # ring OD (seat = OD + 0.1), hole around the pin plunger (0.48)
MOTOR_POCKET = S.MOTOR_D + 0.3
MOTOR_Z0 = S.FLOOR    # the motor sits on the floor; motor_pad holds it down from the PCB (no tape)
MOTOR_PAD_W = 1.0     # TPU strip on the motor can, between its two lead joints
BAT_PCM_L, BAT_PCM_EXTRA = 2.0, 0.5   # cell's PCM end (-X): up to 0.5 thicker than the cell
BAT_RECESS, BAT_RECESS_L = 0.25, 2.5  # floor recess under the PCM end: leaves FLOOR - 0.25 of floor
X_MZ1 = S.BAT_X0 - 0.25               # end of the motor-zone block
PRINT_T = {"bezel_gasket": 0.16, "cushions": CUSHION_T + 0.1, "bottom_seal": S.FLOOR, "pogo_seals": POGO_GASKET + 0.05,
           "motor_pad": None, "mic_seal": 0.3}      # free thickness (None: same as installed)
# mic
MIC_SEAL = 0.25       # foam (PORON) ring on the mic lid: compressed to this under the frame, to the glass gap under the glass
MIC_BORE, MIC_HOLE = 0.5, 0.6          # duct (a groove in the rib face, open to the glass-edge slit), lip outlet
MIC_RIB_FIT = 0.05    # glass clearance at the local rib that narrows the glass-edge slit over the mic (normal 0.15)
MIC_RIB_X = 1.3       # rib half-length along X
VENT_EDGE = 0.3       # border of the rectangular hydrophobic vent around the duct mouth (clamped in the gasket layer)
VENT_WALL = 0.45      # top-shell wall kept between the vent seat and the top round (local thin spot, reported)
FFC_L, FFC_D, FFC_H = 12.5, 3.5, 1.0        # FH34SRJ-18S body (Y x X x Z), centred at S.FFC_X
FPC_T = 0.12          # display FPC tail thickness
# touch + CF variant
TOUCH_Y = S.PCB_W / 2 - 0.3 - S.TOUCH_W / 2      # electrode centre |y|
TOUCH_CF_CLEAR = 1.0  # no carbon within this of a touch electrode or of antenna copper
TOUCH_FACE = 0.6      # PETG over the electrode zone (inside pocket)
WIN_X = S.TOUCH_L / 2 + TOUCH_CF_CLEAR             # touch window half-length
WIN_Z = (S.Z_PCB1 - TOUCH_CF_CLEAR - 0.1, None)    # touch pocket starts at WIN_Z[0] + 0.4 (min_wall classifier)
CF_LAP = 0.3          # the CF shell overlaps each PETG insert's flange from outside by this
Y_TOP = S.DISP_W / 2 + GLASS_FIT                   # cavity narrows to the glass above Z_STEP (thick upper wall)
Z_STEP = S.Z_DISP0 - 0.1   # upper wall over |y| >= Y_TOP: parts there must stay below Z_STEP (else RELIEFS pockets)
# outer shape
R_PLAN = S.CORNER_R   # plan corners: the ears carry the flanks on, so the corners sit under them (>= the top round's
                      # 1.6, the least the round can turn)
SHAPES = {  # name -> (plan corner R, top edge (across, down), bottom edge (across, up), kind)
    # tall elliptical top round, tangent to the top face (soft pebble): reads like an R2.5 from the side, insets 1.6
    # at the top. Lip-face-down its first layers step out <= 0.25 mm each, on the bed: no support. Tall bottom round.
    "pebble": (R_PLAN, (1.6, 2.5), (0.6, 1.2), "fillet"),
    "facet": (R_PLAN, (0.75, 1.8), (0.5, 0.5), "chamfer"),
}
SHAPE = "pebble"
Z_ROUND = S.CASE_T - SHAPES[SHAPE][1][1]   # the top round starts here: the vertical side band is below it
MIN_WALL = 0.6        # thinnest allowed top-shell wall above the seal land (touch faces are TOUCH_FACE by design)
# magnetic charging head (puck): Mill-Max 0955-0-15-20-71-14-11-0 spring pins (solder cup)
PIN = dict(plunger=0.48, barrel=0.89, collar=1.07, length=7.65, tip=1.6, collar_t=0.25, tail=1.5, stroke=1.4,
           f0=0.15, k=0.63)   # free plunger length, collar thickness, cup length; force N at contact + N/mm (15 g, 60 g @ 0.7)
PIN_PRELOAD = 0.35    # pin compression when docked: the tuning knob against the magnet hold
PIN_BORE = 1.0        # guide bores through the watch's bottom shell (barrel 0.89 enters 2.4 mm)
MAG_D, MAG_T = 3.0, 1.0           # watch magnets: 3 x 1 N52, press-fit flush with the back (A N-out, B S-out)
PUCK_MAG_T = 2.0                  # puck magnets: 3 x 2 N52, press-fit flush with the puck face (opposite poles)
MAG_X, MAG_Y = S.MOTOR_X, 5.9     # between the pogo pairs, clear of the motor pocket and the floor-plate edge
MAG_PULL = 2.9        # N, both magnet pairs face to face (~300 g hold at 0.2 mm, research)
PUCK_X = (S.MOTOR_X - 3.9, S.MOTOR_X + 6.4)   # +X extension carries the cable beside the pins
PUCK_TOP_T, PUCK_H, PUCK_WALL = 2.0, 5.2, 0.8   # face plate, total height, skirt wall
PUCK_SKIN = 0.2       # PETG over the puck magnets (0.2 mm magnet gap docked)
PUCK_LIP = 1.0        # cradle lips hug the case's bottom round this high (sideways tug, alignment)
PUCK_HW = S.CASE_W / 2 + 0.8                    # puck half-width over the lips
CABLE_D, CABLE_Z = 2.8, -3.4                    # Adafruit 5412-class 4-core cable, exits +Y low
FFC_SEAT = 0.2        # FPC tail stops this short of the FFC connector back

IN_R = S.PCB_CORNER_R + FIT                       # cavity corners follow the PCB
HL, HW = S.CAV_L / 2, S.CAV_W / 2
OL, OW = S.CASE_L / 2, S.CASE_W / 2
AA_X1 = S.DISP_X1 - S.DISP_AA_MARGIN_FAR
AA_X0 = AA_X1 - S.DISP_AA_L
AA_CX = (AA_X0 + AA_X1) / 2
X_BAR = OL + BAR_DX
Z_BAR = STRAP_R + 0.1        # strap end loop sits 0.1 above the wrist plane: the strap leaves at the case bottom
EAR_TIP = X_BAR + EAR_R
EAR_W = OW - STRAP_W / 2
PLATE_HL, PLATE_HW = HL - SEAL_GAP, HW - SEAL_GAP   # bottom shell floor plate half-size
assert S.PCB_CORNER_R <= IN_R - FIT + 1e-9, "PCB corners must sit inside the cavity corner radius"
assert EAR_W >= 0.9, f"{STRAP_W} mm straps leave {EAR_W:.2f} mm ears"
assert 1.6 <= BAR_DX <= 2.8, "+X bar outside the RF-simulated window (1.6-2.8 mm past the end face)"
assert S.FLOOR - BAT_RECESS >= 0.15 - 1e-9, "PCM recess leaves less than 0.15 mm of floor"
assert MAG_Y + MAG_D / 2 + 0.3 <= PLATE_HW, "watch magnets reach the floor-plate edge"
assert SNAP_Z - (SNAP_DEPTH + FIT) / math.tan(math.radians(SNAP_RET)) >= S.FLOOR + 0.1, "snaps run into the floor plate"
ANT_BB = None         # antenna copper bounding box, set by build() from the board (spec placeholder if none)


# ---------------------------------------------------------------- primitives
def box(x0, x1, y0, y1, z0, z1):
    x0, x1 = sorted((x0, x1))
    y0, y1 = sorted((y0, y1))
    return Pos((x0 + x1) / 2, (y0 + y1) / 2, (z0 + z1) / 2) * Box(x1 - x0, y1 - y0, z1 - z0)


def slab(l, w, r, z0, z1, x=0.0, y=0.0):
    """Rounded-rectangle prism."""
    return Pos(x, y, z0) * extrude(RectangleRounded(l, w, r), z1 - z0)


def cyl(x, y, z0, z1, d):
    return Pos(x, y, z0) * Cylinder(d / 2, z1 - z0, align=(Align.CENTER, Align.CENTER, Align.MIN))


def ycyl(x, y0, y1, z, d):
    return Pos(x, (y0 + y1) / 2, z) * Rot(90, 0, 0) * Cylinder(d / 2, abs(y1 - y0))


def union(shapes):
    out = shapes[0]
    for s in shapes[1:]:
        out = out + s
    return out


def prism_xz(pts, y0, y1):
    """Polygon in the XZ plane extruded along Y from y0 to y1."""
    return extrude(make_face(Polyline(*[(x, y0, z) for x, z in pts], close=True)), y1 - y0, dir=(0, 1, 0))


# ---------------------------------------------------------------- reference bodies
def display():
    return box(S.DISP_X0, S.DISP_X1, -S.DISP_W / 2, S.DISP_W / 2, S.Z_DISP0, S.Z_DISP1)


def fpc():
    """Tail leaves the -X glass edge, U-bends down within FPC_BEND, runs back over the PCB into the FFC."""
    t, w = FPC_T, S.FPC_W
    zt, zb = S.Z_DISP0 + t / 2, S.Z_PCB1 + 0.45            # centre lines of the two runs
    r, zc = (zt - zb) / 2, (zt + zb) / 2
    xc = S.DISP_X0 - S.FPC_BEND + 0.2 + r + t / 2           # bend within FPC_BEND of the glass edge
    a = S.DISP_X0 - xc
    natural_tip = xc + S.FPC_LEN - a - math.pi * r
    ffc_back = S.FFC_X + FFC_D / 2
    tip = min(natural_tip, ffc_back - 0.2)                  # connector back stops it; the rest is slack
    ring = Pos(xc, 0, zc) * Rot(90, 0, 0) * (Cylinder(r + t / 2, w) - Cylinder(r - t / 2, w))
    tail = (box(xc, S.DISP_X0, -w / 2, w / 2, zt - t / 2, zt + t / 2)
            + (ring & box(xc - 2, xc, -w, w, zc - 2, zc + 2))
            + box(xc, tip, -w / 2, w / 2, zb - t / 2, zb + t / 2))
    stiffener = box(tip - 3.5, tip, -w / 2, w / 2, zb + t / 2, zb + t / 2 + 0.3)
    return tail, stiffener, dict(slack=natural_tip - tip, insertion=tip - (S.FFC_X - FFC_D / 2),
                                 short=ffc_back - natural_tip, natural_tip=natural_tip, bend_r=r)


def touch_pads():
    """Capacitive touch electrodes (PCB top copper)."""
    return union([box(x - S.TOUCH_L / 2, x + S.TOUCH_L / 2, sy * (TOUCH_Y - S.TOUCH_W / 2),
                      sy * (TOUCH_Y + S.TOUCH_W / 2), S.Z_PCB1, S.Z_PCB1 + 0.035) for x in S.TOUCH_X for sy in (-1, 1)])


def pads():
    """PCB bottom copper the case meets: pogo pads, motor lead pads, battery wire pads."""
    return union([cyl(x, y, S.Z_PCB0 - 0.03, S.Z_PCB0, POGO_PAD_D) for x, y in POGO_XY]
                 + [cyl(S.MOTOR_X + dx, 0, S.Z_PCB0 - 0.03, S.Z_PCB0, 1.5) for dx in (-S.MOTOR_PAD_DX, S.MOTOR_PAD_DX)]
                 + [box(S.BATPAD_X - 1, S.BATPAD_X + 1, sy * (S.BATPAD_Y - 1), sy * (S.BATPAD_Y + 1), S.Z_PCB0 - 0.03,
                        S.Z_PCB0) for sy in (-1, 1)])


def pcb_placeholder():
    zt = S.Z_PCB1
    groups = {
        "qfn": box(S.ANT_X0 - 0.5 - 7, S.ANT_X0 - 0.5, -3.5, 3.5, zt, zt + 0.9),
        "ffc": box(S.FFC_X - FFC_D / 2, S.FFC_X + FFC_D / 2, -FFC_L / 2, FFC_L / 2, zt, zt + FFC_H),
        "chips": union([box(-4.5, -1.3, 1.0, 2.5, zt, zt + 0.8),      # RTC
                        box(-4.0, -2.0, -3.0, -1.0, zt, zt + 0.95),   # accelerometer
                        box(0.0, 2.5, 1.0, 3.0, zt, zt + 1.0),        # inductor
                        box(0.2, 2.2, -3.2, -1.2, zt, zt + 0.75)]),   # LDO / charger
    }
    board = slab(S.PCB_L, S.PCB_W, S.PCB_CORNER_R, S.Z_PCB0, S.Z_PCB1)
    comps = [(k, "placeholder", v) for k, v in groups.items()]
    return board, groups, comps


def kicad_footprints():
    """(ref, value, footprint, x, y, rot, layer) from the newest populated .kicad_pcb in hardware/."""
    import re
    cands = [f for f in [ROOT / "hardware" / "horae.kicad_pcb", *sorted((ROOT / "hardware" / "out").glob("*.kicad_pcb"))]
             if f.exists() and '(footprint "' in f.read_text()]
    if not cands:
        return [], None
    src = max(cands, key=lambda f: f.stat().st_mtime)
    t = src.read_text()
    out = []
    for m in re.finditer(r'\n\t\(footprint "([^"]+)"(.*?)\n\t\)', t, re.S):
        body = m.group(2)
        at = re.search(r'\(at ([-\d.]+) ([-\d.]+)(?: ([-\d.]+))?\)', body)
        prop = dict(re.findall(r'\(property "(Reference|Value)" "([^"]*)"', body))
        out.append(dict(ref=prop.get("Reference", "?"), value=prop.get("Value", ""), fp=m.group(1).split(":")[-1],
                        x=float(at.group(1)), y=float(at.group(2)), rot=float(at.group(3) or 0),
                        layer=re.search(r'\(layer "([^"]+)"', body).group(1), body=body))
    return out, src


def envelope(fp, x, y):
    """Box for a footprint whose 3D model is missing from the STEP (dims parsed from the footprint name)."""
    import re
    name = fp["fp"] + " " + (re.search(r'\(model "([^"]+)"', fp["body"]) or [None, ""])[1]
    metric = re.search(r"_(\d\d)(\d\d)Metric", name)
    mm = re.search(r"_(\d+(?:\.\d+)?)x(\d+(?:\.\d+)?)mm", name)
    if "FH34SRJ" in name:
        l, w, h = FFC_L, FFC_D, FFC_H
    elif metric:                                          # chip passives: 0603Metric = 0201, 1005Metric = 0402
        l, w = int(metric.group(1)) / 10, int(metric.group(2)) / 10
        h = w + 0.05
    elif "MIC-SMD" in name:                               # LMD2718: 2.75 x 1.85 x 0.9
        l, w, h = 2.75, 1.85, 0.9
    elif mm:                                              # QFN/DFN: "_7x7mm"
        l, w, h = float(mm.group(1)), float(mm.group(2)), 0.9
    else:
        num = lambda k, d: float((re.search(k + r"(\d+(?:\.\d+)?)", name) or [None, d])[1])
        l, w, h = num("_L", 2.0), num("-W", 2.0), num("-H", 1.0)
        w = max(w, num("-LS", 0))
    if round(fp["rot"]) % 180 == 90:
        l, w = w, l
    return box(x - l / 2, x + l / 2, y - w / 2, y + w / 2, S.Z_PCB1, S.Z_PCB1 + h), None


def antenna(fp, cx, cy):
    """Copper polygons of the PCB antenna footprint, as 35 um plates on the board top."""
    import re
    th = math.radians(fp["rot"])
    plates = []
    for poly in re.findall(r'\(fp_poly\s*\(pts(.*?)\)\s*\(stroke.*?\(layer "F\.Cu"\)', fp["body"], re.S):
        pts = [tuple(map(float, q)) for q in re.findall(r'\(xy ([-\d.]+) ([-\d.]+)\)', poly)]
        xs, ys = [], []
        for px, py in pts:   # KiCad: y down, rotation CCW on screen
            bx = fp["x"] + px * math.cos(th) + py * math.sin(th)
            by = fp["y"] - px * math.sin(th) + py * math.cos(th)
            xs.append(bx - cx)
            ys.append(-by - cy)
        plates.append(box(min(xs), max(xs), min(ys), max(ys), S.Z_PCB1 - 0.035, S.Z_PCB1))  # pours are rectangles
    return union(plates) if plates else None


def load_board():
    """Real KiCad STEP if present, else the placeholder.

    Returns board solid, {render group: shape}, [(ref, value, shape)] per component, source note.
    The STEP is in KiCad's frame (Y already flipped, board centre at KiCad (100, 100)); we centre on the board
    body and put its bottom at Z_PCB0. Components without a 3D model in the STEP get envelopes from the .kicad_pcb.
    """
    if not BOARD_STEP.exists():
        board, groups, comps = pcb_placeholder()
        return board, groups, comps, "placeholder PCB"
    step = import_step(str(BOARD_STEP))
    kids = list(step.children)
    body = next((k for k in kids if str(k.label).endswith("_PCB")), None) or max(step.solids(), key=lambda q: q.volume)
    c = body.bounding_box().center()
    sz = body.bounding_box().size
    if abs(sz.X - S.PCB_L) > 0.05 or abs(sz.Y - S.PCB_W) > 0.05:
        print(f"WARNING: STEP board is {sz.X:.2f} x {sz.Y:.2f}, spec says {S.PCB_L:.2f} x {S.PCB_W:.2f} (stale STEP?)")
    mv = Pos(-c.X, -c.Y, S.Z_PCB0)
    board = mv * body
    fps, src = kicad_footprints()
    top = [f for f in fps if f["layer"] == "F.Cu"]
    to_case = lambda f: (f["x"] - c.X, -f["y"] - c.Y)
    comps, matched = [], set()
    for k in kids:
        if k is body:
            continue
        sh = mv * k
        bc = sh.bounding_box().center()
        key = lambda t: "".join(ch for ch in str(t) if ch.isalnum()).upper()[:5]
        same = [f for f in top if f["ref"] not in matched and key(f["fp"]) == key(k.label)]   # same footprint type
        near = min(same or top, key=lambda f: math.dist(to_case(f), (bc.X, bc.Y)), default=None)
        if near and math.dist(to_case(near), (bc.X, bc.Y)) < 1.5:
            matched.add(near["ref"])
            if near["ref"].startswith("TCH"):   # touch electrodes: copper only (their STEP model is a dummy block)
                continue
            comps.append((near["ref"], near["value"], sh))
        else:
            comps.append((str(k.label), "", sh))
    groups = dict(qfn=[], ffc=[], chips=[], switches=[], antenna=[])
    n_env = 0
    for f in top:
        if f["ref"] in matched:
            continue
        if f["ref"].startswith("TCH"):
            continue
        if f["ref"].startswith("AE"):
            groups["antenna"].append(antenna(f, c.X, c.Y))
            continue
        b, nub = envelope(f, *to_case(f))
        n_env += 1
        comps.append((f["ref"], f["value"], b))
    for ref, val, sh in comps:
        if ref.endswith(" nub"):
            continue
        key = ("qfn" if val.startswith("ESP32") else "ffc" if ref.startswith("J") else
               "switches" if ref.startswith("SW") else "chips")
        groups[key].append(sh)
    groups = {k: union(v) for k, v in groups.items() if v and v[0] is not None}
    note = f"{BOARD_STEP.relative_to(ROOT)} ({len(comps)} bodies"
    note += f", refs from {src.relative_to(ROOT)}, {n_env} envelopes for missing models)" if src else ")"
    return board, groups, comps, note


def battery():
    """Cell + its thicker PCM end (in the floor recess); leads run in the bottom shell's channel and are soldered to
    the 2x2 pads (VBAT +, KiCad +Y)."""
    z0, z1 = S.Z_BAT0, S.Z_BAT0 + S.BAT_T
    body = box(S.BAT_X0 + BAT_PCM_L, S.BAT_X1, -S.BAT_W / 2, S.BAT_W / 2, z0, z1)
    body = fillet(body.edges().group_by(Axis.Z)[-1], 0.9)
    zp = S.FLOOR - BAT_RECESS
    pcm = box(S.BAT_X0, S.BAT_X0 + BAT_PCM_L + 0.1, -S.BAT_W / 2 + 0.3, S.BAT_W / 2 - 0.3, zp, zp + S.BAT_T + BAT_PCM_EXTRA)
    zl = MAG_T + 0.6                                     # leads run in the bottom shell's wire channel to the pads
    leads = union([box(S.BATPAD_X - 0.15, S.BAT_X0, sy * (S.BATPAD_Y - 0.15), sy * (S.BATPAD_Y + 0.15), zl, zl + 0.25)
                   + box(S.BATPAD_X - 0.15, S.BATPAD_X + 0.15, sy * (S.BATPAD_Y - 0.15), sy * (S.BATPAD_Y + 0.15), zl,
                         S.Z_PCB0 - 0.03) for sy in (-1, 1)])
    return body + pcm, leads


def motor():
    """Coin ERM standing on the floor in its pocket; its two leads loop up over the can and are soldered to the PCB
    pads (shown as lead + solder columns)."""
    body = cyl(S.MOTOR_X, 0, MOTOR_Z0, MOTOR_Z0 + S.MOTOR_T, S.MOTOR_D)
    leads = union([cyl(S.MOTOR_X + dx, 0, MOTOR_Z0 + S.MOTOR_T + 0.05, S.Z_PCB0 - 0.03, 0.4)
                   for dx in (-S.MOTOR_PAD_DX, S.MOTOR_PAD_DX)])
    return body, leads


def watch_magnets():
    """3 x 1 N52 discs press-fit flush with the back: +Y physical N out, -Y S out (charger keying)."""
    return [cyl(MAG_X, sy * MAG_Y, 0, MAG_T, MAG_D) for sy in (1, -1)]


def spring_bar(sx):
    """Standard spring bar: body between the ears, 0.8 tips through the drilled ears (flush with the outside)."""
    return (ycyl(sx * X_BAR, -STRAP_W / 2 + 0.05, STRAP_W / 2 - 0.05, Z_BAR, BAR_D)
            + ycyl(sx * X_BAR, -OW + 0.05, OW - 0.05, Z_BAR, 0.8))


def spring_bars():
    return spring_bar(-1)


def rf_pin():
    """+X spring bar (steel; kept as far from the antenna as the lug allows). Key name kept for the renders."""
    return spring_bar(1)


def nato(swing=0.0, length=14.0, t=2.0):
    """Two-piece strap stubs: a loop around each bar (STRAP_R, the clearance envelope) tapering into a t-thick strap
    that leaves at wrist level, rounded edges (render + clearance). swing: degrees each stub turns about its bar,
    + = down toward the wrist."""
    w = STRAP_W / 2 - 0.1
    zb = Z_BAR - STRAP_R
    loop = [(STRAP_R * math.cos(a), Z_BAR + STRAP_R * math.sin(a)) for a in np.linspace(math.pi / 2, 1.5 * math.pi, 18)]
    top = [(4.5 * u, zb + t + (2 * STRAP_R - t) * (1 - u) ** 2) for u in np.linspace(1, 0, 10)]
    prof = loop + [(length, zb), (length, zb + t)] + top[:-1]
    parts = []
    for sx in (-1, 1):
        stub = prism_xz([(sx * (X_BAR + x), z) for x, z in prof], -w, w)
        try:
            stub = fillet(stub.edges().filter_by(Axis.Y, reverse=True).group_by(Axis.Y)[0] +
                          stub.edges().filter_by(Axis.Y, reverse=True).group_by(Axis.Y)[-1], 0.5)
        except Exception:
            pass
        stub -= ycyl(sx * X_BAR, -w - 1, w + 1, Z_BAR, BAR_D + 0.1)
        parts.append(Pos(sx * X_BAR, 0, Z_BAR) * Rot(0, sx * swing, 0) * Pos(-sx * X_BAR, 0, -Z_BAR) * stub)
    return union(parts)


# ---------------------------------------------------------------- mic
def mic_port():
    """(x, y, top z) of the mic's acoustic port: from the board STEP model when present, else from spec."""
    return MIC_PORT


MIC_PORT = (S.MIC_X, -(S.MIC_Y + 0.6), S.Z_PCB1 + 0.9)    # replaced by build() from the STEP
MIC_PORT_R = 0.175                                          # port hole radius (STEP: LMD2718 0.35 mm)
MIC_BOX = None                                              # mic body bbox (x0, x1, y0, y1, z1) from the STEP
RELIEFS = []                                                # (ref, value, bbox) of parts the frame is relieved for
RIB_IN = S.DISP_W / 2 + MIC_RIB_FIT                         # |y| of the rib face beside the glass edge

def find_mic(comps):
    """Locate MIC1 and its port (small circle on the top face) in the board bodies -> (port xyz, radius, bbox)."""
    from build123d import GeomType
    for ref, val, sh in comps:
        if ref.startswith("MIC"):
            bb = sh.bounding_box()
            ports = [e for e in sh.edges() if e.geom_type == GeomType.CIRCLE and e.radius < 0.3
                     and abs(e.arc_center.Z - bb.max.Z) < 0.02]
            c = ports[0].arc_center if ports else bb.center()
            r = ports[0].radius if ports else MIC_PORT_R
            return (c.X, c.Y, bb.max.Z), r, (bb.min.X, bb.max.X, bb.min.Y, bb.max.Y, bb.max.Z)
    return None, MIC_PORT_R, None


def mic_sy():
    return 1 if mic_port()[1] > 0 else -1


def mic_beside_glass():
    x, y, _ = mic_port()
    return S.DISP_X0 < x < S.DISP_X1 and abs(y) < HW


def duct_xy():
    """Duct axis: straight above the port; a port at the glass edge gets a groove in the rib face instead
    (open to the 0.05 glass-edge slit, which the port's chamber reaches anyway)."""
    x, y, _ = mic_port()
    if not mic_beside_glass():
        return x, y
    return x, mic_sy() * max(abs(y), RIB_IN + MIC_BORE / 2 - 0.1)


def mic_seal(t=MIC_SEAL):
    """Closed foam ring on the mic lid around the port + duct mouth; squeezed to t under the frame and to the
    glass gap where it runs under the glass edge."""
    x, y, z = mic_port()
    _, yd = duct_xy()
    sy = mic_sy()
    a = abs(y) - MIC_PORT_R - 0.05                       # slot from the port's inner edge ...
    b = abs(yd) + MIC_BORE / 2 + 0.05                    # ... to the duct mouth's outer edge
    if MIC_BOX:
        x0, x1, y0, y1, _ = MIC_BOX
        lid_out, lid_x = min(max(abs(y0), abs(y1)), HW - 0.05), (x1 - x0) / 2 - 0.05
    else:
        lid_out, lid_x = b + 0.4, 0.8
    ring = box(x - lid_x, x + lid_x, sy * (a - 0.3), sy * lid_out, z + 0.01, z + t)
    ring -= box(x - 0.3, x + 0.3, sy * a, sy * b, z - 1, z + t + 1)
    return ring - box(-HL, HL, -RIB_IN, RIB_IN, S.Z_DISP0 - 0.01, z + t + 1)


def mic_seal_walls():
    """(inner, outer, side) ring wall widths in mm."""
    x, y, _ = mic_port()
    _, yd = duct_xy()
    a, b = abs(y) - MIC_PORT_R - 0.05, abs(yd) + MIC_BORE / 2 + 0.05
    lid_out = min(max(abs(MIC_BOX[2]), abs(MIC_BOX[3])), HW - 0.05) if MIC_BOX else b + 0.4
    lid_x = (MIC_BOX[1] - MIC_BOX[0]) / 2 - 0.05 if MIC_BOX else 0.8
    return 0.3, lid_out - b, lid_x - 0.3


def vent_box():
    """Rectangular hydrophobic vent over the duct top, in the gasket layer under the lip: inner border on the glass,
    outer on the rib/upper wall; the lip clamps it when the glass is pushed up."""
    x, _, _ = mic_port()
    _, yd = duct_xy()
    sy, r = mic_sy(), MIC_BORE / 2 + VENT_EDGE
    y_out = OW - top_inset(S.CASE_T - Z_LIP0) - VENT_WALL - 0.05      # keep VENT_WALL to the top round
    y0, y1 = sorted((sy * (abs(yd) - r - 0.1), sy * min(abs(yd) + r, y_out)))
    return x - r - 0.15, x + r + 0.15, y0, y1


def vent():
    x0, x1, y0, y1 = vent_box()
    return box(x0, x1, y0, y1, S.Z_DISP1, Z_LIP0)


# ---------------------------------------------------------------- outer shape
def top_inset(d, style=None):
    """How far the skin's top edge sits inside the side wall at depth d below the case top."""
    _, (a, b), _, kind = SHAPES[style or SHAPE]
    u = max(1 - d / b, 0)
    return a * u if kind != "fillet" else a * (1 - math.sqrt(1 - u * u))


def body_skin(style=None, grow=0.0):
    """Pebble body without the ears: rounded plan (corners under the ears), tall elliptical top round tangent to the
    top face, tall elliptical bottom round. grow: approximate outward offset (charger cradle)."""
    from build123d import chamfer, scale
    r_plan, (a, b), (ab, bb), kind = SHAPES[style or SHAPE]
    edge = fillet if kind == "fillet" else chamfer
    L, W, R, T = S.CASE_L + 2 * grow, S.CASE_W + 2 * grow, r_plan + grow, S.CASE_T + grow
    kb = ab / bb                                      # bottom round: an ab round stretched by 1 / kb in Z
    low = slab(L, W, R, -grow * kb, (T + 1) * kb)
    low = scale(edge(low.edges().group_by(Axis.Z)[0], ab), by=(1, 1, 1 / kb))
    k = a / b                                         # top round: an a round squashed by k in Z
    up = slab(L, W, R, -1, T * k)
    up = scale(edge(up.edges().group_by(Axis.Z)[-1], a), by=(1, 1, 1 / k))
    return low & up


def section_outline(style=None, inset=0.0, n=48):
    """Closed (y, z) outline of the case's YZ cross-section (same rounds as body_skin), inset inward."""
    _, (a, b), (ab, bb), kind = SHAPES[style or SHAPE]
    W, T = OW - inset, S.CASE_T - inset
    if kind == "fillet":
        half = [(W - ab + ab * math.cos(t), inset + bb + bb * math.sin(t)) for t in np.linspace(-math.pi / 2, 0, n)]
        half += [(W - a + a * math.cos(t), T - b + b * math.sin(t)) for t in np.linspace(0, math.pi / 2, n)]
    else:
        half = [(W - ab, inset), (W, inset + bb), (W, T - b), (W - a, T)]
    pts = [(0.0, inset)] + half + [(0.0, T)] + [(-y, z) for y, z in reversed(half)]
    out = [pts[0]]
    for q in pts[1:]:
        if math.dist(q, out[-1]) > 1e-6:
            out.append(q)
    return out


def yz_arc(x, cy, cz, ry, rz, a0, a1):
    """Elliptical arc in the plane at x (centre (cy, cz), radii along Y / Z, degrees from +Y towards +Z)."""
    return Edge.make_ellipse(ry, rz, Plane(origin=(x, cy, cz), x_dir=(0, 1, 0), z_dir=(1, 0, 0)), a0, a1)


def section_face(style=None):
    """The case's YZ cross-section as an exact face in the x = 0 plane (rounds as true ellipse arcs, same as
    body_skin): the ears' rail fuses face-to-face with the flank. The chamfer style's polyline is already exact."""
    _, (a, b), (ab, bb), kind = SHAPES[style or SHAPE]
    if kind != "fillet":
        return make_face(Polyline(*[(0, y, z) for y, z in section_outline(style)], close=True))
    W, T, ln = OW, S.CASE_T, Edge.make_line
    return Face(Wire([ln((0, ab - W, 0), (0, W - ab, 0)), yz_arc(0, W - ab, bb, ab, bb, -90, 0),
                      ln((0, W, bb), (0, W, T - b)), yz_arc(0, W - a, T - b, a, b, 0, 90),
                      ln((0, W - a, T), (0, a - W, T)), yz_arc(0, a - W, T - b, a, b, 90, 180),
                      ln((0, -W, T - b), (0, -W, bb)), yz_arc(0, ab - W, bb, ab, bb, 180, 270)]))


def ear_side(x0):
    """XZ outline of the +X ears: open above the case, then EAR_SLOPE down onto the bar boss, tangent to its outer
    side (the slope covers the boss crown: nothing flatter than 45 deg faces the bed when the top shell prints
    lip-down), round tip, back under the boss to below the floor."""
    th, top = math.radians(EAR_SLOPE), S.CASE_T + 1
    tx, tz = X_BAR + EAR_R * math.sin(th), Z_BAR + EAR_R * math.cos(th)
    xt = tx - (top - tz) / math.tan(th)
    tip = Edge.make_circle(EAR_R, Plane(origin=(X_BAR, 0, Z_BAR), x_dir=(1, 0, 0), z_dir=(0, -1, 0)),
                           90 - EAR_SLOPE, -90, AngularDirection.CLOCKWISE)
    ln = Edge.make_line
    return Face(Wire([ln((x0, 0, -1), (x0, 0, top)), ln((x0, 0, top), (xt, 0, top)), ln((xt, 0, top), (tx, 0, tz)),
                      tip, ln((X_BAR, 0, Z_BAR - EAR_R), (X_BAR - 2.0, 0, -1)), ln((X_BAR - 2.0, 0, -1), (x0, 0, -1))]))


def ear_profile(s):
    """(x, zo, f, zb) at s in [0, 1] along the pebble ear, from EAR_KNEE inside the end face to where the slope
    touches the boss (xt): zo = height of the flank's band top (the ear's outer edge), falling from Z_ROUND with zero
    slope and curvature onto the boss's EAR_SLOPE tangent; f = share of the flank's top round still standing above it
    (1 -> 0, smoothstep); zb = underside, rising smoothly onto the boss's lower arc."""
    th = math.radians(EAR_SLOPE)
    xt, dt, g = X_BAR + EAR_R * math.sin(th), Z_ROUND - Z_BAR - EAR_R * math.cos(th), math.tan(th)
    L = min(max(xt - (OL - EAR_KNEE), 3 * dt / g), 4 * dt / g)     # a shallower drop (thin case) starts later
    c3, c4 = 4 * dt - L * g, L * g - 3 * dt                          # zo = Z_ROUND - c3 s^3 - c4 s^4, both >= 0
    x = xt - L + s * L
    u = min(max((x - X_BAR + 1.2) / 1.2, 0), 1)
    zb = (Z_BAR - EAR_R) * (3 * u * u - 2 * u ** 3) if x <= X_BAR else Z_BAR - math.sqrt(EAR_R ** 2 - (x - X_BAR) ** 2)
    return x, Z_ROUND - c3 * s ** 3 - c4 * s ** 4, 1 - (3 * s * s - 2 * s ** 3), zb


def ear_stations(n=17):
    """Loft stations (x, zo, f, zb, r) along the ear, closer together at both ends; r = the inner top edge's round:
    none at the knee (where the ear's top still is the flank, so it hands over from the body's corner without a
    step), EAR_INNER_R along the fall, fading out onto the boss (whose own edge stays sharp)."""
    def ease(u):
        u = min(max(u, 0), 1)
        return 3 * u * u - 2 * u ** 3
    return [ear_profile(s) + (max(EAR_INNER_R * ease(s / 0.3) * (1 - ease((s - 0.55) / 0.45)), 0.03),)
            for s in (1 - np.cos(np.linspace(0, math.pi, n))) / 2]


def ear_overhang(style=None, clear=0.8):
    """Flattest slope (deg) of the ear's top, where it hangs more than `clear` above the bed when the top shell
    prints lip-face-down (the knee near the top face is bed-supported); the boss below the tangent is >= EAR_SLOPE."""
    _, (a, b), _, _ = SHAPES[style or SHAPE]
    cy, ys, worst = OW - a, np.linspace(STRAP_W / 2, OW - 1e-3, 60), (90.0, None)
    rise = b * np.sqrt(1 - ((ys - cy) / a) ** 2)
    for s in np.linspace(0, 1, 120):
        (x, zo, f, _), (x1, zo1, f1, _), (x2, zo2, f2, _) = (ear_profile(s), ear_profile(max(s - 1e-4, 0)),
                                                            ear_profile(min(s + 1e-4, 1)))
        z = zo + f * rise
        zx = ((zo2 + f2 * rise) - (zo1 + f1 * rise)) / (x2 - x1)
        zy = np.gradient(z, ys)
        ang = np.degrees(np.arctan(np.hypot(zx, zy)))
        hang = z < S.CASE_T - clear
        if hang.any() and ang[hang].min() < worst[0]:
            i = np.flatnonzero(hang)[ang[hang].argmin()]
            worst = (float(ang[i]), (round(float(x), 2), round(float(ys[i]), 2), round(float(z[i]), 2)))
    return worst


def ear_section(x, zo, f, zb, r=0.0, style=None):
    """Closed YZ wire of the +X+Y ear at x: flat underside at zb, the flank's bottom round, the band up to zo, the
    flank's top round scaled to f of its height above zo (f = 1: exactly the flank; f = 0: flat), rounded r into
    the inner face."""
    _, (a, b), (ab, bb), _ = SHAPES[style or SHAPE]
    y0, y1, cy, ln = STRAP_W / 2, OW, OW - a, Edge.make_line
    tb = math.degrees(math.asin((zb - bb) / bb))
    yb = y1 - ab + ab * math.cos(math.radians(tb))
    t0 = math.acos((y0 - cy) / a)                                     # the inner face cuts the round here
    m = f * b * math.cos(t0) / (a * math.sin(t0))                     # how steeply the top falls outward there
    d = r / math.tan((math.pi / 2 - math.atan(m)) / 2)              # tangent length of an r round in that corner
    ya = y0 + d * math.cos(math.atan(m))
    ta = math.acos((ya - cy) / a)
    za, zi = zo + f * b * math.sin(ta), zo + f * b * math.sin(t0)
    top = yz_arc(x, cy, zo, a, f * b, 0, math.degrees(ta)) if f > 1e-9 else ln((x, y1, zo), (x, ya, zo))
    blend = Edge.make_spline([(x, ya, za), (x, y0, zi - d)],
                             tangents=[(0, -a * math.sin(ta), f * b * math.cos(ta)), (0, 0, -1)])
    return Wire([ln((x, y0, zb), (x, yb, zb)), yz_arc(x, y1 - ab, bb, ab, bb, tb, 0), ln((x, y1, bb), (x, y1, zo)),
                 top, blend, ln((x, y0, zi - d), (x, y0, zb))])


def ear(style=None):
    """+X+Y ear. Pebble: the flank (rounds and band) runs straight on past the end face (exact section, so it fuses
    face-to-face with the body: no seam), then from EAR_KNEE a loft lets its top round sink and flatten into the
    boss's 45 deg tangent: one smooth surface from the case top to the bar, no crease; its inner top edge is
    rounded in the sections. Chamfer style: the flank carried on and cut by ear_side."""
    _, _, _, kind = SHAPES[style or SHAPE]
    x0 = OL - R_PLAN - 0.5
    rail = extrude(section_face(style), OL + 6, dir=(1, 0, 0), both=True)
    side = extrude(ear_side(x0 - 1), OW + 2, both=True)
    zone = (STRAP_W / 2, OW + 1, -1, S.CASE_T + 1)
    if kind != "fillet":
        e = rail & side & box(x0, EAR_TIP + 0.5, *zone)
    else:
        st = ear_stations()
        xk, xt = st[0][0], st[-1][0]
        root = extrude(Face(ear_section(x0, *st[0][1:], style=style)), xk - x0, dir=(1, 0, 0))
        loft = Solid.make_loft([ear_section(*q, style=style) for q in st])
        tip = rail & side & box(xt, EAR_TIP + 0.5, *zone)               # meets the loft tangentially: fuzzy fuse
        e = root.fuse(loft, tol=5e-4).fuse(tip, tol=5e-4).clean()
    assert len(e.solids()) == 1, "ear pieces did not fuse"
    return e


def skin_quarter(style=None):
    """+X+Y quarter of the outer skin: the body and one ear growing out of its corner (the ear's inner face meets
    the rounded end in a plain concave corner). Built once and mirrored, so all four ears are identical."""
    e = ear(style)
    body = body_skin(style) & box(0, OL + 10, 0, OW + 10, -5, S.CASE_T + 5)
    q = body + e
    assert q.volume > body.volume + 0.5 * e.volume, "ear did not fuse onto the body"
    return q


_SKINS = {}


def skin(style=None):
    """Outer shape of the closed case: body + ears (cached; every case part is cut from or clipped by it)."""
    key = style or SHAPE
    if key not in _SKINS:
        q = skin_quarter(key)
        half = q + mirror(q, Plane.XZ)
        full = (half + mirror(half, Plane.YZ)).clean()
        assert len(full.solids()) == 1 and abs(full.volume / q.volume - 4) < 4e-3, "skin quarters did not fuse"
        _SKINS[key] = full
    return _SKINS[key]


# ---------------------------------------------------------------- top shell (frame + bezel lip)
def window(z0, h, grow=0.0):
    win = RectangleRounded(S.DISP_AA_L + 2 * (WIN_M + grow), S.DISP_AA_W + 2 * (WIN_M + grow), 0.6 + max(grow, 0))
    return Pos(AA_CX, 0, z0) * extrude(win, h)


def window_cut():
    """Display window through the lip with a 45 deg chamfer on its top edge."""
    win = RectangleRounded(S.DISP_AA_L + 2 * WIN_M, S.DISP_AA_W + 2 * WIN_M, 0.6)
    return window(Z_LIP0 - 0.5, S.CASE_T) + Pos(AA_CX, 0, S.CASE_T - WIN_CHAMFER) * extrude(win, 1.0, taper=-45)


def fpc_hood():
    """-X end over the FPC bend: carries the lip there, chamfered underneath to clear the bend."""
    zl, yl = S.Z_DISP0 + FPC_T + 0.05, S.LEDGE_Y + 0.1
    return prism_xz([(-HL - 0.3, zl - 0.42), (-HL, zl - 0.42), (-HL + 0.3, zl), (S.DISP_X0 - GLASS_FIT, zl),
                     (S.DISP_X0 - GLASS_FIT, Z_LIP0), (-HL - 0.3, Z_LIP0)], -yl, yl)


def snap_profile(sx, grow_tip=0.0, grow_top=0.0):
    """XZ outline of a snap bump on the bottom shell's block end face at end sx (retention face below the tip)."""
    xf, d = sx * (HL - FIT), SNAP_DEPTH + FIT
    zr = d / math.tan(math.radians(SNAP_RET))
    zl = d / math.tan(math.radians(SNAP_RAMP))
    return [(xf - sx * 0.3, SNAP_Z - zr), (xf, SNAP_Z - zr), (xf + sx * (d + grow_tip), SNAP_Z + grow_tip * zr / d),
            (xf + sx * (d + grow_tip), SNAP_Z + 0.05 + grow_top), (xf, SNAP_Z + 0.05 + zl + grow_top),
            (xf - sx * 0.3, SNAP_Z + 0.05 + zl + grow_top)]


def snap_bump(sx, sy):
    yc = sy * SNAP_Y[sx]
    return prism_xz(snap_profile(sx), yc - SNAP_W / 2, yc + SNAP_W / 2)


def snap_recess(sx, sy):
    yc, w = sy * SNAP_Y[sx], SNAP_W / 2 + 0.15
    return Pos(0, 0, -0.02) * prism_xz(snap_profile(sx, 0.05, 0.1), yc - w, yc + w)


def glass_pocket():
    """Glass pocket (GLASS_FIT clearance, corners chamfered POCKET_CHAMFER) + the gasket layer above it (R1 corners):
    keeps the wall at the -X corners, where the pocket comes closest to the top round."""
    from build123d import chamfer
    gl, gw = S.DISP_L + 2 * GLASS_FIT, S.DISP_W + 2 * GLASS_FIT
    g = box(S.DISP_X0 - GLASS_FIT, S.DISP_X1 + GLASS_FIT, -gw / 2, gw / 2, Z_STEP - 0.01, S.Z_DISP1 + 0.001)
    g = chamfer(g.edges().filter_by(Axis.Z), POCKET_CHAMFER)
    return g + slab(gl, gw, 1.0, S.Z_DISP1, Z_LIP0, x=S.DISP_CX)


def mic_features(f):
    """Mic beside the glass: frame relieved over the mic + seal ring, rib narrowing the glass-edge slit, duct up to
    the gasket layer, vent seat there, outlet through the lip."""
    x, y, zt = mic_port()
    sy, zr = mic_sy(), zt + MIC_SEAL
    if MIC_BOX:
        x0, x1, y0, y1, _ = MIC_BOX
        f -= box(x0 - 0.2, x1 + 0.2, y0 - 0.2, y1 + 0.2, S.Z_PCB1, zr)
    if mic_beside_glass():
        f += box(x - MIC_RIB_X, x + MIC_RIB_X, sy * RIB_IN, sy * HW, zr, S.Z_DISP1)
    xd, yd = duct_xy()
    f -= cyl(xd, yd, zr - 1, S.Z_DISP1 + 0.01, MIC_BORE)
    vx0, vx1, vy0, vy1 = vent_box()
    f -= box(vx0 - 0.05, vx1 + 0.05, vy0 - 0.05, vy1 + 0.05, S.Z_DISP1, Z_LIP0)
    return f - cyl(xd, yd, Z_LIP0 - 0.01, S.CASE_T + 1, MIC_HOLE)


def touch_thin():
    """Pockets that thin the wall to TOUCH_FACE over each electrode (inside face, below the top round)."""
    return union([box(x - S.TOUCH_L / 2 - 0.3, x + S.TOUCH_L / 2 + 0.3, sy * (HW - 1), sy * (OW - TOUCH_FACE),
                      S.Z_PCB1 - TOUCH_CF_CLEAR + 0.3, min(Z_STEP, Z_ROUND)) for x in S.TOUCH_X for sy in (-1, 1)])


def top_shell(style=None, probe=False):
    """Frame + bezel lip in one PETG part, printed lip-face-down. probe: before part reliefs and touch thinning."""
    style = style or SHAPE
    f = skin(style) - slab(S.CAV_L, S.CAV_W, IN_R, -1, Z_LIP0)
    z0 = S.Z_PCB1 + S.GAP                                     # bearing faces on the PCB's part-free zones
    inner = box(S.DISP_X1 + GLASS_FIT, HL, -HW, HW, z0, Z_LIP0)                         # antenna strip: copper only
    for sy in (-1, 1):
        inner += box(-HL, S.DISP_X0 - GLASS_FIT, sy * S.LEDGE_Y, sy * HW, z0, Z_LIP0)    # -X corners beside the FPC
        inner += box(-HL, HL, sy * Y_TOP, sy * HW, Z_STEP, Z_LIP0)                    # upper walls beside the glass
        for xa, xb in ((S.DISP_X0 - GLASS_FIT, S.DISP_X0 + S.LEDGE), (S.DISP_X1 - S.LEDGE, S.DISP_X1 + GLASS_FIT)):
            inner += box(xa, xb, sy * Y_TOP, sy * HW, z0, Z_STEP)                      # cushion locators
    for xa, xb in ((S.DISP_X0 - GLASS_FIT - 0.05, S.DISP_X0 + 1.0), (S.DISP_X1 - 1.0, S.DISP_X1 + GLASS_FIT + 0.05)):
        for sy in (-1, 1):                                                     # pocket corners, filled then re-cut
            inner += box(xa, xb, sy * (Y_TOP - 1.2), sy * (Y_TOP + 0.05), S.Z_DISP0, Z_LIP0)
    f += (inner + fpc_hood()) & slab(S.CAV_L, S.CAV_W, IN_R, z0 - 0.5, Z_LIP0) & body_skin(style)   # never through the round
    f -= glass_pocket()                                                        # leaves the pocket corners filled
    f -= window_cut()
    for sx in (-1, 1):
        f -= ycyl(sx * X_BAR, -OW - 1, OW + 1, Z_BAR, BAR_TIP_HOLE)           # drilled ears
        for sy in (-1, 1):
            f -= snap_recess(sx, sy)
    f = mic_features(f)
    if probe:
        return f
    for ref, _, bb in RELIEFS:                                                 # pockets for parts that reach the frame
        f -= box(bb[0] - 0.1, bb[1] + 0.1, max(bb[2] - 0.1, -HW), min(bb[3] + 0.1, HW), S.Z_PCB1, bb[5] + 0.1)
    return f


# ---------------------------------------------------------------- bottom shell
def bottom_shell():
    """Floor plate (inset in the top shell's bore, sealed by bottom_seal) + motor-zone and antenna-end blocks, snap
    bumps, pin guide bores, flush magnets, battery PCM recess, pry notches."""
    top = S.Z_PCB0 - S.GAP
    b = slab(2 * PLATE_HL, 2 * PLATE_HW, IN_R - SEAL_GAP, 0, S.FLOOR)
    blocks = slab(S.CAV_L - 2 * FIT, S.CAV_W - 2 * FIT, IN_R - FIT, S.FLOOR - 0.01, top)
    b += blocks & (box(-HL, X_MZ1, -HW, HW, 0, top) + box(S.BAT_X1 + 0.25, HL, -HW, HW, 0, top))
    b -= cyl(S.MOTOR_X, 0, MOTOR_Z0, top + 1, MOTOR_POCKET)                             # motor stands on the floor
    b -= box(-HL - 1, X_MZ1 + 1, -1.2, 1.2, MOTOR_Z0, top + 1)                          # lead room, open both ends
    for x, y in POGO_XY:                                                                 # pogo seal ring seats
        b -= cyl(x, y, S.Z_PCB0 - 0.03 - POGO_GASKET, top + 1, POGO_RING_D + 0.1)
    for sy in (-1, 1):
        b -= cyl(MAG_X, sy * MAG_Y, -1, MAG_T, MAG_D)                                    # magnets: press-fit, flush
        b -= box(-HL - 1, S.BAT_X0, sy * (S.POGO_Y + 1.2), sy * (HW + 1), MAG_T + 0.45, top + 1)   # battery leads
    for x, y in POGO_XY:                                                                 # charger pin guide bores
        b -= cyl(x, y, -1, top + 1, PIN_BORE)
        b -= Pos(x, y, -0.01) * Cone(PIN_BORE / 2 + 0.3, PIN_BORE / 2, 0.31, align=(Align.CENTER, Align.CENTER, Align.MIN))
    b -= box(S.BAT_X0 - 0.05, S.BAT_X0 + BAT_RECESS_L, -S.BAT_W / 2 + 0.25, S.BAT_W / 2 - 0.25,
             S.FLOOR - BAT_RECESS, S.FLOOR + 0.01)                                        # PCM end recess
    for sx in (-1, 1):
        for sy in (-1, 1):
            b += snap_bump(sx, sy)
        b -= box(sx * (PLATE_HL - PRY_L), sx * (PLATE_HL + 0.5), -PRY_W / 2, PRY_W / 2, -1, PRY_DEPTH)   # pry notch
    return b - bottom_seal()                                                             # the seal ring's slot


# ---------------------------------------------------------------- captured soft parts
def bezel_gasket(t=S.BEZEL_GASKET):
    """TPU 90A frame between the lip and the glass border, over the glass-edge slit; seat cut for the mic vent."""
    g = slab(S.DISP_L + 2 * GLASS_FIT, S.DISP_W + 2 * GLASS_FIT, 1.0, S.Z_DISP1, S.Z_DISP1 + t, x=S.DISP_CX)
    g -= window(S.Z_DISP1 - 1, 3, -GASKET_REVEAL)                  # reveal: accent ring inside the window
    vx0, vx1, vy0, vy1 = vent_box()
    return g - box(vx0 - 0.05, vx1 + 0.05, vy0 - 0.05, vy1 + 0.05, S.Z_DISP1 - 1, S.Z_DISP1 + 1)


def cushions(t=CUSHION_T):
    """TPU 90A blocks under the 4 glass corners, on the PCB's part-free ledge zones: push the glass up into the
    gasket; located by the shell's corner blocks / antenna block and the cushion locators."""
    out = []
    for sy in (-1, 1):
        for xa, xb in ((S.DISP_X0 - GLASS_FIT + 0.05, S.DISP_X0 + S.LEDGE),
                       (S.DISP_X1 - S.LEDGE, S.DISP_X1 + GLASS_FIT - 0.05)):
            out.append(box(xa, xb, sy * (S.LEDGE_Y + 0.05), sy * (Y_TOP - 0.05), S.Z_PCB1, S.Z_PCB1 + t))
    return union(out)


def bottom_seal(squeeze=0.0):
    """TPU 90A ring in the radial gap between the floor plate and the top shell's bore (radial seal: no axial load
    on the snaps). squeeze: per-side oversize (printed part)."""
    g = SEAL_GAP + squeeze
    ring = slab(S.CAV_L + 2 * squeeze, S.CAV_W + 2 * squeeze, IN_R + squeeze, 0, S.FLOOR)
    return ring - slab(2 * (HL - g), 2 * (HW - g), IN_R - g, -1, S.FLOOR + 1)


def pogo_seals(t=POGO_GASKET):
    """Four TPU 90A rings in counterbores around the pin bores, squeezed against the PCB around each pad: seal the
    bores from the inside."""
    z1 = S.Z_PCB0 - 0.03
    return union([cyl(x, y, z1 - t, z1, POGO_RING_D) - cyl(x, y, z1 - t - 1, z1 + 1, POGO_SEAL_D) for x, y in POGO_XY])


def motor_pad(extra=0.0):
    """TPU 90A H-shaped pad on the motor can: the bar runs between the two lead joints, the cross bars key into the
    motor pocket so it cannot slide; the closed case holds the motor on the floor."""
    z0, z1, x = MOTOR_Z0 + S.MOTOR_T, S.Z_PCB0 - 0.03 + extra, S.MOTOR_X
    h = box(x - MOTOR_PAD_W / 2, x + MOTOR_PAD_W / 2, -2.9, 2.9, z0, z1)
    h += union([box(x - 1.8, x + 1.8, sy * 2.1, sy * 2.9, z0, z1) for sy in (-1, 1)])
    return h & cyl(x, 0, z0 - 1, z1 + 1, MOTOR_POCKET - 0.1)


# ---------------------------------------------------------------- PETG-CF variant: plain-PETG inserts
def cf_windows(ant_bb):
    """[(name, region, flange)]: top-shell zones within TOUCH_CF_CLEAR of antenna copper / touch electrodes become
    PETG inserts; each has a flange the CF shell overlaps from outside by CF_LAP (it cannot fall out)."""
    c = TOUCH_CF_CLEAR
    ya = max(abs(ant_bb.min.Y), abs(ant_bb.max.Y)) + c
    za = min(ant_bb.min.Z, S.Z_PCB1) - c - 0.01
    out = [("antenna_window", box(S.DISP_X1 + GLASS_FIT - 0.01, OL + 1, -ya, ya, za, Z_LIP0),
            box(S.DISP_X1 + GLASS_FIT - 0.01, HL + (OL - HL) / 2, -ya - CF_LAP, ya + CF_LAP, za - CF_LAP, Z_LIP0))]
    for x in S.TOUCH_X:
        for sy in (-1, 1):
            out.append(("touch_window", box(x - WIN_X, x + WIN_X, sy * (Y_TOP - 0.01), sy * (OW + 1), za, Z_LIP0),
                        box(x - WIN_X - CF_LAP, x + WIN_X + CF_LAP, sy * (Y_TOP - 0.01), sy * (OW - 0.4), za - CF_LAP, Z_LIP0)))
    return out


def cf_split(top, ant_bb):
    """-> CF top shell, PETG antenna window, PETG touch windows (4 solids)."""
    wins = cf_windows(ant_bb)
    cut = union([r + fl for _, r, fl in wins])
    ant = union([top & (r + fl) for n, r, fl in wins if n == "antenna_window"])
    tw = union([top & (r + fl) for n, r, fl in wins if n == "touch_window"])
    return top - cut, ant, tw


def carbon_keepouts(ant_bb):
    """Boxes no carbon may enter: antenna copper and each touch electrode, grown by TOUCH_CF_CLEAR."""
    c = TOUCH_CF_CLEAR
    boxes = [box(ant_bb.min.X - c, ant_bb.max.X + c, ant_bb.min.Y - c, ant_bb.max.Y + c, ant_bb.min.Z - c, ant_bb.max.Z + c)]
    boxes += [box(x - S.TOUCH_L / 2 - c, x + S.TOUCH_L / 2 + c, sy * (TOUCH_Y - S.TOUCH_W / 2 - c),
                  sy * (TOUCH_Y + S.TOUCH_W / 2 + c), S.Z_PCB1 - c, S.Z_PCB1 + c) for x in S.TOUCH_X for sy in (-1, 1)]
    return boxes


# ---------------------------------------------------------------- magnetic charging head
def pin_geom():
    """Spring pin z levels in the watch frame (puck face = case back = z 0): tip, barrel top/bottom, collar, tail."""
    tip_free = S.Z_PCB0 - 0.03 + PIN_PRELOAD
    btop = tip_free - PIN["tip"]
    bbot = btop - (PIN["length"] - PIN["tip"] - PIN["collar_t"] - PIN["tail"])
    return dict(tip_free=tip_free, tip_docked=S.Z_PCB0 - 0.03, btop=btop, bbot=bbot,
                cbot=bbot - PIN["collar_t"], tbot=bbot - PIN["collar_t"] - PIN["tail"])


def charger_pins(docked=True):
    g = pin_geom()
    tip = g["tip_docked"] if docked else g["tip_free"]
    out = []
    for x, y in POGO_XY:
        out += [cyl(x, y, g["btop"] - 0.3, tip, PIN["plunger"]), cyl(x, y, g["bbot"], g["btop"], PIN["barrel"]),
                cyl(x, y, g["cbot"], g["bbot"], PIN["collar"]), cyl(x, y, g["tbot"], g["cbot"], PIN["barrel"])]
    return union(out)


def charger():
    """Magnetic cable head in the watch frame, docked. -> dict of parts (puck_top, puck_base, pins, puck_magnets,
    cable, boot). Two snapped PETG halves capture the pin collars and clamp the cable; no glue."""
    g = pin_geom()
    x0, x1 = PUCK_X
    xc, L = (x0 + x1) / 2, x1 - x0
    env = slab(L, 2 * PUCK_HW, 1.6, -PUCK_H, 0, x=xc)
    lip_x0 = max(x0, -OL + R_PLAN + 0.5)                       # lips only where the case side is straight
    lips = box(lip_x0, x1, -PUCK_HW, PUCK_HW, -0.01, PUCK_LIP) - box(lip_x0 - 1, x1 + 1, -OW + 0.6, OW - 0.6, -1, 5)
    env += lips & slab(L, 2 * PUCK_HW, 1.6, -1, PUCK_LIP, x=xc)
    env -= body_skin(grow=0.1)                                  # cradle: the case back + 0.1
    inner = slab(L - 2 * PUCK_WALL, 2 * (PUCK_HW - PUCK_WALL), 0.8, -PUCK_H - 1, -PUCK_TOP_T, x=xc)
    top = env - inner
    zb = -PUCK_H + 0.8                                          # base plate top
    base = slab(L - 2 * PUCK_WALL - 0.1, 2 * (PUCK_HW - PUCK_WALL) - 0.1, 0.75, -PUCK_H, zb, x=xc)
    for x, y in POGO_XY:
        base += cyl(x, y, zb - 0.01, g["cbot"], 1.6)                                     # posts push the collars up
        base -= cyl(x, y, zb - 1, g["cbot"] + 1, PIN["barrel"] + 0.06)                   # solder cup
        top -= cyl(x, y, -PUCK_TOP_T - 1, 1, PIN["barrel"] + 0.04)                      # barrel bore
        top -= cyl(x, y, -PUCK_TOP_T - 1, g["bbot"], PIN["collar"] + 0.05)              # collar seat from below
    mags = []
    for sy in (1, -1):                       # puck magnets go in from inside under a PUCK_SKIN face; base posts hold them
        top -= cyl(MAG_X, sy * MAG_Y, -PUCK_TOP_T - 1, -PUCK_SKIN, MAG_D)
        mags.append(cyl(MAG_X, sy * MAG_Y, -PUCK_SKIN - PUCK_MAG_T, -PUCK_SKIN, MAG_D))
        base += cyl(MAG_X, sy * MAG_Y, zb - 0.01, -PUCK_SKIN - PUCK_MAG_T - 0.02, 2.4)
    for sx in (-1, 1):                                                                   # base snaps into the skirt
        bump = box(xc + sx * (L / 2 - PUCK_WALL - 0.3), xc + sx * (L / 2 - PUCK_WALL + 0.2), -2.0, 2.0, zb - 0.55, zb - 0.25)
        base += bump
        top -= Pos(0, 0, 0) * box(xc + sx * (L / 2 - PUCK_WALL - 0.1), xc + sx * (L / 2 - PUCK_WALL + 0.25), -2.15, 2.15,
                                  zb - 0.6, zb - 0.2)
    cx, cz = S.MOTOR_X + S.POGO_DX + 2.2, CABLE_Z                                         # cable: +Y, low, beside the pins
    chan = Pos(cx, (PUCK_HW + 2) / 2, cz) * Rot(90, 0, 0) * Cylinder(CABLE_D / 2 - 0.1, PUCK_HW + 2)
    top -= Pos(cx, PUCK_HW - 0.4, cz) * Rot(90, 0, 0) * Cylinder(1.75, 1.2)              # boot flange seat + exit hole
    top -= chan
    base -= chan
    for yr in (3.0, 5.0):                                                                # strain-relief teeth bite the jacket
        base += box(cx - CABLE_D / 2, cx + CABLE_D / 2, yr - 0.2, yr + 0.2, cz - CABLE_D / 2 - 0.2, cz - CABLE_D / 2 + 0.25)
    cable = Pos(cx, (PUCK_HW + 14) / 2 + 1.0, cz) * Rot(90, 0, 0) * Cylinder(CABLE_D / 2, PUCK_HW + 12)
    boot = (Pos(cx, PUCK_HW + 2.5, cz) * Rot(90, 0, 0) * Cone(1.75, 1.55, 5.0)
            + Pos(cx, PUCK_HW - 0.35, cz) * Rot(90, 0, 0) * Cylinder(1.7, 0.8))
    boot -= Pos(cx, PUCK_HW + 2, cz) * Rot(90, 0, 0) * Cylinder(CABLE_D / 2 - 0.05, 8)
    return dict(puck_top=top, puck_base=base, pins=charger_pins(True), puck_magnets=union(mags),
                cable=cable, boot=boot)


# ---------------------------------------------------------------- assembly of printed + captured parts
def case_parts(style=None, variant="petg"):
    """All case parts at their installed size. variant 'petg': one-piece PETG top shell; 'cf': CF top shell +
    PETG inserts (needs the antenna copper bbox)."""
    top = top_shell(style) - touch_thin()
    m = dict(top_shell=top, bottom_shell=bottom_shell(), bezel_gasket=bezel_gasket(), cushions=cushions(),
             bottom_seal=bottom_seal(), pogo_seals=pogo_seals(), motor_pad=motor_pad(), mic_seal=mic_seal(), vent=vent())
    if variant == "cf":
        m["top_shell_cf"], m["antenna_window"], m["touch_windows"] = cf_split(top, ANT_BB)
        del m["top_shell"]
    return m


# ---------------------------------------------------------------- build + checks
def vol(s):
    try:
        return s.volume if s is not None else 0.0
    except Exception:
        return 0.0


def interference(a, b):
    ba, bb = a.bounding_box(), b.bounding_box()
    if (ba.min.X > bb.max.X or bb.min.X > ba.max.X or ba.min.Y > bb.max.Y or bb.min.Y > ba.max.Y
            or ba.min.Z > bb.max.Z or bb.min.Z > ba.max.Z):
        return 0.0
    try:
        return vol(a & b)
    except Exception:
        return 0.0


def build():
    global MIC_PORT, MIC_PORT_R, MIC_BOX, RELIEFS, ANT_BB
    board, groups, comps, note = load_board()
    port, MIC_PORT_R, mbox = find_mic(comps)
    if port:
        MIC_PORT, MIC_BOX = port, mbox
        if S.DISP_X0 < port[0] < S.DISP_X1 and abs(port[1]) < S.DISP_W / 2:
            print(f"WARNING: mic port in the STEP is under the glass (|y| {abs(port[1]):.2f}); rotate MIC1 so the port "
                  f"faces the board edge")
        if abs(abs(port[1]) - (S.MIC_Y + 0.6)) > 0.05 or abs(port[0] - S.MIC_X) > 0.05:
            print(f"NOTE: STEP mic port ({port[0]:.2f}, {port[1]:+.2f}) differs from spec MIC_X/MIC_Y + 0.6")
    ant = groups.get("antenna") or box(S.ANT_X0 - 0.45, S.PCB_L / 2 - 0.35, -6.1, 6.1, S.Z_PCB1 - 0.035, S.Z_PCB1)
    ANT_BB = ant.bounding_box()
    probe = top_shell(probe=True)                       # frame before reliefs: which parts poke into it?
    RELIEFS = []
    for ref, val, sh in comps:
        if ref.startswith("MIC") or interference(probe, sh) < 1e-3:
            continue
        bb = sh.bounding_box()
        RELIEFS.append((ref, val, (bb.min.X, bb.max.X, bb.min.Y, bb.max.Y, bb.min.Z, bb.max.Z)))
    tail, stiff, fit = fpc()
    bat, leads = battery()
    m = case_parts()
    m["variant_cf"] = case_parts(variant="cf")
    m.update(display=display(), fpc=tail, stiffener=stiff, pcb=board, battery=bat, bat_leads=leads,
             watch_magnets=union(watch_magnets()), bars=spring_bars(), rf_pin=rf_pin(), strap=nato())
    m.update(groups)
    m["pads"], m["touch"] = pads(), touch_pads()
    m["motor"], m["motor_leads"] = motor()
    m.update(charger())
    return m, fit, comps, note


SHELLS = ["top_shell", "bottom_shell"]
SOFT = ["bezel_gasket", "vent", "cushions", "bottom_seal", "pogo_seals", "motor_pad", "mic_seal"]
CASE = SHELLS + SOFT
INTERNAL = ["display", "fpc", "stiffener", "pcb", "qfn", "ffc", "chips", "switches", "touch", "antenna", "pads",
            "battery", "bat_leads", "watch_magnets", "motor", "motor_leads"]
CHARGER = ["puck_top", "puck_base", "pins", "puck_magnets", "cable", "boot"]
LOOSE = {  # captured part -> (directions it may legitimately move 0.3 mm in the model, why)
    "bezel_gasket": ((), ""), "vent": ((), ""), "cushions": ((), ""), "mic_seal": ((), ""), "motor_pad": ((), ""),
    "pogo_seals": ((), ""), "display": ((), ""), "pcb": ((), ""), "motor": ((), ""),
    "bottom_seal": (("-z",), "radially squeezed, friction"), "watch_magnets": (("-z",), "press-fit"),
    "battery": (("+z",), "0.3 swell gap by design; leads + pocket hold it"),
}
E_PETG, E_PETG_CF, E_TPU90 = 2000.0, 3500.0, 15.0   # MPa, rough printed values
MU = 0.3


def ear_roots(f):
    """Cross-section areas (mm^2) of the four ears just past the case ends."""
    return [g.area for sx in (-1, 1)
            for g in (f & (Plane(origin=(sx * (OL + 0.3), 0, 0), z_dir=(1, 0, 0)) * Rectangle(400, 400))).faces()]


def pogo_vs_pcb():
    """[(net, physical xy, net of the PCB pad found there)] for the dock pins, from the newest .kicad_pcb."""
    import re
    fps, _ = kicad_footprints()
    pads = [((f["x"] - 100, 100 - f["y"]), re.findall(r'\(net (?:\d+ )?"([^"]+)"\)', f["body"]))
            for f in fps if f["layer"] == "B.Cu"]
    out = []
    for x, y, net in POGO:
        hit = [n for (px, py), n in pads if math.dist((px, py), (x, y)) < 0.05]
        out.append((net, (x, y), hit[0][0] if hit and hit[0] else None))
    return out


def play(m, key, others, step=0.3):
    """Directions a captured part can move `step` mm without touching anything in the closed case."""
    free = []
    for i, ax in enumerate("xyz"):
        for sg in (-1, 1):
            d = [0.0, 0.0, 0.0]
            d[i] = sg * step
            moved = Pos(*d) * m[key]
            if not any(interference(moved, m[o]) > 1e-4 for o in others if o != key and o in m):
                free.append(("+" if sg > 0 else "-") + ax)
    return free


def snap_numbers(E=E_PETG):
    """Per snap at each end: wall stiffness (cantilever strip from the stiff block above), deflection force, strain,
    closing and opening force (wedge with friction)."""
    out = {}
    for sx, z_top in ((-1, S.Z_DISP0 + FPC_T + 0.05 - 0.42), (1, S.Z_PCB1 + S.GAP)):
        H = z_top - SNAP_Z
        w = SNAP_W + 2 * H
        k = 3 * E * (w * S.WALL ** 3 / 12) / H ** 3
        f = k * SNAP_DEPTH
        wedge = lambda a: (math.tan(math.radians(a)) + MU) / (1 - MU * math.tan(math.radians(a)))
        out[sx] = dict(H=H, k=k, f=f, strain=3 * S.WALL * SNAP_DEPTH / (2 * H * H), close=f * wedge(SNAP_RAMP),
                       open=f * wedge(SNAP_RET))
    return out


def stack_numbers():
    """Axial preload the snaps carry (N): soft parts squeezed between the shells, and the radial seal balance."""
    a_cush = 4 * (S.LEDGE + GLASS_FIT - 0.05) * (Y_TOP - S.LEDGE_Y - 0.1)
    cush = E_TPU90 * (PRINT_T["cushions"] - CUSHION_T) / PRINT_T["cushions"] * a_cush
    rings = E_TPU90 * (PRINT_T["pogo_seals"] - POGO_GASKET) / PRINT_T["pogo_seals"] * 4 * math.pi / 4 * (POGO_RING_D ** 2 - POGO_SEAL_D ** 2)
    pad_h = S.Z_PCB0 - 0.03 - MOTOR_Z0 - S.MOTOR_T
    pad = E_TPU90 * 0.1 / (pad_h + 0.1) * MOTOR_PAD_W * (S.MOTOR_D - 1.6)
    gasket_area = (S.DISP_L + 2 * GLASS_FIT) * (S.DISP_W + 2 * GLASS_FIT) - (S.DISP_AA_L + 2 * WIN_M) * (S.DISP_AA_W + 2 * WIN_M)
    # radial bottom seal: printed SEAL_GAP + 2 SEAL_SQUEEZE in SEAL_GAP; the long walls (cantilevers from the upper
    # wall at Z_STEP) are the spring, the TPU ring nearly rigid in comparison
    H = Z_STEP - S.FLOOR / 2
    k_wall = 3 * E_PETG * (S.WALL ** 3 / 12) / H ** 3                       # N/mm per mm of wall
    k_ring = E_TPU90 * S.FLOOR / SEAL_GAP
    d_wall = 2 * SEAL_SQUEEZE * k_ring / (k_ring + k_wall)
    q = k_wall * d_wall
    return dict(cushions=cush, rings=rings, pad=pad, gasket_p=cush / gasket_area, wall_bulge=d_wall, seal_q=q,
                seal_p=q / (S.FLOOR - 0.07), total=cush + rings + pad)


def checks(m, fit, comps):
    ok = True

    def verdict(good, text):
        nonlocal ok
        ok &= bool(good)
        print(f"  {'ok ' if good else 'BAD'} {text}")

    def near(name, got, want):
        verdict(abs(got - want) <= 0.05, f"{name:<22} {got:7.2f}  (spec {want:.2f})")
    v = m["variant_cf"]
    print("dimension checks")
    body = union([m[k] for k in SHELLS]) & box(-OL, OL, -OW - 1, OW + 1, -1, S.CASE_T + 1)
    bb = body.bounding_box()
    near("body length", bb.size.X, S.CASE_L)
    near("body width", bb.size.Y, S.CASE_W)
    near("total thickness", bb.size.Z, S.CASE_T)
    lug = m["top_shell"].bounding_box()
    print(f"  shape '{SHAPE}' {SHAPES[SHAPE]}, lug-to-lug {lug.size.X:.2f} mm (+{(lug.size.X - S.CASE_L) / 2:.2f} per end); "
          f"+X bar axis {X_BAR - OL:.2f} past the end face, {X_BAR - S.PCB_L / 2:.2f} past the PCB edge, "
          f"{X_BAR - ANT_BB.max.X:.2f} (surface {X_BAR - ANT_BB.max.X - BAR_D / 2:.2f}) past the antenna copper")
    want = dict(top_shell=1, bottom_shell=1, top_shell_cf=1, antenna_window=1, touch_windows=4, bottom_seal=1,
                bezel_gasket=1, cushions=4, pogo_seals=4, puck_top=1, puck_base=1)
    got = {k: len((m[k] if k in m else v[k]).solids()) for k in want}
    verdict(got == want, "solid counts: " + ", ".join(f"{k} {c}" for k, c in got.items()))
    roots = ear_roots(m["top_shell"])
    a_min = min(roots) if roots else 0
    verdict(len(roots) == 4 and a_min >= 3.0, f"ears: {len(roots)} attached, root sections "
            f"{', '.join(f'{a:.2f}' for a in roots)} mm^2 (2026-10-04: 3.61)")
    e, h = EAR_R - BAR_TIP_HOLE / 2, a_min / EAR_W
    print(f"  per bar (2 ears, PETG): tip bearing {2 * 40 * 0.8 * min(EAR_W, 0.8):.0f} N (0.8 tip, 40 MPa), tear-out "
          f"{2 * 2 * e * EAR_W * 20:.0f} N (layer shear 20 MPa), root bending {2 * 45 * EAR_W * h * h / 6 / (BAR_DX - 0.3):.0f} N "
          f"(45 MPa, {h:.1f} tall root, lever {BAR_DX - 0.3:.2f})")
    ang, where = ear_overhang()
    verdict(ang >= 40, f"ear tops print lip-down unsupported: flattest {ang:.0f} deg at {where} (more than 0.8 above "
            f"the bed; >= 40)")
    walls = min_wall(m["top_shell"], S.FLOOR + 0.05, Z_LIP0 - 0.05)
    (wt, _), (wv, _), (ws, _), (wp, wherep) = walls["touch"], walls["vent"], walls["snap"], walls["plain"]
    verdict(wp >= MIN_WALL - 0.01 and wt >= TOUCH_FACE - 0.01 and wv >= VENT_WALL - 0.01 and ws >= 0.5,
            f"thinnest top-shell wall {wp:.2f} mm at {wherep} (>= {MIN_WALL}, nominal {S.WALL}); touch faces "
            f"{wt:.2f} (by design {TOUCH_FACE}); behind the snap recesses {ws:.2f} (>= 0.5); over the mic vent seat "
            f"{wv:.2f} (>= {VENT_WALL})")
    verdict(abs(v["top_shell_cf"].bounding_box().size.X - 2 * EAR_TIP) < 0.05, "CF variant: the ears are on the CF shell")
    near_cf = max(interference(v["top_shell_cf"], b) for b in carbon_keepouts(ANT_BB))
    verdict(near_cf < 1e-3, f"CF variant: no carbon within {TOUCH_CF_CLEAR} mm of antenna copper or touch electrodes "
            f"({near_cf:.4f} mm^3)")
    print(f"  FPC: tip {fit['insertion']:.2f} mm into the FFC body ({FFC_D} deep), "
          f"{'slack %.2f' % fit['slack'] if fit['slack'] > 0 else 'short of the back by %.2f' % fit['short']} mm")
    for net, (x, y), got_net in pogo_vs_pcb():
        verdict(got_net in (net, None), f"charger pin {net:<6} at ({x:+.2f}, {y:+.2f}): PCB pad there is "
                f"{got_net or 'not found (no .kicad_pcb?)'}")

    print("closure: snaps, seal, preload")
    for E, name in ((E_PETG, "PETG"), (E_PETG_CF, "PETG-CF")):
        sn = snap_numbers(E)
        for sx, d in sn.items():
            good = d["strain"] <= (0.035 if name == "PETG" else 0.025)
            verdict(good, f"{name} snap at {'-X' if sx < 0 else '+X'}: {SNAP_DEPTH} engagement, wall {d['H']:.1f} free -> "
                    f"{d['f']:.1f} N to flex, strain {100 * d['strain']:.1f} %, close {d['close']:.0f} N, "
                    f"open {d['open']:.0f} N per bump")
    st = stack_numbers()
    sn = snap_numbers()
    hold = 2 * (sn[-1]["open"] + sn[1]["open"])
    verdict(st["total"] < hold / 3, f"preload on the snaps {st['total']:.0f} N (cushions {st['cushions']:.0f}, pogo rings "
            f"{st['rings']:.0f}, motor pad {st['pad']:.0f}) vs {hold:.0f} N to pop all four")
    print(f"  bezel gasket contact {st['gasket_p']:.2f} MPa from the cushions; bottom seal (radial, no snap load): "
          f"walls spring out {st['wall_bulge']:.3f} mm, {st['seal_q']:.2f} N/mm ({st['seal_p']:.2f} MPa) on the TPU ring")
    others = SHELLS + SOFT + ["display", "fpc", "pcb", "battery", "motor", "motor_leads", "bat_leads", "watch_magnets",
                              "qfn", "ffc", "chips", "switches"]
    for k, (allowed, why) in LOOSE.items():
        free = play(m, k, others)
        extra = [d for d in free if d not in allowed]
        verdict(not extra, f"{k:<14} located: free 0.3 mm moves {free or 'none'}" + (f" ({why})" if free else ""))
    for k in ("antenna_window", "touch_windows"):
        mm = dict(m, top_shell=v["top_shell_cf"], **{k: v[k]})
        free = play(mm, k, others + [k])
        verdict(not free, f"CF {k:<14} located: free 0.3 mm moves {free or 'none'}")

    print("interference checks (mm^3)")
    assert interference(m["battery"], Pos(0, 0, 1) * m["battery"]) > 100, "interference check is blind"
    pairs = [(c, i) for c in CASE for i in INTERNAL if i in m]
    pairs += [(a, b) for i, a in enumerate(CASE) for b in CASE[i + 1:]]
    pairs += [(k, "rf_pin") for k in CASE] + [(k, "bars") for k in CASE]
    pairs += [("strap", k) for k in CASE + ["bars", "rf_pin"]]
    pairs += [("motor", k) for k in ["battery", "bat_leads", "watch_magnets", "pcb", "motor_pad"]]
    pairs += [(c, w) for c in CHARGER for w in SHELLS + ["watch_magnets", "pcb", "strap"] if not (c == "pins" and w == "pcb")]
    clamp = [{"cable", "boot"}, {"cable", "puck_top"}, {"cable", "puck_base"}]          # the halves squeeze the cable
    pairs += [(a, b) for i, a in enumerate(CHARGER) for b in CHARGER[i + 1:] if {a, b} not in clamp]
    gap = S.Z_PCB0 - (MOTOR_Z0 + S.MOTOR_T)
    print(f"  motor {S.MOTOR_D:g} x {S.MOTOR_T:g} on the floor in a {MOTOR_POCKET:.1f} pocket, {gap:.2f} to the PCB "
          f"(motor_pad + soldered leads); battery {S.BAT_L:.1f} x {S.BAT_W:g} x {S.BAT_T:g}, PCM end "
          f"{S.BAT_T + BAT_PCM_EXTRA:g} thick in a {BAT_RECESS} recess ({S.FLOOR - BAT_RECESS:.2f} floor left, "
          f"{S.Z_PCB0 - (S.FLOOR - BAT_RECESS + S.BAT_T + BAT_PCM_EXTRA):.2f} under the PCB)")
    print(f"  straps {STRAP_W:.0f} mm on {BAR_D} spring bars: ears {EAR_W:.2f} wide, drilled {BAR_TIP_HOLE} through, "
          f"{EAR_R - BAR_TIP_HOLE / 2:.2f} mm around the hole; bar axis z {Z_BAR:.2f} "
          f"(strap {Z_BAR - STRAP_R:.2f}..{Z_BAR + STRAP_R:.2f} of {S.CASE_T:.2f})")
    for swing in (-30, 45, 90):
        hit = max(interference(nato(swing), m[k]) for k in CASE + ["bars", "rf_pin"])
        verdict(hit < 1e-3, f"strap swung {swing:+d} deg about the bar: {hit:.4f} mm^3 against the case")
    x, y, z = mic_port()
    xd, yd = duct_xy()
    inner, outer, side = mic_seal_walls()
    print(f"  mic port {2 * MIC_PORT_R:.2f} at ({x:.2f}, {y:+.2f}, z {z:.2f}): edge {abs(y) - MIC_PORT_R - S.DISP_W / 2:+.2f} "
          f"from the glass edge; duct {MIC_BORE} groove at |y| {abs(yd):.2f}; seal ring walls {inner:.2f} (under the "
          f"glass) / {outer:.2f} (lid edge) / {side:.2f}; vent {vent_box()[1] - vent_box()[0]:.2f} x "
          f"{abs(vent_box()[3] - vent_box()[2]):.2f}; outlet {MIC_HOLE}")
    g = pin_geom()
    force = 4 * (PIN["f0"] + PIN["k"] * PIN_PRELOAD)
    verdict(force < MAG_PULL / 1.5, f"charger: 4 pins x {PIN_PRELOAD} preload = {force:.2f} N vs magnets {MAG_PULL:.1f} N "
            f"(hold margin {MAG_PULL / force:.1f}x); pin barrel {g['btop']:.2f} mm into the {PIN_BORE} bores, "
            f"stroke used {PIN_PRELOAD}/{PIN['stroke']}")
    worst = 0.0
    for a, b in pairs:
        val = interference(m[a], m[b])
        worst = max(worst, val)
        if val > 1e-3:
            ok = False
            print(f"  BAD {a} x {b}: {val:.4f}")
    print(f"  {len(pairs)} pairs, worst {worst:.5f}")
    hits = []
    for ref, val, sh in comps:   # every component body vs case, glass, battery, FPC
        for k in CASE + ["display", "battery"] + ([] if ref.startswith("J") else ["fpc", "stiffener"]):
            vv = interference(m[k], sh)
            if vv > 1e-3:
                hits.append(f"{ref} {val} x {k}: {vv:.3f}")
    for ref, val, bb in RELIEFS:
        print(f"  NOTE frame relieved for {ref} {val} (x {bb[0]:.1f}..{bb[1]:.1f}, y {bb[2]:.1f}..{bb[3]:.1f}, "
              f"top z {bb[5]:.2f}) - move it inboard or lower it to drop the pocket")
    print(f"  per-component: {len(comps)} bodies, {len(hits)} collisions")
    for h in hits:
        print("  BAD", h)
    return ok and not hits


PRINT = {  # part -> (folder, filament, rotation into print orientation, note)
    "top_shell": ("petg", "PETG Basic / Matte", (180, 0, 0), "lip face down on the plate, 0.4 nozzle, 0.1 layers, no supports"),
    "bottom_shell": ("petg", "PETG Basic / Matte", (0, 0, 0), "floor down, 0.4 nozzle, 0.1 layers, no supports"),
    "bezel_gasket": ("tpu", "TPU 90A", (0, 0, 0), "flat, 2 x 0.08 layers, 15 mm/s from the external spool"),
    "cushions": ("tpu", "TPU 90A", (0, 0, 0), "4 blocks, printed 0.1 tall (squeezed 8 %)"),
    "bottom_seal": ("tpu", "TPU 90A", (0, 0, 0), f"ring {SEAL_GAP + 2 * SEAL_SQUEEZE:.2f} wide x {S.FLOOR} tall, 0.1 layers"),
    "pogo_seals": ("tpu", "TPU 90A", (0, 0, 0), "4 rings, printed 0.05 tall"),
    "motor_pad": ("tpu", "TPU 90A", (0, 0, 0), "strip, printed 0.1 tall"),
    "mic_seal": ("tpu", "TPU 90A", (0, 0, 0), "printed 0.30; die-cut PORON 0.3 is better"),
    "top_shell_cf": ("variant-cf", "PETG-CF", (180, 0, 0), "lip down; hardened 0.4 (0.6 recommended), modest fan"),
    "antenna_window": ("variant-cf", "PETG, matched", (180, 0, 0), "matte, colour-matched (INSERTS); drops in from inside"),
    "touch_windows": ("variant-cf", "PETG, matched", (180, 0, 0), "4 inserts, flush with the skin; drop in from inside"),
    "puck_top": ("charger", "PETG Basic", (180, 0, 0), "face down, no supports"),
    "puck_base": ("charger", "PETG Basic", (0, 0, 0), "plate down"),
    "boot": ("charger", "TPU 90A", (90, 0, 0), "upright, slow"),
}
DENSITY = {"PETG-CF": 1.29e-3, "PETG": 1.27e-3, "TPU": 1.21e-3}


def printable(m, k):
    """Part in print orientation, at its printed (uncompressed) size."""
    extra = {"bezel_gasket": lambda: bezel_gasket(PRINT_T["bezel_gasket"]), "cushions": lambda: cushions(PRINT_T["cushions"]),
             "bottom_seal": lambda: bottom_seal(SEAL_SQUEEZE), "pogo_seals": lambda: pogo_seals(PRINT_T["pogo_seals"]),
             "motor_pad": lambda: motor_pad(0.1), "mic_seal": lambda: mic_seal(PRINT_T["mic_seal"])}
    s = extra[k]() if k in extra else (m[k] if k in m else m["variant_cf"][k])
    s = Rot(*PRINT[k][2]) * s
    return Pos(0, 0, -s.bounding_box().min.Z) * s


def summary(m):
    print(f"\n{'part':<15} {'filament':<19} {'L x W x H (mm)':<20} {'g':>5}  print")
    for k, (_, mat, _, note) in PRINT.items():
        s = printable(m, k)
        sz = s.bounding_box().size
        dens = DENSITY["PETG-CF" if "CF" in mat else "TPU" if "TPU" in mat else "PETG"]
        print(f"{k:<15} {mat:<19} {sz.X:5.1f} x {sz.Y:5.1f} x {sz.Z:4.2f} {vol(s) * dens:6.2f}  {note}")


def export(m):
    import shutil
    import trimesh                       # 3MF via trimesh: OCCT's 3MF mesher rejects some filleted parts
    for folder in {f for f, *_ in PRINT.values()} | {"multi-material", "petg-cf"}:   # keeps cad/out/variant-thin/
        shutil.rmtree(OUT / folder, ignore_errors=True)
    kids = []
    for k, sh in m.items():
        if k == "variant_cf" or sh is None:
            continue
        sh.label = k
        sh.color = Color(COLORS.get(k, "#888888"))
        kids.append(sh)
    OUT.mkdir(parents=True, exist_ok=True)
    export_step(Compound(children=kids, label="horae_rev_a"), str(OUT / "horae-assembly.step"))
    for k, (folder, *_ ) in PRINT.items():
        (OUT / folder).mkdir(exist_ok=True)
        stl = OUT / folder / f"{k}.stl"
        export_stl(printable(m, k), str(stl), tolerance=0.005, angular_tolerance=0.1)
        trimesh.Scene({k: trimesh.load(stl)}).export(OUT / folder / f"{k}.3mf")


# ---------------------------------------------------------------- colours, materials
COLORWAYS = {  # name: (case filament, case hex, case finish, TPU filament, TPU hex, TPU finish, strap, strap hex)
    "Stealth": ("Bambu PETG-CF Black", "#2C2C2C", "cf", "TPU 95A HF Black", "#1A1C22", "tpu", "black FKM", "#1E1F21"),
    "Titanium": ("Bambu PETG-CF Titan Gray", "#5E5F60", "cf", "TPU 90A Quicksilver", "#9EA2A2", "tpu", "charcoal nylon", "#3A3C40"),
    "Arctic": ("Bambu PETG Matte White", "#E9E9E6", "matte", "TPU 90A Crystal Blue", "#7EB4E1", "tpu_clear", "white silicone", "#E6E6E2"),
    "Galaxy": ("Prusament PETG Galaxy Black", "#1E1F21", "glitter", "TPU 95A HF Blue", "#0072CE", "tpu", "navy", "#1F2A44"),
    "Indigo": ("Bambu PETG-CF Indigo Blue", "#46527A", "cf", "TPU 90A White", "#F2F2E6", "tpu", "navy", "#1F2A44"),
    "Malachite": ("Bambu PETG-CF Malachite Green", "#3A8F7C", "cf", "TPU 95A HF Black", "#1A1C22", "tpu", "black", "#1E1F21"),
    "Paper": ("Bambu PETG Basic Dark Beige", "#DBC8B6", "gloss", "TPU 90A Cocoa Brown", "#5C4738", "tpu", "tan leather", "#A97C55"),
    "Ember": ("Bambu PETG Matte Black", "#262628", "matte", "TPU 95A HF Red", "#C8102E", "tpu", "black", "#1E1F21"),
}
INSERTS = {  # CF colorways: plain-PETG antenna/touch windows, matte and colour-matched so they disappear (rendered
    # in the case colour, matte, without the carbon grain); pick the swatch closest to the printed CF part
    "Stealth": "Bambu PETG Matte Black", "Titanium": "grey PETG Basic (e.g. Gray, matched to the printed Titan Gray)",
    "Indigo": "navy PETG", "Malachite": "teal-green PETG"}
HERO = "Titanium"     # best in photos
FINISH = {  # PBR (metallic, roughness, texture, opacity)
    "gloss": (0.0, 0.2, None, 1.0), "satin": (0.0, 0.35, None, 1.0), "matte": (0.0, 0.62, None, 1.0),
    "cf": (0.0, 0.62, "cf", 1.0), "glitter": (0.0, 0.25, "glitter", 1.0), "tpu": (0.0, 0.52, None, 1.0),
    "matte_tile": (0.0, 0.62, "plain", 1.0),   # matte PETG through the same texture path as the CF it sits in
    "tpu_clear": (0.0, 0.42, None, 0.72), "metal": (1.0, 0.22, None, 1.0), "gold": (1.0, 0.28, None, 1.0),
    "pcb": (0.0, 0.45, None, 1.0), "plastic": (0.0, 0.45, None, 1.0), "epaper": (0.0, 0.85, None, 1.0),
    "strap": (0.0, 0.68, None, 1.0), "membrane": (0.0, 0.6, None, 1.0),
}
TECH_CASE, TECH_CASE2, TECH_TPU, TECH_INSERT = "#62666d", "#4c5056", "#e4572e", "#d9d3c3"
COLORS = dict(
    top_shell=TECH_CASE, bottom_shell=TECH_CASE2, top_shell_cf="#3b3e43", antenna_window=TECH_INSERT,
    touch_windows=TECH_INSERT, bezel_gasket=TECH_TPU, cushions=TECH_TPU, bottom_seal=TECH_TPU, pogo_seals=TECH_TPU,
    motor_pad=TECH_TPU, mic_seal=TECH_TPU, vent="#f4f4ef", boot=TECH_TPU, display="#dcdad1", fpc="#c8861a",
    stiffener="#9c6610", pcb="#1e5b3e", qfn="#2b2b2d", ffc="#e6dfca", chips="#3a3a3c", switches="#b9bec5",
    touch="#d9a92e", pads="#d9a92e", antenna="#c9a24a", battery="#c4c9cf", bat_leads="#d8b246",
    watch_magnets="#a8aeb5", motor="#a7adb4", motor_leads="#d8b246", bars="#cfd3d8", rf_pin="#cfd3d8",
    strap="#2b2d31", puck_top="#e8e6e1", puck_base="#d6d3cc", pins="#d8b246", puck_magnets="#a8aeb5", cable="#1e1f21",
)
ROLE = dict(  # part -> (colour source, finish): "case"/"tpu"/"strap"/"insert" follow the colorway
    top_shell="case", bottom_shell="case", top_shell_cf="case", antenna_window="insert", touch_windows="insert",
    bezel_gasket="tpu", cushions="tpu", bottom_seal="tpu", pogo_seals="tpu", motor_pad="tpu", mic_seal="tpu",
    strap="strap", vent="membrane", display="epaper", fpc="pcb", stiffener="pcb", pcb="pcb", qfn="plastic",
    ffc="plastic", chips="plastic", switches="metal", touch="gold", pads="gold", antenna="gold", battery="metal",
    bat_leads="gold", watch_magnets="metal", motor="metal", motor_leads="gold", bars="metal", rf_pin="metal",
    puck_top="gloss", puck_base="gloss", pins="gold", puck_magnets="metal", cable="strap", boot="tpu",
)
WATCH = SHELLS + SOFT + INTERNAL + ["bars", "rf_pin"]
_mesh_cache = {}
_tex_cache = {}


def pvmesh(shape, tol=0.004):
    """Triangle mesh (pyvista) of a shape, face by face, with normals taken from the exact surfaces (no shading seams
    where faces meet smoothly); faces OCCT cannot mesh are retried once, then skipped and counted."""
    import pyvista as pv
    from OCP.BRep import BRep_Tool
    from OCP.BRepAdaptor import BRepAdaptor_Surface
    from OCP.BRepBuilderAPI import BRepBuilderAPI_Copy
    from OCP.BRepLProp import BRepLProp_SLProps
    from OCP.BRepMesh import BRepMesh_IncrementalMesh
    from OCP.TopAbs import TopAbs_REVERSED
    from OCP.TopLoc import TopLoc_Location
    key = id(shape)
    if key in _mesh_cache:
        return _mesh_cache[key][1]
    BRepMesh_IncrementalMesh(shape.wrapped, tol, True, 0.12, True)
    pts, nrm, tris, bad = [], [], [], 0
    for f in shape.faces():
        loc = TopLoc_Location()
        tri = BRep_Tool.Triangulation_s(f.wrapped, loc)
        if tri is None:                                  # small faces can defeat the relative deflection: retry
            g = BRepBuilderAPI_Copy(f.wrapped, True, False).Shape()     # a copy with an absolute one
            BRepMesh_IncrementalMesh(g, 0.003, False, 0.12, False)
            f = type(f)(g)
            tri = BRep_Tool.Triangulation_s(f.wrapped, loc)
        if tri is None:
            bad += 1
            continue
        trsf, base = loc.Transformation(), len(pts)
        rev = f.wrapped.Orientation() == TopAbs_REVERSED
        props = BRepLProp_SLProps(BRepAdaptor_Surface(f.wrapped), 1, 1e-6)
        for i in range(1, tri.NbNodes() + 1):
            pts.append(tri.Node(i).Transformed(trsf).Coord())
            n = None
            if tri.HasUVNodes():
                uv = tri.UVNode(i)
                props.SetParameters(uv.X(), uv.Y())
                if props.IsNormalDefined():
                    d = props.Normal()
                    n = (-d.X(), -d.Y(), -d.Z()) if rev else (d.X(), d.Y(), d.Z())
            nrm.append(n)
        for i in range(1, tri.NbTriangles() + 1):
            a, b, c = tri.Triangle(i).Get()
            tris.append((base + a - 1, base + c - 1, base + b - 1) if rev else (base + a - 1, base + b - 1, base + c - 1))
    if bad:
        print(f"  (mesh: {bad} face(s) skipped)")
    mesh = pv.PolyData(np.array(pts, float), np.column_stack([np.full(len(tris), 3), np.array(tris)]).ravel())
    fallback = mesh.compute_normals(split_vertices=False, cell_normals=False, auto_orient_normals=False,
                                    consistent_normals=False)["Normals"]
    mesh.point_data["Normals"] = np.array([n if n is not None else fallback[i] for i, n in enumerate(nrm)], float)
    _mesh_cache[key] = (shape, mesh)
    return mesh


def linear_rgb(hexcol):
    """sRGB hex -> linear RGB: VTK's PBR takes plain base colours as linear (sRGB textures are converted), so
    passing the hex straight washes darks out (2C2C2C rendered mid-grey) and mismatches textured parts."""
    c = np.array([int(hexcol[i:i + 2], 16) for i in (1, 3, 5)], float) / 255
    return tuple(np.where(c <= 0.04045, c / 12.92, ((c + 0.055) / 1.055) ** 2.4))


def surface_texture(kind, hexcol):
    """Procedural albedo tiles: PETG-CF (fine fibre noise, faint streaks along the extrusion, sparse glints),
    glitter (5 % sparse silver flakes) and plain (faint noise only: matte PETG beside CF)."""
    import pyvista as pv
    key = (kind, hexcol)
    if key in _tex_cache:
        return _tex_cache[key]
    rng = np.random.default_rng(7)
    n = 512
    base = np.array([int(hexcol[i:i + 2], 16) for i in (1, 3, 5)], float) / 255
    if kind == "cf":
        noise = rng.normal(0, 1, (n, n))
        streak = np.cumsum(rng.normal(0, 1, (n, n)), axis=1)
        streak = (streak - streak.mean(axis=1, keepdims=True)) / (streak.std(axis=1, keepdims=True) + 1e-9)
        lum = 1 + 0.045 * noise + 0.03 * streak + 0.25 * (rng.random((n, n)) > 0.9985)
    else:
        lum = np.ones((n, n)) + 0.02 * rng.normal(0, 1, (n, n))
    img = np.clip(base[None, None, :] * lum[..., None], 0, 1)
    if kind == "glitter":
        flakes = rng.random((n, n)) > 0.95
        img[flakes] = np.array([0.80, 0.80, 0.82]) * (0.7 + 0.3 * rng.random((flakes.sum(), 1)))
    tex = pv.Texture((img * 255).astype(np.uint8))
    tex.repeat = True
    tex.UseSRGBColorSpaceOn()
    _tex_cache[key] = tex
    return tex


def env_cubemap():
    """Procedural soft studio environment for PBR reflections (bright ceiling, a soft box, darker floor)."""
    import tempfile
    import pyvista as pv
    from PIL import Image
    if "env" in _tex_cache:
        return _tex_cache["env"]
    d = Path(tempfile.mkdtemp())
    n = 256
    y, x = np.mgrid[0:n, 0:n] / (n - 1)
    paths = []
    for k in ("px", "nx", "py", "ny", "pz", "nz"):
        if k == "py":
            img = 0.80 + 0.05 * (1 - np.hypot(x - .5, y - .5))
        elif k == "ny":
            img = 0.30 + 0.05 * x
        else:
            img = 0.32 + 0.42 * (1 - y) ** 1.6 + (0.5 * np.exp(-(((x - .5) / .18) ** 2 + ((y - .35) / .2) ** 2)) if k == "nx" else 0)
        rgb = np.clip(np.stack([img, img, img * 1.03], -1), 0, 1)
        paths.append(str(d / f"{k}.png"))
        Image.fromarray((rgb * 255).astype(np.uint8)).save(paths[-1])
    _tex_cache["env"] = pv.cubemap_from_filenames(paths)
    return _tex_cache["env"]


def studio(w=1600, h=1000, bg=("#e7e9ec", "#ffffff")):
    import pyvista as pv
    p = pv.Plotter(off_screen=True, window_size=(w, h), lighting="none")
    p.set_background(bg[0], top=bg[1])
    p.set_environment_texture(env_cubemap(), is_srgb=True)
    for pos, i in (((-40, -70, 90), 1.9), ((70, -30, 35), 0.7), ((15, 80, 50), 1.0)):    # exposure for linear albedo
        p.add_light(pv.Light(position=pos, focal_point=(0, 0, 0), intensity=i, light_type="scene light"))
    return p


def finish(p, ssao=True, shadows=False, floor=None):
    import pyvista as pv
    if floor is not None:
        p.add_mesh(pv.Plane(center=(0, 0, floor), direction=(0, 0, 1), i_size=400, j_size=400), color="#ffffff",
                   pbr=True, roughness=0.95)
    if ssao:
        p.enable_ssao(radius=1.2, bias=0.02, kernel_size=128, blur=True)
    if shadows:
        p.enable_shadows()
    p.enable_anti_aliasing("ssaa")


def look(key, colorway=None):
    """(hex, finish) of a part in a colorway (None: technical colours)."""
    role = ROLE.get(key, "plastic")
    if colorway is None:
        fin = role if role in FINISH else ("gloss" if role in ("case", "insert") else "tpu" if role == "tpu" else "strap")
        return COLORS.get(key, "#888888"), fin
    _, case, cfin, _, tpu, tfin, _, strap = COLORWAYS[colorway]
    if role == "case":
        return case, cfin
    if role == "insert":
        return case, "matte_tile"
    if role == "tpu":
        return tpu, tfin
    if role == "strap":
        return (strap if key == "strap" else "#1e1f21"), "strap"
    return COLORS.get(key, "#888888"), role if role in FINISH else "plastic"


def add(p, m, keys, offset=(0, 0, 0), screen=True, alpha=None, colorway=None):
    import pyvista as pv
    for k in keys:
        if k not in m or m[k] is None:
            continue
        o = offset.get(k, (0, 0, 0)) if isinstance(offset, dict) else offset
        col, fin = look(k, colorway)
        metallic, rough, tex, opacity = FINISH[fin]
        mesh = pvmesh(m[k]).translate(o, inplace=False)
        kw = dict(pbr=True, metallic=metallic, roughness=rough, smooth_shading=True,
                  opacity=(alpha or {}).get(k, opacity))
        if tex:                                                        # box mapping: project along each vertex's
            pts, nrm = mesh.points, np.abs(mesh.point_data["Normals"])  # dominant normal, one tile per 4 mm
            ax = nrm.argmax(axis=1)
            uv = np.where(ax[:, None] == 2, pts[:, [0, 1]], np.where(ax[:, None] == 1, pts[:, [0, 2]], pts[:, [1, 2]]))
            mesh.active_texture_coordinates = (uv / 4.0).astype(np.float32)
            actor = p.add_mesh(mesh, color="white", **kw)
            actor.GetProperty().SetBaseColorTexture(surface_texture(tex, col))   # PBR ignores add_mesh(texture=)
        else:
            p.add_mesh(mesh, color=linear_rgb(col), **kw)
    if screen and "display" in keys:
        o = offset.get("display", (0, 0, 0)) if isinstance(offset, dict) else offset
        plane = pv.Plane(center=(AA_CX + o[0], o[1], S.Z_DISP1 + 0.004 + o[2]), direction=(0, 0, 1),
                         i_size=S.DISP_AA_L, j_size=S.DISP_AA_W)
        actor = p.add_mesh(plane, color="white", pbr=True, roughness=0.85, metallic=0.0)
        ft = face_texture()
        ft.UseSRGBColorSpaceOn()
        actor.GetProperty().SetBaseColorTexture(ft)


def cam(p, pos, focal, zoom=1.0, up=(0, 0, 1)):
    p.camera_position = [pos, focal, up]
    p.camera.zoom(zoom)


def face_texture():
    import pyvista as pv
    from PIL import Image, ImageDraw, ImageFont
    w = 1800
    h = round(w * S.DISP_AA_W / S.DISP_AA_L)
    img = Image.new("RGB", (w, h), (224, 222, 214))
    d = ImageDraw.Draw(img)

    def font(size, bold=True):
        for path, idx in [("/System/Library/Fonts/Avenir Next.ttc", 2 if bold else 0),
                          ("/System/Library/Fonts/Helvetica.ttc", 1 if bold else 0)]:
            try:
                return ImageFont.truetype(path, size, index=idx)
            except OSError:
                pass
        return ImageFont.load_default(size)
    ink = (30, 30, 32)
    d.text((w * 0.40, h * 0.46), "10:42", fill=ink, font=font(int(h * 0.6)), anchor="mm")
    d.text((w * 0.885, h * 0.30), "SAT", fill=ink, font=font(int(h * 0.15)), anchor="mm")
    d.text((w * 0.885, h * 0.50), "03", fill=ink, font=font(int(h * 0.22)), anchor="mm")
    d.text((w * 0.885, h * 0.70), "OCT", fill=ink, font=font(int(h * 0.15)), anchor="mm")
    d.line([(w * 0.79, h * 0.16), (w * 0.79, h * 0.84)], fill=ink, width=6)
    d.rectangle([w * 0.06, h * 0.88, w * 0.06 + w * 0.62, h * 0.92], outline=ink, width=4)
    d.rectangle([w * 0.06, h * 0.88, w * 0.06 + w * 0.62 * 0.8, h * 0.92], fill=ink)
    return pv.Texture(np.asarray(img))


def label_font(size):
    from PIL import ImageFont
    for path, idx in [("/System/Library/Fonts/Avenir Next.ttc", 0), ("/System/Library/Fonts/Helvetica.ttc", 0)]:
        try:
            return ImageFont.truetype(path, size, index=idx)
        except OSError:
            pass
    return ImageFont.load_default(size)


def hero_parts(m, colorway):
    """Watch parts for a colorway: CF colorways show the CF top shell with its PETG windows."""
    keys = ["bottom_shell", "bottom_seal", "bezel_gasket", "display", "bars", "rf_pin", "strap"]
    mm = dict(m)
    if COLORWAYS[colorway][2] == "cf":
        v = m["variant_cf"]
        mm.update(top_shell_cf=v["top_shell_cf"], antenna_window=v["antenna_window"], touch_windows=v["touch_windows"])
        keys += ["top_shell_cf", "antenna_window", "touch_windows"]
    else:
        keys += ["top_shell"]
    return mm, keys


def render_assembled(m):
    """Hero: three-quarter view from the -X end, so the near ears' fall from the flank to the bars reads."""
    mm, keys = hero_parts(m, HERO)
    p = studio(1600, 1000)
    add(p, mm, keys, colorway=HERO)
    finish(p)
    cam(p, (-62, -58, 40), (-1.0, 0, 1.0), 1.22)
    p.screenshot(str(MEDIA / "cad-assembled.png"))
    p.close()


def render_lug(m):
    """Close-ups of one ear (-X, -Y): three-quarter with strap and bar, side profile, top."""
    from PIL import Image, ImageDraw
    mm, keys = hero_parts(m, HERO)
    case = [k for k in keys if k != "strap"]
    x, y = -OL - 1.0, -OW + 1.0
    shots = [("three-quarter", keys, (-46, -76, 50), (x, y + 1, 3.0), 3.0, (0, 0, 1)),
             ("side: the flank runs on and sinks onto the bar", case, (0, -80, 2), (x, -OW, 3.2), 3.4, (0, 0, 1)),
             ("top: the ears carry the flanks, strap between", keys, (-8, -12, 80), (x + 2.5, 0, 3), 1.35, (0, 1, 0))]
    tiles = []
    for title, ks, d, foc, z, up in shots:
        p = studio(1000, 760)
        add(p, mm, ks, colorway=HERO)
        finish(p)
        cam(p, tuple(np.add(foc, d)), foc, z, up=up)
        img = Image.fromarray(p.screenshot(return_img=True))
        p.close()
        ImageDraw.Draw(img).text((24, 18), title, font=label_font(26), fill=(30, 30, 30))
        tiles.append(img)
    sheet = Image.new("RGB", (3000, 860), (245, 246, 248))
    for i, t in enumerate(tiles):
        sheet.paste(t, (i * 1000, 0))
    roots = ear_roots(m["top_shell"])
    ang, _ = ear_overhang()
    ImageDraw.Draw(sheet).text(
        (24, 790), f"Ear = the case's own side section carried past the end face, its top round sinking and flattening "
        f"into a {EAR_SLOPE:.0f} deg tangent of the bar boss: one surface from the case top to the bar.   Root "
        f"section {min(roots):.1f} mm^2 per ear, bar {X_BAR - OL:.2f} past the end face, lug-to-lug "
        f"{2 * EAR_TIP:.1f} mm, flattest bed-facing slope {ang:.0f} deg.", font=label_font(21), fill=(70, 70, 74))
    sheet.save(MEDIA / "cad-lug.png")


def render_colors(m):
    """The colorways side by side (real filaments)."""
    from PIL import Image, ImageDraw
    tiles = []
    for name, (cf, case, _, tf, tpu, _, strap, _) in COLORWAYS.items():
        mm, keys = hero_parts(m, name)
        p = studio(800, 560)
        add(p, mm, keys, colorway=name)
        finish(p)
        cam(p, (-46, -76, 50), (1.5, 0, 1.0), 1.12)
        img = Image.fromarray(p.screenshot(return_img=True))
        p.close()
        d = ImageDraw.Draw(img)
        d.text((24, 18), name, font=label_font(34), fill=(25, 25, 28))
        d.text((24, 62), f"{cf} / {tf}", font=label_font(18), fill=(70, 70, 74))
        d.text((24, 86), f"{strap} strap" + (f"; windows: {INSERTS[name].split(' (')[0]}" if name in INSERTS else ""),
               font=label_font(18), fill=(110, 110, 114))
        tiles.append(img)
    sheet = Image.new("RGB", (4 * 800, 2 * 560), (245, 246, 248))
    for i, t in enumerate(tiles):
        sheet.paste(t, ((i % 4) * 800, (i // 4) * 560))
    sheet.save(MEDIA / "cad-colors.png")


def exploded(m, groups, off, fname, alpha=None, title=None, flip=False, colorway=None, size=(1600, 1500),
             view=(-60, -100, 75), frac=0.6):
    """Parallel-projection exploded view, framed to fill the left `frac` of the image; labels on the right.
    groups = [(label, keys, anchor)]: anchor None puts the dot on the right-most point of those parts that a pick
    at that pixel actually hits (so it sits on what it names); a world point pins it explicitly."""
    from PIL import Image, ImageDraw
    from vtkmodules.vtkRenderingCore import vtkPropPicker
    w, h = size
    p = studio(w, h)
    keys = [k for k in off if k in m]
    mm = {k: (Rot(180, 0, 0) * m[k] if flip else m[k]) for k in keys}
    actors = {}
    for k in keys:
        before = set(p.renderer.actors)
        add(p, mm, [k], off, alpha=alpha, colorway=colorway, screen=not flip)
        actors[k] = [p.renderer.actors[n] for n in set(p.renderer.actors) - before]
    finish(p)
    p.enable_parallel_projection()
    pts = {k: pvmesh(mm[k]).cell_centers().points + np.array(off[k]) for k in keys}     # face interiors, not edges
    allp = np.vstack(list(pts.values()))
    c = (allp.min(axis=0) + allp.max(axis=0)) / 2
    cam(p, tuple(c + np.array(view, float)), tuple(c), 1.0)
    cm = p.camera
    cm.OrthogonalizeViewUp()
    d, up = np.array(cm.GetDirectionOfProjection()), np.array(cm.GetViewUp())
    right = np.cross(d, up)
    u, v = (allp - c) @ right, (allp - c) @ up
    half = max(np.ptp(v) / 2, np.ptp(u) / 2 / (frac * w / h)) * 1.06            # world half-height of the view
    cm.parallel_scale = half
    shift = right * ((u.max() + u.min()) / 2 + (0.5 - frac / 2) * 2 * half * w / h) + up * (v.max() + v.min()) / 2
    cm.SetFocalPoint(*(c + shift))
    cm.SetPosition(*(c + shift - d * 200))
    p.renderer.ResetCameraClippingRange()
    img = Image.fromarray(p.screenshot(return_img=True))
    M = cm.GetCompositeProjectionTransformMatrix(w / h, -1, 1)
    A = np.array([[M.GetElement(i, j) for j in range(4)] for i in range(4)])

    def screen(q):
        q = np.c_[np.atleast_2d(q), np.ones(len(np.atleast_2d(q)))] @ A.T
        return np.c_[(q[:, 0] / q[:, 3] + 1) / 2 * w, (q[:, 1] / q[:, 3] + 1) / 2 * h]
    picker = vtkPropPicker()
    ghosts = {id(a) for k in keys for a in actors[k] if (alpha or {}).get(k, 1.0) < 1.0}
    anchors = []
    for _, gkeys, pt in groups:
        if pt is not None:
            x, y = screen(np.array(pt, float))[0]
        else:
            q = np.vstack([pts[k] for k in gkeys if k in pts])
            sc = screen(q)
            mine = {id(a) for k in gkeys if k in actors for a in actors[k]}
            x, y = sc[sc[:, 0].argmax()]
            order = np.argsort(-sc[:, 0])
            for i in np.r_[order[:4000:20], order[::max(1, len(order) // 400)]]:    # right-most first, then all
                picker.Pick(sc[i, 0], sc[i, 1], 0, p.renderer)
                hit = picker.GetViewProp()
                if hit is not None and (id(hit) in mine or id(hit) in ghosts):
                    x, y = sc[i]
                    break
        anchors.append((x, h - y))
    p.close()
    dr = ImageDraw.Draw(img)
    f = label_font(26)
    tx, last = frac * w + 90, -1e9
    for i in sorted(range(len(groups)), key=lambda i: anchors[i][1]):
        label = groups[i][0]
        x, y = anchors[i]
        ty = max(y, last + (64 + 30 * label.count("\n")))
        last = ty
        dr.line([(x, y), (tx - 60, y), (tx - 12, ty)], fill=(70, 70, 70), width=2)
        dr.ellipse([x - 5, y - 5, x + 5, y + 5], fill=(70, 70, 70))
        dr.multiline_text((tx, ty), label, font=f, fill=(30, 30, 30), anchor="lm" if "\n" not in label else "ls")
    if title:
        dr.text((40, 36), title, font=label_font(34), fill=(30, 30, 30))
    img.save(MEDIA / fname)


def render_exploded(m):
    groups = [  # (label, keys, z offset, anchor z)
        (f"Top shell, one PETG print: {S.LIP:g} lip + walls\n+ {STRAP_W:g} mm strap ears + snap recesses",
         ["top_shell", "bars", "rf_pin"], 30, S.Z_DISP1),
        (f"TPU 90A bezel gasket {S.BEZEL_GASKET:g} + mic vent", ["bezel_gasket", "vent"], 23, S.Z_DISP1),
        ("Display GDEM0097T61 + FPC tail", ["display", "fpc", "stiffener"], 16, S.Z_DISP0),
        ("4 TPU cushions push the glass up", ["cushions"], 10.5, S.Z_PCB1 + 0.5),
        (f"PCB {S.PCB_T:g} mm + parts, mic seal", ["pcb", "qfn", "ffc", "chips", "touch", "antenna", "pads", "mic_seal"],
         5, S.Z_PCB1),
        (f"Battery {S.BAT_L:.1f} x {S.BAT_W:g} x {S.BAT_T:.1f} + coin motor,\nboth soldered; TPU motor pad + pogo rings",
         ["battery", "bat_leads", "motor", "motor_leads", "motor_pad", "pogo_seals"], -1, S.Z_BAT1),
        ("TPU bottom seal ring (radial)", ["bottom_seal"], -6, S.FLOOR),
        ("Bottom shell, one PETG print: floor, blocks,\n4 snap bumps, 2 flush magnets", ["bottom_shell", "watch_magnets"],
         -11, S.FLOOR),
    ]
    off = {k: (0, 0, dz) for _, keys, dz, _ in groups for k in keys}
    off["motor_pad"] = off["pogo_seals"] = (0, 0, 1.5)
    seen = (AA_CX, S.DISP_AA_W / 2 + WIN_M - GASKET_REVEAL / 2, Z_LIP0 + 23)    # the gasket's reveal, far side
    exploded(m, [(lab, keys, seen if "gasket" in keys[0] else None) for lab, keys, _, _ in groups], off,
             "cad-exploded.png", size=(1700, 1500))


def render_assembly(m):
    """Build order: everything goes into the upside-down top shell, the bottom shell clicks on last."""
    steps = [
        ("1  top shell, lip face down", ["top_shell", "bars", "rf_pin"]),
        ("2  bezel gasket + vent on the lip", ["bezel_gasket", "vent"]),
        ("3  display face down (FPC already\n    plugged into the PCB)", ["display", "fpc", "stiffener"]),
        ("4  4 cushions on the glass corners", ["cushions"]),
        ("5  mic seal into its relief", ["mic_seal"]),
        ("6  fold the PCB over, parts down", ["pcb", "qfn", "ffc", "chips", "touch", "antenna", "pads"]),
        ("7  battery + motor (soldered), motor pad", ["battery", "bat_leads", "motor", "motor_leads", "motor_pad"]),
        ("8  pogo seal rings on the pads", ["pogo_seals"]),
        ("9  seal ring on the floor plate, press\n    the bottom shell on: 4 clicks", ["bottom_seal", "bottom_shell", "watch_magnets"]),
    ]
    off = {k: (0, 0, 5.2 * i - 12) for i, (_, keys) in enumerate(steps) for k in keys}
    exploded(m, [(lab, keys, None) for lab, keys in steps], off, "cad-assembly.png", flip=True,
             title="Assembly order (upside down, no glue)", size=(1700, 1700))


def render_sealing(m):
    ghost = {k: 0.22 for k in ("top_shell", "bottom_shell", "pcb", "display")}
    off = dict(top_shell=(0, 0, 26), bezel_gasket=(0, 0, 20), vent=(0, 0, 20), display=(0, 0, 14), cushions=(0, 0, 9),
               pcb=(0, 0, 4), touch=(0, 0, 4), mic_seal=(0, 0, 4), pogo_seals=(0, 0, -1.5), motor_pad=(0, 0, -1.5),
               bottom_seal=(0, 0, -6), bottom_shell=(0, 0, -11), watch_magnets=(0, 0, -11))
    vx0, vx1, vy0, vy1 = vent_box()
    groups = [
        ("Top shell: lip + walls in one piece\n(no lip-to-frame joint to seal)", ["top_shell"], None),
        (f"TPU 90A bezel gasket {S.BEZEL_GASKET:g} + {vx1 - vx0:.1f} x {vy1 - vy0:.1f}\nhydrophobic mic vent",
         ["bezel_gasket", "vent"], None),
        ("4 TPU cushions press the glass\ninto the gasket", ["cushions"], None),
        ("Foam seal ring on the mic", ["mic_seal"], None),
        ("TPU rings seal the 4 pin bores", ["pogo_seals"], None),
        (f"TPU bottom seal ring {SEAL_GAP:g} wide: radial,\nsqueezed by the springy walls", ["bottom_seal"], None),
        ("Bottom shell (PETG)", ["bottom_shell"], None),
    ]
    exploded(m, groups, off, "cad-sealing.png", alpha=ghost, title="Sealing (PETG ghosted, TPU = orange)",
             size=(1700, 1500))


def render_charger(m):
    """Magnetic cable head docked on the watch (from below) + exploded."""
    import pyvista as pv
    from PIL import Image, ImageDraw
    keys = WATCH + ["strap"] + CHARGER
    p = studio(1100, 900)
    add(p, m, keys, colorway=None)
    finish(p)
    cam(p, (-55, -60, -45), (S.MOTOR_X + 4, 0, -1), 1.45)
    left = Image.fromarray(p.screenshot(return_img=True))
    p.close()
    off = dict(puck_top=(0, 0, -6), puck_magnets=(0, 0, -6), pins=(0, 0, -10), puck_base=(0, 0, -16),
               cable=(0, 0, -16), boot=(0, 0, -16), bottom_shell=(0, 0, 0), watch_magnets=(0, 0, 0))
    p = studio(1100, 900)
    mm = dict(m, bottom_shell=m["bottom_shell"] & box(-OL - 5, S.MOTOR_X + 7.5, -OW - 1, OW + 1, -1, 10))  # -X end
    add(p, mm, list(off), off)
    zp = m["pins"].bounding_box().min.Z - 10 - 0.5                   # under the pins' solder cups
    for (x, y, net) in POGO:
        p.add_point_labels([(x, y, zp)], [{"USB_DM": "D-", "USB_DP": "D+"}.get(net, net)],
                           font_size=16, point_size=1, shape_opacity=0.8, always_visible=True, text_color="#222222",
                           shape_color="#ffffff")
    for sy, pole in ((1, "N"), (-1, "S")):
        p.add_point_labels([(MAG_X, sy * MAG_Y, -0.2)], [f"{pole} out"], font_size=14, point_size=1, shape_opacity=0.8,
                           always_visible=True, text_color="#b03a2e" if pole == "N" else "#1f5aa6", shape_color="#ffffff")
        p.add_point_labels([(MAG_X, sy * MAG_Y, -6 + PUCK_TOP_T + 0.4)], ["S up" if pole == "N" else "N up"],
                           font_size=14, point_size=1, shape_opacity=0.8, always_visible=True,
                           text_color="#1f5aa6" if pole == "N" else "#b03a2e", shape_color="#ffffff")
    finish(p)
    cam(p, (-70, -70, 30), (S.MOTOR_X, 0, -8), 1.35)
    right = Image.fromarray(p.screenshot(return_img=True))
    p.close()
    sheet = Image.new("RGB", (2200, 960), (245, 246, 248))
    sheet.paste(left, (0, 60))
    sheet.paste(right, (1100, 60))
    d = ImageDraw.Draw(sheet)
    d.text((30, 20), "Magnetic charging head on the case back", font=label_font(30), fill=(30, 30, 30))
    d.text((1130, 20), "Exploded: 4 Mill-Max 0955 spring pins, 3 x 2 N52 magnets, TPU boot", font=label_font(30),
           fill=(30, 30, 30))
    d.text((1130, 925), "Watch magnets: +Y N out, -Y S out; a puck turned 180 deg repels (it would put VBUS on GND)",
           font=label_font(20), fill=(90, 90, 90))
    sheet.save(MEDIA / "cad-charger.png")


def min_wall(shape, z0, z1, step=0.1):
    """Thinnest material between two different boundaries (outer skin, cavity, pockets, ducts) in horizontal slices
    z0..z1 -> {"touch" | "vent" | "snap" | "plain": (mm, where)}: thinned touch faces, mic vent seat, the skin behind
    the snap recesses (the snap spring), everything else.
    Fins with both faces on one boundary (the ears) are covered by ear_roots()."""
    from scipy.spatial import cKDTree
    best = {k: (99.0, "") for k in ("touch", "vent", "snap", "plain")}
    tz = (WIN_Z[0] + 0.4 - 0.05, min(Z_STEP, Z_ROUND) + 0.05)
    vx0, vx1, vy0, vy1 = vent_box()
    for z in np.arange(z0, z1 + 1e-9, step):
        for f in (shape & (Plane.XY.offset(z) * Rectangle(400, 400))).faces():
            rings = [np.array([(q.X, q.Y) for q in (w.position_at(t) for t in np.linspace(0, 1, int(w.length / 0.03) + 20))])
                     for w in [f.outer_wire(), *f.inner_wires()]]
            for i in range(len(rings)):
                for j in range(i + 1, len(rings)):
                    d, _ = cKDTree(rings[j]).query(rings[i])
                    p = rings[i]
                    touch = (tz[0] <= z <= tz[1]) & (np.abs(p[:, 1]) > HW - 1.1) & np.any(
                        [np.abs(p[:, 0] - x) <= S.TOUCH_L / 2 + 0.35 + TOUCH_FACE for x in S.TOUCH_X], axis=0)
                    vent = (z >= S.Z_DISP1 - 0.05) & (p[:, 0] > vx0 - 0.6) & (p[:, 0] < vx1 + 0.6) & \
                        (np.abs(p[:, 1]) > min(abs(vy0), abs(vy1)) - 0.6)
                    snap = (np.abs(p[:, 0]) > HL - 0.1) & (SNAP_Z - 0.6 <= z <= SNAP_Z + 1.0) & np.any(
                        [np.abs(np.abs(p[:, 1]) - SNAP_Y[sx]) <= SNAP_W / 2 + 0.6 for sx in (-1, 1)], axis=0)
                    for key, mask in (("touch", touch), ("vent", vent & ~touch), ("snap", snap & ~touch & ~vent),
                                      ("plain", ~touch & ~vent & ~snap)):
                        if mask.any():
                            k = int(np.flatnonzero(mask)[np.argmin(d[mask])])
                            if d[k] < best[key][0]:
                                best[key] = (float(d[k]), f"z {z:.2f}, ({p[k][0]:+.2f}, {p[k][1]:+.2f})")
    return best

def section_polys(shape, y, x=None):
    """Cut shape with the plane y=const (or x=const) -> list of (outer, [holes]) polylines in (x or y, z)."""
    plane = Plane(origin=(x, 0, 0), z_dir=(1, 0, 0)) if x is not None else Plane(origin=(0, y, 0), z_dir=(0, 1, 0))
    cut = shape & (plane * Rectangle(400, 400))

    def pts(w):
        return np.array([((q.Y if x is not None else q.X), q.Z) for q in (w.position_at(t) for t in np.linspace(0, 1, 240))])
    return [(pts(f.outer_wire()), [pts(w) for w in f.inner_wires() if w.edges()]) for f in cut.faces()
            if f.outer_wire().edges()]                         # (OCCT can leave an empty sliver face in a section)


def draw_sections(ax, m, keys, plane, hatch=("top_shell", "bottom_shell"), flip_y=1):
    """Fill the cut faces of parts at plane ('y', v) or ('x', v) into a matplotlib axis."""
    from matplotlib.patches import PathPatch
    from matplotlib.path import Path as MPath

    def area(a):
        return 0.5 * np.sum(a[:-1, 0] * a[1:, 1] - a[1:, 0] * a[:-1, 1])
    for k in keys:
        if k not in m:
            continue
        polys = section_polys(m[k], plane[1]) if plane[0] == "y" else section_polys(m[k], None, x=plane[1])
        for outer, holes in polys:
            rings = [r * np.array([flip_y, 1]) for r in [outer] + holes]
            rings = [rings[0] if area(rings[0]) > 0 else rings[0][::-1]] + [h if area(h) < 0 else h[::-1] for h in rings[1:]]
            verts = np.concatenate(rings)
            codes = np.concatenate([[MPath.MOVETO] + [MPath.LINETO] * (len(r) - 1) for r in rings])
            ax.add_patch(PathPatch(MPath(verts, codes), facecolor=COLORS.get(k, "#7a7f86"), edgecolor="#111", lw=0.5,
                                   hatch="////" if k in hatch else None, alpha=0.95))


def render_section(m):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    y2 = S.POGO_Y
    keys = CASE + INTERNAL + ["bars", "rf_pin"]
    fig = plt.figure(figsize=(16, 10), dpi=100, facecolor="#f4f5f7")
    ax1 = fig.add_axes([0.03, 0.55, 0.94, 0.38])
    ax2 = fig.add_axes([0.03, 0.04, 0.55, 0.46])
    ax3 = fig.add_axes([0.62, 0.04, 0.35, 0.46])
    ears = union([m["top_shell"] & box(sx * OL, sx * (EAR_TIP + 1), -OW, OW, -1, S.CASE_T) for sx in (-1, 1)])
    for outer, holes in section_polys(ears, -(OW - EAR_W / 2)):
        for r in [outer] + holes:
            ax1.fill(r[:, 0], r[:, 1], facecolor="#c9ccd1", edgecolor="#555", lw=0.6, ls="--", zorder=0)
    draw_sections(ax1, m, keys, ("y", 0.0))
    draw_sections(ax2, m, keys, ("y", y2))
    for ax in (ax1, ax2):
        ax.set_aspect("equal")
        ax.set_facecolor("#f4f5f7")
        ax.axis("off")
    ax1.set_xlim(-OL - 4.5, EAR_TIP + 9)
    ax1.set_ylim(-3.6, S.CASE_T + 1.6)
    ax1.set_title("Section at y = 0 (through the motor), looking from -Y: two shells, snap-fit", fontsize=15, loc="left")
    xt = EAR_TIP + 4                                           # the layer-by-layer stack is the table below
    ax1.annotate("", (xt, 0), (xt, S.CASE_T), arrowprops=dict(arrowstyle="<->", lw=1.4, color="#c0392b", shrinkA=0, shrinkB=0))
    ax1.text(xt + 0.5, S.CASE_T / 2, f"{S.CASE_T:.2f} mm\ntotal", va="center", fontsize=13, color="#c0392b", weight="bold")
    ax1.annotate("", (-OL, -2.4), (OL, -2.4), arrowprops=dict(arrowstyle="<->", lw=1.0, color="#333", shrinkA=0, shrinkB=0))
    ax1.text(0, -3.1, f"case body {S.CASE_L:.1f} mm   (lug-to-lug {2 * EAR_TIP:.1f} mm, {STRAP_W:g} mm spring-bar straps)",
             ha="center", fontsize=11)
    for x, label in [(S.DISP_X0 - 0.2, "-X: FPC end"), (S.DISP_X1 + 2.2, "+X: antenna end (plastic only)")]:
        ax1.text(x, S.CASE_T + 0.6, label, ha="center", fontsize=10, color="#555")
    for sx in (-1, 1):
        ax1.text(sx * X_BAR, -0.5, "ear (dashed, beside\nthe strap) + spring bar", ha="center", va="top", fontsize=9, color="#555")
    ax1.annotate("top shell (hatched): lip + walls + ears", (-4, S.CASE_T - 0.15), (-14, S.CASE_T + 1.2), fontsize=9,
                 color="#333", arrowprops=dict(arrowstyle="-", lw=0.6, color="#333"))
    ax1.annotate("bottom shell: floor + blocks", (S.BAT_X1 + 3, 1.5), (S.BAT_X1 - 6, -1.6), fontsize=9, color="#333",
                 arrowprops=dict(arrowstyle="-", lw=0.6, color="#333"))
    ax2.set_xlim(-OL - 3.4, -6.5)
    ax2.set_ylim(-1.2, S.CASE_T + 1.4)
    ax2.set_title(f"Detail, -X end at y = {y2:+.1f} (through two charger pin bores)", fontsize=13, loc="left")
    px = [x for x, yy in POGO_XY if yy > 0]
    L = -OL
    notes = [((S.DISP_X0 - 0.6, S.Z_DISP0 - 0.3), (L - 1.2, S.CASE_T + 0.9), "FPC U-bend under the hood"),
             ((S.FFC_X - 1.0, S.Z_PCB1 + 0.5), (L + 7.5, S.CASE_T + 0.9), "FFC connector"),
             ((px[0], 1.2), (L + 8.6, 0.6), f"pin bores {PIN_BORE:.1f} mm, pads above"), ((px[1], 1.2), (L + 8.6, 0.6), ""),
             ((px[1] + 0.8, S.Z_PCB0 - 0.25), (L + 8.6, 2.3), "TPU pogo rings"),
             ((L + 11.5, 2.0), (L + 11.0, 3.1), "battery"),
             ((L + 0.4, 3), (L - 3.2, 3.6), "top shell wall"),
             ((L + 2.0, 0.2), (L + 3.5, -0.9), "bottom shell floor"),
             ((L + 0.6, 0.2), (L - 3.2, 1.0), "TPU seal ring"),
             ((L + 1.0, S.CASE_T - 0.15), (L + 0.2, S.CASE_T + 0.5), "lip"),
             ((L + 5.5, S.Z_DISP1 + 0.08), (L + 9.5, S.CASE_T + 0.5), "TPU bezel gasket")]
    for xy, txt, s in notes:
        ax2.annotate(s, xy, txt, fontsize=10, arrowprops=dict(arrowstyle="-", lw=0.7, color="#333"))
    ax3.axis("off")
    rows = [("lip (top shell)", S.LIP), ("bezel gasket (TPU)", S.BEZEL_GASKET), ("glass", S.DISP_T), ("gap", S.GAP),
            ("tallest part", S.PART_H), ("PCB", S.PCB_T), ("gap", S.GAP), ("battery swell", S.BAT_SWELL),
            ("battery", S.BAT_T), ("floor (bottom shell)", S.FLOOR)]
    assert abs(sum(v for _, v in rows) - S.CASE_T) < 1e-9, "stack table out of step with spec.CASE_T"
    ax3.text(0, 0.98, "Z stack (top down), mm", fontsize=13, weight="bold", va="top", transform=ax3.transAxes)
    for i, (n, v) in enumerate(rows):
        ax3.text(0.02, 0.88 - i * 0.075, n, fontsize=12, transform=ax3.transAxes)
        ax3.text(0.75, 0.88 - i * 0.075, f"{v:.2f}", fontsize=12, ha="right", transform=ax3.transAxes)
    ax3.text(0.02, 0.88 - len(rows) * 0.075, "total", fontsize=13, weight="bold", transform=ax3.transAxes)
    ax3.text(0.75, 0.88 - len(rows) * 0.075, f"{sum(v for _, v in rows):.2f}", fontsize=13, weight="bold", ha="right",
             transform=ax3.transAxes)
    fig.savefig(MEDIA / "cad-section.png", dpi=100, facecolor=fig.get_facecolor())
    plt.close(fig)


def render_snap(m):
    """Sections through a snap at each end + the radial seal, with the closure numbers."""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    keys = CASE + ["pcb", "battery", "motor", "watch_magnets"]
    fig = plt.figure(figsize=(16, 9), dpi=100, facecolor="#f4f5f7")
    sn, st = snap_numbers(), stack_numbers()
    for i, sx in enumerate((1, -1)):
        ax = fig.add_axes([0.01 + 0.34 * i, 0.16, 0.32, 0.68])
        y = sx * SNAP_Y[sx] if sx > 0 else -SNAP_Y[sx]
        draw_sections(ax, m, keys, ("y", y))
        xe = sx * OL
        ax.set_xlim(sorted((xe - sx * 3.6, xe + sx * 4.4)))
        ax.set_ylim(-0.7, 5.0)
        ax.set_aspect("equal")
        ax.axis("off")
        if sx < 0:
            ax.invert_xaxis()
        d = sn[sx]
        ax.set_title(f"{'+X (antenna) end' if sx > 0 else '-X (FPC/motor) end'}, section at y = {y:+.1f}", fontsize=13,
                     loc="left")
        xf, xo = sx * (HL - FIT), xe + sx * 0.7                         # labels sit outside the case
        notes = [((sx * (OL - 0.3), 3.0), 3.6, f"wall {S.WALL:g}: springs out\n{SNAP_DEPTH} as the bump passes"),
                 ((sx * (HL + 0.12), SNAP_Z + 0.35), 2.2, "recess in the top\nshell's end wall"),
                 ((xf + sx * 0.12, SNAP_Z), 1.1, f"snap bump (bottom shell):\n{SNAP_DEPTH} engagement, "
                  f"{SNAP_RAMP:.0f} deg lead-in,\n{SNAP_RET:.0f} deg retention"),
                 ((sx * (HL - SEAL_GAP / 2), 0.2), -0.3, f"TPU seal ring {SEAL_GAP:g} x {S.FLOOR:g} (radial)")]
        for xy, ty, txt in notes:
            ax.annotate(txt, xy, (xo, ty), fontsize=10, va="center", ha="left", annotation_clip=False,
                        arrowprops=dict(arrowstyle="-", lw=0.7, color="#333"))
        ax.text(0.0, -0.08, f"wall free height {d['H']:.1f}: {d['f']:.0f} N to flex, strain {100 * d['strain']:.1f} %,\n"
                f"close {d['close']:.0f} N, open {d['open']:.0f} N per bump", transform=ax.transAxes, fontsize=10,
                color="#444", va="top")
    ax = fig.add_axes([0.70, 0.1, 0.29, 0.8])
    ax.axis("off")
    lines = [("Closure", ""), ("4 snap bumps (2 per end)", f"{SNAP_W:g} wide"),
             ("engagement / lead-in / retention", f"{SNAP_DEPTH} / {SNAP_RAMP:.0f} / {SNAP_RET:.0f} deg"),
             ("to close (all four)", f"~{2 * (sn[1]['close'] + sn[-1]['close']):.0f} N"),
             ("to pop all four", f"~{2 * (sn[1]['open'] + sn[-1]['open']):.0f} N"),
             ("preload they carry", f"{st['total']:.0f} N"),
             ("", ""), ("Seal", ""), ("TPU 90A ring, radial", f"{SEAL_GAP:g} gap, +{2 * SEAL_SQUEEZE:.1f} squeeze"),
             ("walls spring out", f"{st['wall_bulge']:.3f} mm"),
             ("ring contact", f"{st['seal_q']:.2f} N/mm, {st['seal_p']:.2f} MPa"),
             ("bezel gasket contact", f"{st['gasket_p']:.2f} MPa"),
             ("", ""), ("Opening", ""), ("remove the straps (quick-release)", ""),
             ("spudger in the pry notch", f"at each end, {PRY_W:g} mm"),
             ("lever the floor out", "one end, then the other")]
    for i, (a, b) in enumerate(lines):
        bold = b == "" and a in ("Closure", "Seal", "Opening")
        ax.text(0.0, 0.97 - i * 0.055, a, fontsize=13 if bold else 11, weight="bold" if bold else "normal",
                transform=ax.transAxes)
        ax.text(1.0, 0.97 - i * 0.055, b, fontsize=11, ha="right", transform=ax.transAxes)
    fig.suptitle("Snap-fit + radial seal between the two shells (no glue, no screws)", x=0.02, ha="left", fontsize=16)
    fig.savefig(MEDIA / "cad-snap.png", dpi=100, facecolor=fig.get_facecolor())
    plt.close(fig)


def render_scale(m):
    """Top and side orthographic views next to the Fitbit Charge 3 (size target) and earlier rev A outlines."""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.patches import FancyBboxPatch
    hw, zc = 30.0, S.CASE_T / 2
    mm, keys = hero_parts(m, HERO)

    def ortho(pos, focal, up, hh):
        p = studio(1600, round(1600 * hh / hw), bg=("#f4f5f7", "#f4f5f7"))
        add(p, mm, keys, colorway=HERO)
        finish(p, ssao=False)
        p.enable_parallel_projection()
        p.camera_position = [pos, focal, up]
        p.camera.parallel_scale = hh
        img = p.screenshot(return_img=True)
        p.close()
        return img
    top = ortho((0, 0, 100), (0, 0, 0), (0, 1, 0), 15.0)
    side = ortho((0, -100, zc), (0, 0, zc), (0, 0, 1), 7.5)
    fig, (ax, ax2) = plt.subplots(2, 1, figsize=(16, 8.4), dpi=100, facecolor="#f4f5f7",
                                  gridspec_kw=dict(height_ratios=[38, 15.5]))
    fig.subplots_adjust(0.01, 0.01, 0.99, 0.99, hspace=0.04)
    ax.imshow(top, extent=[-hw, hw, -15, 15], zorder=2)
    ax2.imshow(side, extent=[-hw, hw, zc - 7.5, zc + 7.5], zorder=2)
    cx = 50.0
    refs = [("Fitbit Charge 3", (38.0, 18.3, 11.8, 5.0), "#1a73e8", "-", "corner radius guessed"),
            ("rev A, Day 0", (36.7, 20.0, 7.45, 3.2), "#d9822b", "-.", "Day-0 design"),
            ("rev A, 2026-10-04", (35.6, 18.0, 7.05, 3.3), "#8e44ad", ":", "3.0 mm cell"),
            ("rev A now", (S.CASE_L, S.CASE_W, S.CASE_T, S.CORNER_R), "#3a4250", "--", "this case")]
    for i, (name, (l, w, h, r), col, ls, note) in enumerate(refs):
        ax.add_patch(FancyBboxPatch((cx - l / 2 + r, -w / 2 + r), l - 2 * r, w - 2 * r, boxstyle=f"round,pad={r}",
                                    fill=False, ec=col, lw=2.0, ls=ls))
        ax2.add_patch(FancyBboxPatch((cx - l / 2 + 1.2, 1.2), l - 2.4, h - 2.4, boxstyle="round,pad=1.2", fill=False,
                                     ec=col, lw=2.0, ls=ls))
        ax.text(cx - 19, 20.0 - 2.4 * i, f"{name}   {l:.1f} x {w:.1f} x {h:g} mm", fontsize=13, weight="bold", color=col,
                va="center")
        ax.text(cx + 16, 20.0 - 2.4 * i, f"({note})", fontsize=10, color="#777", va="center")
        x = cx + 20.5 + 2.6 * i
        ax2.annotate("", (x, 0), (x, h), arrowprops=dict(arrowstyle="<->", lw=1.1, color=col, shrinkA=0, shrinkB=0))
        ax2.text(x, h + 0.6, f"{h:g}", fontsize=10, color=col, ha="center")

    def dim(a, x0, y0, x1, y1, text, off, vertical=False, color="#222"):
        a.annotate("", (x0, y0), (x1, y1), arrowprops=dict(arrowstyle="<->", lw=1.1, color=color, shrinkA=0, shrinkB=0))
        if vertical:
            a.text(x0 + off, (y0 + y1) / 2, text, rotation=90, va="center", ha="center", fontsize=12, color=color)
        else:
            a.text((x0 + x1) / 2, y0 + off, text, ha="center", va="center", fontsize=12, color=color)
    dim(ax, -OL, -OW - 2.5, OL, -OW - 2.5, f"{S.CASE_L:.1f} body", -1.2)
    dim(ax, -EAR_TIP, -OW - 5.5, EAR_TIP, -OW - 5.5, f"{2 * EAR_TIP:.1f} lug to lug", -1.2, color="#666")
    dim(ax, -EAR_TIP - 2.5, -OW, -EAR_TIP - 2.5, OW, f"{S.CASE_W:.1f}", -1.3, vertical=True)
    dim(ax2, -EAR_TIP - 2.5, 0, -EAR_TIP - 2.5, S.CASE_T, f"{S.CASE_T:.2f}", -1.3, vertical=True)
    ax.text(0, OW + 3.5, f"Horae rev A   {S.CASE_L:.1f} x {S.CASE_W:.1f} x {S.CASE_T:.2f} mm", ha="center", fontsize=15,
            weight="bold", color="#222")
    ax.text(cx, -12.2, "plan outlines to scale (Charge 3 approximate)", ha="center", fontsize=10, color="#777")
    ax2.text(cx, 13.0, "side profiles to scale", ha="center", fontsize=10, color="#777")
    ax2.text(0, S.CASE_T + 1.2, f"side view: straps leave {Z_BAR - STRAP_R:.2f}..{Z_BAR + STRAP_R:.2f} above the wrist",
             ha="center", fontsize=11, color="#555")
    for a, (y0, y1) in ((ax, (-17, 22)), (ax2, (-1.5, 14))):
        a.set_xlim(-hw - 2, cx + 32)
        a.set_ylim(y0, y1)
        a.set_aspect("equal")
        a.set_facecolor("#f4f5f7")
        a.axis("off")
    fig.savefig(MEDIA / "cad-scale.png", dpi=100, facecolor=fig.get_facecolor(), bbox_inches=None)
    plt.close(fig)


def render_board(m, comps, note):
    """Top view, display hidden: what sits under the glass, the top shell's bearing blocks, the cushions."""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.patches import Rectangle as MRect
    hw, hh = 25.0, 12.5
    p = studio(1600, 800, bg=("#f4f5f7", "#f4f5f7"))
    add(p, m, ["top_shell", "bars", "rf_pin", "pcb", "qfn", "ffc", "chips", "touch", "antenna", "cushions"],
        alpha={"top_shell": 0.5})
    finish(p, ssao=False)
    p.enable_parallel_projection()
    p.camera_position = [(0, 0, 100), (0, 0, 0), (0, 1, 0)]
    p.camera.parallel_scale = hh
    img = p.screenshot(return_img=True)
    p.close()
    fig, ax = plt.subplots(figsize=(16, 10), dpi=100, facecolor="#f4f5f7")
    fig.subplots_adjust(0.01, 0.04, 0.99, 0.94)
    ax.imshow(img, extent=[-hw, hw, -hh, hh])
    ax.add_patch(MRect((S.DISP_X0, -S.DISP_W / 2), S.DISP_L, S.DISP_W, fill=False, ec="#2a6fdb", lw=1.6, ls="--"))
    ax.add_patch(MRect((AA_X0, -S.DISP_AA_W / 2), S.DISP_AA_L, S.DISP_AA_W, fill=False, ec="#2a6fdb", lw=1, ls=":"))
    ax.add_patch(MRect((S.ANT_X0, -S.PCB_W / 2), S.CAV_L / 2 - S.ANT_X0, S.PCB_W, fill=False, ec="#c0392b", lw=1.2, ls="--"))
    big = {}
    for ref, val, sh in comps:
        if ref.endswith(" nub") or ref[:1] in "CRL" and ref[:2] != "L4" or ref.startswith("D"):
            continue
        big[ref] = (val, sh.bounding_box().center())
    side = {}
    for ref, (val, c) in sorted(big.items(), key=lambda kv: kv[1][1].X):
        up = c.Y > 0
        n = side.setdefault(up, 0)
        side[up] += 1
        ty = (hh + 0.8 + (n % 4) * 1.05) * (1 if up else -1)
        ax.annotate(f"{ref} {val}", (c.X, c.Y), (c.X, ty), ha="center", va="center", fontsize=10,
                    arrowprops=dict(arrowstyle="-", lw=0.6, color="#444"))
    ax.annotate("TCH1-4 touch electrodes", (S.TOUCH_X[1], -TOUCH_Y), (S.TOUCH_X[1] + 7, -hh - 2.5),
                ha="left", va="center", fontsize=10, arrowprops=dict(arrowstyle="-", lw=0.6, color="#444"))
    ax.annotate("TPU cushions under the\nglass corners (orange)", (S.DISP_X1 - 0.5, S.LEDGE_Y + 1), (hw + 2.5, 6),
                ha="left", va="center", fontsize=10, arrowprops=dict(arrowstyle="-", lw=0.6, color="#444"))
    if "antenna" in m:
        ac = m["antenna"].bounding_box().center()
        ax.annotate("AE1 PCB antenna (copper)", (ac.X, ac.Y), (hw + 2.5, 0), ha="left", va="center", fontsize=10,
                    arrowprops=dict(arrowstyle="-", lw=0.6, color="#444"))
    ax.text(S.DISP_X0, -S.DISP_W / 2 - 0.7, "glass outline (dashed), active area (dotted)", color="#2a6fdb", fontsize=10, va="top")
    ax.text(S.ANT_X0, S.PCB_W / 2 + 0.3, "antenna keep-out", color="#c0392b", fontsize=10, va="bottom")
    ax.set_title("Board in the top shell (shell semi-transparent; display hidden)", fontsize=14, loc="left")
    fig.text(0.01, 0.015, note, fontsize=9, color="#777")
    ax.set_xlim(-hw - 1, hw + 14)
    ax.set_ylim(-hh - 4.5, hh + 4.5)
    ax.set_aspect("equal")
    ax.axis("off")
    fig.savefig(MEDIA / "cad-board-in-case.png", dpi=100, facecolor=fig.get_facecolor())
    plt.close(fig)


def render_mic(m, comps):
    """Close-up YZ section through the mic port: seal ring, duct groove, vent in the gasket layer, outlet in the lip."""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    px, py, pz = mic_port()
    xd, yd = duct_xy()
    sy = mic_sy()
    mm = dict(m)
    mm.update({f"mic{i}": sh for i, (ref, _, sh) in enumerate(comps) if ref.startswith("MIC")})
    keys = CASE + ["display", "fpc", "pcb", "chips", "ffc", "battery", "touch"] + [k for k in mm if k.startswith("mic") and k[3:].isdigit()]
    fig, ax = plt.subplots(figsize=(16, 9), dpi=100, facecolor="#f4f5f7")
    fig.subplots_adjust(0.02, 0.02, 0.98, 0.92)
    draw_sections(ax, mm, keys, ("x", xd), hatch=("top_shell", "bottom_shell"), flip_y=sy)
    ay, ad = abs(py), abs(yd)
    vx0, vx1, vy0, vy1 = vent_box()
    inner, outer, side = mic_seal_walls()
    zt = S.Z_PCB1
    notes = [((ad, S.CASE_T - 0.1), (ad - 3.0, S.CASE_T + 0.8), f"outlet {MIC_HOLE:g} mm through the lip"),
             ((ad - 0.6, S.Z_DISP1 + 0.07), (ad - 8.0, S.CASE_T + 0.35), f"{vx1 - vx0:.1f} x {vy1 - vy0:.1f} mm hydrophobic vent (gasket layer)"),
             ((ad - 1.6, S.Z_DISP1 + 0.07), (ad - 8.0, S.CASE_T - 0.2), "TPU bezel gasket"),
             ((ad + 0.1, (pz + S.Z_DISP1) / 2 + 0.2), (ad + 2.2, S.Z_DISP1 - 0.1), f"duct: {MIC_BORE:g} groove in the rib"),
             ((S.DISP_W / 2 + MIC_RIB_FIT / 2, S.Z_DISP0 + 0.6), (ad + 2.2, S.Z_DISP0 + 0.2), f"{MIC_RIB_FIT:g} glass-edge slit (small leak inward)"),
             ((ad + MIC_BORE / 2 + 0.05 + outer / 2, pz + 0.12), (ad + 2.2, zt + 0.95), f"foam seal ring ({outer:.2f} / {inner:.2f} walls)"),
             ((ay - 0.6, pz - 0.4), (ad + 2.2, zt + 0.35), "LMD2718 top-port mic"),
             ((S.DISP_W / 2 - 0.6, S.Z_DISP0 + 0.5), (ad - 8.0, S.Z_DISP0 + 0.3), "glass"),
             ((ad - 1.0, S.Z_PCB0 + 0.3), (ad - 8.0, S.Z_PCB0 + 0.3), "PCB")]
    for xy, txt, label in notes:
        ax.annotate(label, xy, txt, fontsize=12, arrowprops=dict(arrowstyle="-", lw=0.7, color="#333"))
    ax.annotate("", (ay, pz), (ad, S.CASE_T + 0.45), arrowprops=dict(arrowstyle="<-", lw=1.5, color="#1a73e8"))
    ax.text(ad + 0.1, S.CASE_T + 0.4, "sound", color="#1a73e8", fontsize=11)
    ax.set_xlim(ad - 8.5, OW + 3.5)
    ax.set_ylim(S.Z_PCB0 - 0.4, S.CASE_T + 1.1)
    ax.set_aspect("equal")
    ax.axis("off")
    ax.set_title(f"Mic duct, section at x = {xd:+.2f} looking along X (port {2 * MIC_PORT_R:.2f} at |y| {ay:.2f}: its "
                 f"edge is {ay - MIC_PORT_R - S.DISP_W / 2:+.2f} mm from the glass edge)", fontsize=15, loc="left")
    fig.savefig(MEDIA / "cad-mic.png", dpi=100, facecolor=fig.get_facecolor())
    plt.close(fig)


def render_shape_options(m):
    """Pebble vs facet outer shape (3/4 view + end-on profile), same ears and shells."""
    from PIL import Image, ImageDraw
    rest = {k: m[k] for k in ("display", "bars", "rf_pin", "bottom_shell", "bottom_seal")}
    tiles = []
    for name in ("pebble", "facet"):
        r, (a, b), (ab, bb), kind = SHAPES[name]
        edge = "round" if kind == "fillet" else "chamfer"
        mm = dict(rest, top_shell=m["top_shell"] if name == SHAPE else top_shell(name) - touch_thin())
        keys = list(mm)
        for view in ("34", "end"):
            p = studio(800, 550)
            add(p, mm, keys, screen=view == "34", colorway="Paper")
            finish(p)
            if view == "34":
                cam(p, (-48, -78, 58), (0, 0, 2.0), 1.45)
            else:
                p.enable_parallel_projection()
                p.camera_position = [(80, 0, S.CASE_T / 2), (0, 0, S.CASE_T / 2), (0, 0, 1)]
                p.camera.parallel_scale = 7.0
            img = Image.fromarray(p.screenshot(return_img=True))
            p.close()
            d = ImageDraw.Draw(img)
            d.text((20, 14), (f"{'A  pebble (default)' if name == 'pebble' else 'B  facet'}: R{r:g} plan, {a:g} x {b:g} top "
                              f"{edge}, {ab:g} x {bb:g} bottom") if view == "34" else "end-on profile (from +X)",
                   font=label_font(20), fill=(40, 40, 40))
            tiles.append(img)
    sheet = Image.new("RGB", (1600, 1100), (245, 246, 248))
    for i, t in enumerate(tiles):
        sheet.paste(t, ((i // 2) * 800, (i % 2) * 550))
    sheet.save(MEDIA / "cad-shape-options.png")


def main():
    m, fit, comps, note = build()
    print(f"PCB: {note}")
    ok = checks(m, fit, comps)
    summary(m)
    export(m)
    print(f"exports -> {OUT.relative_to(ROOT)}/")
    if "--no-render" not in sys.argv and not THIN:
        MEDIA.mkdir(parents=True, exist_ok=True)
        for f in (render_assembled, render_lug, render_colors, render_exploded, render_assembly, render_sealing,
                  render_section, render_snap, render_scale, render_charger, render_shape_options):
            f(m)
        render_board(m, comps, note)
        render_mic(m, comps)
        print(f"renders -> {MEDIA.relative_to(ROOT)}/cad-*.png")
    if not ok:
        sys.exit("checks FAILED")


if __name__ == "__main__":
    main()
