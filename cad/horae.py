#!/usr/bin/env python3
"""Project Horae rev A mechanics: reference bodies, 3-part case, charging dock, checks, exports, renders.

    .venv/bin/python cad/horae.py            # everything (cad/out/*, media/2026-10-03/cad-*.png)
    .venv/bin/python cad/horae.py --no-render

All shared dimensions come from spec.py. Splash-resistant case, PETG-CF body with a plain-PETG RF window:
  frame  walls, glass ledges, 4 sealed TPU buttons, 14 mm spring-bar lugs (PCB goes in from below, glass from
         above). Split at x = ANT_X0 - 1: frame_cf (PETG-CF) + frame_rf (PETG, antenna end), Z-stepped lap joint.
  back   0.6 mm floor + pogo/magnet block (-X) + support block (+X). Split the same way: back_cf + back_rf.
  bezel  0.5 mm lip with the display window, plain PETG (no CF over the antenna; 0.2 mm nozzle)
  TPU 95A: gasket_back (frame/back ring), gasket_bezel (bezel/glass+frame ring), gasket_pogo (seals the pogo
         wells on the PCB bottom), button x4 (plug + flange sealing each wall window)
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
MAG_D, MAG_T = 2.0, 2.0   # N52 disc in a blind pocket from the skin side (sealed); 3 mm won't fit the 3 mm strip
MAG_Y = S.BATPAD_Y    # under the battery pads but 1.4 mm below them; wire/solder channel above the magnet
POGO_PAD_D = 1.0
POGO_HOLE_D = 1.3     # P50-style pin: 1.0 barrel + 0.3
PIN_L, PIN_D, PLUNGER_D, PLUNGER_L = 16.0, 1.0, 0.6, 2.5
PIN_PRELOAD = 0.5     # free pin tip sits this far above the pad -> 0.5 mm of stroke used when docked
PIN_BORE = 1.1
STRAP_W = 14.0        # spring-bar strap; 16 mm bars would leave 1.25 mm lug ears on an 18.5 mm case (too flexy)
BAR_D = 1.0           # spring-bar tip hole (0.8 tips), -X lug
PIN_RF_D = 1.5        # +X lug: plastic (nylon/PETG) through-pin instead of a steel spring bar (RF window)
EAR_R = 1.8
BAR_DX = 2.2          # bar axis past the case end face (room for the strap loop)
FFC_L, FFC_D, FFC_H = 12.5, 3.5, 1.0        # FH34SRJ-18S body (Y x X x Z), centred at S.FFC_X
BACK_GASKET = 0.3     # TPU ring between frame and back (compressed; printed 0.4). Frame starts above it
POGO_GASKET = 0.5     # TPU pad under the PCB around the pogo pads (compressed; printed 0.6)
POGO_SEAL_D = 0.8     # gasket hole around each 0.6 mm plunger; seals on the 1.0 mm pad ring
GASKET_PRINT = {"gasket_back": 0.4, "gasket_bezel": 0.25, "gasket_pogo": 0.6}   # printed (free) thickness
X_RF = S.ANT_X0 - 1.5 # RF window (no carbon) from here; antenna copper starts ~0.3 before ANT_X0 (feed)
RF_LAP = 1.5          # frame lap joint: the PETG upper half overhangs the CF lower half by this
BTN_WIN = (3.6, 2.0)  # button window through the wall (x, z)
BTN_FLANGE, BTN_RECESS = 0.6, 0.3   # TPU flange margin around the window, recess depth in the inner wall face
SW_L, SW_D, NUB_W, NUB_OUT = 3.5, 2.9, 1.6, 0.65   # EVQ-P7M01P body X x Y, nub width, nub past the body edge
SW_Y = S.PCB_W / 2 - S.BUTTON_INSET - SW_D / 2     # switch body centre |y|
NUB_TIP = SW_Y + SW_D / 2 + NUB_OUT                # |y| of the nub tip
DOCK_WALL, DOCK_DEPTH, DOCK_BAY_H = 2.5, 3.0, 4.5

IN_R = S.CORNER_R - S.WALL
HL, HW = S.CAV_L / 2, S.CAV_W / 2
OL, OW = S.CASE_L / 2, S.CASE_W / 2
Z_FRAME0 = S.FLOOR + BACK_GASKET
BTN_Z = S.Z_PCB1 + 0.7                             # nub centre height
AA_X1 = S.DISP_X1 - S.DISP_AA_MARGIN_FAR
AA_X0 = AA_X1 - S.DISP_AA_L
AA_CX = (AA_X0 + AA_X1) / 2
POGO_Y = [(i - 1.5) * S.POGO_PITCH for i in range(4)]
X_BAR = OL + BAR_DX
Z_BAR = Z_FRAME0 + EAR_R
EAR_TIP = X_BAR + EAR_R
ACT_Z = (S.Z_PCB1 + 0.3, S.Z_PCB1 + 1.1)    # switch actuator band
PIN_TIP_FREE = S.Z_PCB0 + PIN_PRELOAD
DOCK_ZB = PIN_TIP_FREE - PIN_L - 0.6         # dock bottom (pin tail ends 0.6 above the table)
DOCK_L2 = EAR_TIP + 0.3 + DOCK_WALL
DOCK_W2 = OW + 0.3 + DOCK_WALL
assert S.PCB_CORNER_R <= IN_R - FIT + 1e-9, "PCB corners must sit inside the cavity corner radius"
assert X_RF - RF_LAP > max(S.BUTTON_X) + BTN_WIN[0] / 2 + BTN_FLANGE, "RF lap joint runs into a button"


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
    xc = -HL + 0.2 + r + t / 2                              # 0.2 clear of the end wall
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


def switch(x, y):
    """EVQ-P7M01P envelope: body + nub pointing out of the nearest long edge."""
    sy = 1 if y > 0 else -1
    body = box(x - SW_L / 2, x + SW_L / 2, y - SW_D / 2, y + SW_D / 2, S.Z_PCB1, S.Z_PCB1 + S.PART_H)
    nub = box(x - NUB_W / 2, x + NUB_W / 2, y + sy * SW_D / 2, sy * NUB_TIP, *ACT_Z)
    return body, nub


def pads():
    return union([cyl(S.POGO_X, y, S.Z_PCB0 - 0.03, S.Z_PCB0, POGO_PAD_D) for y in POGO_Y]
                 + [box(S.POGO_X - 1, S.POGO_X + 1, sy * (S.BATPAD_Y - 1), sy * (S.BATPAD_Y + 1), S.Z_PCB0 - 0.03,
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
    sw = [switch(bx, sy * SW_Y) for bx in S.BUTTON_X for sy in (-1, 1)]
    groups["switches"] = union([b for b, _ in sw])
    groups["actuators"] = union([n for _, n in sw])
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
    if "EVQ-P7M01P" in name:
        return switch(x, y)
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
            comps.append((near["ref"], near["value"], sh))
        else:
            comps.append((str(k.label), "", sh))
    groups = dict(qfn=[], ffc=[], chips=[], switches=[], actuators=[], antenna=[])
    n_env = 0
    for f in top:
        if f["ref"] in matched:
            continue
        if f["ref"].startswith("AE"):
            groups["antenna"].append(antenna(f, c.X, c.Y))
            continue
        b, nub = envelope(f, *to_case(f))
        n_env += 1
        comps.append((f["ref"], f["value"], b))
        if nub is not None:
            comps.append((f["ref"] + " nub", f["value"], nub))
            groups["actuators"].append(nub)
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


def magnets(z0):
    return [cyl(S.POGO_X, sy * MAG_Y, z0, z0 + MAG_T, MAG_D) for sy in (-1, 1)]


def spring_bars():
    """Steel spring bar at -X only."""
    return ycyl(-X_BAR, -STRAP_W / 2, STRAP_W / 2, Z_BAR, 1.5) + ycyl(-X_BAR, -OW + 0.3, OW - 0.3, Z_BAR, 0.8)


def rf_pin():
    """Plastic through-pin at the +X (antenna) lug, flush with the ear faces."""
    return ycyl(X_BAR, -OW + 0.05, OW - 0.05, Z_BAR, PIN_RF_D)


# ---------------------------------------------------------------- case
def frame():
    """Whole frame (split into CF + RF parts by split_rf)."""
    outer = slab(S.CASE_L, S.CASE_W, S.CORNER_R, Z_FRAME0, S.Z_DISP1)
    for sx in (-1, 1):                                   # spring-bar lug ears
        for sy in (-1, 1):
            y0, y1 = sy * (STRAP_W / 2 + 0.1), sy * OW
            outer += box(sx * (OL - S.CORNER_R), sx * X_BAR, y0, y1, Z_FRAME0, Z_BAR + EAR_R)
            outer += ycyl(sx * X_BAR, y0, y1, Z_BAR, 2 * EAR_R)
    f = outer - slab(S.CAV_L, S.CAV_W, IN_R, Z_FRAME0 - 1, S.Z_DISP1 + 1)

    z0 = S.Z_PCB1 + S.GAP                                # glass ledges + glass locators, resting on the PCB
    blocks = box(S.DISP_X1 + GLASS_FIT, HL, -HW, HW, z0, S.Z_DISP1)    # antenna end: full width (copper only)
    for sy in (-1, 1):                                                 # corner ledges under both glass ends
        blocks += box(-HL, S.DISP_X0 + S.LEDGE, sy * S.LEDGE_Y, sy * HW, z0, S.Z_DISP1)
        blocks += box(S.DISP_X1 - S.LEDGE, HL, sy * S.LEDGE_Y, sy * HW, z0, S.Z_DISP1)
    f += blocks & slab(S.CAV_L, S.CAV_W, IN_R, z0, S.Z_DISP1)
    gw = S.DISP_W / 2 + GLASS_FIT
    f -= box(S.DISP_X0 - GLASS_FIT, S.DISP_X1 + GLASS_FIT, -gw, gw, S.Z_DISP0, S.Z_DISP1 + 1)

    for sx in (-1, 1):
        f -= ycyl(sx * X_BAR, -OW - 1, OW + 1, Z_BAR, BAR_D if sx < 0 else PIN_RF_D + 0.1)

    wl, wh = BTN_WIN
    m = BTN_FLANGE
    for bx in S.BUTTON_X:                                # window through the wall + recess for the TPU flange
        for sy in (-1, 1):
            f -= box(bx - wl / 2, bx + wl / 2, sy * (HW - 1), sy * (OW + 1), BTN_Z - wh / 2, BTN_Z + wh / 2)
            f -= box(bx - wl / 2 - m, bx + wl / 2 + m, sy * (HW - 1), sy * (HW + BTN_RECESS),
                     BTN_Z - wh / 2 - m, BTN_Z + wh / 2 + m)
    return f


def button(bx, sy):
    """TPU button: plug filling the wall window (flush outside) + flange in the inner recess; pocket for the nub."""
    wl, wh = BTN_WIN
    m = BTN_FLANGE
    b = box(bx - wl / 2, bx + wl / 2, sy * (HW + BTN_RECESS), sy * OW, BTN_Z - wh / 2, BTN_Z + wh / 2)
    b += box(bx - wl / 2 - m, bx + wl / 2 + m, sy * HW, sy * (HW + BTN_RECESS), BTN_Z - wh / 2 - m, BTN_Z + wh / 2 + m)
    return b - box(bx - NUB_W / 2 - 0.15, bx + NUB_W / 2 + 0.15, sy * (HW - 1), sy * (NUB_TIP + 0.05),
                   ACT_Z[0] - 0.15, ACT_Z[1] + 0.15)


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
    b = fillet(b.edges().group_by(Axis.Z)[0], 0.4)
    top = S.Z_PCB0 - S.GAP
    blocks = slab(S.CAV_L - 2 * FIT, S.CAV_W - 2 * FIT, IN_R - FIT, S.FLOOR - 0.1, top)
    x_pogo1 = S.BAT_X0 - 0.25
    b += blocks & (box(-HL, x_pogo1, -HW, HW, 0, top) + box(S.BAT_X1 + 0.25, HL, -HW, HW, 0, top))
    gy = POGO_Y[-1] + 1.15                               # pogo gasket pocket (gasket_pogo sits in it)
    b -= box(-HL + 0.5, x_pogo1 - 0.4, -gy, gy, S.Z_PCB0 - 0.03 - POGO_GASKET, top + 1)
    for y in POGO_Y:
        b -= cyl(S.POGO_X, y, -1, top + 1, POGO_HOLE_D)
        b -= Pos(S.POGO_X, y, -0.01) * Cone(POGO_HOLE_D / 2 + 0.35, POGO_HOLE_D / 2, 0.36,
                                             align=(Align.CENTER, Align.CENTER, Align.MIN))
    for sy in (-1, 1):
        b -= cyl(S.POGO_X, sy * MAG_Y, -1, MAG_T + 0.05, MAG_D + 0.1)          # blind from the skin side
        b -= box(-HL - 1, x_pogo1 + 1, sy * (gy + 0.5), sy * (HW + 1), MAG_T + 0.45, top + 1)  # battery wires
    return b


def gasket_back(t=BACK_GASKET):
    ring = slab(S.CASE_L, S.CASE_W, S.CORNER_R, S.FLOOR, S.FLOOR + t)
    return ring - slab(S.CAV_L, S.CAV_W, IN_R, S.FLOOR - 1, S.FLOOR + t + 1)


def gasket_pogo(t=POGO_GASKET):
    gy = POGO_Y[-1] + 1.15
    z1 = S.Z_PCB0 - 0.03                                 # under the 30 um pads
    g = box(-HL + 0.55, S.BAT_X0 - 0.25 - 0.45, -gy + 0.05, gy - 0.05, z1 - t, z1)
    for y in POGO_Y:
        g -= cyl(S.POGO_X, y, z1 - t - 1, z1 + 1, POGO_SEAL_D)
    return g


def window(z0, h):
    win = RectangleRounded(S.DISP_AA_L + 2 * WIN_M, S.DISP_AA_W + 2 * WIN_M, 0.6)
    return Pos(AA_CX, 0, z0) * extrude(win, h)


def gasket_bezel(t=S.BEZEL_GASKET):
    g = slab(S.CASE_L, S.CASE_W, S.CORNER_R, S.Z_DISP1, S.Z_DISP1 + t)
    return g - window(S.Z_DISP1 - 1, 3)


def bezel():
    b = slab(S.CASE_L, S.CASE_W, S.CORNER_R, S.Z_DISP1 + S.BEZEL_GASKET, S.CASE_T)
    b = fillet(b.edges().group_by(Axis.Z)[-1], 0.3)
    return b - window(S.Z_DISP1 - 1, 3)


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
    for y in POGO_Y:
        d -= cyl(S.POGO_X, y, bay_top - 0.5, 1, PIN_BORE)
    for sy in (-1, 1):
        d -= cyl(S.POGO_X, sy * MAG_Y, -(MAG_T + 0.05), 1, MAG_D + 0.1)
    d -= box(S.POGO_X - 2, 5.5, -5.5, 5.5, DOCK_ZB - 1, bay_top)                 # wiring bay, open below
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
    try:
        return vol(a & b)
    except Exception:
        return 0.0


def build():
    board, groups, comps, note = load_board()
    tail, stiff, fit = fpc()
    bat, tabs = battery()
    frame_cf, frame_rf = split_rf(frame(), lap=True)
    back_cf, back_rf = split_rf(back(), lap=False)
    m = dict(frame_cf=frame_cf, frame_rf=frame_rf, back_cf=back_cf, back_rf=back_rf, bezel=bezel(),
             gasket_back=gasket_back(), gasket_bezel=gasket_bezel(), gasket_pogo=gasket_pogo(),
             buttons=union([button(bx, sy) for bx in S.BUTTON_X for sy in (-1, 1)]),
             display=display(), fpc=tail, stiffener=stiff,
             pcb=board, battery=bat, bat_tabs=tabs, case_magnets=union(magnets(0.0)),
             bars=spring_bars(), rf_pin=rf_pin(), dock=dock(), dock_magnets=union(magnets(-MAG_T)))
    m.update(groups)
    m["pads"] = pads()
    m["pins_docked"] = union([pogo_pin(S.POGO_X, y, S.Z_PCB0 - 0.03) for y in POGO_Y])
    m["pins_free"] = union([pogo_pin(S.POGO_X, y, PIN_TIP_FREE) for y in POGO_Y])
    m["usb_pcb"], m["usb_c"] = usb_board()
    return m, fit, comps, note


CASE = ["frame_cf", "frame_rf", "back_cf", "back_rf", "bezel", "gasket_back", "gasket_bezel", "gasket_pogo",
        "buttons"]
INTERNAL = ["display", "fpc", "stiffener", "pcb", "qfn", "ffc", "chips", "switches", "actuators", "antenna", "pads",
            "battery", "bat_tabs", "case_magnets"]
METAL = ["case_magnets", "bars"]


def checks(m, fit, comps):
    ok = True

    def near(name, got, want):
        nonlocal ok
        good = abs(got - want) <= 0.05
        ok &= good
        print(f"  {'ok ' if good else 'BAD'} {name:<22} {got:7.2f}  (spec {want:.2f})")
    print("dimension checks")
    bb = m["bezel"].bounding_box()
    near("bezel length", bb.size.X, S.CASE_L)
    near("bezel width", bb.size.Y, S.CASE_W)
    near("back length", (m["back_cf"] + m["back_rf"]).bounding_box().size.X, S.CASE_L)
    near("frame width", (m["frame_cf"] + m["frame_rf"]).bounding_box().size.Y, S.CASE_W)
    zs = [m[k].bounding_box() for k in CASE]
    near("total thickness", max(b.max.Z for b in zs) - min(b.min.Z for b in zs), S.CASE_T)
    print(f"  lug-to-lug {2 * EAR_TIP:.2f} mm, button plug at the nub {OW - NUB_TIP - 0.05:.2f} mm thick")
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
    "back_cf": ("petg-cf", (0, 0, 0), "skin side down, 0.4 hardened nozzle"),
    "back_rf": ("petg", (0, 0, 0), "skin side down; RF window. AMS lite: print with back_cf as one object"),
    "bezel": ("petg", (180, 0, 0), "visible face down, 0.2 nozzle; plain PETG (no carbon over the antenna)"),
    "gasket_back": ("tpu", (0, 0, 0), "flat, printed 0.40 (0.30 compressed), 0.1 layers"),
    "gasket_bezel": ("tpu", (0, 0, 0), "flat, printed 0.25 (0.20 compressed), 0.08 layers"),
    "gasket_pogo": ("tpu", (0, 0, 0), "flat, printed 0.60 (0.50 compressed)"),
    "button": ("tpu", (90, 0, 0), "flange down; print 4"),
    "dock": ("petg", (0, 0, 0), "upright, open bays down; bay ceilings bridge"),
}
DENSITY = {"petg-cf": 1.29e-3, "petg": 1.27e-3, "tpu": 1.21e-3}


def printable(m, k):
    """Part in print orientation, at its printed (uncompressed) thickness."""
    if k == "button":
        s = button(S.BUTTON_X[0], 1)
    elif k in GASKET_PRINT:
        s = globals()[k](GASKET_PRINT[k])
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
    for k, (mat, _, _) in PRINT.items():
        (OUT / mat).mkdir(exist_ok=True)
        s = printable(m, k)
        export_stl(s, str(OUT / mat / f"{k}.stl"), tolerance=0.005, angular_tolerance=0.1)
        mesher = Mesher()
        mesher.add_shape(s, linear_deflection=0.005, angular_deflection=0.1)
        mesher.write(str(OUT / mat / f"{k}.3mf"))
    (OUT / "multi-material").mkdir()
    for name in ("frame", "back"):          # one 3MF, two objects: assign PETG-CF / PETG in Bambu Studio (AMS lite)
        mesher = Mesher()
        for k in (f"{name}_cf", f"{name}_rf"):
            mesher.add_shape(printable(m, k), linear_deflection=0.005, angular_deflection=0.1)
        mesher.write(str(OUT / "multi-material" / f"{name}-cf+petg.3mf"))


# ---------------------------------------------------------------- renders
COLORS = dict(
    frame_cf="#2e3238", back_cf="#3a3f47", frame_rf="#dcd6c4", back_rf="#cfc8b4", bezel="#1f2227",
    gasket_back="#e4572e", gasket_bezel="#e4572e", gasket_pogo="#e4572e", buttons="#e4572e", rf_pin="#f2efe6", display="#d9d7cf", fpc="#c8861a", stiffener="#9c6610",
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
        metal = k in ("pads", "pins_docked", "pins_free", "bars", "case_magnets", "dock_magnets", "switches", "usb_c")
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
    add(p, m, WATCH)
    cam(p, (-48, -78, 58), (0, 0, 2.5), 1.55)
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
        ("Frame: PETG-CF + PETG RF window,\n4 TPU buttons, 14 mm lugs", ["frame_cf", "frame_rf", "buttons", "bars", "rf_pin"],
         18, S.Z_DISP1 - 1),
        ("PCB 0.8 mm + parts", ["pcb", "qfn", "ffc", "chips", "switches", "actuators", "antenna", "pads"], 8, S.Z_PCB1),
        ("Battery envelope 27 x 15 x 2.5", ["battery", "bat_tabs"], 0, S.Z_BAT1),
        ("Back: PETG-CF + PETG RF window,\nTPU gaskets, 2x2 magnets",
         ["back_cf", "back_rf", "case_magnets", "gasket_back", "gasket_pogo"], -9, S.FLOOR),
    ]
    off = {k: (0, 0, dz) for _, keys, dz, _ in groups for k in keys}
    off.update(gasket_bezel=(0, 0, 33), gasket_back=(0, 0, -6.5), gasket_pogo=(0, 0, -6.0))
    exploded(m, [(lab, keys, (OL - 4, -OW, z + dz)) for lab, keys, dz, z in groups], off, "cad-exploded.png")


def render_sealing(m):
    ghost = {k: 0.22 for k in ("frame_cf", "back_cf", "bezel", "pcb", "display")}
    off = dict(bezel=(0, 0, 30), gasket_bezel=(0, 0, 25), display=(0, 0, 19), frame_cf=(0, 0, 12), frame_rf=(0, 0, 12),
               buttons=(0, 0, 12), pcb=(0, 0, 4), gasket_pogo=(0, 0, -2), gasket_back=(0, 0, -7), back_cf=(0, 0, -12),
               back_rf=(0, 0, -12), case_magnets=(0, 0, -12))
    gx = (S.POGO_X, POGO_Y[0] - 1, S.Z_PCB0 - 2.2)
    groups = [
        ("Bezel: plain PETG (whole part)", ["bezel"], (OL - 4, -OW, S.CASE_T + 30)),
        ("TPU bezel gasket 0.2 (glass + frame top)", ["gasket_bezel"], (OL - 2, -OW, S.Z_DISP1 + 25)),
        ("Frame RF window: plain PETG,\nZ-step lap joint to PETG-CF", ["frame_rf"], (OL - 1, -OW, S.Z_DISP1 + 12)),
        ("4 TPU buttons sealing the wall windows", ["buttons"], (S.BUTTON_X[1], -OW, BTN_Z + 12)),
        ("TPU pogo seal under the PCB pads", ["gasket_pogo"], gx),
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

    y = POGO_Y[2]
    keys = CASE + INTERNAL + ["bars", "rf_pin"]
    hatch = {"frame_cf", "frame_rf", "back_cf", "back_rf", "bezel"}
    fig = plt.figure(figsize=(16, 10), dpi=100, facecolor="#f4f5f7")
    ax1 = fig.add_axes([0.03, 0.55, 0.94, 0.38])
    ax2 = fig.add_axes([0.03, 0.04, 0.55, 0.46])
    ax3 = fig.add_axes([0.62, 0.04, 0.35, 0.46])

    def area(a):
        return 0.5 * np.sum(a[:-1, 0] * a[1:, 1] - a[1:, 0] * a[:-1, 1])
    polys = {k: section_polys(m[k], y) for k in keys if k in m}
    for ax in (ax1, ax2):
        for k, ps in polys.items():
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
    ax1.set_ylim(-2.2, S.CASE_T + 1.6)
    ax1.set_title(f"Section at y = {y:+.2f} mm (through a pogo pin hole), looking from -Y", fontsize=15, loc="left")

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
    ax1.annotate("", (-OL, -1.2), (OL, -1.2), arrowprops=dict(arrowstyle="<->", lw=1.0, color="#333333",
                                                              shrinkA=0, shrinkB=0))
    ax1.text(0, -1.9, f"case body {S.CASE_L:.1f} mm   (lug-to-lug {2 * EAR_TIP:.1f} mm)", ha="center",
             fontsize=11)
    for x, label in [(S.DISP_X0 - 0.2, "-X: FPC end"), (S.DISP_X1 + 2.2, "+X: antenna end (plastic only)")]:
        ax1.text(x, S.CASE_T + 0.6, label, ha="center", fontsize=10, color="#555")
    ax1.text(-X_BAR, Z_BAR - 1.6, "steel spring bar", ha="center", va="top", fontsize=9, color="#555")
    ax1.text(X_BAR, Z_BAR - 1.6, "plastic pin", ha="center", va="top", fontsize=9, color="#555")

    ax2.set_xlim(-OL - 0.8, -7.5)
    ax2.set_ylim(-1.0, S.CASE_T + 1.6)
    ax2.set_title("Detail, -X end", fontsize=13, loc="left")
    notes = [((-17.0, 5.15), (-19.6, 7.9), "FPC U-bend"), ((-12, 4.7), (-12.5, 7.9), "FFC connector"),
             ((S.POGO_X, 1.5), (-13.6, 1.3), "pogo hole 1.3, pad above"),
             ((-11, 2.4), (-9.6, 3.0), "battery"), ((-18.6, 3), (-19.6, -0.8), "frame wall"),
             ((-16.0, 0.3), (-15.0, -0.8), "back plate"), ((-15.5, 7.0), (-16.0, 7.9), "bezel"),
             ((-18.7, Z_FRAME0 - 0.15), (-21.2, 1.6), "TPU gasket"),
             ((S.POGO_X + 0.9, S.Z_PCB0 - 0.3), (-13.6, 2.3), "TPU pogo seal"),
             ((-12.0, S.Z_DISP1 + 0.1), (-10.5, 8.5), "TPU bezel gasket")]
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
    ax.text(0, OW + 3.5, f"Horae rev A   {S.CASE_L:.1f} x {S.CASE_W:.1f} x {S.CASE_T:.1f} mm", ha="center",
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
    add(p, m, ["frame_cf", "frame_rf", "back_cf", "back_rf", "buttons", "bars", "rf_pin", "pcb", "qfn", "ffc", "chips",
               "switches", "actuators", "antenna"], alpha={"frame_cf": 0.55, "frame_rf": 0.55})
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
        print(f"renders -> {MEDIA.relative_to(ROOT)}/cad-*.png")
    if not ok:
        sys.exit("checks FAILED")


if __name__ == "__main__":
    main()
