#!/usr/bin/env python3
"""Project Horae rev A mechanics: reference bodies, 3-part case, charging dock, checks, exports, renders.

    .venv/bin/python cad/horae.py            # everything (cad/out/*, media/2026-10-04/cad-*.png)
    .venv/bin/python cad/horae.py --no-render
    .venv/bin/python cad/horae.py --thin     # spec with BAT_T 2.5 (thinner cell) -> cad/out/variant-thin/, no renders

All shared dimensions come from spec.py. Splash-resistant, one filament per print (A1 mini, no AMS):
  frame  plain PETG: walls, glass ledges, touch areas thinned to 0.6 mm, mic duct, and the spring-bar ears:
         the lower side band of the long walls carried past each end (one solid with the frame, drilled through)
  back   plain PETG: floor + motor/pogo/magnet block (-X) + support block (+X)
  bezel  plain PETG: lip with the display window and the mic outlet
  TPU 95A (separate print): gasket_back, gasket_bezel, gasket_pogo, mic_seal (die-cut PORON preferred)
  variant-cf/: PETG-CF frame + back, PETG antenna-end pieces and touch inserts, keyed + glued
  Outer shape: SHAPE skin (rounded "pebble" by default) + lugs() clips every case part.
If hardware/out/horae.step exists it replaces the placeholder PCB.
"""
import math
import sys
from pathlib import Path

import numpy as np
from build123d import (Align, Axis, Box, Color, Compound, Cone, Cylinder, Plane, Polyline, Pos, Rectangle,
                       RectangleRounded, Rot, export_step, export_stl, extrude, fillet, import_step, make_face)

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
MEDIA = ROOT / "media" / "2026-10-04"
BOARD_STEP = ROOT / "hardware" / "out" / "horae.step"

# --- cad-only dimensions (case <-> dock; nothing here touches the PCB) ---
FIT = 0.1             # per-side clearance of the back-plate blocks in the cavity
GLASS_FIT = 0.15      # per-side clearance around the display glass
WIN_M = S.DISP_AA_MARGIN_FAR - S.LIP_OVERLAP   # window = active area + this (0.75) -> 1.0 overlap on 3 sides
MAG_D, MAG_T = 2.0, 2.0   # N52 disc in a blind pocket from the skin side (sealed), under each battery pad
MAG_X, MAG_Y = S.BATPAD_X, S.BATPAD_Y
POGO = [(x, -y, net) for x, y, net in S.POGO_PADS]   # physical (spec Y is KiCad, down): the dock wires pins by these
POGO_XY = [(x, y) for x, y, _ in POGO]
POGO_PAD_D = 1.0
POGO_HOLE_D = 1.3     # P50-style pin: 1.0 barrel + 0.3
PIN_L, PIN_D, PLUNGER_D, PLUNGER_L = 16.0, 1.0, 0.6, 2.5
PIN_PRELOAD = 0.5     # free pin tip sits this far above the pad -> 0.5 mm of stroke used when docked
PIN_BORE = 1.1
STRAP_W = 16.0        # two-piece quick-release strap on standard spring bars; lug gap = STRAP_W -> 1.0 mm ears
BAR_D = 1.5           # spring-bar body (quick-release 1.5 bars, 0.8 tips)
BAR_TIP_HOLE = 1.1    # drilled lugs: straight through the ears (tips bear on the full ear width; 1.78 bars fit too)
STRAP_R = 1.85        # strap end loop around the bar (3.7 mm thick end): clearance envelope
BAR_DX = STRAP_R + 0.3   # bar axis past the case end face: the loop swings 0.3 clear of the end face
EAR_R = 1.6           # ear end radius around the bar: 1.05 mm of PETG around the tip hole
EAR_EDGE = 0.4        # round on the ears' outer long edges
EAR_WEB = 0.6         # plan-view fillet where an ear's inner face leaves the rounded case end (no notch at the root)
MIC_SEAL = 0.25       # foam (PORON) ring on the mic lid: compressed to this under the frame, to the glass gap under the glass
MIC_BORE, MIC_HOLE = 0.5, 0.6          # duct (a groove in the rib face, open to the glass-edge slit), bezel outlet
MIC_RIB_FIT = 0.05    # glass clearance at the local rib that closes the glass gap over the mic (normal 0.15)
MIC_RIB_X = 1.3       # rib half-length along X
VENT_EDGE = 0.3       # adhesive border of the rectangular hydrophobic vent around the duct mouth (vent <= 0.2 thick)
FFC_L, FFC_D, FFC_H = 12.5, 3.5, 1.0        # FH34SRJ-18S body (Y x X x Z), centred at S.FFC_X
FPC_T = 0.12          # display FPC tail thickness
BACK_GASKET = 0.3     # TPU ring between frame and back (compressed; printed 0.4). Frame starts above it
POGO_GASKET = 0.5     # TPU pad under the PCB around the pogo pads (compressed; printed 0.6)
POGO_SEAL_D = 0.8     # gasket hole around each 0.6 mm plunger; seals on the 1.0 mm pad ring
X_MZ1 = S.BAT_X0 - 0.25                 # end of the motor-zone block in the back
MOTOR_POCKET = S.MOTOR_D + 0.4
MOTOR_TAPE = 0.2      # double-sided foam tape: the motor sits on the floor; its leads loop over the can to the pads
LEAD_GAP = 0.5        # wanted between the motor can and the PCB for the leads + solder joints
MOTOR_Z0 = min(S.FLOOR, max(S.FLOOR - 0.3, S.Z_PCB0 - LEAD_GAP - S.MOTOR_T - MOTOR_TAPE))   # pocket floor (sinks
                                                                                            # into the floor if needed)
BAT_PCM_L, BAT_PCM_EXTRA = 2.0, 0.5   # cell's PCM end (-X): up to 0.5 thicker than the cell
BAT_RECESS, BAT_RECESS_L = 0.3, 2.5   # floor recess under the PCM end (leaves FLOOR - 0.3 of floor)
GASKET_PRINT = {"gasket_back": 0.4, "gasket_bezel": 0.25, "gasket_pogo": 0.6, "mic_seal": 0.3}   # printed (free) thickness
X_RF = S.ANT_X0 - 1.5 # CF variant: no carbon from here to the +X end (antenna copper starts ~0.45 before ANT_X0)
RF_LAP = 1.5          # frame lap joint: the PETG upper half overhangs the CF lower half by this
TOUCH_Y = S.PCB_W / 2 - 0.3 - S.TOUCH_W / 2      # electrode centre |y|
TOUCH_CF_CLEAR = 1.0  # no carbon within this of an electrode
TOUCH_FACE = 0.6      # PETG window thickness over the electrode zone
WIN_X = S.TOUCH_L / 2 + TOUCH_CF_CLEAR             # window half-length
WIN_Z = (S.Z_PCB1 - TOUCH_CF_CLEAR - 0.1, S.Z_DISP1 + 1)   # open at the top: insert drops in, bezel caps it
Y_TOP = S.DISP_W / 2 + GLASS_FIT                   # cavity narrows to the glass above Z_STEP (thick upper wall)
Z_STEP = S.Z_DISP0 - 0.1   # upper wall over |y| >= Y_TOP: parts there must stay below Z_STEP (else RELIEFS pockets)
R_PLAN = S.CORNER_R        # skin plan-view corner radius
SHAPES = {  # name -> (plan corner R, top edge (across, down), bottom edge, kind)
    # tall elliptical top round (1.6 across x 2.5 down): reads like an R2.5 from the side, but insets only 0.56 at the
    # frame top (0.6 below the case top), leaving 0.64 of wall at the -X glass-pocket corners (an R2.5 left 0.3)
    "pebble": (R_PLAN, (1.6, 2.5), 1.2, "fillet"),
    "facet": (R_PLAN, (0.75, 1.8), 0.8, "chamfer"),
}
SHAPE = "pebble"
Z_ROUND = S.CASE_T - SHAPES[SHAPE][1][1]   # the top round starts here: the vertical side band is below it
MIN_WALL = 0.6        # thinnest allowed frame wall (touch faces are TOUCH_FACE by design; nominal S.WALL)
DOCK_WALL, DOCK_DEPTH, DOCK_BAY_H = 2.5, 3.0, 4.5

IN_R = S.PCB_CORNER_R + FIT                       # cavity corners follow the PCB
HL, HW = S.CAV_L / 2, S.CAV_W / 2
OL, OW = S.CASE_L / 2, S.CASE_W / 2
Z_FRAME0 = S.FLOOR + BACK_GASKET
AA_X1 = S.DISP_X1 - S.DISP_AA_MARGIN_FAR
AA_X0 = AA_X1 - S.DISP_AA_L
AA_CX = (AA_X0 + AA_X1) / 2
X_BAR = OL + BAR_DX
Z_BAR = Z_FRAME0 + EAR_R     # ears stand on the frame's bottom plane: the strap leaves low, near the wrist
Z_EAR1 = Z_BAR + EAR_R       # top of the round ear end (the ear rises to Z_ROUND at the case end)
EAR_TIP = X_BAR + EAR_R
EAR_W = OW - STRAP_W / 2
PIN_TIP_FREE = S.Z_PCB0 + PIN_PRELOAD
DOCK_ZB = PIN_TIP_FREE - PIN_L - 0.6         # dock bottom (pin tail ends 0.6 above the table)
DOCK_L2 = EAR_TIP + 0.3 + DOCK_WALL
DOCK_W2 = OW + 0.3 + DOCK_WALL
assert S.PCB_CORNER_R <= IN_R - FIT + 1e-9, "PCB corners must sit inside the cavity corner radius"
assert X_RF - RF_LAP > max(S.TOUCH_X) + WIN_X, "RF lap joint runs into a touch window"
assert Z_EAR1 <= Z_ROUND + 1e-6, "ears reach into the top round"
assert EAR_W >= 0.9, f"{STRAP_W} mm straps leave {EAR_W:.2f} mm ears"


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
    return union([cyl(x, y, S.Z_PCB0 - 0.03, S.Z_PCB0, POGO_PAD_D) for x, y in POGO_XY]
                 + [cyl(S.MOTOR_X + dx, 0, S.Z_PCB0 - 0.03, S.Z_PCB0, 1.5) for dx in (-S.MOTOR_PAD_DX, S.MOTOR_PAD_DX)]
                 + [box(MAG_X - 1, MAG_X + 1, sy * (S.BATPAD_Y - 1), sy * (S.BATPAD_Y + 1), S.Z_PCB0 - 0.03,
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
    """Cell + its thicker PCM end (sitting in the floor recess); leads soldered to the 2x2 pads above the magnets."""
    z0, z1 = S.Z_BAT0, S.Z_BAT0 + S.BAT_T
    body = box(S.BAT_X0 + BAT_PCM_L, S.BAT_X1, -S.BAT_W / 2, S.BAT_W / 2, z0, z1)
    body = fillet(body.edges().group_by(Axis.Z)[-1], 0.9)
    zp = S.FLOOR - BAT_RECESS
    pcm = box(S.BAT_X0, S.BAT_X0 + BAT_PCM_L + 0.1, -S.BAT_W / 2 + 0.3, S.BAT_W / 2 - 0.3, zp, zp + S.BAT_T + BAT_PCM_EXTRA)
    zl = MAG_T + 0.6                                     # leads run in the back's wire channel to the pads
    leads = union([box(MAG_X - 0.15, S.BAT_X0, sy * (MAG_Y - 0.15), sy * (MAG_Y + 0.15), zl, zl + 0.25)
                   + box(MAG_X - 0.15, MAG_X + 0.15, sy * (MAG_Y - 0.15), sy * (MAG_Y + 0.15), zl, S.Z_PCB0 - 0.03)
                   for sy in (-1, 1)])
    return body + pcm, leads


def motor():
    """Coin ERM on foam tape on the floor; its two leads loop up over the can and are soldered to the PCB pads
    (shown as the lead + solder columns on the pads)."""
    z0 = MOTOR_Z0 + MOTOR_TAPE
    body = cyl(S.MOTOR_X, 0, z0, z0 + S.MOTOR_T, S.MOTOR_D)
    leads = union([cyl(S.MOTOR_X + dx, 0, z0 + S.MOTOR_T + 0.05, S.Z_PCB0 - 0.03, 0.4) for dx in (-S.MOTOR_PAD_DX, S.MOTOR_PAD_DX)])
    return body, leads


def magnets(z0):
    return [cyl(MAG_X, sy * MAG_Y, z0, z0 + MAG_T, MAG_D) for sy in (-1, 1)]


def spring_bar(sx):
    """Standard spring bar: body between the ears, 0.8 tips through the drilled ears (flush with the outside)."""
    return (ycyl(sx * X_BAR, -STRAP_W / 2 + 0.05, STRAP_W / 2 - 0.05, Z_BAR, BAR_D)
            + ycyl(sx * X_BAR, -OW + 0.05, OW - 0.05, Z_BAR, 0.8))


def spring_bars():
    return spring_bar(-1)


def rf_pin():
    """+X spring bar (steel; kept as far from the antenna as the lug allows). Key name kept for the renders."""
    return spring_bar(1)


def nato(swing=0.0):
    """Two-piece strap stubs: curved end around each bar + 12 mm of strap (render + clearance only).
    swing: degrees each stub is turned about its bar, + = down toward the wrist."""
    w, t, r = STRAP_W / 2 - 0.1, 1.8, STRAP_R
    parts = []
    for sx in (-1, 1):
        stub = (ycyl(sx * X_BAR, -w, w, Z_BAR, 2 * r) + box(sx * X_BAR, sx * (X_BAR + 12), -w, w, Z_BAR + r - t, Z_BAR + r)
                - ycyl(sx * X_BAR, -w - 1, w + 1, Z_BAR, BAR_D + 0.1))
        parts.append(Pos(sx * X_BAR, 0, Z_BAR) * Rot(0, sx * swing, 0) * Pos(-sx * X_BAR, 0, -Z_BAR) * stub)
    return union(parts)


def mic_port():
    """(x, y, top z) of the mic's acoustic port: from the board STEP model when present, else from spec."""
    return MIC_PORT


# spec MIC_Y is in KiCad coordinates (Y down) -> physical -Y; port 0.6 mm outward along the mic's long axis
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
    """Rectangular adhesive hydrophobic vent over the duct mouth: inner border on the glass, outer on the frame
    top, all of it under the bezel."""
    x, _, _ = mic_port()
    _, yd = duct_xy()
    sy, r = mic_sy(), MIC_BORE / 2 + VENT_EDGE
    y0, y1 = sorted((sy * (abs(yd) - r - 0.1), sy * min(abs(yd) + r, bezel_inner_edge() - 0.03)))
    return x - r - 0.15, x + r + 0.15, y0, y1


def vent():
    x0, x1, y0, y1 = vent_box()
    return box(x0, x1, y0, y1, S.Z_DISP1 + 0.01, S.Z_DISP1 + 0.16)


def bezel_inner_edge():
    """|y| of the bezel's underside edge (top of the bezel gasket) for the current skin."""
    return OW - top_inset(S.CASE_T - (S.Z_DISP1 + S.BEZEL_GASKET))


def top_inset(d, style=None):
    """How far the skin's top edge round sits inside the side wall at depth d below the case top."""
    _, (a, b), _, kind = SHAPES[style or SHAPE]
    u = max(1 - d / b, 0)
    return a * (1 - math.sqrt(1 - u * u)) if kind == "fillet" else a * u


# ---------------------------------------------------------------- case
def lugs():
    """Spring-bar ears: the side band of the long walls (full height to the top round at the case end) carried past
    each end, sloping down tangent to a round end around the bar. Plan: case outline + EAR_W strips with EAR_WEB
    fillets where they leave the rounded ends; EAR_EDGE rounds on the outer edges. frame() and skin() both add it,
    so the skin never clips it."""
    x0, x1 = OL - R_PLAN - 0.5, EAR_TIP + 0.5
    plan = RectangleRounded(S.CASE_L, S.CASE_W, R_PLAN)
    for sx in (-1, 1):
        for sy in (-1, 1):
            plan += Pos(sx * (x0 + x1) / 2, sy * (OW - EAR_W / 2)) * Rectangle(x1 - x0, EAR_W)
    plan = fillet([v for v in plan.vertices() if abs(abs(v.Y) - STRAP_W / 2) < 1e-6 and abs(v.X) < OL], EAR_WEB)
    c, p = (X_BAR, Z_BAR), (OL, Z_ROUND)               # side profile: hull of the band end and the bar circle
    th = math.atan2(p[1] - c[1], p[0] - c[0]) - math.acos(EAR_R / math.dist(c, p))
    tp = (c[0] + EAR_R * math.cos(th), c[1] + EAR_R * math.sin(th))   # where the sloped top meets the round end
    out = []
    for sx in (-1, 1):
        prof = make_face(Polyline(*[(sx * x, 0, z) for x, z in [(x0 - 1, Z_FRAME0), (X_BAR, Z_FRAME0), c, tp, p,
                                                                (x0 - 1, Z_ROUND)]], close=True))
        side = extrude(prof, OW + 1, dir=(0, 1, 0), both=True) + ycyl(sx * X_BAR, -OW - 1, OW + 1, Z_BAR, 2 * EAR_R)
        for sy in (-1, 1):
            corner = box(sx * (x0 + 0.2), sx * x1, sy * (STRAP_W / 2 - 2), sy * (OW + 1), Z_FRAME0, Z_ROUND)
            ear = (Pos(0, 0, Z_FRAME0) * extrude(plan, Z_ROUND - Z_FRAME0)) & corner & side
            face = max(ear.faces(), key=lambda f: sy * f.center().Y)              # the outer face, flush with the side
            out.append(fillet([e for e in face.edges() if abs(e.center().X - sx * (x0 + 0.2)) > 1e-3], EAR_EDGE))
    return union(out)


def skin(style=None):
    """Outer skin that clips every case part: rounded plan + rounded/chamfered top and bottom edges, plus the lugs."""
    from build123d import chamfer, scale
    r_plan, (a, b), r_bot, kind = SHAPES[style or SHAPE]
    edge = fillet if kind == "fillet" else chamfer
    low = slab(S.CASE_L, S.CASE_W, r_plan, 0, S.CASE_T + 1)
    low = edge(low.edges().group_by(Axis.Z)[0], r_bot)
    k = a / b                                            # top edge: an a x b round = an a round squashed by k in Z
    up = slab(S.CASE_L, S.CASE_W, r_plan, -1, S.CASE_T * k)
    up = scale(edge(up.edges().group_by(Axis.Z)[-1], a), by=(1, 1, 1 / k))
    return (low & up) + lugs()


def frame():
    """Whole frame, before the touch windows and the CF/RF split."""
    outer = slab(S.CASE_L, S.CASE_W, S.CORNER_R, Z_FRAME0, S.Z_DISP1) + lugs()
    f = outer - slab(S.CAV_L, S.CAV_W, IN_R, Z_FRAME0 - 1, S.Z_DISP1 + 1)

    z0 = S.Z_PCB1 + S.GAP                                # glass ledges + glass locators, resting on the PCB
    blocks = box(S.DISP_X1 + GLASS_FIT, HL, -HW, HW, z0, S.Z_DISP1)    # antenna end: full width (copper only)
    for sy in (-1, 1):
        blocks += box(-HL, S.DISP_X0 + S.LEDGE, sy * S.LEDGE_Y, sy * HW, z0, S.Z_DISP1)
        blocks += box(S.DISP_X1 - S.LEDGE, HL, sy * S.LEDGE_Y, sy * HW, z0, S.Z_DISP1)
        blocks += box(-HL, HL, sy * Y_TOP, sy * HW, Z_STEP, S.Z_DISP1)   # thick upper wall (room for the top round)
    f += blocks & slab(S.CAV_L, S.CAV_W, IN_R, z0, S.Z_DISP1)
    # the -X end wall is only WALL thick and the top round eats it: a lip over the FPC bend keeps the bezel-gasket
    # land (chamfered underneath to clear the bend; prints as a bridge between the corner ledges)
    zl, yl = S.Z_DISP0 + FPC_T + 0.05, S.LEDGE_Y + 0.1
    xz = [(-HL - 0.3, zl - 0.42), (-HL, zl - 0.42), (-HL + 0.3, zl), (S.DISP_X0 - GLASS_FIT, zl),
          (S.DISP_X0 - GLASS_FIT, S.Z_DISP1), (-HL - 0.3, S.Z_DISP1)]
    f += extrude(make_face(Polyline(*[(x, -yl, z) for x, z in xz], close=True)), 2 * yl, dir=(0, 1, 0))
    gw = S.DISP_W / 2 + GLASS_FIT
    f -= box(S.DISP_X0 - GLASS_FIT, S.DISP_X1 + GLASS_FIT, -gw, gw, S.Z_DISP0, S.Z_DISP1 + 1)
    for sx in (-1, 1):                                   # drilled lugs: tip holes straight through both ears
        f -= ycyl(sx * X_BAR, -OW - 1, OW + 1, Z_BAR, BAR_TIP_HOLE)

    # mic beside the glass: the upper wall seals on the foam ring; a rib narrows the glass-edge gap over it
    x, y, zt = mic_port()
    sy = mic_sy()
    zr = zt + MIC_SEAL
    if MIC_BOX:
        x0, x1, y0, y1, _ = MIC_BOX
        f -= box(x0 - 0.2, x1 + 0.2, y0 - 0.2, y1 + 0.2, S.Z_PCB1, zr)          # clear the mic + ring
    if mic_beside_glass():
        f += box(x - MIC_RIB_X, x + MIC_RIB_X, sy * RIB_IN, sy * HW, zr, S.Z_DISP1)
    xd, yd = duct_xy()
    f -= cyl(xd, yd, zr - 1, S.Z_DISP1 + 1, MIC_BORE)
    for ref, _, bb in RELIEFS:                                     # pockets for parts that reach the upper wall
        f -= box(bb[0] - 0.1, bb[1] + 0.1, max(bb[2] - 0.1, -HW), min(bb[3] + 0.1, HW), S.Z_PCB1, bb[5] + 0.1)
    return f


def window_boxes():
    return [box(x - WIN_X, x + WIN_X, sy * Y_TOP, sy * (OW + 1), *WIN_Z) for x in S.TOUCH_X for sy in (-1, 1)]


def touch_thin():
    """Pockets that thin the wall to TOUCH_FACE over each electrode (inside face, below the top round)."""
    return union([box(x - S.TOUCH_L / 2 - 0.3, x + S.TOUCH_L / 2 + 0.3, sy * (HW - 1), sy * (OW - TOUCH_FACE),
                      WIN_Z[0] + 0.4, min(Z_STEP, Z_ROUND)) for x in S.TOUCH_X for sy in (-1, 1)])


def touch_windows(f):
    """Plain-PETG wall sections over the touch electrodes, thinned to TOUCH_FACE over the electrode."""
    return union([f & b for b in window_boxes()]) - touch_thin()


def split_rf(part, lap):
    """-> (CF part, RF part). RF = x >= X_RF; with lap, its upper half also overhangs the CF side by RF_LAP."""
    big = 100
    rf = box(X_RF, big, -big, big, -big, big)
    if lap:
        zm = (Z_FRAME0 + S.Z_DISP1) / 2
        rf += box(X_RF - RF_LAP, big, -big, big, zm, big)
    else:
        rf += box(X_RF - 1.2, X_RF, -3.0, 3.0, -1, S.FLOOR)          # tongue key into the CF back
    return part - rf, part & rf


def back():
    b = slab(S.CASE_L, S.CASE_W, S.CORNER_R, 0, S.FLOOR)
    top = S.Z_PCB0 - S.GAP
    blocks = slab(S.CAV_L - 2 * FIT, S.CAV_W - 2 * FIT, IN_R - FIT, S.FLOOR - 0.1, top)
    b += blocks & (box(-HL, X_MZ1, -HW, HW, 0, top) + box(S.BAT_X1 + 0.25, HL, -HW, HW, 0, top))
    b -= cyl(S.MOTOR_X, 0, MOTOR_Z0, top + 1, MOTOR_POCKET)                  # motor pocket: foam-tape seat on the floor
    b -= box(-HL - 1, X_MZ1 + 1, -1.2, 1.2, MOTOR_Z0, top + 1)               # open both ends (no slivers; lead room)
    b -= box(X_MZ1, S.BAT_X0 + BAT_RECESS_L, -S.BAT_W / 2 - 0.1, S.BAT_W / 2 + 0.1, S.FLOOR - BAT_RECESS, S.FLOOR + 1)
    for sy in (-1, 1):                                                   # pogo gasket strips sit in these
        b -= box(-HL + 0.5, X_MZ1 - 0.4, sy * (S.POGO_Y - 1.0), sy * (S.POGO_Y + 1.0),
                 S.Z_PCB0 - 0.03 - POGO_GASKET, top + 1)
    for x, y in POGO_XY:
        b -= cyl(x, y, -1, top + 1, POGO_HOLE_D)
        b -= Pos(x, y, -0.01) * Cone(POGO_HOLE_D / 2 + 0.35, POGO_HOLE_D / 2, 0.36,
                                     align=(Align.CENTER, Align.CENTER, Align.MIN))
    for sy in (-1, 1):
        b -= cyl(MAG_X, sy * MAG_Y, -1, MAG_T + 0.05, MAG_D + 0.1)          # blind from the skin side
        b -= box(-HL - 1, S.BAT_X0, sy * (S.POGO_Y + 1.2), sy * (HW + 1), MAG_T + 0.45, top + 1)  # wires + pads
    return b


def gasket_back(t=BACK_GASKET):
    ring = slab(S.CASE_L, S.CASE_W, S.CORNER_R, S.FLOOR, S.FLOOR + t)
    return ring - slab(S.CAV_L, S.CAV_W, IN_R, S.FLOOR - 1, S.FLOOR + t + 1)


def gasket_pogo(t=POGO_GASKET):
    """Two TPU strips under the PCB, one per pair of pogo pads."""
    z1 = S.Z_PCB0 - 0.03                                 # under the 30 um pads
    g = union([box(-HL + 0.55, X_MZ1 - 0.45, sy * (S.POGO_Y - 0.95), sy * (S.POGO_Y + 0.95), z1 - t, z1)
               for sy in (-1, 1)])
    for x, y in POGO_XY:
        g -= cyl(x, y, z1 - t - 1, z1 + 1, POGO_SEAL_D)
    return g


def window(z0, h):
    win = RectangleRounded(S.DISP_AA_L + 2 * WIN_M, S.DISP_AA_W + 2 * WIN_M, 0.6)
    return Pos(AA_CX, 0, z0) * extrude(win, h)


def gasket_bezel(t=S.BEZEL_GASKET):
    g = slab(S.CASE_L, S.CASE_W, S.CORNER_R, S.Z_DISP1, S.Z_DISP1 + t)
    x0, x1, y0, y1 = vent_box()
    return g - window(S.Z_DISP1 - 1, 3) - box(x0 - 0.1, x1 + 0.1, y0 - 0.1, y1 + 0.1, S.Z_DISP1 - 1, S.Z_DISP1 + 1)


def bezel():
    z0 = S.Z_DISP1 + S.BEZEL_GASKET
    b = slab(S.CASE_L, S.CASE_W, S.CORNER_R, z0, S.CASE_T) - window(S.Z_DISP1 - 1, 3)
    xd, yd = duct_xy()
    return b - cyl(xd, yd, z0 - 1, S.CASE_T + 1, MIC_HOLE)


def case_parts(style=None, variant="petg"):
    """Printed case parts clipped by the skin. variant 'petg' = one-piece parts; 'cf' = CF + PETG pieces."""
    e = skin(style)
    f = frame() & e
    b = back() & e
    common = dict(bezel=bezel() & e, gasket_back=gasket_back() & e, gasket_bezel=gasket_bezel() & e,
                  gasket_pogo=gasket_pogo(), mic_seal=mic_seal())
    if variant == "petg":
        return dict(frame=f - touch_thin(), back=b, **common)
    tw = touch_windows(f)
    frame_cf, frame_rf = split_rf(f - union(window_boxes()), lap=True)
    back_cf, back_rf = split_rf(b, lap=False)
    return dict(frame_cf=frame_cf, frame_rf=frame_rf, touch_windows=tw, back_cf=back_cf, back_rf=back_rf, **common)


# ---------------------------------------------------------------- dock (watch bottom = z 0)
def dock():
    d = slab(2 * DOCK_L2, 2 * DOCK_W2, 6.0, DOCK_ZB, DOCK_DEPTH)
    d = fillet(d.edges().group_by(Axis.Z)[-1], 1.5)
    pocket = slab(S.CASE_L + 0.6, S.CASE_W + 0.6, S.CORNER_R + 0.3, 0, 10)
    for sx in (-1, 1):
        pocket += box(sx * (OL - 1), sx * (DOCK_L2 + 1), -(STRAP_W / 2 + 0.3), STRAP_W / 2 + 0.3, 0, 10)
        for sy in (-1, 1):   # ear pockets: the ear tips locate the watch in X
            pocket += box(sx * (OL - S.CORNER_R), sx * (EAR_TIP + 0.3), sy * (STRAP_W / 2 - 0.2), sy * (OW + 0.3), 0, 10)
    d -= pocket
    bay_top = DOCK_ZB + DOCK_BAY_H
    for x, y in POGO_XY:
        d -= cyl(x, y, bay_top - 0.5, 1, PIN_BORE)
    for sy in (-1, 1):
        d -= cyl(MAG_X, sy * MAG_Y, -(MAG_T + 0.05), 1, MAG_D + 0.1)
    d -= box(S.MOTOR_X - 3, 5.5, -5.5, 5.5, DOCK_ZB - 1, bay_top)                # wiring bay, open below
    d -= box(-5.3, 5.3, DOCK_W2 - 12.3, DOCK_W2 + 1, DOCK_ZB - 1, bay_top)        # USB-C breakout, open at back
    return d


def pogo_pin(x, y, tip):
    barrel_top = PIN_TIP_FREE - PLUNGER_L
    p = cyl(x, y, PIN_TIP_FREE - PIN_L, barrel_top, PIN_D) + cyl(x, y, barrel_top - 0.01, tip - 0.2, PLUNGER_D)
    return p + Pos(x, y, tip - 0.2) * Cone(PLUNGER_D / 2, 0.12, 0.2, align=(Align.CENTER, Align.CENTER, Align.MIN))


def usb_board():
    z = DOCK_ZB + 0.2
    return (box(-5, 5, DOCK_W2 - 12, DOCK_W2 - 0.05, z, z + 0.8),
            box(-4.47, 4.47, DOCK_W2 - 7.35, DOCK_W2 - 0.05, z + 0.8, z + 0.8 + 3.16))


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
    global MIC_PORT, MIC_PORT_R, MIC_BOX, RELIEFS
    board, groups, comps, note = load_board()
    port, MIC_PORT_R, mbox = find_mic(comps)
    if port:
        MIC_PORT, MIC_BOX = port, mbox
        if S.DISP_X0 < port[0] < S.DISP_X1 and abs(port[1]) < S.DISP_W / 2:
            print(f"WARNING: mic port in the STEP is under the glass (|y| {abs(port[1]):.2f}); rotate MIC1 so the port "
                  f"faces the board edge")
        if abs(abs(port[1]) - (S.MIC_Y + 0.6)) > 0.05 or abs(port[0] - S.MIC_X) > 0.05:
            print(f"NOTE: STEP mic port ({port[0]:.2f}, {port[1]:+.2f}) differs from spec MIC_X/MIC_Y + 0.6")
    probe = frame()                                     # frame before reliefs: which parts poke into it?
    RELIEFS = []
    for ref, val, sh in comps:
        if ref.startswith("MIC") or interference(probe, sh) < 1e-3:
            continue
        bb = sh.bounding_box()
        RELIEFS.append((ref, val, (bb.min.X, bb.max.X, bb.min.Y, bb.max.Y, bb.min.Z, bb.max.Z)))
    tail, stiff, fit = fpc()
    bat, tabs = battery()
    m = case_parts()
    m["variant_cf"] = case_parts(variant="cf")
    m.update(display=display(), fpc=tail, stiffener=stiff,
             pcb=board, battery=bat, bat_tabs=tabs, case_magnets=union(magnets(0.0)),
             bars=spring_bars(), rf_pin=rf_pin(), strap=nato(), dock=dock(), dock_magnets=union(magnets(-MAG_T)))
    m.update(groups)
    m["pads"] = pads()
    m["touch"] = touch_pads()
    m["vent"] = vent()
    m["motor"], m["motor_leads"] = motor()
    m["pins_docked"] = union([pogo_pin(x, y, S.Z_PCB0 - 0.03) for x, y in POGO_XY])
    m["pins_free"] = union([pogo_pin(x, y, PIN_TIP_FREE) for x, y in POGO_XY])
    m["usb_pcb"], m["usb_c"] = usb_board()
    return m, fit, comps, note


CASE = ["frame", "back", "bezel", "gasket_back", "gasket_bezel", "gasket_pogo", "mic_seal"]
CF_PARTS = ["frame_cf", "frame_rf", "touch_windows", "back_cf", "back_rf"]
INTERNAL = ["display", "fpc", "stiffener", "pcb", "qfn", "ffc", "chips", "switches", "touch", "antenna", "pads",
            "battery", "bat_tabs", "case_magnets", "motor", "motor_leads", "vent"]
METAL = ["case_magnets", "bars"]


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


def checks(m, fit, comps):
    ok = True

    def verdict(good, text):
        nonlocal ok
        ok &= bool(good)
        print(f"  {'ok ' if good else 'BAD'} {text}")

    def near(name, got, want):
        verdict(abs(got - want) <= 0.05, f"{name:<22} {got:7.2f}  (spec {want:.2f})")
    print("dimension checks")
    body = union([m[k] for k in CASE]) & box(-OL, OL, -OW - 1, OW + 1, -1, S.CASE_T + 1)
    bb = body.bounding_box()
    near("body length", bb.size.X, S.CASE_L)
    near("body width", bb.size.Y, S.CASE_W)
    near("total thickness", bb.size.Z, S.CASE_T)
    lug = union([m[k] for k in CASE]).bounding_box()
    print(f"  shape '{SHAPE}' {SHAPES[SHAPE]}, lug-to-lug {lug.size.X:.2f} mm (+{(lug.size.X - S.CASE_L) / 2:.2f} per end), "
          f"touch window face {TOUCH_FACE} mm")
    v = m["variant_cf"]
    parts = {k: m[k] for k in ("frame", "back", "bezel")} | {k: v[k] for k in ("frame_cf", "frame_rf", "back_cf", "back_rf")}
    n = {k: len(s.solids()) for k, s in parts.items()}
    verdict(all(c == 1 for c in n.values()), "one solid each: " + ", ".join(f"{k} {c}" for k, c in n.items()))
    roots = ear_roots(m["frame"])
    want = 0.9 * EAR_W * (Z_EAR1 - Z_FRAME0)
    verdict(len(roots) == 4 and min(roots) >= want, f"lugs: {len(roots)} ears, root sections "
            f"{', '.join(f'{a:.2f}' for a in roots)} mm^2 (>= {want:.2f}: {EAR_W:.2f} x {Z_EAR1 - Z_FRAME0:.2f} full side band)")
    walls = min_wall(m["frame"], Z_FRAME0 + 0.05, S.Z_DISP1 - 0.05)
    (w, where), (wp, wherep) = walls["all"], walls["plain"]
    verdict(w >= MIN_WALL - 0.01, f"thinnest frame wall {w:.2f} mm at {where} (>= {MIN_WALL}); away from the "
            f"{TOUCH_FACE} touch faces {wp:.2f} at {wherep} (nominal {S.WALL})")
    near_cf = max(interference(v[k], b) for k in ("frame_cf", "back_cf")
                  for b in [box(x - S.TOUCH_L / 2 - TOUCH_CF_CLEAR, x + S.TOUCH_L / 2 + TOUCH_CF_CLEAR,
                                sy * (TOUCH_Y - S.TOUCH_W / 2 - TOUCH_CF_CLEAR), sy * (TOUCH_Y + S.TOUCH_W / 2 + TOUCH_CF_CLEAR),
                                S.Z_PCB1 - TOUCH_CF_CLEAR, S.Z_PCB1 + TOUCH_CF_CLEAR) for x in S.TOUCH_X for sy in (-1, 1)])
    verdict(near_cf < 1e-3, f"CF variant: no carbon within {TOUCH_CF_CLEAR} mm of the touch electrodes ({near_cf:.4f} mm^3)")
    print(f"  FPC: tip {fit['insertion']:.2f} mm into the FFC body ({FFC_D} deep), "
          f"{'slack %.2f' % fit['slack'] if fit['slack'] > 0 else 'short of the back by %.2f' % fit['short']} mm")
    cf_x = max(v[k].bounding_box().max.X for k in ("frame_cf", "back_cf"))
    ant_x = m["antenna"].bounding_box().min.X if "antenna" in m else S.ANT_X0 + 0.8
    verdict(cf_x <= X_RF + 1e-6 and ant_x - cf_x >= 1.0, f"CF variant: carbon ends at x = {cf_x:.2f}, antenna copper "
            f"starts at {ant_x:.2f} ({ant_x - cf_x:.2f} mm, need >= 1.0)")
    for k in METAL:
        if m[k].bounding_box().max.X > X_RF:
            print(f"  NOTE metal in the RF end: {k} (max x {m[k].bounding_box().max.X:.1f})")
    for net, (x, y), got in pogo_vs_pcb():
        verdict(got in (net, None), f"dock pin {net:<6} at ({x:+.2f}, {y:+.2f}): PCB pad there is "
                f"{got or 'not found (no .kicad_pcb?)'}")

    print("interference checks (mm^3)")
    assert interference(m["battery"], Pos(0, 0, 1) * m["battery"]) > 100, "interference check is blind"
    pairs = [(c, i) for c in CASE for i in INTERNAL if i in m]
    pairs += [(a, b) for i, a in enumerate(CASE) for b in CASE[i + 1:]]
    pairs += [("dock", k) for k in CASE + ["pins_docked", "dock_magnets", "usb_pcb", "usb_c"]]
    pairs += [("pins_docked", k) for k in CASE + ["pcb", "battery", "case_magnets"]]
    pairs += [(k, "rf_pin") for k in CASE + ["dock"]]
    pairs += [("strap", k) for k in CASE + ["bars", "rf_pin"]]
    pairs += [("motor", k) for k in ["battery", "bat_tabs", "case_magnets", "pcb"]]
    gap = S.Z_PCB0 - (MOTOR_Z0 + MOTOR_TAPE + S.MOTOR_T)
    print(f"  motor {S.MOTOR_D:g} x {S.MOTOR_T:g} on {MOTOR_TAPE} tape in a {MOTOR_POCKET:.1f} pocket on the {MOTOR_Z0:.2f} "
          f"floor: {gap:.2f} under the PCB for the soldered leads; battery {S.BAT_L:.1f} x {S.BAT_W:g} x {S.BAT_T:g} "
          f"at x {S.BAT_X0:.2f}..{S.BAT_X1:.2f}, PCM end {S.BAT_T + BAT_PCM_EXTRA:g} thick in a {BAT_RECESS} floor recess "
          f"({S.FLOOR - BAT_RECESS:.2f} floor left, {S.Z_PCB0 - (S.FLOOR - BAT_RECESS + S.BAT_T + BAT_PCM_EXTRA):.2f} under the PCB)")
    if gap < LEAD_GAP - 1e-6:
        print(f"  NOTE only {gap:.2f} mm between the motor and the PCB for the leads + solder joints")
    print(f"  straps {STRAP_W:.0f} mm on {BAR_D} spring bars: ears {EAR_W:.2f} x {Z_EAR1 - Z_FRAME0:.2f} mm, drilled "
          f"{BAR_TIP_HOLE} through, {EAR_R - BAR_TIP_HOLE / 2:.2f} mm around the hole; bar axis z {Z_BAR:.2f} "
          f"(strap {Z_BAR - STRAP_R:.2f}..{Z_BAR + STRAP_R:.2f} of {S.CASE_T:.2f})")
    print(f"  +X spring bar: axis {X_BAR - OL:.2f} mm past the +X case end, {X_BAR - S.PCB_L / 2:.2f} mm past the PCB edge "
          f"(bar surface {X_BAR - BAR_D / 2 - S.PCB_L / 2:.2f} mm)")
    for swing in (-30, 45, 90):                          # strap end must not bind when it swings about the bar
        hit = max(interference(nato(swing), m[k]) for k in CASE + ["bars", "rf_pin"])
        verdict(hit < 1e-3, f"strap swung {swing:+d} deg about the bar: {hit:.4f} mm^3 against the case")
    x, y, z = mic_port()
    xd, yd = duct_xy()
    inner, outer, side = mic_seal_walls()
    print(f"  mic port {2 * MIC_PORT_R:.2f} at ({x:.2f}, {y:+.2f}, z {z:.2f}): edge {abs(y) - MIC_PORT_R - S.DISP_W / 2:+.2f} "
          f"from the glass edge; duct {MIC_BORE} groove at |y| {abs(yd):.2f}; seal ring walls {inner:.2f} (under the "
          f"glass) / {outer:.2f} (lid edge) / {side:.2f}; vent {vent_box()[1] - vent_box()[0]:.2f} x "
          f"{abs(vent_box()[3] - vent_box()[2]):.2f}; outlet {MIC_HOLE}")
    if outer < 0.3:
        print(f"  NOTE mic seal ring outer wall {outer:.2f} mm (< 0.3): the port is too close to the glass edge")
    seat = fit["natural_tip"] + 0.2 - FFC_D / 2
    print(f"  FFC_X that seats the tail 0.2 mm short of the connector back: DISP_X0 + {seat - S.DISP_X0:.2f} "
          f"(spec DISP_X0 + {S.FFC_X - S.DISP_X0:.2f}); bend radius {fit['bend_r']:.2f} mm")
    worst = 0.0
    for a, b in pairs:
        v = interference(m[a], m[b])
        worst = max(worst, v)
        if v > 1e-3:
            ok = False
            print(f"  BAD {a} x {b}: {v:.4f}")
    print(f"  {len(pairs)} pairs, worst {worst:.5f}")
    hits = []
    for ref, val, sh in comps:   # every component body vs case, glass, battery, FPC
        for k in CASE + ["display", "battery"] + ([] if ref.startswith("J") else ["fpc", "stiffener"]):
            v = interference(m[k], sh)
            if v > 1e-3:
                hits.append(f"{ref} {val} x {k}: {v:.3f}")
    for ref, val, bb in RELIEFS:
        print(f"  NOTE frame relieved for {ref} {val} (x {bb[0]:.1f}..{bb[1]:.1f}, y {bb[2]:.1f}..{bb[3]:.1f}, "
              f"top z {bb[5]:.2f}) - move it inboard or lower it to drop the pocket")
    print(f"  per-component: {len(comps)} bodies, {len(hits)} collisions")
    for h in hits:
        print("  BAD", h)
    return ok and not hits


PRINT = {  # part -> (folder, material, rotation into print orientation, note)
    "frame": ("petg", "petg", (0, 0, 0), "upright, open top up; ledges bridge, no supports"),
    "back": ("petg", "petg", (0, 0, 0), "skin side down, no supports"),
    "bezel": ("petg", "petg", (180, 0, 0), "visible face down"),
    "dock": ("petg", "petg", (0, 0, 0), "upright, open bays down; 0.4 nozzle is fine"),
    "gasket_back": ("tpu", "tpu", (0, 0, 0), "flat, printed 0.40 (0.30 compressed), 0.1 layers"),
    "gasket_bezel": ("tpu", "tpu", (0, 0, 0), "flat, printed 0.25 (0.20 compressed), 0.08 layers"),
    "gasket_pogo": ("tpu", "tpu", (0, 0, 0), "flat, printed 0.60 (0.50 compressed)"),
    "mic_seal": ("tpu", "tpu", (0, 0, 0), "printed 0.30; die-cut PORON 0.3 is better (squeezed to 0.15)"),
    "frame_cf": ("variant-cf", "petg-cf", (0, 0, 0), "upright, 0.4 hardened nozzle"),
    "back_cf": ("variant-cf", "petg-cf", (0, 0, 0), "skin side down, 0.4 hardened nozzle"),
    "frame_rf": ("variant-cf", "petg", (0, 0, 0), "upright; antenna end, lap-jointed + glued to frame_cf"),
    "back_rf": ("variant-cf", "petg", (0, 0, 0), "skin side down; tongue-keyed + glued to back_cf"),
    "touch_windows": ("variant-cf", "petg", (0, 0, 0), "4 inserts, drop into the open-top wall notches, glued"),
}
DENSITY = {"petg-cf": 1.29e-3, "petg": 1.27e-3, "tpu": 1.21e-3}


def printable(m, k):
    """Part in print orientation, at its printed (uncompressed) thickness."""
    if k in GASKET_PRINT:
        s = globals()[k](GASKET_PRINT[k])
        if k not in ("gasket_pogo", "mic_seal"):
            s = s & skin()
    else:
        s = m[k] if k in m else m["variant_cf"][k]
    s = Rot(*PRINT[k][2]) * s
    return Pos(0, 0, -s.bounding_box().min.Z) * s


def summary(m):
    print(f"\n{'part':<13} {'material':<8} {'L x W x H (mm)':<20} {'g':>5}  print orientation")
    for k, (_, mat, _, note) in PRINT.items():
        s = printable(m, k)
        sz = s.bounding_box().size
        print(f"{k:<13} {mat:<8} {sz.X:5.1f} x {sz.Y:5.1f} x {sz.Z:4.2f} {vol(s) * DENSITY[mat]:6.2f}  {note}")


def export(m):
    import shutil
    for folder in {f for f, *_ in PRINT.values()}:      # keeps cad/out/variant-thin/ (written by --thin)
        shutil.rmtree(OUT / folder, ignore_errors=True)
    kids = []
    for k, v in m.items():
        if k in ("pins_free", "variant_cf"):
            continue
        v.label = k
        v.color = Color(COLORS.get(k, "#888888"))
        kids.append(v)
    OUT.mkdir(parents=True, exist_ok=True)
    export_step(Compound(children=kids, label="horae_rev_a"), str(OUT / "horae-assembly.step"))
    import trimesh                       # 3MF via trimesh: OCCT's 3MF mesher rejects some filleted parts
    stl = {}
    for k, (folder, mat, _, _) in PRINT.items():
        (OUT / folder).mkdir(exist_ok=True)
        stl[k] = OUT / folder / f"{k}.stl"
        export_stl(printable(m, k), str(stl[k]), tolerance=0.005, angular_tolerance=0.1)
        trimesh.Scene({k: trimesh.load(stl[k])}).export(OUT / folder / f"{k}.3mf")


# ---------------------------------------------------------------- renders
COLORS = dict(
    frame="#2f333a", back="#3a3f47", bezel="#22252a",
    frame_cf="#2e3238", back_cf="#3a3f47", frame_rf="#dcd6c4", back_rf="#cfc8b4",
    gasket_back="#e4572e", gasket_bezel="#e4572e", gasket_pogo="#e4572e", touch_windows="#cfc8b4", touch="#d9a92e", rf_pin="#c9cdd3", strap="#2b2d31", mic_seal="#e4572e", vent="#f7f7f2", motor="#a7adb4", motor_leads="#d8b246", display="#d9d7cf", fpc="#c8861a", stiffener="#9c6610",
    pcb="#1e5b3e", qfn="#2b2b2d", ffc="#e6dfca", chips="#3a3a3c", switches="#b9bec5", actuators="#1d1d1f",
    pads="#d9a92e", antenna="#c9a24a", battery="#c4c9cf", bat_tabs="#e3e6ea", case_magnets="#9ea4ab", dock_magnets="#9ea4ab",
    bars="#c9cdd3", dock="#e9e7e1", pins_docked="#d8b246", pins_free="#d8b246", usb_pcb="#23306a", usb_c="#c9cdd2",
)
WATCH = CASE + INTERNAL + ["bars", "rf_pin"]
_mesh_cache = {}


def pvmesh(shape):
    import pyvista as pv
    key = id(shape)
    if key not in _mesh_cache:
        v, t = shape.tessellate(0.004, 0.12)
        pts = np.array([(p.X, p.Y, p.Z) for p in v], float)
        faces = np.column_stack([np.full(len(t), 3), np.array(t)]).ravel()
        _mesh_cache[key] = (shape, pv.PolyData(pts, faces).compute_normals(split_vertices=True, feature_angle=32))
    return _mesh_cache[key][1]


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


def plotter(w=1600, h=1000, shape=(1, 1)):
    import pyvista as pv
    p = pv.Plotter(off_screen=True, window_size=(w, h), shape=shape, border=False)
    p.set_background("#e3e5e8", top="#fafbfc")
    p.enable_anti_aliasing("ssaa")
    return p


def add(p, m, keys, offset=(0, 0, 0), screen=True, alpha=None):
    import pyvista as pv
    for k in keys:
        if k not in m:
            continue
        o = offset.get(k, (0, 0, 0)) if isinstance(offset, dict) else offset
        metal = k in ("pads", "touch", "pins_docked", "pins_free", "bars", "case_magnets", "dock_magnets", "usb_c")
        p.add_mesh(pvmesh(m[k]).translate(o, inplace=False), color=COLORS.get(k, "#888888"), smooth_shading=True,
                   opacity=(alpha or {}).get(k, 1.0),
                   specular=0.6 if metal else 0.18, specular_power=40 if metal else 18, diffuse=0.85, ambient=0.18)
    if screen and "display" in keys:
        o = offset.get("display", (0, 0, 0)) if isinstance(offset, dict) else offset
        plane = pv.Plane(center=(AA_CX + o[0], o[1], S.Z_DISP1 + 0.004 + o[2]), direction=(0, 0, 1),
                         i_size=S.DISP_AA_L, j_size=S.DISP_AA_W)
        p.add_mesh(plane, texture=face_texture(), ambient=0.35, diffuse=0.75, specular=0.05)


def cam(p, pos, focal, zoom=1.0, up=(0, 0, 1)):
    p.camera_position = [pos, focal, up]
    p.camera.zoom(zoom)


def render_assembled(m):
    p = plotter(1600, 1000)
    add(p, m, WATCH + ["strap"])
    cam(p, (-48, -78, 58), (0, 0, 2.0), 1.3)
    p.screenshot(str(MEDIA / "cad-assembled.png"))
    p.close()


def label_font(size):
    from PIL import ImageFont
    for path, idx in [("/System/Library/Fonts/Avenir Next.ttc", 0), ("/System/Library/Fonts/Helvetica.ttc", 0)]:
        try:
            return ImageFont.truetype(path, size, index=idx)
        except OSError:
            pass
    return ImageFont.load_default(size)


def exploded(m, groups, off, fname, alpha=None, title=None):
    """Parallel-projection exploded view; groups = [(label, keys, anchor world point)]."""
    from PIL import Image, ImageDraw
    from vtkmodules.vtkRenderingCore import vtkCoordinate
    w, h = 1600, 1500
    p = plotter(w, h)
    add(p, m, list(off), off, alpha=alpha)
    p.enable_parallel_projection()
    cam(p, (-60, -100, 75), (17, 0, 15), 1.0)
    p.camera.parallel_scale = 31
    img = Image.fromarray(p.screenshot(return_img=True))
    coord = vtkCoordinate()
    coord.SetCoordinateSystemToWorld()
    anchors = []
    for _, _, pt in groups:
        coord.SetValue(*pt)
        x, y = coord.GetComputedDoubleDisplayValue(p.renderer)
        anchors.append((x, h - y))
    p.close()
    d = ImageDraw.Draw(img)
    f = label_font(27)
    tx, last = 1065, -1e9
    for i in sorted(range(len(groups)), key=lambda i: anchors[i][1]):
        label = groups[i][0]
        x, y = anchors[i]
        ty = max(y, last + (95 if "\n" in label else 70))   # keep labels from overlapping
        last = ty
        d.line([(x, y), (tx - 60, y), (tx - 12, ty)], fill=(70, 70, 70), width=2)
        d.ellipse([x - 5, y - 5, x + 5, y + 5], fill=(70, 70, 70))
        d.multiline_text((tx, ty), label, font=f, fill=(30, 30, 30), anchor="lm" if "\n" not in label else "ls")
    if title:
        d.text((40, 40), title, font=label_font(34), fill=(30, 30, 30))
    img.save(MEDIA / fname)


def render_exploded(m):
    groups = [  # (label, keys, z offset, anchor z)
        (f"Bezel, plain PETG, {S.LIP:g} lip\non a {S.BEZEL_GASKET:g} TPU gasket", ["bezel", "gasket_bezel"], 36, S.CASE_T),
        ("Display GDEM0097T61 + FPC tail", ["display", "fpc", "stiffener"], 27, S.Z_DISP1),
        (f"Frame, one-piece PETG, with\n{STRAP_W:g} mm spring-bar ears", ["frame", "bars", "rf_pin"],
         18, S.Z_DISP1 - 1),
        (f"PCB {S.PCB_T:g} mm + parts, touch pads, mic", ["pcb", "qfn", "ffc", "chips", "touch", "antenna", "pads",
                                                        "mic_seal", "vent"], 8, S.Z_PCB1),
        (f"Battery {S.BAT_L:.1f} x {S.BAT_W:g} x {S.BAT_T:.1f} + {S.MOTOR_D:g} x {S.MOTOR_T:g}\ncoin motor, both soldered to pads",
         ["battery", "bat_tabs", "motor", "motor_leads"], 0, S.Z_BAT1),
        (f"Back, one-piece PETG, {S.FLOOR:g} floor:\nmotor + pogo block, 2x2 magnets",
         ["back", "case_magnets", "gasket_back", "gasket_pogo"], -9, S.FLOOR),
    ]
    off = {k: (0, 0, dz) for _, keys, dz, _ in groups for k in keys}
    off.update(gasket_bezel=(0, 0, 33), gasket_back=(0, 0, -6.5), gasket_pogo=(0, 0, -6.0))
    exploded(m, [(lab, keys, (OL - 4, -OW, z + dz)) for lab, keys, dz, z in groups], off, "cad-exploded.png")


def render_sealing(m):
    ghost = {k: 0.22 for k in ("frame", "back", "bezel", "pcb", "display")}
    off = dict(bezel=(0, 0, 30), gasket_bezel=(0, 0, 25), vent=(0, 0, 25), display=(0, 0, 19), frame=(0, 0, 12),
               pcb=(0, 0, 4), touch=(0, 0, 4), mic_seal=(0, 0, 4), gasket_pogo=(0, 0, -2), gasket_back=(0, 0, -7),
               back=(0, 0, -12), case_magnets=(0, 0, -12))
    mx, my, mz = mic_port()
    vx0, vx1, vy0, vy1 = vent_box()
    groups = [
        (f"Bezel: PETG, {MIC_HOLE:g} mic outlet", ["bezel"], (OL - 4, -OW, S.CASE_T + 30)),
        (f"TPU bezel gasket {S.BEZEL_GASKET:g} + {vx1 - vx0:.1f} x {vy1 - vy0:.1f} mm\nhydrophobic mic vent in it",
         ["gasket_bezel", "vent"], (mx, my, S.Z_DISP1 + 25)),
        (f"Frame: one-piece PETG, touch areas\nthinned to {TOUCH_FACE:g}, {MIC_BORE:g} mic duct", ["frame"],
         (OL - 1, -OW, S.Z_DISP1 + 12)),
        ("Foam seal ring on the mic", ["mic_seal"], (mx, my, mz + 4)),
        ("TPU pogo seal under the PCB pads", ["gasket_pogo"], (S.MOTOR_X, -S.POGO_Y - 1, S.Z_PCB0 - 2.2)),
        (f"TPU back gasket {BACK_GASKET:g} (frame / back)", ["gasket_back"], (OL - 3, -OW + 0.4, S.FLOOR - 7)),
        ("Back: one-piece PETG", ["back"], (OL - 1.5, -OW, S.FLOOR - 12)),
    ]
    exploded(m, groups, off, "cad-sealing.png", alpha=ghost,
             title="Sealing (PETG ghosted, TPU / foam = orange)")


def render_dock(m):
    import pyvista as pv
    p = plotter(1600, 800, shape=(1, 2))
    p.subplot(0, 0)
    add(p, m, WATCH + ["dock", "pins_docked", "dock_magnets", "usb_pcb", "usb_c"])
    p.add_text("Watch on dock", font_size=16, color="#333333", position="upper_left")
    cam(p, (-60, -95, 75), (0, 0, -3), 1.2)
    p.subplot(0, 1)
    add(p, m, ["dock", "pins_free", "dock_magnets", "usb_pcb", "usb_c"])
    p.add_text("Dock: 4 P50 pogo pins (wired to the pads they meet), 2x2 magnets, USB-C at the back", font_size=14,
               color="#333333", position="upper_left")
    short = {"USB_DM": "D-", "USB_DP": "D+"}
    p.add_point_labels([(x, y, PIN_TIP_FREE + 0.6) for x, y, _ in POGO], [short.get(n, n) for *_, n in POGO],
                       font_size=20, point_size=1, shape_opacity=0.75, always_visible=True, text_color="#222222",
                       shape_color="#ffffff")
    cam(p, (-55, 95, 80), (-2, 0, -4), 1.3)
    p.screenshot(str(MEDIA / "cad-dock.png"))
    p.close()
    del pv


def min_wall(shape, z0, z1, step=0.1):
    """Thinnest material between two different boundaries (outer skin, cavity, pockets, ducts) in horizontal slices
    z0..z1 -> {"all": (mm, where), "plain": same but away from the thinned touch faces}. Fins with both faces on one
    boundary (the ears) are covered by ear_roots()."""
    from scipy.spatial import cKDTree
    best = {"all": (99.0, ""), "plain": (99.0, "")}
    tz = (WIN_Z[0] + 0.4 - 0.05, min(Z_STEP, Z_ROUND) + 0.05)
    for z in np.arange(z0, z1 + 1e-9, step):
        for f in (shape & (Plane.XY.offset(z) * Rectangle(400, 400))).faces():
            rings = [np.array([(q.X, q.Y) for q in (w.position_at(t) for t in np.linspace(0, 1, int(w.length / 0.03) + 20))])
                     for w in [f.outer_wire(), *f.inner_wires()]]
            for i in range(len(rings)):
                for j in range(i + 1, len(rings)):
                    d, _ = cKDTree(rings[j]).query(rings[i])
                    touch = (tz[0] <= z <= tz[1]) & (np.abs(rings[i][:, 1]) > HW - 1.1) & np.any(
                        [np.abs(rings[i][:, 0] - x) <= S.TOUCH_L / 2 + 0.35 + TOUCH_FACE for x in S.TOUCH_X], axis=0)
                    for key, mask in (("all", np.ones(len(d), bool)), ("plain", ~touch)):
                        if mask.any():
                            k = int(np.flatnonzero(mask)[np.argmin(d[mask])])
                            if d[k] < best[key][0]:
                                best[key] = (float(d[k]), f"z {z:.2f}, ({rings[i][k][0]:+.2f}, {rings[i][k][1]:+.2f})")
    return best


def section_polys(shape, y, x=None):
    """Cut shape with the plane y=const (or x=const) -> list of (outer, [holes]) polylines in (x or y, z)."""
    plane = Plane(origin=(x, 0, 0), z_dir=(1, 0, 0)) if x is not None else Plane(origin=(0, y, 0), z_dir=(0, 1, 0))
    cut = shape & (plane * Rectangle(400, 400))
    out = []
    for f in cut.faces():
        def pts(w):
            a = np.array([((q.Y if x is not None else q.X), q.Z) for q in (w.position_at(t) for t in np.linspace(0, 1, 240))])
            return a
        out.append((pts(f.outer_wire()), [pts(w) for w in f.inner_wires()]))
    return out


def render_section(m):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.patches import PathPatch
    from matplotlib.path import Path as MPath

    y, y2 = 0.0, S.POGO_Y
    keys = CASE + INTERNAL + ["bars", "rf_pin"]
    hatch = {"frame", "back", "bezel"}
    fig = plt.figure(figsize=(16, 10), dpi=100, facecolor="#f4f5f7")
    ax1 = fig.add_axes([0.03, 0.55, 0.94, 0.38])
    ax2 = fig.add_axes([0.03, 0.04, 0.55, 0.46])
    ax3 = fig.add_axes([0.62, 0.04, 0.35, 0.46])

    def area(a):
        return 0.5 * np.sum(a[:-1, 0] * a[1:, 1] - a[1:, 0] * a[:-1, 1])
    polys = {k: section_polys(m[k], y) for k in keys if k in m}
    polys2 = {k: section_polys(m[k], y2) for k in keys if k in m}
    ears = union([m["frame"] & box(sx * OL, sx * (EAR_TIP + 1), -OW, OW, -1, S.CASE_T) for sx in (-1, 1)])
    for outer, holes in section_polys(ears, -(OW - EAR_W / 2)):    # the ears beside the strap, behind the cut
        for r in [outer] + holes:
            ax1.fill(r[:, 0], r[:, 1], facecolor="#c9ccd1", edgecolor="#555", lw=0.6, ls="--", zorder=0)
    for ax, pp in ((ax1, polys), (ax2, polys2)):
        for k, ps in pp.items():
            for outer, holes in ps:
                rings = [outer if area(outer) > 0 else outer[::-1]] + [h if area(h) < 0 else h[::-1] for h in holes]
                verts = np.concatenate(rings)
                codes = np.concatenate([[MPath.MOVETO] + [MPath.LINETO] * (len(r) - 1) for r in rings])
                ax.add_patch(PathPatch(MPath(verts, codes), facecolor=COLORS[k], edgecolor="#111", lw=0.5,
                                       hatch="////" if k in hatch else None, alpha=0.95))
        ax.set_aspect("equal")
        ax.set_facecolor("#f4f5f7")
        ax.axis("off")
    ax1.set_xlim(-OL - 4.5, EAR_TIP + 16)
    ax1.set_ylim(-3.6, S.CASE_T + 1.6)
    ax1.set_title(f"Section at y = {y:+.2f} mm (through the motor), looking from -Y", fontsize=15, loc="left")

    # stack dimensions on the right of the full section
    layers = [("floor", 0, S.FLOOR), ("battery + swell", S.Z_BAT0, S.Z_BAT1), ("PCB", S.Z_PCB0, S.Z_PCB1),
              ("parts", S.Z_PCB1, S.Z_PCB1 + S.PART_H), ("glass", S.Z_DISP0, S.Z_DISP1),
              ("gasket", S.Z_DISP1, S.Z_DISP1 + S.BEZEL_GASKET), ("lip", S.Z_DISP1 + S.BEZEL_GASKET, S.CASE_T)]
    xd = EAR_TIP + 3.0
    last = 0
    for i, (name, z0, z1) in enumerate(layers):
        x = xd + (i % 2) * 0.9
        ax1.annotate("", (x, z0), (x, z1), arrowprops=dict(arrowstyle="<->", lw=0.8, color="#333333",
                                                           shrinkA=0, shrinkB=0))
        ty = (z0 + z1) / 2 if i == 0 else max((z0 + z1) / 2, last + 0.62)
        last = ty
        ax1.text(xd + 2.2, ty, f"{name} {z1 - z0:.2f}", va="center", fontsize=10, color="#222")
    xt = EAR_TIP + 12
    ax1.annotate("", (xt, 0), (xt, S.CASE_T), arrowprops=dict(arrowstyle="<->", lw=1.4, color="#c0392b",
                                                              shrinkA=0, shrinkB=0))
    ax1.text(xt + 0.5, S.CASE_T / 2, f"{S.CASE_T:.2f} mm\ntotal", va="center", fontsize=13, color="#c0392b",
             weight="bold")
    ax1.annotate("", (-OL, -2.4), (OL, -2.4), arrowprops=dict(arrowstyle="<->", lw=1.0, color="#333333",
                                                              shrinkA=0, shrinkB=0))
    ax1.text(0, -3.1, f"case body {S.CASE_L:.1f} mm   (lug-to-lug {2 * EAR_TIP:.1f} mm, {STRAP_W:g} mm spring-bar straps)",
             ha="center", fontsize=11)
    for x, label in [(S.DISP_X0 - 0.2, "-X: FPC end"), (S.DISP_X1 + 2.2, "+X: antenna end (plastic only)")]:
        ax1.text(x, S.CASE_T + 0.6, label, ha="center", fontsize=10, color="#555")
    for sx in (-1, 1):
        ax1.text(sx * X_BAR, Z_BAR - EAR_R - 0.4, "ear (dashed, beside\nthe strap) + spring bar", ha="center", va="top",
                 fontsize=9, color="#555")
    ax1.annotate("coin motor on foam tape,\nleads soldered to the PCB", (S.MOTOR_X, 1.8), (S.MOTOR_X + 4, -1.6),
                 fontsize=9, color="#333",
                 arrowprops=dict(arrowstyle="-", lw=0.6, color="#333"))

    ax2.set_xlim(-OL - 2.5, -5.5)
    ax2.set_ylim(-1.6, S.CASE_T + 1.6)
    ax2.set_title(f"Detail, -X end at y = {y2:+.1f} (through two pogo pins)", fontsize=13, loc="left")
    px = [x for x, yy in POGO_XY if yy > 0]
    L = -OL                                                    # notes relative to the -X case end
    notes = [((S.DISP_X0 - 0.6, S.Z_DISP0 - 0.3), (L - 2.6, S.CASE_T + 0.5), "FPC U-bend"),
             ((S.FFC_X - 1.0, S.Z_PCB1 + 0.5), (L + 6.5, S.CASE_T + 0.5), "FFC connector"),
             ((px[0], 1.5), (L + 7.2, 1.0), "pogo holes 1.3, pads above"), ((px[1], 1.5), (L + 7.2, 1.0), ""),
             ((L + 10.5, 2.0), (L + 10.0, 3.0), "battery"), ((L + 0.4, 3), (L - 1.2, -0.8), "frame wall"),
             ((L + 1.5, 0.3), (L + 3.0, -1.0), "back plate"), ((L + 1.0, S.CASE_T - 0.2), (L + 0.0, S.CASE_T + 1.0), "bezel"),
             ((L + 0.5, Z_FRAME0 - 0.15), (L - 4.1, 1.6), "TPU gasket"),
             ((px[1] + 0.8, S.Z_PCB0 - 0.25), (L + 7.2, 2.2), "TPU pogo seal"),
             ((L + 5.5, S.Z_DISP1 + 0.1), (L + 8.0, S.CASE_T + 1.1), "TPU bezel gasket")]
    for xy, txt, s in notes:
        ax2.annotate(s, xy, txt, fontsize=10, arrowprops=dict(arrowstyle="-", lw=0.7, color="#333"))

    ax3.axis("off")
    rows = [("lip (bezel)", S.LIP), ("bezel gasket (TPU)", S.BEZEL_GASKET), ("glass", S.DISP_T), ("gap", S.GAP),
            ("tallest part", S.PART_H), ("PCB", S.PCB_T), ("gap", S.GAP), ("battery swell", S.BAT_SWELL),
            ("battery", S.BAT_T), ("floor (back)", S.FLOOR)]
    assert abs(sum(v for _, v in rows) - S.CASE_T) < 1e-9, "stack table out of step with spec.CASE_T"
    ax3.text(0, 0.98, "Z stack (top down), mm", fontsize=13, weight="bold", va="top", transform=ax3.transAxes)
    for i, (n, v) in enumerate(rows):
        ax3.text(0.02, 0.88 - i * 0.075, n, fontsize=12, transform=ax3.transAxes)
        ax3.text(0.75, 0.88 - i * 0.075, f"{v:.2f}", fontsize=12, ha="right", transform=ax3.transAxes)
    ax3.text(0.02, 0.88 - len(rows) * 0.075, "total", fontsize=13, weight="bold", transform=ax3.transAxes)
    ax3.text(0.75, 0.88 - len(rows) * 0.075, f"{sum(v for _, v in rows):.2f}", fontsize=13, weight="bold",
             ha="right", transform=ax3.transAxes)
    fig.savefig(MEDIA / "cad-section.png", dpi=100, facecolor=fig.get_facecolor())
    plt.close(fig)


def render_scale(m):
    """Top and side orthographic views next to the Fitbit Charge 3 (size target) and the previous rev A outlines."""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.patches import FancyBboxPatch

    hw, zc = 30.0, S.CASE_T / 2

    def ortho(pos, focal, up, hh):                       # orthographic render with a known mm extent
        p = plotter(1600, round(1600 * hh / hw))
        p.set_background("#f4f5f7")
        add(p, m, WATCH)
        p.enable_parallel_projection()
        p.camera_position = [pos, focal, up]
        p.camera.parallel_scale = hh
        img = p.screenshot(transparent_background=True, return_img=True)
        p.close()
        return img
    top = ortho((0, 0, 100), (0, 0, 0), (0, 1, 0), 15.0)
    side = ortho((0, -100, zc), (0, 0, zc), (0, 0, 1), 7.5)

    fig, (ax, ax2) = plt.subplots(2, 1, figsize=(16, 8.4), dpi=100, facecolor="#f4f5f7",
                                  gridspec_kw=dict(height_ratios=[38, 15.5]))
    fig.subplots_adjust(0.01, 0.01, 0.99, 0.99, hspace=0.04)
    ax.imshow(top, extent=[-hw, hw, -15, 15], zorder=2)
    ax2.imshow(side, extent=[-hw, hw, zc - 7.5, zc + 7.5], zorder=2)
    cx = 50.0                                            # comparison outlines, centred here (L, W, T, plan R)
    refs = [("Fitbit Charge 3", (38.0, 18.3, 11.8, 5.0), "#1a73e8", "-", "corner radius guessed"),
            ("previous pass", (36.7, 20.0, 7.45, 3.2), "#d9822b", "-.", "Charge-6-length pass"),
            ("new rev A", (S.CASE_L, S.CASE_W, S.CASE_T, S.CORNER_R), "#3a4250", "--", "this case")]
    for i, (name, (l, w, h, r), col, ls, note) in enumerate(refs):
        ax.add_patch(FancyBboxPatch((cx - l / 2 + r, -w / 2 + r), l - 2 * r, w - 2 * r, boxstyle=f"round,pad={r}",
                                    fill=False, ec=col, lw=2.0, ls=ls))
        ax2.add_patch(FancyBboxPatch((cx - l / 2 + 1.2, 1.2), l - 2.4, h - 2.4, boxstyle="round,pad=1.2", fill=False,
                                     ec=col, lw=2.0, ls=ls))
        ax.text(cx - 19, 19.5 - 2.6 * i, f"{name}   {l:.1f} x {w:.1f} x {h:g} mm", fontsize=13, weight="bold",
                color=col, va="center")
        ax.text(cx + 15, 19.5 - 2.6 * i, f"({note})", fontsize=10, color="#777", va="center")
        x = cx + 20.5 + 3.4 * i
        ax2.annotate("", (x, 0), (x, h), arrowprops=dict(arrowstyle="<->", lw=1.1, color=col, shrinkA=0, shrinkB=0))
        ax2.text(x, h + 0.6, f"{h:g}", fontsize=11, color=col, ha="center")

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
    ax.text(0, OW + 3.5, f"Horae rev A   {S.CASE_L:.1f} x {S.CASE_W:.1f} x {S.CASE_T:.2f} mm", ha="center",
            fontsize=15, weight="bold", color="#222")
    ax.text(cx, -12.2, "plan outlines to scale (Charge 3 approximate)", ha="center", fontsize=10, color="#777")
    ax2.text(cx, 13.0, "side profiles to scale", ha="center", fontsize=10, color="#777")
    ax2.text(0, S.CASE_T + 1.2, f"side view: straps leave {Z_BAR - STRAP_R:.2f}..{Z_BAR + STRAP_R:.2f} above the wrist",
             ha="center", fontsize=11, color="#555")
    for a, (y0, y1) in ((ax, (-17, 21)), (ax2, (-1.5, 14))):
        a.set_xlim(-hw - 2, cx + 30)
        a.set_ylim(y0, y1)
        a.set_aspect("equal")
        a.set_facecolor("#f4f5f7")
        a.axis("off")
    fig.savefig(MEDIA / "cad-scale.png", dpi=100, facecolor=fig.get_facecolor(), bbox_inches=None)
    plt.close(fig)


def render_board(m, comps, note):
    """Top view, bezel + display + FPC hidden: what sits under the glass."""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.patches import Rectangle as MRect

    hw, hh = 25.0, 12.5
    p = plotter(1600, 800)
    p.set_background("#f4f5f7")
    add(p, m, ["frame", "back", "bars", "rf_pin", "pcb", "qfn", "ffc", "chips", "touch", "antenna"],
        alpha={"frame": 0.55})
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
    ax.add_patch(MRect((S.ANT_X0, -S.PCB_W / 2), S.CAV_L / 2 - S.ANT_X0, S.PCB_W, fill=False, ec="#c0392b",
                       lw=1.2, ls="--"))
    big = {}
    for ref, val, sh in comps:
        if ref.endswith(" nub") or ref[:1] in "CRL" and ref[:2] != "L4" or ref.startswith("D"):
            continue
        big[ref] = (val, sh.bounding_box().center())
    side = {}
    for ref, (val, c) in sorted(big.items(), key=lambda kv: kv[1][1].X):
        up = c.Y > 0 if not ref.startswith("SW") else c.Y > 0
        n = side.setdefault(up, 0)
        side[up] += 1
        ty = (hh + 0.8 + (n % 4) * 1.05) * (1 if up else -1)
        ax.annotate(f"{ref} {val}", (c.X, c.Y), (c.X, ty), ha="center", va="center", fontsize=10,
                    arrowprops=dict(arrowstyle="-", lw=0.6, color="#444"))
    ax.annotate("TCH1-4 touch electrodes\n(PETG wall windows)", (S.TOUCH_X[1], -TOUCH_Y), (S.TOUCH_X[1] + 7, -hh - 2.5),
                ha="left", va="center", fontsize=10, arrowprops=dict(arrowstyle="-", lw=0.6, color="#444"))
    if "antenna" in m:
        ac = m["antenna"].bounding_box().center()
        ax.annotate("AE1 PCB antenna (copper)", (ac.X, ac.Y), (hw + 2.5, 0), ha="left", va="center", fontsize=10,
                    arrowprops=dict(arrowstyle="-", lw=0.6, color="#444"))
    ax.text(S.DISP_X0, -S.DISP_W / 2 - 0.7, "glass outline (dashed), active area (dotted)", color="#2a6fdb",
            fontsize=10, va="top")
    ax.text(S.ANT_X0, S.PCB_W / 2 + 0.3, "antenna keep-out", color="#c0392b", fontsize=10, va="bottom")
    ax.set_title("Board in frame (frame semi-transparent; bezel, display, FPC hidden)", fontsize=14, loc="left")
    fig.text(0.01, 0.015, note, fontsize=9, color="#777")
    ax.set_xlim(-hw - 1, hw + 14)
    ax.set_ylim(-hh - 4.5, hh + 4.5)
    ax.set_aspect("equal")
    ax.axis("off")
    fig.savefig(MEDIA / "cad-board-in-case.png", dpi=100, facecolor=fig.get_facecolor())
    plt.close(fig)


def render_mic(m, comps):
    """Close-up YZ section through the mic port (x = port x): seal pad, duct, vent, outlet, glass edge."""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.patches import PathPatch
    from matplotlib.path import Path as MPath
    px, py, pz = mic_port()
    xd, yd = duct_xy()
    sy = mic_sy()
    keys = CASE + ["display", "fpc", "pcb", "chips", "ffc", "vent", "battery", "touch"]
    mic = [sh for ref, _, sh in comps if ref.startswith("MIC")]
    fig, ax = plt.subplots(figsize=(16, 9), dpi=100, facecolor="#f4f5f7")
    fig.subplots_adjust(0.02, 0.02, 0.98, 0.92)

    def area(a):
        return 0.5 * np.sum(a[:-1, 0] * a[1:, 1] - a[1:, 0] * a[:-1, 1])
    shapes = [(k, m[k]) for k in keys if k in m] + [("mic", sh) for sh in mic]
    for k, shp in shapes:
        for outer, holes in section_polys(shp, None, x=xd):
            rings = [r * np.array([sy, 1]) for r in [outer] + holes]          # show the mic side as +|y|
            rings = [rings[0] if area(rings[0]) > 0 else rings[0][::-1]] + [h if area(h) < 0 else h[::-1] for h in rings[1:]]
            verts = np.concatenate(rings)
            codes = np.concatenate([[MPath.MOVETO] + [MPath.LINETO] * (len(r) - 1) for r in rings])
            ax.add_patch(PathPatch(MPath(verts, codes), facecolor=COLORS.get(k, "#7a7f86"), edgecolor="#111", lw=0.6,
                                   hatch="////" if k in ("frame", "back", "bezel") else None))
    ay, ad = abs(py), abs(yd)
    vx0, vx1, vy0, vy1 = vent_box()
    inner, outer, side = mic_seal_walls()
    zt = S.Z_PCB1
    notes = [((ad, S.CASE_T - 0.12), (ad - 3.0, S.CASE_T + 0.8), f"outlet {MIC_HOLE:g} mm through the bezel"),
             (((abs(vy0) + abs(vy1)) / 2 - 0.3, S.Z_DISP1 + 0.08), (ad - 7.5, S.CASE_T + 0.35),
              f"{vx1 - vx0:.1f} x {vy1 - vy0:.1f} mm adhesive hydrophobic vent (gasket layer)"),
             ((ad + 0.7, S.Z_DISP1 + 0.1), (ad + 1.6, S.CASE_T + 0.8), "TPU bezel gasket"),
             ((ad + 0.1, (pz + S.Z_DISP1) / 2 + 0.2), (ad + 2.2, S.Z_DISP1 - 0.1), f"duct: {MIC_BORE:g} groove in the rib"),
             ((S.DISP_W / 2 + MIC_RIB_FIT / 2, S.Z_DISP0 + 0.6), (ad + 2.2, S.Z_DISP0 + 0.2),
              f"{MIC_RIB_FIT:g} glass-edge slit (small leak inward)"),
             ((ad + MIC_BORE / 2 + 0.05 + outer / 2, pz + 0.12), (ad + 2.2, zt + 0.95),
              f"foam seal ring on the lid ({outer:.2f} / {inner:.2f} walls)"),
             ((ay - 0.6, pz - 0.4), (ad + 2.2, zt + 0.35), "LMD2718 top-port mic"),
             ((S.DISP_W / 2 - 0.6, S.Z_DISP0 + 0.5), (ad - 7.5, S.CASE_T - 0.3), "glass"),
             ((ad - 1.0, S.Z_PCB0 + 0.3), (ad - 7.5, S.Z_PCB0 + 0.3), "PCB")]
    for xy, txt, label in notes:
        ax.annotate(label, xy, txt, fontsize=12, arrowprops=dict(arrowstyle="-", lw=0.7, color="#333"))
    ax.annotate("", (ay, pz), (ad, S.CASE_T + 0.45), arrowprops=dict(arrowstyle="<-", lw=1.5, color="#1a73e8"))
    ax.text(ad + 0.1, S.CASE_T + 0.4, "sound", color="#1a73e8", fontsize=11)
    ax.set_xlim(ad - 8.0, OW + 3.5)
    ax.set_ylim(S.Z_PCB0 - 0.4, S.CASE_T + 1.1)
    ax.set_aspect("equal")
    ax.axis("off")
    ax.set_title(f"Mic duct, section at x = {xd:+.2f} looking along X (port {2 * MIC_PORT_R:.2f} at |y| {ay:.2f}: its "
                 f"edge is {ay - MIC_PORT_R - S.DISP_W / 2:+.2f} mm from the glass edge)", fontsize=15, loc="left")
    fig.savefig(MEDIA / "cad-mic.png", dpi=100, facecolor=fig.get_facecolor())
    plt.close(fig)


def render_shape_options(m):
    """Two outer-shape candidates side by side (3/4 view + end-on profile)."""
    keys = ["frame", "back", "bezel", "gasket_back", "gasket_bezel"]
    rest = {k: m[k] for k in ("display", "bars", "rf_pin")}
    def title(name):
        r, (a, b), rb, kind = SHAPES[name]
        edge = "round" if kind == "fillet" else "chamfer"
        return f"R{r:g} plan, {a:g} x {b:g} top {edge}, {rb:g} bottom {edge}"
    opts = [(f"A  pebble (default): {title('pebble')}", {k: m[k] for k in keys}),
            (f"B  facet: {title('facet')}", case_parts("facet"))]
    p = plotter(1600, 1100, shape=(2, 2))
    for col, (title, parts) in enumerate(opts):
        mm = {**parts, **rest}
        p.subplot(0, col)
        add(p, mm, keys + list(rest))
        p.add_text(title, font_size=12, color="#333333", position="upper_left")
        cam(p, (-48, -78, 58), (0, 0, 2.0), 1.45)
        p.subplot(1, col)
        add(p, mm, keys + list(rest), screen=False)
        p.enable_parallel_projection()
        p.camera_position = [(80, 0, S.CASE_T / 2), (0, 0, S.CASE_T / 2), (0, 0, 1)]
        p.camera.parallel_scale = 7.5
        p.add_text("end-on profile (from +X)", font_size=11, color="#555555", position="upper_left")
    p.screenshot(str(MEDIA / "cad-shape-options.png"))
    p.close()


def main():
    m, fit, comps, note = build()
    print(f"PCB: {note}")
    ok = checks(m, fit, comps)
    summary(m)
    export(m)
    print(f"exports -> {OUT.relative_to(ROOT)}/")
    if "--no-render" not in sys.argv and not THIN:
        MEDIA.mkdir(parents=True, exist_ok=True)
        for f in (render_assembled, render_exploded, render_sealing, render_section, render_scale, render_dock):
            f(m)
        render_board(m, comps, note)
        render_shape_options(m)
        render_mic(m, comps)
        print(f"renders -> {MEDIA.relative_to(ROOT)}/cad-*.png")
    if not ok:
        sys.exit("checks FAILED")


if __name__ == "__main__":
    main()
