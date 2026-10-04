#!/usr/bin/env python3
"""Project Horae rev A mechanics: reference bodies, 3-part case, charging dock, checks, exports, renders.

    .venv/bin/python cad/horae.py            # everything (cad/out/*, media/2026-10-03/cad-*.png)
    .venv/bin/python cad/horae.py --no-render

All shared dimensions come from spec.py. Splash-resistant case, PETG-CF body with a plain-PETG RF window:
  frame  walls, glass ledges, 4 PETG touch windows, 16 mm spring-bar lugs, mic duct (PCB goes in from below, glass from
         above). Split at x = ANT_X0 - 1: frame_cf (PETG-CF) + frame_rf (PETG, antenna end), Z-stepped lap joint.
  back   0.6 mm floor + pogo/magnet block (-X) + support block (+X). Split the same way: back_cf + back_rf.
  bezel  0.5 mm lip with the display window, plain PETG (no CF over the antenna; 0.2 mm nozzle)
  TPU 95A: gasket_back (frame/back ring), gasket_bezel (bezel/glass+frame ring), gasket_pogo (seals the pogo
         wells on the PCB bottom)
  Outer shape: SHAPE envelope (rounded "pebble" by default) clips every case part.
If hardware/out/horae.step exists it replaces the placeholder PCB.
"""
import math
import sys
from pathlib import Path

import numpy as np
from build123d import (Align, Axis, Box, Color, Compound, Cone, Cylinder, Mesher, Plane, Pos, Rectangle,
                       RectangleRounded, Rot, export_step, export_stl, extrude, fillet, import_step)

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import spec as S  # noqa: E402

OUT = ROOT / "cad" / "out"
MEDIA = ROOT / "media" / "2026-10-03"
BOARD_STEP = ROOT / "hardware" / "out" / "horae.step"

# --- cad-only dimensions (case <-> dock; nothing here touches the PCB) ---
FIT = 0.1             # per-side clearance of the back-plate blocks in the cavity
GLASS_FIT = 0.15      # per-side clearance around the display glass
WIN_M = S.DISP_AA_MARGIN_FAR - S.LIP_OVERLAP   # window = active area + this (0.75) -> 1.0 overlap on 3 sides
MAG_D, MAG_T = 2.0, 2.0   # N52 disc in a blind pocket from the skin side (sealed), under each battery pad
MAG_X, MAG_Y = S.BATPAD_X, S.BATPAD_Y
POGO_XY = [(x, y) for x, y, _ in S.POGO_PADS]
POGO_PAD_D = 1.0
POGO_HOLE_D = 1.3     # P50-style pin: 1.0 barrel + 0.3
PIN_L, PIN_D, PLUNGER_D, PLUNGER_L = 16.0, 1.0, 0.6, 2.5
PIN_PRELOAD = 0.5     # free pin tip sits this far above the pad -> 0.5 mm of stroke used when docked
PIN_BORE = 1.1
STRAP_W = 16.0        # two-piece quick-release strap on standard spring bars; lug gap = STRAP_W
BAR_D = 1.5           # spring-bar body (1.78 bars also fit the tip holes)
BAR_TIP_HOLE, BAR_TIP_DEPTH = 1.1, 0.9   # blind holes from the inner ear faces -> 0.35 mm outer skin on 1.25 ears
BAR_DX = 2.2          # bar axis past the case end face: room for the curved strap end, back stays exposed
EAR_R = 1.8           # ear radius around the bar axis
MIC_GASKET = 0.25     # TPU/foam ring on the mic top around its port (compressed)
MIC_BORE, MIC_HOLE = 1.0, 0.7          # duct bore in the frame boss, outlet hole in the bezel
VENT_D, VENT_T = 2.2, 0.3              # pocket in the boss top for a 2.0 mm hydrophobic vent (GORE-style), under the gasket
MIC_BOSS_D, MIC_BOSS_OFF = 2.8, 0.25   # boss around duct + vent, shifted outward in |y| to clear the FPC edge
FFC_L, FFC_D, FFC_H = 12.5, 3.5, 1.0        # FH34SRJ-18S body (Y x X x Z), centred at S.FFC_X
BACK_GASKET = 0.3     # TPU ring between frame and back (compressed; printed 0.4). Frame starts above it
POGO_GASKET = 0.5     # TPU pad under the PCB around the pogo pads (compressed; printed 0.6)
POGO_SEAL_D = 0.8     # gasket hole around each 0.6 mm plunger; seals on the 1.0 mm pad ring
X_MZ1 = S.BAT_X0 - 0.25                 # end of the motor-zone block in the back
MOTOR_POCKET = S.MOTOR_D + 0.4
MOTOR_TAPE = 0.2      # foam tape under the motor
MOTOR_SPRING_FREE = 1.1   # free spring height above the motor can (check the part; 0.5 mm compression wanted)
GASKET_PRINT = {"gasket_back": 0.4, "gasket_bezel": 0.25, "gasket_pogo": 0.6, "mic_gasket": 0.3}   # printed (free) thickness
X_RF = S.ANT_X0 - 1.5 # RF window (no carbon) from here; antenna copper starts ~0.3 before ANT_X0 (feed)
RF_LAP = 1.5          # frame lap joint: the PETG upper half overhangs the CF lower half by this
TOUCH_Y = S.PCB_W / 2 - 0.3 - S.TOUCH_W / 2      # electrode centre |y|
TOUCH_CF_CLEAR = 1.0  # no carbon within this of an electrode
TOUCH_FACE = 0.6      # PETG window thickness over the electrode zone
WIN_X = S.TOUCH_L / 2 + TOUCH_CF_CLEAR             # window half-length
WIN_Z = (S.Z_PCB1 - TOUCH_CF_CLEAR - 0.1, S.Z_DISP1 + 1)   # open at the top: insert drops in, bezel caps it
Y_TOP = S.DISP_W / 2 + GLASS_FIT                   # cavity narrows to the glass above Z_STEP (thick upper wall)
Z_STEP = S.Z_DISP0 - 0.1   # parts within 1.0 mm of the long edges must be <= 1.1 tall (D4 1N5819WS is 1.11)
SHAPES = {  # name -> (plan corner R, top edge, bottom edge, kind)
    "pebble": (3.2, 2.5, 1.2, "fillet"),
    "facet": (3.2, 1.8, 0.8, "chamfer"),
}
SHAPE = "pebble"
DOCK_WALL, DOCK_DEPTH, DOCK_BAY_H = 2.5, 3.0, 4.5

IN_R = S.PCB_CORNER_R + FIT                       # cavity corners follow the PCB
HL, HW = S.CAV_L / 2, S.CAV_W / 2
OL, OW = S.CASE_L / 2, S.CASE_W / 2
Z_FRAME0 = S.FLOOR + BACK_GASKET
AA_X1 = S.DISP_X1 - S.DISP_AA_MARGIN_FAR
AA_X0 = AA_X1 - S.DISP_AA_L
AA_CX = (AA_X0 + AA_X1) / 2
X_BAR = OL + BAR_DX
Z_BAR = Z_FRAME0 + EAR_R + 0.2
EAR_TIP = X_BAR + EAR_R
PIN_TIP_FREE = S.Z_PCB0 + PIN_PRELOAD
DOCK_ZB = PIN_TIP_FREE - PIN_L - 0.6         # dock bottom (pin tail ends 0.6 above the table)
DOCK_L2 = EAR_TIP + 0.3 + DOCK_WALL
DOCK_W2 = OW + 0.3 + DOCK_WALL
assert S.PCB_CORNER_R <= IN_R - FIT + 1e-9, "PCB corners must sit inside the cavity corner radius"
assert X_RF - RF_LAP > max(S.TOUCH_X) + WIN_X, "RF lap joint runs into a touch window"


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
    t, w = 0.12, S.FPC_W
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
                                 short=ffc_back - natural_tip)


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
    if "FH34SRJ" in name:
        l, w, h = FFC_L, FFC_D, FFC_H
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
        near = min(top, key=lambda f: math.dist(to_case(f), (bc.X, bc.Y)), default=None)
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
    z0, z1 = S.Z_BAT0, S.Z_BAT0 + S.BAT_T
    body = box(S.BAT_X0 + 1.5, S.BAT_X1, -S.BAT_W / 2, S.BAT_W / 2, z0, z1)
    body = fillet(body.edges().group_by(Axis.Z)[-1], 0.9)
    seal = box(S.BAT_X0 + 0.4, S.BAT_X0 + 1.6, -S.BAT_W / 2 + 0.3, S.BAT_W / 2 - 0.3, z0 + 0.6, z1 - 0.6)
    tabs = union([box(S.BAT_X0, S.BAT_X0 + 0.5, sy * 4.5, sy * 6.5, z0 + 1.15, z0 + 1.35) for sy in (-1, 1)])
    return body + seal, tabs


def motor():
    """Coin ERM on 0.2 foam tape; two contact springs (shown compressed) up to the PCB pads."""
    z0 = S.FLOOR + MOTOR_TAPE
    body = cyl(S.MOTOR_X, 0, z0, z0 + S.MOTOR_T, S.MOTOR_D)
    springs = union([cyl(S.MOTOR_X + dx, 0, z0 + S.MOTOR_T, S.Z_PCB0 - 0.03, 0.9) for dx in (-S.MOTOR_PAD_DX, S.MOTOR_PAD_DX)])
    return body, springs


def magnets(z0):
    return [cyl(MAG_X, sy * MAG_Y, z0, z0 + MAG_T, MAG_D) for sy in (-1, 1)]


def spring_bar(sx):
    """Standard 16 mm spring bar: body + tips in the blind ear holes."""
    return (ycyl(sx * X_BAR, -STRAP_W / 2 + 0.05, STRAP_W / 2 - 0.05, Z_BAR, BAR_D)
            + ycyl(sx * X_BAR, -STRAP_W / 2 - BAR_TIP_DEPTH + 0.1, STRAP_W / 2 + BAR_TIP_DEPTH - 0.1, Z_BAR, 0.8))


def spring_bars():
    return spring_bar(-1)


def rf_pin():
    """+X spring bar (steel; kept as far from the antenna as the lug allows). Key name kept for the renders."""
    return spring_bar(1)


def nato():
    """Two-piece strap stubs: curved end around each bar + 12 mm of strap (render + clearance only)."""
    w, t, r = STRAP_W / 2 - 0.1, 1.8, BAR_D / 2 + 1.1
    parts = []
    for sx in (-1, 1):
        parts.append(ycyl(sx * X_BAR, -w, w, Z_BAR, 2 * r))
        parts.append(box(sx * X_BAR, sx * (X_BAR + 12), -w, w, Z_BAR + r - t, Z_BAR + r))
    return union(parts) - union([ycyl(sx * X_BAR, -w - 1, w + 1, Z_BAR, BAR_D + 0.1) for sx in (-1, 1)])


def mic_port():
    """(x, y, top z) of the mic's acoustic port: from the board STEP model when present, else from spec."""
    return MIC_PORT


MIC_PORT = (S.MIC_X - 0.595, S.MIC_Y, S.Z_PCB1 + 0.9)   # replaced by build() from the STEP
MIC_BOX = None                                          # mic body bbox (x0, x1, y0, y1, z1) from the STEP


def find_mic(comps):
    """Locate MIC1 and its port (small circle on the top face) in the board bodies."""
    from build123d import GeomType
    for ref, val, sh in comps:
        if ref.startswith("MIC"):
            bb = sh.bounding_box()
            ports = [e.arc_center for e in sh.edges() if e.geom_type == GeomType.CIRCLE and e.radius < 0.3
                     and abs(e.arc_center.Z - bb.max.Z) < 0.02]
            c = ports[0] if ports else bb.center()
            return (c.X, c.Y, bb.max.Z), (bb.min.X, bb.max.X, bb.min.Y, bb.max.Y, bb.max.Z)
    return None, None


def mic_gasket(t=MIC_GASKET):
    x, y, z = mic_port()
    return cyl(x, y, z, z + t, 1.5) - cyl(x, y, z - 1, z + t + 1, 0.6)


def vent_xy():
    x, y, _ = mic_port()
    return x - 0.2, y + math.copysign(MIC_BOSS_OFF, y)   # away from the glass gap and the FPC


def vent():
    x, y = vent_xy()
    return cyl(x, y, S.Z_DISP1 - VENT_T, S.Z_DISP1 - 0.05, VENT_D - 0.2)


# ---------------------------------------------------------------- case
def skin(style=None):
    """Outer skin that clips every case part: rounded plan + rounded/chamfered top and bottom edges."""
    r_plan, r_top, r_bot, kind = SHAPES[style or SHAPE]
    e = slab(S.CASE_L, S.CASE_W, r_plan, 0, S.CASE_T)
    top, bot = e.edges().group_by(Axis.Z)[-1], e.edges().group_by(Axis.Z)[0]
    if kind == "fillet":
        e = fillet(top, r_top)
        e = fillet(e.edges().group_by(Axis.Z)[0], r_bot)
    else:
        from build123d import chamfer
        e = chamfer(top, r_top)
        e = chamfer(e.edges().group_by(Axis.Z)[0], r_bot)
    big = 100
    return e + box(OL, big, -big, big, -big, big) + box(-big, -OL, -big, big, -big, big)   # lugs are not clipped


def frame():
    """Whole frame, before the touch windows and the CF/RF split."""
    outer = slab(S.CASE_L, S.CASE_W, S.CORNER_R, Z_FRAME0, S.Z_DISP1)
    for sx in (-1, 1):                                   # spring-bar lug ears
        for sy in (-1, 1):
            y0, y1 = sy * STRAP_W / 2, sy * OW           # ear = 1.25 mm
            outer += box(sx * (OL - S.CORNER_R), sx * X_BAR, y0, y1, Z_FRAME0, Z_BAR + EAR_R)
            outer += ycyl(sx * X_BAR, y0, y1, Z_BAR, 2 * EAR_R)
    f = outer - slab(S.CAV_L, S.CAV_W, IN_R, Z_FRAME0 - 1, S.Z_DISP1 + 1)

    z0 = S.Z_PCB1 + S.GAP                                # glass ledges + glass locators, resting on the PCB
    blocks = box(S.DISP_X1 + GLASS_FIT, HL, -HW, HW, z0, S.Z_DISP1)    # antenna end: full width (copper only)
    for sy in (-1, 1):
        blocks += box(-HL, S.DISP_X0 + S.LEDGE, sy * S.LEDGE_Y, sy * HW, z0, S.Z_DISP1)
        blocks += box(S.DISP_X1 - S.LEDGE, HL, sy * S.LEDGE_Y, sy * HW, z0, S.Z_DISP1)
        blocks += box(-HL, HL, sy * Y_TOP, sy * HW, Z_STEP, S.Z_DISP1)   # thick upper wall (room for the top round)
    f += blocks & slab(S.CAV_L, S.CAV_W, IN_R, z0, S.Z_DISP1)
    gw = S.DISP_W / 2 + GLASS_FIT
    f -= box(S.DISP_X0 - GLASS_FIT, S.DISP_X1 + GLASS_FIT, -gw, gw, S.Z_DISP0, S.Z_DISP1 + 1)

    for sx in (-1, 1):                                   # blind spring-bar tip holes
        for sy in (-1, 1):
            f -= ycyl(sx * X_BAR, sy * (STRAP_W / 2 - 0.5), sy * (STRAP_W / 2 + BAR_TIP_DEPTH), Z_BAR, BAR_TIP_HOLE)

    x, y, zt = mic_port()                                # mic: relieve the ledge, sealed duct up to the bezel
    if MIC_BOX:
        x0, x1, y0, y1, ztop = MIC_BOX
        zr = ztop + MIC_GASKET
        f -= box(x0 - 0.2, x1 + 0.2, y0 - 0.2, y1 + 0.2, S.Z_PCB1, zr)
        f -= box(S.DISP_X0 - GLASS_FIT, x1 + 0.2, y0 - 0.2, y1 + 0.2, S.Z_PCB1, S.Z_DISP0)
    else:
        zr = zt + MIC_GASKET
    vx, vy = vent_xy()
    f += (cyl(vx, vy, zr, S.Z_DISP1, MIC_BOSS_D) & slab(S.CAV_L, S.CAV_W, IN_R, zr, S.Z_DISP1)
          & box(-HL - 1, S.DISP_X0 - GLASS_FIT, -HW, HW, zr, S.Z_DISP1))
    f -= cyl(x, y, zr - 1, S.Z_DISP1 + 1, MIC_BORE)
    f -= cyl(vx, vy, S.Z_DISP1 - VENT_T, S.Z_DISP1 + 1, VENT_D)          # vent pocket, capped by the bezel gasket
    return f


def window_boxes():
    return [box(x - WIN_X, x + WIN_X, sy * Y_TOP, sy * (OW + 1), *WIN_Z) for x in S.TOUCH_X for sy in (-1, 1)]


def touch_windows(f):
    """Plain-PETG wall sections over the touch electrodes, thinned to TOUCH_FACE over the electrode."""
    w = union([f & b for b in window_boxes()])
    for x in S.TOUCH_X:
        for sy in (-1, 1):
            w -= box(x - S.TOUCH_L / 2 - 0.3, x + S.TOUCH_L / 2 + 0.3, sy * (HW - 1), sy * (OW - TOUCH_FACE),
                     WIN_Z[0] + 0.4, Z_STEP)
    return w


def split_rf(part, lap):
    """-> (CF part, RF part). RF = x >= X_RF; with lap, its upper half also overhangs the CF side by RF_LAP."""
    big = 100
    rf = box(X_RF, big, -big, big, -big, big)
    if lap:
        zm = (Z_FRAME0 + S.Z_DISP1) / 2
        rf += box(X_RF - RF_LAP, big, -big, big, zm, big)
    return part - rf, part & rf


def back():
    b = slab(S.CASE_L, S.CASE_W, S.CORNER_R, 0, S.FLOOR)
    top = S.Z_PCB0 - S.GAP
    blocks = slab(S.CAV_L - 2 * FIT, S.CAV_W - 2 * FIT, IN_R - FIT, S.FLOOR - 0.1, top)
    b += blocks & (box(-HL, X_MZ1, -HW, HW, 0, top) + box(S.BAT_X1 + 0.25, HL, -HW, HW, 0, top))
    b -= cyl(S.MOTOR_X, 0, S.FLOOR, top + 1, MOTOR_POCKET)               # motor pocket down to the floor
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
    x, y, _ = mic_port()
    return g - window(S.Z_DISP1 - 1, 3) - cyl(x, y, S.Z_DISP1 - 1, S.Z_DISP1 + 1, MIC_HOLE + 0.2)


def bezel():
    z0 = S.Z_DISP1 + S.BEZEL_GASKET
    b = slab(S.CASE_L, S.CASE_W, S.CORNER_R, z0, S.CASE_T) - window(S.Z_DISP1 - 1, 3)
    x, y, _ = mic_port()
    return b - cyl(x, y, z0 - 1, S.CASE_T + 1, MIC_HOLE)


def case_parts(style=None):
    """All printed case parts, clipped by the outer envelope."""
    e = skin(style)
    f = frame() & e
    tw = touch_windows(f)
    f = f - union(window_boxes())
    frame_cf, frame_rf = split_rf(f, lap=True)
    back_cf, back_rf = split_rf(back() & e, lap=False)
    return dict(frame_cf=frame_cf, frame_rf=frame_rf, touch_windows=tw, back_cf=back_cf, back_rf=back_rf,
                bezel=bezel() & e, gasket_back=gasket_back() & e, gasket_bezel=gasket_bezel() & e,
                gasket_pogo=gasket_pogo(), mic_gasket=mic_gasket())


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
    global MIC_PORT, MIC_BOX
    board, groups, comps, note = load_board()
    port, mbox = find_mic(comps)
    if port:
        MIC_PORT, MIC_BOX = port, mbox
    tail, stiff, fit = fpc()
    bat, tabs = battery()
    m = case_parts()
    m.update(display=display(), fpc=tail, stiffener=stiff,
             pcb=board, battery=bat, bat_tabs=tabs, case_magnets=union(magnets(0.0)),
             bars=spring_bars(), rf_pin=rf_pin(), strap=nato(), dock=dock(), dock_magnets=union(magnets(-MAG_T)))
    m.update(groups)
    m["pads"] = pads()
    m["touch"] = touch_pads()
    m["vent"] = vent()
    m["motor"], m["motor_springs"] = motor()
    m["pins_docked"] = union([pogo_pin(x, y, S.Z_PCB0 - 0.03) for x, y in POGO_XY])
    m["pins_free"] = union([pogo_pin(x, y, PIN_TIP_FREE) for x, y in POGO_XY])
    m["usb_pcb"], m["usb_c"] = usb_board()
    return m, fit, comps, note


CASE = ["frame_cf", "frame_rf", "touch_windows", "back_cf", "back_rf", "bezel", "gasket_back", "gasket_bezel",
        "gasket_pogo", "mic_gasket"]
INTERNAL = ["display", "fpc", "stiffener", "pcb", "qfn", "ffc", "chips", "switches", "touch", "antenna", "pads",
            "battery", "bat_tabs", "case_magnets", "motor", "motor_springs", "vent"]
METAL = ["case_magnets", "bars"]


def checks(m, fit, comps):
    ok = True

    def near(name, got, want):
        nonlocal ok
        good = abs(got - want) <= 0.05
        ok &= good
        print(f"  {'ok ' if good else 'BAD'} {name:<22} {got:7.2f}  (spec {want:.2f})")
    print("dimension checks")
    body = union([m[k] for k in CASE]) & box(-OL, OL, -OW - 1, OW + 1, -1, S.CASE_T + 1)
    bb = body.bounding_box()
    near("body length", bb.size.X, S.CASE_L)
    near("body width", bb.size.Y, S.CASE_W)
    near("total thickness", bb.size.Z, S.CASE_T)
    print(f"  shape '{SHAPE}' {SHAPES[SHAPE]}, lug-to-lug {2 * EAR_TIP:.2f} mm, touch window face {TOUCH_FACE} mm")
    w, where = min_wall(union([m[k] for k in ("frame_cf", "frame_rf", "touch_windows")]))
    good = w >= 0.8 - 1e-6
    ok &= good
    print(f"  {'ok ' if good else 'BAD'} thinnest frame wall {w:.2f} mm ({where})")
    near_cf = max(interference(m[k], b) for k in ("frame_cf", "back_cf", "bezel")
                  for b in [box(x - S.TOUCH_L / 2 - TOUCH_CF_CLEAR, x + S.TOUCH_L / 2 + TOUCH_CF_CLEAR,
                                sy * (TOUCH_Y - S.TOUCH_W / 2 - TOUCH_CF_CLEAR), sy * (TOUCH_Y + S.TOUCH_W / 2 + TOUCH_CF_CLEAR),
                                S.Z_PCB1 - TOUCH_CF_CLEAR, S.Z_PCB1 + TOUCH_CF_CLEAR) for x in S.TOUCH_X for sy in (-1, 1)])
    ok &= near_cf < 1e-3
    print(f"  {'ok ' if near_cf < 1e-3 else 'BAD'} no carbon within {TOUCH_CF_CLEAR} mm of the touch electrodes "
          f"({near_cf:.4f} mm^3)")
    print(f"  FPC: tip {fit['insertion']:.2f} mm into the FFC body ({FFC_D} deep), "
          f"{'slack %.2f' % fit['slack'] if fit['slack'] > 0 else 'short of the back by %.2f' % fit['short']} mm")
    cf_x = max(m[k].bounding_box().max.X for k in ("frame_cf", "back_cf"))
    ant_x = m["antenna"].bounding_box().min.X if "antenna" in m else S.ANT_X0 + 0.8
    good = cf_x <= X_RF + 1e-6 and ant_x - cf_x >= 1.0
    ok &= good
    print(f"  {'ok ' if good else 'BAD'} carbon ends at x = {cf_x:.2f}, antenna copper starts at {ant_x:.2f} "
          f"({ant_x - cf_x:.2f} mm, need >= 1.0)")
    for k in METAL:
        if m[k].bounding_box().max.X > X_RF:
            print(f"  NOTE metal in the RF end: {k} (max x {m[k].bounding_box().max.X:.1f})")

    print("interference checks (mm^3)")
    assert interference(m["battery"], Pos(0, 0, 1) * m["battery"]) > 100, "interference check is blind"
    pairs = [(c, i) for c in CASE for i in INTERNAL if i in m]
    pairs += [(a, b) for i, a in enumerate(CASE) for b in CASE[i + 1:]]
    pairs += [("dock", k) for k in CASE + ["pins_docked", "dock_magnets", "usb_pcb", "usb_c"]]
    pairs += [("pins_docked", k) for k in CASE + ["pcb", "battery", "case_magnets"]]
    pairs += [(k, "rf_pin") for k in CASE + ["dock"]]
    pairs += [("strap", k) for k in CASE + ["bars", "rf_pin"]]
    pairs += [("motor", k) for k in ["battery", "bat_tabs", "case_magnets", "pcb"]]
    comp = S.FLOOR + MOTOR_TAPE + S.MOTOR_T + MOTOR_SPRING_FREE - S.Z_PCB0
    print(f"  motor spring compression {comp:.2f} mm (free {MOTOR_SPRING_FREE}), pocket {MOTOR_POCKET} dia, "
          f"battery {S.BAT_L:.1f} x {S.BAT_W} x {S.BAT_T} at x {S.BAT_X0:.2f}..{S.BAT_X1:.2f}")
    ear = OW - STRAP_W / 2
    print(f"  straps {STRAP_W:.0f} mm on spring bars: ears {ear:.2f} mm, tip holes {BAR_TIP_HOLE} x {BAR_TIP_DEPTH} deep "
          f"({ear - BAR_TIP_DEPTH:.2f} skin), lug-to-lug {2 * EAR_TIP:.1f} mm")
    print(f"  +X spring bar: axis {X_BAR - OL:.2f} mm past the +X case end, {X_BAR - S.PCB_L / 2:.2f} mm past the PCB edge "
          f"(bar surface {X_BAR - BAR_D / 2 - S.PCB_L / 2:.2f} mm)")
    x, y, z = mic_port()
    print(f"  mic port at ({x:.2f}, {y:+.2f}, z {z:.2f}), {S.DISP_X0 - x:.2f} mm past the glass edge; spec MIC_Y {S.MIC_Y:+.2f}")
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
    print(f"  per-component: {len(comps)} bodies, {len(hits)} collisions")
    for h in hits:
        print("  BAD", h)
    return ok and not hits


PRINT = {  # part -> (material, rotation into print orientation, note)
    "frame_cf": ("petg-cf", (0, 0, 0), "upright, 0.4 hardened nozzle; ledges/windows bridge, no supports"),
    "frame_rf": ("petg", (0, 0, 0), "upright; RF window, no carbon. AMS lite: print with frame_cf as one object"),
    "touch_windows": ("petg", (0, 0, 0), "4 wall inserts; AMS lite: print with frame_cf as one object, else glue"),
    "back_cf": ("petg-cf", (0, 0, 0), "skin side down, 0.4 hardened nozzle"),
    "back_rf": ("petg", (0, 0, 0), "skin side down; RF window. AMS lite: print with back_cf as one object"),
    "bezel": ("petg", (180, 0, 0), "visible face down, 0.2 nozzle; plain PETG (no carbon over the antenna)"),
    "gasket_back": ("tpu", (0, 0, 0), "flat, printed 0.40 (0.30 compressed), 0.1 layers"),
    "gasket_bezel": ("tpu", (0, 0, 0), "flat, printed 0.25 (0.20 compressed), 0.08 layers"),
    "gasket_pogo": ("tpu", (0, 0, 0), "flat, printed 0.60 (0.50 compressed)"),
    "mic_gasket": ("tpu", (0, 0, 0), "1.5 OD ring, printed 0.3; die-cut PORON is easier"),
    "dock": ("petg", (0, 0, 0), "upright, open bays down; bay ceilings bridge"),
}
DENSITY = {"petg-cf": 1.29e-3, "petg": 1.27e-3, "tpu": 1.21e-3}


def printable(m, k):
    """Part in print orientation, at its printed (uncompressed) thickness."""
    if k in GASKET_PRINT:
        s = globals()[k](GASKET_PRINT[k])
        if k not in ("gasket_pogo", "mic_gasket"):
            s = s & skin()
    else:
        s = m[k]
    s = Rot(*PRINT[k][1]) * s
    return Pos(0, 0, -s.bounding_box().min.Z) * s


def summary(m):
    print(f"\n{'part':<13} {'material':<8} {'L x W x H (mm)':<20} {'g':>5}  print orientation")
    for k, (mat, _, note) in PRINT.items():
        s = printable(m, k)
        sz = s.bounding_box().size
        print(f"{k:<13} {mat:<8} {sz.X:5.1f} x {sz.Y:5.1f} x {sz.Z:4.2f} {vol(s) * DENSITY[mat]:6.2f}  {note}")


def export(m):
    import shutil
    shutil.rmtree(OUT, ignore_errors=True)
    kids = []
    for k, v in m.items():
        if k in ("pins_free",):
            continue
        v.label = k
        v.color = Color(COLORS.get(k, "#888888"))
        kids.append(v)
    OUT.mkdir(parents=True)
    export_step(Compound(children=kids, label="horae_rev_a"), str(OUT / "horae-assembly.step"))
    import trimesh                       # 3MF via trimesh: OCCT's 3MF mesher rejects some filleted parts
    stl = {}
    for k, (mat, _, _) in PRINT.items():
        (OUT / mat).mkdir(exist_ok=True)
        stl[k] = OUT / mat / f"{k}.stl"
        export_stl(printable(m, k), str(stl[k]), tolerance=0.005, angular_tolerance=0.1)
        trimesh.Scene({k: trimesh.load(stl[k])}).export(OUT / mat / f"{k}.3mf")
    (OUT / "multi-material").mkdir()
    for name, ks in (("frame", ("frame_cf", "frame_rf", "touch_windows")), ("back", ("back_cf", "back_rf"))):
        # one 3MF, several objects in place: assign PETG-CF / PETG per object in Bambu Studio (AMS lite)
        trimesh.Scene({k: trimesh.load(stl[k]) for k in ks}).export(OUT / "multi-material" / f"{name}-cf+petg.3mf")


# ---------------------------------------------------------------- renders
COLORS = dict(
    frame_cf="#2e3238", back_cf="#3a3f47", frame_rf="#dcd6c4", back_rf="#cfc8b4", bezel="#1f2227",
    gasket_back="#e4572e", gasket_bezel="#e4572e", gasket_pogo="#e4572e", touch_windows="#cfc8b4", touch="#d9a92e", rf_pin="#c9cdd3", strap="#2b2d31", mic_gasket="#e4572e", vent="#f7f7f2", motor="#a7adb4", motor_springs="#d8b246", display="#d9d7cf", fpc="#c8861a", stiffener="#9c6610",
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
        ("Bezel, plain PETG, on a TPU gasket", ["bezel", "gasket_bezel"], 36, S.CASE_T),
        ("Display GDEM0097T61 + FPC tail", ["display", "fpc", "stiffener"], 27, S.Z_DISP1),
        ("Frame: PETG-CF + PETG RF window,\n4 PETG touch windows, 16 mm lugs", ["frame_cf", "frame_rf", "touch_windows", "bars", "rf_pin"],
         18, S.Z_DISP1 - 1),
        ("PCB 0.8 mm + parts, touch pads", ["pcb", "qfn", "ffc", "chips", "touch", "antenna", "pads"], 8, S.Z_PCB1),
        (f"Battery {S.BAT_L:.1f} x {S.BAT_W:.0f} x {S.BAT_T}\n+ {S.MOTOR_D:.0f} x {S.MOTOR_T:.0f} coin vibration motor", ["battery", "bat_tabs", "motor", "motor_springs"],
         0, S.Z_BAT1),
        ("Back: PETG-CF + PETG RF window,\nTPU gaskets, 2x2 magnets",
         ["back_cf", "back_rf", "case_magnets", "gasket_back", "gasket_pogo"], -9, S.FLOOR),
    ]
    off = {k: (0, 0, dz) for _, keys, dz, _ in groups for k in keys}
    off.update(gasket_bezel=(0, 0, 33), gasket_back=(0, 0, -6.5), gasket_pogo=(0, 0, -6.0))
    exploded(m, [(lab, keys, (OL - 4, -OW, z + dz)) for lab, keys, dz, z in groups], off, "cad-exploded.png")


def render_sealing(m):
    ghost = {k: 0.22 for k in ("frame_cf", "back_cf", "bezel", "pcb", "display")}
    off = dict(bezel=(0, 0, 30), gasket_bezel=(0, 0, 25), display=(0, 0, 19), frame_cf=(0, 0, 12), frame_rf=(0, 0, 12),
               touch_windows=(0, 0, 12), pcb=(0, 0, 4), touch=(0, 0, 4), mic_gasket=(0, 0, 4), gasket_pogo=(0, 0, -2), gasket_back=(0, 0, -7), back_cf=(0, 0, -12),
               back_rf=(0, 0, -12), case_magnets=(0, 0, -12))
    gx = (S.MOTOR_X, -S.POGO_Y - 1, S.Z_PCB0 - 2.2)
    groups = [
        ("Bezel: plain PETG (whole part)", ["bezel"], (OL - 4, -OW, S.CASE_T + 30)),
        ("TPU bezel gasket 0.2 (glass + frame top)", ["gasket_bezel"], (OL - 2, -OW, S.Z_DISP1 + 25)),
        ("Frame RF window: plain PETG,\nZ-step lap joint to PETG-CF", ["frame_rf"], (OL - 1, -OW, S.Z_DISP1 + 12)),
        ("4 PETG touch windows (no carbon\nnear the electrodes, 0.6 face)", ["touch_windows"], (S.TOUCH_X[1], -OW, S.Z_PCB1 + 12)),
        ("TPU pogo seal under the PCB pads", ["gasket_pogo"], gx),
        ("Mic: TPU ring + duct + vent in the bezel", ["mic_gasket"], (mic_port()[0], mic_port()[1], mic_port()[2] + 4)),
        ("TPU back gasket 0.3 (frame / back)", ["gasket_back"], (OL - 3, -OW + 0.4, S.FLOOR - 7)),
        ("Back RF window: plain PETG", ["back_rf"], (OL - 1.5, -OW, S.FLOOR - 12)),
    ]
    exploded(m, groups, off, "cad-sealing.png", alpha=ghost,
             title="Sealing + RF window (PETG-CF ghosted, PETG = sand, TPU = orange)")


def render_dock(m):
    import pyvista as pv
    p = plotter(1600, 800, shape=(1, 2))
    p.subplot(0, 0)
    add(p, m, WATCH + ["dock", "pins_docked", "dock_magnets", "usb_pcb", "usb_c"])
    p.add_text("Watch on dock", font_size=16, color="#333333", position="upper_left")
    cam(p, (-60, -95, 75), (0, 0, -3), 1.2)
    p.subplot(0, 1)
    add(p, m, ["dock", "pins_free", "dock_magnets", "usb_pcb", "usb_c"])
    p.add_text("Dock: 4 P50 pogo pins, 2x2 magnets, USB-C at the back", font_size=16, color="#333333",
               position="upper_left")
    cam(p, (-55, 95, 80), (-2, 0, -4), 1.3)
    p.screenshot(str(MEDIA / "cad-dock.png"))
    p.close()
    del pv


def min_wall(shape):
    """Thinnest outer wall along rays at mid long side and through both +Y cavity corners -> (mm, where)."""
    from matplotlib.path import Path as MPath
    rays = [("long side x=0", (0.0, 0.0), (0.0, 1.0)),
            ("+X corner", (HL - IN_R, HW - IN_R), (math.sqrt(.5), math.sqrt(.5))),
            ("-X corner", (-HL + IN_R, HW - IN_R), (-math.sqrt(.5), math.sqrt(.5)))]
    best = (99.0, "")
    for name, (ox, oy), (dx, dy) in rays:
        plane = Plane(origin=(ox, oy, 0), x_dir=(dx, dy, 0), z_dir=(dy, -dx, 0))
        cut = shape & (plane * Rectangle(400, 400))
        paths = []
        for f in cut.faces():
            for wire in [f.outer_wire(), *f.inner_wires()]:
                pts = [(q.X - ox) * dx + (q.Y - oy) * dy for q in (wire.position_at(t) for t in np.linspace(0, 1, 400))]
                zs = [q.Z for q in (wire.position_at(t) for t in np.linspace(0, 1, 400))]
                paths.append(MPath(np.column_stack([pts, zs])))
        s_vals = np.arange(0, 14, 0.01)
        for z in np.arange(Z_FRAME0 + 0.1, S.Z_DISP1 - 0.05, 0.1):
            pts = np.column_stack([s_vals, np.full_like(s_vals, z)])
            inside = np.zeros(len(s_vals), bool)
            for pth in paths:
                inside ^= pth.contains_points(pts)        # even-odd: holes cancel
            idx = np.nonzero(inside)[0]
            if len(idx) == 0:
                continue
            run_end = idx[-1]
            run_start = run_end
            while run_start > 0 and inside[run_start - 1]:
                run_start -= 1
            t = (run_end - run_start + 1) * 0.01
            if t < best[0]:
                best = (t, f"{name}, z={z:.2f}")
    return best


def section_polys(shape, y):
    """Cut shape with the plane y=const -> list of (outer, [holes]) polylines in (x, z)."""
    plane = Plane(origin=(0, y, 0), z_dir=(0, 1, 0))
    cut = shape & (plane * Rectangle(400, 400))
    out = []
    for f in cut.faces():
        def pts(w):
            a = np.array([(q.X, q.Z) for q in (w.position_at(t) for t in np.linspace(0, 1, 240))])
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
    keys = CASE + INTERNAL + ["bars", "rf_pin", "motor", "motor_springs"]
    hatch = {"frame_cf", "frame_rf", "back_cf", "back_rf", "bezel"}
    fig = plt.figure(figsize=(16, 10), dpi=100, facecolor="#f4f5f7")
    ax1 = fig.add_axes([0.03, 0.55, 0.94, 0.38])
    ax2 = fig.add_axes([0.03, 0.04, 0.55, 0.46])
    ax3 = fig.add_axes([0.62, 0.04, 0.35, 0.46])

    def area(a):
        return 0.5 * np.sum(a[:-1, 0] * a[1:, 1] - a[1:, 0] * a[:-1, 1])
    polys = {k: section_polys(m[k], y) for k in keys if k in m}
    polys2 = {k: section_polys(m[k], y2) for k in keys if k in m}
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
    ax1.set_xlim(-OL - 4.5, OL + 17.5)
    ax1.set_ylim(-3.6, S.CASE_T + 1.6)
    ax1.set_title(f"Section at y = {y:+.2f} mm (through the motor), looking from -Y", fontsize=15, loc="left")

    # stack dimensions on the right of the full section
    layers = [("floor", 0, S.FLOOR), ("battery + swell", S.Z_BAT0, S.Z_BAT1), ("PCB", S.Z_PCB0, S.Z_PCB1),
              ("parts", S.Z_PCB1, S.Z_PCB1 + S.PART_H), ("glass", S.Z_DISP0, S.Z_DISP1),
              ("gasket", S.Z_DISP1, S.Z_DISP1 + S.BEZEL_GASKET), ("lip", S.Z_DISP1 + S.BEZEL_GASKET, S.CASE_T)]
    xd = OL + 4.6
    last = 0
    for i, (name, z0, z1) in enumerate(layers):
        x = xd + (i % 2) * 0.9
        ax1.annotate("", (x, z0), (x, z1), arrowprops=dict(arrowstyle="<->", lw=0.8, color="#333333",
                                                           shrinkA=0, shrinkB=0))
        ty = (z0 + z1) / 2 if i == 0 else max((z0 + z1) / 2, last + 0.62)
        last = ty
        ax1.text(xd + 2.2, ty, f"{name} {z1 - z0:.2f}", va="center", fontsize=10, color="#222")
    xt = OL + 14
    ax1.annotate("", (xt, 0), (xt, S.CASE_T), arrowprops=dict(arrowstyle="<->", lw=1.4, color="#c0392b",
                                                              shrinkA=0, shrinkB=0))
    ax1.text(xt + 0.5, S.CASE_T / 2, f"{S.CASE_T:.2f} mm\ntotal", va="center", fontsize=13, color="#c0392b",
             weight="bold")
    ax1.annotate("", (-OL, -2.4), (OL, -2.4), arrowprops=dict(arrowstyle="<->", lw=1.0, color="#333333",
                                                              shrinkA=0, shrinkB=0))
    ax1.text(0, -3.1, f"case body {S.CASE_L:.1f} mm   (lug-to-lug {2 * EAR_TIP:.1f} mm, 16 mm spring-bar straps)", ha="center",
             fontsize=11)
    for x, label in [(S.DISP_X0 - 0.2, "-X: FPC end"), (S.DISP_X1 + 2.2, "+X: antenna end (plastic only)")]:
        ax1.text(x, S.CASE_T + 0.6, label, ha="center", fontsize=10, color="#555")
    ax1.text(-X_BAR, Z_BAR - 2.2, "spring bar", ha="center", va="top", fontsize=9, color="#555")
    ax1.text(X_BAR, Z_BAR - 2.2, "spring bar", ha="center", va="top", fontsize=9, color="#555")
    ax1.annotate("coin motor + springs", (S.MOTOR_X, 1.8), (S.MOTOR_X + 4, -1.6), fontsize=9, color="#333",
                 arrowprops=dict(arrowstyle="-", lw=0.6, color="#333"))

    ax2.set_xlim(-OL - 2.5, -5.5)
    ax2.set_ylim(-1.6, S.CASE_T + 1.6)
    ax2.set_title(f"Detail, -X end at y = {y2:+.1f} (through two pogo pins)", fontsize=13, loc="left")
    px = [x for x, yy in POGO_XY if yy > 0]
    notes = [((S.DISP_X0 - 0.6, 5.0), (-21.0, 7.9), "FPC U-bend"), ((S.FFC_X - 1.0, S.Z_PCB1 + 0.5), (-12.0, 7.9), "FFC connector"),
             ((px[0], 1.5), (-11.2, 1.0), "pogo holes 1.3, pads above"), ((px[1], 1.5), (-11.2, 1.0), ""),
             ((-8.0, 2.0), (-8.5, 3.0), "battery"), ((-20.1, 3), (-21.6, -0.8), "frame wall"),
             ((-17.0, 0.3), (-15.5, -1.0), "back plate"), ((-17.5, S.CASE_T - 0.2), (-18.5, 8.4), "bezel"),
             ((-20.0, Z_FRAME0 - 0.15), (-22.6, 1.6), "TPU gasket"),
             ((px[1] + 0.8, S.Z_PCB0 - 0.25), (-11.2, 2.2), "TPU pogo seal"),
             ((-13.0, S.Z_DISP1 + 0.1), (-10.5, 8.6), "TPU bezel gasket")]
    for xy, txt, s in notes:
        ax2.annotate(s, xy, txt, fontsize=10, arrowprops=dict(arrowstyle="-", lw=0.7, color="#333"))

    ax3.axis("off")
    rows = [("lip (bezel)", S.LIP), ("bezel gasket (TPU)", S.BEZEL_GASKET), ("glass", S.DISP_T), ("gap", S.GAP), ("tallest part", S.PART_H),
            ("PCB", S.PCB_T), ("gap", S.GAP), ("battery swell", S.BAT_SWELL), ("battery", S.BAT_T),
            ("floor (back)", S.FLOOR)]
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
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.patches import FancyBboxPatch

    # orthographic top render with a known mm extent, composited into matplotlib
    hw, hh = 30.0, 15.0
    p = plotter(1600, 800)
    p.set_background("#f4f5f7")
    add(p, m, WATCH)
    p.enable_parallel_projection()
    p.camera_position = [(0, 0, 100), (0, 0, 0), (0, 1, 0)]
    p.camera.parallel_scale = hh
    img = p.screenshot(transparent_background=True, return_img=True)
    p.close()

    fig, ax = plt.subplots(figsize=(16, 6), dpi=100, facecolor="#f4f5f7")
    fig.subplots_adjust(0.01, 0.01, 0.99, 0.99)
    ax.set_facecolor("#f4f5f7")
    ax.imshow(img, extent=[-hw, hw, -hh, hh], zorder=2)
    cx = 50.0
    cl, cw, cr = 36.73, 23.09, 7.0
    for xo, ls, col, lw in [(cx, "-", "#1a73e8", 2.2)]:
        ax.add_patch(FancyBboxPatch((xo - cl / 2 + cr, -cw / 2 + cr), cl - 2 * cr, cw - 2 * cr,
                                    boxstyle=f"round,pad={cr}", fill=False, ec=col, lw=lw, ls=ls))
    ax.add_patch(FancyBboxPatch((cx - OL + S.CORNER_R, -OW + S.CORNER_R), S.CASE_L - 2 * S.CORNER_R,
                                S.CASE_W - 2 * S.CORNER_R, boxstyle=f"round,pad={S.CORNER_R}", fill=False,
                                ec="#3a4250", lw=1.6, ls="--"))

    def dim(x0, y0, x1, y1, text, off, vertical=False, color="#222"):
        ax.annotate("", (x0, y0), (x1, y1), arrowprops=dict(arrowstyle="<->", lw=1.1, color=color,
                                                            shrinkA=0, shrinkB=0))
        if vertical:
            ax.text(x0 + off, (y0 + y1) / 2, text, rotation=90, va="center", ha="center", fontsize=12, color=color)
        else:
            ax.text((x0 + x1) / 2, y0 + off, text, ha="center", va="center", fontsize=12, color=color)
    dim(-OL, -OW - 2.5, OL, -OW - 2.5, f"{S.CASE_L:.1f} body", -1.2)
    dim(-EAR_TIP, -OW - 5.5, EAR_TIP, -OW - 5.5, f"{2 * EAR_TIP:.1f} lug to lug", -1.2, color="#666")
    dim(-EAR_TIP - 2.5, -OW, -EAR_TIP - 2.5, OW, f"{S.CASE_W:.1f}", -1.3, vertical=True)
    dim(cx - cl / 2, -cw / 2 - 2.5, cx + cl / 2, -cw / 2 - 2.5, f"{cl:.2f}", -1.2, color="#1a73e8")
    dim(cx + cl / 2 + 2.5, -cw / 2, cx + cl / 2 + 2.5, cw / 2, f"{cw:.2f}", 1.3, vertical=True, color="#1a73e8")
    ax.text(0, OW + 3.5, f"Horae rev A   {S.CASE_L:.1f} x {S.CASE_W:.1f} x {S.CASE_T:.2f} mm", ha="center",
            fontsize=15, weight="bold", color="#222")
    ax.text(cx, cw / 2 + 2.0, "Fitbit Charge 6   36.73 x 23.09 x 11.2 mm", ha="center", fontsize=15,
            weight="bold", color="#1a73e8")
    ax.text(cx, 0, "Horae body outline\n(dashed)", ha="center", va="center", fontsize=11, color="#3a4250")
    ax.text(cx, -cw / 2 - 6.6, "Charge 6 outline approximate (corner radius guessed)", ha="center", fontsize=10,
            color="#777")
    ax.set_xlim(-hw - 2, cx + 25)
    ax.set_ylim(-hh - 2, hh + 3)
    ax.set_aspect("equal")
    ax.axis("off")
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
    add(p, m, ["frame_cf", "frame_rf", "touch_windows", "back_cf", "back_rf", "bars", "rf_pin", "pcb", "qfn", "ffc",
               "chips", "touch", "antenna"], alpha={"frame_cf": 0.55, "frame_rf": 0.55, "touch_windows": 0.55})
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
        ty = (hh + 0.8 + (n % 3) * 1.5) * (1 if up else -1)
        ax.annotate(f"{ref} {val}", (c.X, c.Y), (c.X, ty), ha="center", va="center", fontsize=10,
                    arrowprops=dict(arrowstyle="-", lw=0.6, color="#444"))
    ax.annotate("TCH1-4 touch electrodes\n(PETG wall windows)", (S.TOUCH_X[1], -TOUCH_Y), (S.TOUCH_X[1] + 4, -hh - 2.5),
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
    """Close-up XZ section through the mic port: duct, gaskets, vent."""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.patches import PathPatch
    from matplotlib.path import Path as MPath
    px, py, pz = mic_port()
    keys = CASE + ["display", "fpc", "pcb", "chips", "ffc", "vent", "battery", "case_magnets"]
    mic = [sh for ref, _, sh in comps if ref.startswith("MIC")]
    fig, ax = plt.subplots(figsize=(16, 9), dpi=100, facecolor="#f4f5f7")
    fig.subplots_adjust(0.02, 0.02, 0.98, 0.92)

    def area(a):
        return 0.5 * np.sum(a[:-1, 0] * a[1:, 1] - a[1:, 0] * a[:-1, 1])
    shapes = [(k, m[k]) for k in keys if k in m] + [("mic", sh) for sh in mic]
    for k, shp in shapes:
        for outer, holes in section_polys(shp, py):
            rings = [outer if area(outer) > 0 else outer[::-1]] + [h if area(h) < 0 else h[::-1] for h in holes]
            verts = np.concatenate(rings)
            codes = np.concatenate([[MPath.MOVETO] + [MPath.LINETO] * (len(r) - 1) for r in rings])
            ax.add_patch(PathPatch(MPath(verts, codes), facecolor=COLORS.get(k, "#7a7f86"), edgecolor="#111", lw=0.6,
                                   hatch="////" if k in ("frame_cf", "frame_rf", "back_cf", "bezel") else None))
    z0 = S.Z_DISP1 + S.BEZEL_GASKET
    notes = [((px, S.CASE_T - 0.1), (px - 2.4, S.CASE_T + 0.7), f"outlet {MIC_HOLE} mm through gasket + bezel"),
             ((px + 0.7, S.Z_DISP1 - 0.15), (px + 2.0, S.CASE_T + 0.7), f"2.0 mm hydrophobic vent in a {VENT_D} x {VENT_T} pocket"),
             ((px + 0.6, S.Z_DISP1 + 0.1), (px + 3.6, S.Z_DISP1 + 0.45), "TPU bezel gasket"),
             ((px - 0.3, (pz + S.Z_DISP1) / 2), (px - 3.2, 5.9), f"duct {MIC_BORE} mm in a frame boss"),
             ((px + 0.55, pz + 0.12), (px - 3.2, 4.75), "TPU/foam ring on the mic top"),
             ((px + 0.9, pz - 0.4), (px + 2.6, 3.9), "LMD2718 top-port mic"),
             ((S.DISP_X0 + 0.6, S.Z_DISP0 + 0.5), (S.DISP_X0 + 2.2, 4.75), "glass (ledge relieved at this corner)"),
             ((px - 0.3, S.Z_PCB0 + 0.4), (px - 3.2, 3.55), "PCB")]
    for xy, txt, label in notes:
        ax.annotate(label, xy, txt, fontsize=12, arrowprops=dict(arrowstyle="-", lw=0.7, color="#333"))
    ax.annotate("", (px, pz), (px, S.CASE_T + 0.4), arrowprops=dict(arrowstyle="<-", lw=1.5, color="#1a73e8"))
    ax.text(px + 0.12, S.CASE_T + 0.35, "sound", color="#1a73e8", fontsize=11)
    ax.set_xlim(px - 3.8, px + 6.5)
    ax.set_ylim(3.2, S.CASE_T + 1.0)
    ax.set_aspect("equal")
    ax.axis("off")
    ax.set_title(f"Mic duct, section at y = {py:+.2f} (through the port at x = {px:.2f}, "
                 f"{S.DISP_X0 - px:.2f} mm past the glass edge)", fontsize=15, loc="left")
    fig.savefig(MEDIA / "cad-mic.png", dpi=100, facecolor=fig.get_facecolor())
    plt.close(fig)


def render_shape_options(m):
    """Two outer-shape candidates side by side (3/4 view + end-on profile)."""
    keys = ["frame_cf", "frame_rf", "touch_windows", "back_cf", "back_rf", "bezel", "gasket_back", "gasket_bezel"]
    rest = {k: m[k] for k in ("display", "bars", "rf_pin")}
    opts = [("A  pebble (default): R3.2 plan, R2.5 top round, R1.2 bottom round", {k: m[k] for k in keys}),
            ("B  facet: R3.2 plan, 1.8 top chamfer, 0.8 bottom chamfer", case_parts("facet"))]
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
    if "--no-render" not in sys.argv:
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
