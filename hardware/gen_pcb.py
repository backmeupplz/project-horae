"""Generate horae.kicad_pcb from design.py + spec.py: outline, stack, placement, nets, zones, keep-outs, DSN.

Run inside the KiCad container: ./kicad python3 gen_pcb.py
Critical parts are pinned (decoupling at its pins, crystals, RF chain, touch resistors, buck, charger); the rest go to the
free spot nearest their target (greedy legalizer, biggest first). A part that lands > 1 mm from its target fails the build.
"""
import math, os, re, sys
import pcbnew
sys.path.insert(0, "..")
import spec as S
from design import PARTS, ESP_PINS
ESP_NET = {int(k): v for k, v in ESP_PINS.items()}
from gen_sch import uid

MM = pcbnew.FromMM
OX, OY = 100.0, 100.0                 # board centre on the KiCad canvas
X0, X1 = -S.PCB_L / 2, S.PCB_L / 2
Y0, Y1 = -S.PCB_W / 2, S.PCB_W / 2
EDGE = 0.15                            # courtyard-to-edge margin
VIA_D, VIA_H = 0.45, 0.2               # JLC's free 4-layer via class: 0.2 mm holes cost extra (+Kelvin test, TG155) below a 0.45 mm pad
RF_W, RF_GAP = 0.15, 0.15              # 50 ohm GCPW on F.Cu over In1 in JLC04061H-3313 (3313 0.0994 mm, Er 4.1, LPI mask): 50.3 ohm
POWER_W = 0.3                          # power class (Freerouting necks it down at 0.4 mm-pitch pads)
TOUCH_KEEP = 0.5                       # no other copper within this of an electrode, on any layer
DRIFT_MAX = 1.0                        # legalizer: fail when a part lands further than this from its target
U1_XY = (4.8, 0.0)
POWER_NETS = ["BUCK_SW", "EPD_SW"]                            # 0.3 mm: the two switch nodes (drawn by hand)
SUPPLY_NETS = ["+3V3", "VBAT", "VBUS", "MOT_N"]                # 0.2 mm: <= 0.35 A peaks (WiFi TX) = 17 mV over 20 mm
TOUCH_NETS = ["TOUCH_UP_E", "TOUCH_DOWN_E", "TOUCH_MENU_E", "TOUCH_BACK_E"]
F_ONLY_NETS = ["XTAL_P", "XTAL_N", "XTAL_P_L", "VDD3P3"]   # 40 MHz crystal and the PA supply: F.Cu, no vias
# panel tabs (panel.py mills a 2 mm slot around the board except here; 5 x 0.6 mm mouse bites reaching 1/3 into the board,
# JLC, so no nub stands proud of the outline): two at the -X end either side of the case's centring rib at y 0, and both
# long edges past the rib at x 8.5 (>= 1.5 mm from every rib). Tracks, vias and parts stay >= 1.2 mm from a tab (the -X
# tabs pass 0.8 mm from the bare VBUS/GND pogo pads, the only copper there), pours >= 0.6 mm
TAB_GAP, TAB_HOLE, TAB_PITCH, TAB_HOLES = 2.0, 0.6, 0.95, 5
RIBS = [(-12.0, Y0), (-12.0, Y1), (8.5, Y0), (8.5, Y1), (X0, 0.0), (X1, 0.0)]     # case crush ribs (cad/horae.py)
TABS = [((X0, 1.5), (X0, 5.9)), ((X0, -5.9), (X0, -1.5)), ((10.3, Y0), (14.7, Y0)), ((10.3, Y1), (14.7, Y1))]   # 4.4 mm (5 holes):
# the straight edges stop at the R2.5 corners (x +-14.3, y +-5.5), so each tab ends <= 0.4 mm into an arc (< 0.04 mm off line)
assert all(min(math.hypot(rx - x, ry - y) for x, y in (a, b)) >= 1.5 and not (min(a[0], b[0]) < rx < max(a[0], b[0]) or min(a[1], b[1]) < ry < max(a[1], b[1]))
           for a, b in TABS for rx, ry in RIBS if (a[0] == b[0] == rx) or (a[1] == b[1] == ry)), "tab too close to a rib"
TAB_POUR_BACK, TAB_COPPER_BACK, TAB_PART_BACK = 0.6, 1.2, 1.0   # from the edge at a tab: pours, tracks/vias, courtyards
FPC_SLOT_X = S.FFC_X - 1.75                 # J1's slot face (nail side) toward the U-bend at -X
FPC_LANE = (X0 - 1, -S.FPC_W / 2 - 0.3, FPC_SLOT_X, S.FPC_W / 2 + 0.3)    # the ribbon runs here just above the board
LEDGES = [(X0 - 1, Y0 - 1, S.DISP_X0 + S.LEDGE, -S.LEDGE_Y), (X0 - 1, S.LEDGE_Y, S.DISP_X0 + S.LEDGE, Y1 + 1)]  # case ledges
# 3D model z fixes (STEP truthfulness for the case check): ref -> (datasheet max height, model z min, model z max)
HEIGHT = {"U6": (0.74, 0.0, 1.021), "Y1": (0.60, 0.0, 0.83), "L5": (0.80, -0.01, 0.71), "L4": (1.00, 0.0, 1.01),
          "U2": (0.50, -0.48, 0.03), "U3": (0.50, -0.38, 0.021), "Q1": (0.50, -0.231, 0.27), "Q2": (0.50, -0.231, 0.27)}
POLAR = {"U1": "1", "U2": "A1", "U3": "A1", "U4": "1", "U6": "1", "J1": "1", "Q1": "1", "Q2": "1", "MIC1": "1", "Y1": "1",
         "D1": "1", "D2": "1", "D3": "1", "D4": "1"}   # F.Silkscreen pin-1 dot / cathode bar (JLC checks polarity against silk)

# Pinned parts not covered by the hand-placed clusters below.
PIN = {
    "J1": (S.FFC_X, 0.0, None),
    # capacitive touch electrodes along the long edges (TCH1 UP, TCH2 DOWN at +X; TCH3 MENU, TCH4 BACK at -X)
    "TCH1": (S.TOUCH_X[1], Y0 + S.TOUCH_W / 2 + 0.3, 0), "TCH2": (S.TOUCH_X[1], Y1 - S.TOUCH_W / 2 - 0.3, 0),
    "TCH3": (S.TOUCH_X[0], Y0 + S.TOUCH_W / 2 + 0.3, 0), "TCH4": (S.TOUCH_X[0], Y1 - S.TOUCH_W / 2 - 0.3, 0),
}
BOTTOM = {  # bottom-side pads (no parts): dock pogo pads, battery wire pads, motor lead pads, test pads
    **{tp: next(p[:2] for p in S.POGO_PADS if p[2] == net) for tp, net in (("TP1", "VBUS"), ("TP2", "USB_DM"), ("TP3", "USB_DP"), ("TP4", "GND"))},
    "TP5": (S.BATPAD_X, S.BATPAD_Y), "TP6": (S.BATPAD_X, -S.BATPAD_Y),   # VBAT next to the charger, GND next to the ESD
    "TP7": (S.MOTOR_X - S.MOTOR_PAD_DX, 0.0), "TP8": (S.MOTOR_X + S.MOTOR_PAD_DX, 0.0),
    # debug pads (TX, RX, EN, BOOT) between J1 and U1, over the flat part of the pouch (its PCM end is x -10.1..-8.0):
    # a 2 mm grid, 1 mm gaps for probes or wire tacks
    "TP9": (-1.0, 1.0), "TP10": (-3.0, 1.0), "TP11": (-1.0, -1.0), "TP12": (-3.0, -1.0), "TP13": (-7.15, 0.35),
}
TARGET = {  # loose targets for the legalizer (KiCad coords, y down)
    "R4": (-0.3, 3.4),
    "C25": (-1.95, 2.6), "C24": (-1.75, 4.05),
}


def fp_path(lib):
    return "lib/horae.pretty" if lib == "horae" else f"/usr/share/kicad/footprints/{lib}.pretty"


def V(x, y):
    return pcbnew.VECTOR2I(MM(OX + x), MM(OY + y))


def P(v):
    return (pcbnew.ToMM(v.x) - OX, pcbnew.ToMM(v.y) - OY)


def box(fp):
    lay = pcbnew.B_CrtYd if fp.IsFlipped() else pcbnew.F_CrtYd
    fp.BuildCourtyardCaches()          # cached outline does not follow SetPosition otherwise
    cy = fp.GetCourtyard(lay)
    b = cy.BBox() if cy.OutlineCount() else fp.GetBoundingBox(False)
    r = [pcbnew.ToMM(b.GetLeft()) - OX, pcbnew.ToMM(b.GetTop()) - OY, pcbnew.ToMM(b.GetRight()) - OX, pcbnew.ToMM(b.GetBottom()) - OY]
    for pad in fp.Pads():              # some imported courtyards do not cover their pads; pads + 0.15 mm always count
        if not (pad.IsOnLayer(pcbnew.F_Cu) or pad.IsOnLayer(pcbnew.B_Cu)):
            continue
        pb = pad.GetBoundingBox()
        r = [min(r[0], pcbnew.ToMM(pb.GetLeft()) - OX - 0.15), min(r[1], pcbnew.ToMM(pb.GetTop()) - OY - 0.15),
             max(r[2], pcbnew.ToMM(pb.GetRight()) - OX + 0.15), max(r[3], pcbnew.ToMM(pb.GetBottom()) - OY + 0.15)]
    return tuple(r)


def overlap(a, b, m=0.05):
    return a[0] < b[2] + m and b[0] < a[2] + m and a[1] < b[3] + m and b[1] < a[3] + m


def tab_rects(depth, along=0.0, end_depth=None):
    """Board-side strips along each panel tab, `depth` (`end_depth` on the short edges) deep from the edge, extended
    `along` past the tab ends."""
    out = []
    for (ax, ay), (bx, by) in TABS:
        if ax == bx:   # tab on a short (X) edge
            sx = 1 if ax > 0 else -1
            depth_ = depth if end_depth is None else end_depth
            out.append((min(ax, ax - sx * depth_), min(ay, by) - along, max(ax, ax - sx * depth_), max(ay, by) + along))
        else:
            sy = 1 if ay > 0 else -1
            out.append((min(ax, bx) - along, min(ay, ay - sy * depth), max(ax, bx) + along, max(ay, ay - sy * depth)))
    return out


def main():
    pcbnew.KIID.SeedGenerator(1)   # reproducible UUIDs -> stable item order in the DSN -> reproducible Freerouting
    board = pcbnew.NewBoard("horae.kicad_pcb")
    board.SetCopperLayerCount(4)
    ds = board.GetDesignSettings()
    ds.SetBoardThickness(MM(S.PCB_T))
    ds.m_TrackMinWidth, ds.m_MinClearance = MM(0.1), MM(0.1)     # >= 0.10 mm everywhere (JLC 0.09 + margin, no 3.5 mil surcharge)
    ds.m_ViasMinSize, ds.m_MinThroughDrill = MM(VIA_D), MM(VIA_H)
    nc = ds.m_NetSettings.GetDefaultNetclass()
    nc.SetTrackWidth(MM(0.1)); nc.SetClearance(MM(0.11))          # 0.01 margin for widening necked wires to 0.10
    nc.SetViaDiameter(MM(VIA_D)); nc.SetViaDrill(MM(VIA_H))

    nets = {}
    for p in PARTS:
        for n in p[5].values():
            if n not in nets:
                nets[n] = pcbnew.NETINFO_ITEM(board, n)
                board.Add(nets[n])

    # outline: rounded rectangle
    r = S.PCB_CORNER_R
    def seg(a, b, layer=pcbnew.Edge_Cuts, w=0.1):
        s = pcbnew.PCB_SHAPE(board); s.SetShape(pcbnew.SHAPE_T_SEGMENT); s.SetLayer(layer)
        s.SetStart(V(*a)); s.SetEnd(V(*b)); s.SetWidth(MM(w)); board.Add(s); return s
    def arc(c, a0):
        s = pcbnew.PCB_SHAPE(board); s.SetShape(pcbnew.SHAPE_T_ARC); s.SetLayer(pcbnew.Edge_Cuts); s.SetWidth(MM(0.1))
        pts = [(c[0] + r * math.cos(math.radians(a)), c[1] + r * math.sin(math.radians(a))) for a in (a0, a0 + 45, a0 + 90)]
        s.SetArcGeometry(V(*pts[0]), V(*pts[1]), V(*pts[2])); board.Add(s)
    seg((X0 + r, Y0), (X1 - r, Y0)); seg((X1, Y0 + r), (X1, Y1 - r)); seg((X1 - r, Y1), (X0 + r, Y1)); seg((X0, Y1 - r), (X0, Y0 + r))
    arc((X1 - r, Y0 + r), 270); arc((X1 - r, Y1 - r), 0); arc((X0 + r, Y1 - r), 90); arc((X0 + r, Y0 + r), 180)

    fps = {}
    for ref, sym, val, fpname, lcsc, pins, block in PARTS:
        lib, name = fpname.split(":")
        fp = pcbnew.FootprintLoad(fp_path(lib), name)
        fp.SetFPID(pcbnew.LIB_ID(lib, name))
        fp.SetReference(ref); fp.SetValue(val)
        fp.SetPath(pcbnew.KIID_PATH("/" + uid("s", ref)))
        for pad in fp.Pads():
            n = pins.get(pad.GetNumber())
            if n:
                pad.SetNet(nets[n])
        fp.Reference().SetVisible(False); fp.Value().SetVisible(False)   # no silk refs on a 16 mm board
        for it in fp.GraphicalItems():                                   # footprint silk goes to Fab; polarity marks are added below
            if it.GetLayer() in (pcbnew.F_SilkS, pcbnew.B_SilkS):
                it.SetLayer(pcbnew.F_Fab if it.GetLayer() == pcbnew.F_SilkS else pcbnew.B_Fab)
        if ref in HEIGHT:                                                # datasheet max height, model sitting on the board
            h, z0, z1 = HEIGHT[ref]
            m = fp.Models()[0]; k = h / (z1 - z0)
            m.m_Scale.z = k; m.m_Offset.z = -z0 * k
        if not lcsc and ref.startswith(("C", "AE")):                     # unfitted parts (C12) and the antenna get no paste
            for pad in fp.Pads():
                ls = pad.GetLayerSet(); ls.RemoveLayer(pcbnew.F_Paste); pad.SetLayerSet(ls)
        board.Add(fp)
        fps[ref] = fp

    def put(fp, x, y, rot=0, flip=False):
        fp.SetPosition(V(x, y)); fp.SetOrientationDegrees(rot)
        if flip and not fp.IsFlipped():
            fp.Flip(fp.GetPosition(), pcbnew.FLIP_DIRECTION_TOP_BOTTOM)
    def j1_net(num):
        return [q for q in fps["J1"].Pads() if q.GetNumber() == str(num)][0].GetNetname()
    def pad_xy(fp, num):
        p = [q for q in fp.Pads() if q.GetNumber() == num][0].GetPosition()
        return P(p)
    def pin_pad(ref, num, x, y, direction):
        """Place a 2-pad part with pad `num` centred on (x, y) and its other pad toward `direction`."""
        fp = fps[ref]
        for rot in (0, 90, 180, 270):
            put(fp, 0, 0, rot)
            a = pad_xy(fp, num); b = pad_xy(fp, "2" if num == "1" else "1")
            v = (round(b[0] - a[0], 2), round(b[1] - a[1], 2))
            if (direction == "+x" and v[0] > 0.2) or (direction == "-x" and v[0] < -0.2) or (direction == "+y" and v[1] > 0.2) or (direction == "-y" and v[1] < -0.2):
                put(fp, x - a[0], y - a[1], rot); return
        raise SystemExit(f"cannot orient {ref}")
    def track(net, pts, w, layer=pcbnew.F_Cu):
        for a, b in zip(pts, pts[1:]):
            if abs(a[0] - b[0]) < 1e-6 and abs(a[1] - b[1]) < 1e-6:
                continue                                       # no zero-length segments (DRC: dangling track)
            t = pcbnew.PCB_TRACK(board); t.SetStart(V(*a)); t.SetEnd(V(*b)); t.SetWidth(MM(w))
            t.SetLayer(layer); t.SetNet(nets[net]); t.SetLocked(True); board.Add(t)
    def via(net, x, y):
        v = pcbnew.PCB_VIA(board); v.SetPosition(V(x, y)); v.SetWidth(MM(VIA_D)); v.SetDrill(MM(VIA_H))
        v.SetNet(nets[net]); v.SetLocked(True); board.Add(v); return v

    # antenna: long axis across the board at the +X end, feed/ground pads facing the board (-X)
    ae = fps["AE1"]
    put(ae, X1 - 5.20, -9.845, -90)
    cu = lambda: [gr.GetBoundingBox() for gr in ae.GraphicalItems() if gr.GetLayer() == pcbnew.F_Cu] + [p.GetBoundingBox() for p in ae.Pads()]
    cy0 = (min(pcbnew.ToMM(b.GetTop()) for b in cu()) + max(pcbnew.ToMM(b.GetBottom()) for b in cu())) / 2 - OY
    put(ae, X1 - 5.20, -9.845 - cy0, -90)   # centre the (trimmed, asymmetric) copper across the board
    cu_x1 = max(pcbnew.ToMM(b.GetRight()) for b in cu()) - OX
    put(ae, X1 - 5.20 + (X1 - 0.35 - cu_x1), -9.845 - cy0, -90)   # meander tip 0.35 mm from the +X edge
    ant_cu_x = min(pcbnew.ToMM(b.GetLeft()) for b in cu()) - OX
    fx, fy = pad_xy(ae, "1")
    ANT_KEEP_X = fx + 0.45      # ground and tracks may reach the feed/short pads; the meander stays clear

    # ESP32 (rot 180: pins 1-14 face the antenna, pin 1 at the feed corner)
    u1 = fps["U1"]
    put(u1, *U1_XY, 180)
    up = lambda n: pad_xy(u1, str(n))

    # FFC: the slot is on the fitting-nail side (pads 19/20), which faces the U-bend at -X
    j1 = fps["J1"]
    for rot in (90, 270):
        put(j1, *PIN["J1"][:2], rot)
        if pad_xy(j1, "19")[0] < PIN["J1"][0]:
            break
    for ref in ("TCH1", "TCH2", "TCH3", "TCH4"):
        put(fps[ref], *PIN[ref])
    for ref, (x, y) in BOTTOM.items():
        put(fps[ref], x, y, 0, flip=True)
    for txt, ref in (("+", "TP5"), ("-", "TP6")):     # battery polarity next to the wire pads
        bx_, by_ = BOTTOM[ref]
        t = pcbnew.PCB_TEXT(board); t.SetText(txt); t.SetLayer(pcbnew.B_SilkS); t.SetMirrored(True)
        t.SetTextSize(pcbnew.VECTOR2I(MM(1.2), MM(1.2))); t.SetTextThickness(MM(0.2))
        t.SetPosition(V(bx_ + 1.9, by_)); board.Add(t)

    pp = pin_pad
    # --- RF chain: pin 1 -> 45 deg jog south -> C11 (shunt) -> L3 (series) -> C12 (shunt, DNP, at the corner) -> feed.
    # 0.15 mm pad gaps (mask webs >= JLC's 0.10, no shared openings); W0.15/S0.15 GCPW
    rx, ry = up(1)
    ry2 = ry + 0.5
    pp("C11", "1", rx + 1.25, ry2, "+y")
    pp("L3", "1", rx + 1.83, ry2, "+x")
    pp("C12", "1", fx, ry2, "-y")
    c11a, l3a, l3b, c12a = pad_xy(fps["C11"], "1"), pad_xy(fps["L3"], "1"), pad_xy(fps["L3"], "2"), pad_xy(fps["C12"], "1")
    track("RF_CHIP", [(rx, ry), (rx + 0.55, ry), (rx + 1.05, ry2), c11a, l3a], RF_W)
    track("RF_ANT", [l3b, c12a, (fx, fy)], RF_W)
    ae2 = pad_xy(ae, "2")                                   # IFA short: straight to the plane
    track("GND", [ae2, (ae2[0] - 0.75, ae2[1])], 0.3)
    via("GND", ae2[0] - 0.75, ae2[1])

    # --- VDD3P3 (PA supply): pins 2+3 -> C3 (1 uF) -> L2 (2 nH) -> +3V3, F.Cu only, no vias (Espressif HDG 1.4.2)
    p2, p3 = up(2), up(3)
    pp("C3", "1", p3[0] + 1.15, p3[1] + 0.04, "+y")          # >= 0.15 mm pad gaps to C10 and C11 (JLC SMD pad spacing)
    pp("L2", "2", p3[0] + 1.78, p3[1] + 0.15, "+x")
    c3a, l2b = pad_xy(fps["C3"], "1"), pad_xy(fps["L2"], "2")
    track("VDD3P3", [p2, (p2[0] + 0.5, p2[1]), (p3[0] + 0.5, p3[1]), c3a, l2b], 0.2)
    track("VDD3P3", [p3, (p3[0] + 0.5, p3[1])], 0.2)
    l2a = pad_xy(fps["L2"], "1")
    track("+3V3", [l2a, (l2a[0] + 0.48, l2a[1] - 0.35)], 0.2)
    via("+3V3", l2a[0] + 0.48, l2a[1] - 0.35)
    # --- EN: C10 1 uF right at pin 4's outer end; the pin's inner end drops to a via under the package (EN runs west to R1/TP11)
    p4 = up(4)
    tip = p4[0] + 0.4                                        # outer end of the east pads
    pp("C10", "1", tip + 0.38, p4[1] - 0.15, "+x")
    track("EN", [p4, (tip + 0.2, p4[1]), pad_xy(fps["C10"], "1")], 0.12)
    c10b = pad_xy(fps["C10"], "2")
    track("GND", [c10b, (c10b[0] + 0.68, c10b[1] + 0.12)], 0.15)
    via("GND", c10b[0] + 0.68, c10b[1] + 0.12)                   # 0.3 mm clear of R15's electrode-side pad
    # BOOT, VIB, CHG_STAT and EN leave inward (pad inner end -> tented via between the pads and the EP) so the east side is
    # free for the touch resistors
    inner = p4[0] - 0.4
    for pin, dy in ((4, 0.1), (5, -0.15), (10, 0.15), (11, -0.1), (12, -0.35)):
        px_, py_ = up(pin)
        track(ESP_NET[pin], [(px_, py_), (inner, py_), (U1_XY[0] + 2.5, py_ + dy)], 0.12)
        via(ESP_NET[pin], U1_XY[0] + 2.5, py_ + dy)
    # --- touch series resistors (Espressif: within 1 mm of the pin): a column at 0.6 mm pitch fanned out from pins 9..6,
    # each _E end leaving east to its own via (staggered columns, >= 0.3 mm apart); inside the "touch fan-out" area the
    # Touch class may come to 0.2 mm (horae.kicad_dru), everywhere else it keeps 0.3
    for k, (ref, pin) in enumerate((("R14", 9), ("R16", 8), ("R17", 7), ("R15", 6))):
        ry_ = -1.2 + 0.6 * k
        pp(ref, "1", tip + 0.95, ry_, "+x")
        px_, py_ = up(pin)
        jx = tip + 0.1 + abs(ry_ - py_)                      # 45-degree jogs, all starting at the same x: parallel, 0.28 apart
        track(ESP_NET[pin], [(px_, py_), (tip + 0.1, py_), (jx, ry_), pad_xy(fps[ref], "1")], 0.12)
        e = pad_xy(fps[ref], "2"); vx = tip + (2.07 if k % 2 == 0 else 2.57)
        track(ESP_NET[pin] + "_E", [e, (vx, ry_)], 0.12)
        via(ESP_NET[pin] + "_E", vx, ry_)
    fanout = (tip, -1.55, tip + 3.05, 0.95)
    open("out/fanout.txt", "w").write(" ".join(f"{v:.3f}" for v in fanout))

    # --- VDDA (pins 55/56): C6 1 uF + C36 10 nF in the corner east of pin 56; VDD3P3_CPU (46): C34; VDD3P3_RTC (20): C20
    p55, p56, p46, p20 = up(55), up(56), up(46), up(20)
    pp("C6", "1", p56[0] + 0.55, p56[1] + 0.15, "+x")
    pp("C36", "1", p56[0] + 0.55, p56[1] + 0.8, "+x")
    c6a, c36a = pad_xy(fps["C6"], "1"), pad_xy(fps["C36"], "1")
    track("+3V3", [p55, (p55[0], p55[1] + 0.52), (p56[0], p56[1] + 0.52), p56], 0.15)
    track("+3V3", [p56, (p56[0], c6a[1]), c6a, c36a], 0.15)
    for pin, vx in ((49, 4.45), (50, 5.1)):                    # UART leaves inward (tented vias between pads and EP)
        px_, py_ = up(pin)
        track(ESP_NET[pin], [(px_, py_), (px_, py_ - 0.4), (vx, py_ - 0.93)], 0.12)
        via(ESP_NET[pin], vx, py_ - 0.93)
    pp("C34", "1", p46[0], p46[1] + 0.78, "+y")
    c34b = pad_xy(fps["C34"], "2")
    track("GND", [c34b, (c34b[0], c34b[1] + 0.45)], 0.15)
    via("GND", c34b[0], c34b[1] + 0.45)                       # just outside TCH2's keep-out
    track("+3V3", [p46, pad_xy(fps["C34"], "1")], 0.15)
    # north row: SPI/USB pins 23..27 drop to staggered vias right above the pads (two rows, 0.8 mm apart)
    for pin, dy in ((27, 0.9), (26, 1.55), (25, 0.9), (24, 1.55), (23, 0.9)):
        px_, py_ = up(pin)
        track(ESP_NET[pin], [(px_, py_), (px_, py_ - dy)], 0.12)
        via(ESP_NET[pin], px_, py_ - dy)
    pp("C20", "1", p20[0], p20[1] - 0.8, "+x")
    track("+3V3", [p20, pad_xy(fps["C20"], "1")], 0.15)
    for pin, vx in ((20, 4.9), (19, 5.55), (18, 6.2), (17, 6.85)):   # inward: tented vias between the pads and the EP
        px_, py_ = up(pin)
        track(ESP_NET[pin], [(px_, py_), (px_, py_ + 0.4), (vx, py_ + 0.93)], 0.12)
        via(ESP_NET[pin], vx, py_ + 0.93)
    # VDD_SPI (29): C9 100 nF + C8 1 uF in U1's empty NW corner, straight above the pin (0.2 mm gaps)
    p29 = up(29)
    for ref, dx, tx in (("C9", -0.38, -0.33), ("C8", 0.38, 0.35)):   # C8 0.17 mm from pin 28
        pp(ref, "1", p29[0] + dx, p29[1] - 0.55, "-y")
        track("VDD_SPI", [p29, (p29[0] + tx, p29[1]), pad_xy(fps[ref], "1")], 0.2)

    # --- 40 MHz crystal (Espressif HDG 1.4.3): L1 straight off pin 54, crystal ~1.4 mm out, XTAL_P east of it, XTAL_N round
    # its west side, load caps at the crystal ends; F.Cu only, no vias, nothing under it
    p53, p54 = up(53), up(54)
    pp("L1", "1", p54[0], p54[1] + 0.78, "+y")
    l1a, l1b = pad_xy(fps["L1"], "1"), pad_xy(fps["L1"], "2")
    put(fps["Y1"], p54[0] + 1.05, p54[1] + 3.0, 180)        # pads: 1 (XTAL_P) NE, 3 (XTAL_N) SW, 2/4 GND
    y1 = {n: pad_xy(fps["Y1"], n) for n in "1234"}
    pp("C1", "1", y1["1"][0] + 0.93, y1["1"][1], "+y")
    xn = y1["3"][0] - 0.95
    pp("C2", "1", xn, p53[1] + 1.05, "-x")                 # XTAL_N load cap where the trace turns down, GND pad west
    c2a = pad_xy(fps["C2"], "1")
    track("XTAL_P_L", [p54, l1a], 0.12)
    track("XTAL_P", [l1b, (y1["1"][0], l1b[1]), y1["1"], pad_xy(fps["C1"], "1")], 0.12)
    track("XTAL_N", [p53, (p53[0], p53[1] + 0.7), c2a, (xn, y1["3"][1]), y1["3"]], 0.12)
    # crystal ground: both GND pads tied under the body (no signal under it) and on to C1's ground pad; C2's via SW of it
    track("GND", [y1["2"], y1["4"], (y1["4"][0] + 0.75, y1["4"][1] - 0.35), pad_xy(fps["C1"], "2")], 0.2)
    c2b = pad_xy(fps["C2"], "2")
    track("GND", [c2b, (c2b[0] - 0.1, c2b[1] + 0.65)], 0.2)
    via("GND", c2b[0] - 0.1, c2b[1] + 0.65)

    # --- 32.768 kHz crystal + accelerometer in the NE corner (north of the U1 corner, clear of the north pins' exits)
    put(fps["U6"], up(14)[0] + 1.45, up(14)[1] - 1.75, 90)   # INT1/INT2 on its west side, SCL/SDA on its south side
    u6v = pad_xy(fps["U6"], "9")
    pp("C7", "1", u6v[0] + 0.18, u6v[1] - 0.74, "+x")
    # U6's supply/ground ring outside the package (nothing on F.Cu under it): Vdd/Vdd_IO bridged to C7, CS (pin 2) down a via
    u6 = {n: pad_xy(fps["U6"], n) for n in ("2", "3", "6", "7", "8", "9", "10")}
    c7a, c7b = pad_xy(fps["C7"], "1"), pad_xy(fps["C7"], "2")
    track("+3V3", [u6["10"], u6["9"], (u6["9"][0], u6["9"][1] - 0.4), c7a], 0.15)
    track("+3V3", [c7a, (c7a[0], c7a[1] - 0.65)], 0.15)                      # Vdd/Vdd_IO's own way down (the CS/SA0 via is boxed in)
    via("+3V3", c7a[0], c7a[1] - 0.65)
    track("GND", [u6["6"], u6["7"], u6["8"], (u6["8"][0], u6["8"][1] - 0.4), c7b], 0.15)
    u6m = ((u6["2"][0] + u6["3"][0]) / 2, u6["2"][1])
    track("+3V3", [u6["3"], u6m, u6["2"]], 0.15)                              # SA0 high with CS: 0x19
    track("+3V3", [u6m, (u6m[0], u6m[1] + 0.54)], 0.15)
    via("+3V3", u6m[0], u6m[1] + 0.54)
    # Vdd/Vdd_IO's via joined to the CS/SA0 via on In2 round U6's east side (between the GND vias, the motor-gate via and the antenna
    # keep-out), so the channel north of U6 stays free for VIB
    ex = 11.58
    track("+3V3", [(c7a[0], c7a[1] - 0.65), (c7a[0], -6.0), (ex, -6.0), (ex, -3.5), (ex - 0.45, u6m[1] + 0.54),
                   (u6m[0], u6m[1] + 0.54)], 0.2, pcbnew.In2_Cu)
    # I2C on F.Cu: SCL (pin 14) straight up to U6 pin 1; SDA (pin 13) loops south of the CS/SA0 via to pin 4
    p13, p14, u61, u64 = up(13), up(14), pad_xy(fps["U6"], "1"), pad_xy(fps["U6"], "4")
    track("I2C_SCL", [p14, (p14[0] + 0.4, p14[1]), (u61[0], p14[1] - 0.3), u61], 0.12)
    track("I2C_SDA", [p13, (p13[0] + 0.95, p13[1]), (p13[0] + 1.3, p13[1] - 0.35), (u64[0] - 0.25, p13[1] - 0.35),
                      (u64[0], p13[1] - 0.6), u64], 0.12)
    y2x, y2y = up(15)[0] - 0.1, -6.45
    put(fps["Y2"], y2x, y2y, 0)
    if pad_xy(fps["Y2"], "1")[0] < pad_xy(fps["Y2"], "2")[0]:   # XTAL32_P (pin 21, east of 22) on the east pad
        put(fps["Y2"], y2x, y2y, 180)
    y2a, y2b = pad_xy(fps["Y2"], "1"), pad_xy(fps["Y2"], "2")
    pp("C32", "1", y2a[0] + 0.8, y2a[1], "-y")              # GND pads to the free board edge
    pp("C33", "1", y2b[0] - 0.8, y2b[1], "-y")
    track("XTAL32_P", [y2a, pad_xy(fps["C32"], "1")], 0.12)
    track("XTAL32_N", [y2b, pad_xy(fps["C33"], "1")], 0.12)
    # the 32 kHz pair on F.Cu over the north row (C20 lies flat on the row, DC/RES/BUSY leave inward)
    p21, p22 = up(21), up(22)
    track("XTAL32_P", [p21, (p21[0], p21[1] - 1.5), (y2a[0], p21[1] - 1.5), y2a], 0.12)
    track("XTAL32_N", [p22, (p22[0], p22[1] - 1.8), (y2b[0], p22[1] - 1.8), y2b], 0.12)
    p15, p16 = up(15), up(16)                                   # accelerometer interrupts straight across to its west pads
    track("ACC_INT1", [p15, (p15[0], pad_xy(fps["U6"], "12")[1]), pad_xy(fps["U6"], "12")], 0.12)
    track("ACC_INT2", [p16, (p16[0], pad_xy(fps["U6"], "11")[1]), pad_xy(fps["U6"], "11")], 0.12)
    p12 = up(12)
    pp("C18", "1", p12[0] + 0.78, p12[1], "+x")               # BAT_ADC filter (0.5 s with the divider) at the ADC pin
    track("BAT_ADC", [p12, pad_xy(fps["C18"], "1")], 0.12)

    # --- display booster (GD p.20): L4 between TCH3 and TCH1 with its quiet +3V3 pad between the electrodes and the SW pad
    # south; switch, boost diode and pump cap all touch the SW pad's south edge, the pump diodes and sense R below them.
    # J1's GDR/RESE/VSHR (contacts 18/17/16) come down the channel between the J1 fan-out and L4.
    put(fps["L4"], -1.1, -4.8, 270)                           # pad 1 (+3V3) north, pad 2 (SW) south
    swy = pad_xy(fps["L4"], "2")[1] + 0.4                     # SW pad's south edge
    pp("C35", "1", -1.58, pad_xy(fps["L4"], "1")[1] - 1.35, "+x")   # VCI/booster bulk above the +3V3 pad
    def place3(ref, x, y, up_pin, west_pin):
        """3-pin part centred at (x, y) with pad `up_pin` north and pad `west_pin` west of the other south pad."""
        for rot in (0, 90, 180, 270):
            put(fps[ref], x, y, rot)
            pu = pad_xy(fps[ref], up_pin); others = [q for q in "123" if q != up_pin]
            pw = pad_xy(fps[ref], west_pin); po = pad_xy(fps[ref], [q for q in others if q != west_pin][0])
            if pu[1] < y - 0.2 and pw[0] < po[0]:
                return
        raise SystemExit(f"cannot orient {ref}")
    place3("Q1", -2.1, swy + 0.65, "3", "1")                  # drain up into the SW pad, gate west, source east
    pp("D3", "2", -1.26, swy + 0.3, "+y")                     # SW -> PREVGH (anode up)
    pp("C22", "1", -0.39, swy + 0.57, "+y")                   # SW -> pump (SW pad up)
    pp("D2", "2", -0.54, swy + 2.3, "+y")                     # pump clamp: PUMP up, GND down
    pp("D1", "1", 0.32, swy + 1.8, "+y")                      # PUMP -> PREVGL (0.16 mm from D2)
    q1g, q1s, q1d = pad_xy(fps["Q1"], "1"), pad_xy(fps["Q1"], "2"), pad_xy(fps["Q1"], "3")
    pp("R12", "1", q1s[0], q1s[1] + 0.67, "+y")               # 2.2R sense straight below the source
    pp("C26", "1", -3.2, q1s[1] + 1.0, "+y")                 # VSHR, at the channel's foot
    j18, j17, j16 = pad_xy(j1, "18"), pad_xy(j1, "17"), pad_xy(j1, "16")
    pp("R11", "1", j18[0] + 0.95, j18[1] - 0.45, "-y")        # GDR pull-down just past J1's GDR contact
    l4sw = pad_xy(fps["L4"], "2")
    # bulk 10 uF and the EN pull-up west of U1, tied on F.Cu (EN reaches R1 from pin 4's inward via)
    pp("R1", "1", -0.65, 0.95, "+x")
    pp("C5", "1", 0.1, 2.78, "-y")
    track("+3V3", [pad_xy(fps["R1"], "1"), (-0.65, 1.35), (0.6, 1.35), (0.6, 2.78), pad_xy(fps["C5"], "1")], 0.12)
    for a in (q1d, pad_xy(fps["D3"], "2"), pad_xy(fps["C22"], "1")):
        track("EPD_SW", [a, (a[0], swy - 0.15), l4sw], 0.3)
    c22b, d1a, d2b = pad_xy(fps["C22"], "2"), pad_xy(fps["D1"], "1"), pad_xy(fps["D2"], "2")
    track("EPD_PUMP", [d2b, c22b, d1a], 0.2)
    tail = j18[0] + 0.45                                      # J1 contact tails
    r11a = pad_xy(fps["R11"], "1")
    track("EPD_GDR", [j18, (tail + 0.3, j18[1]), (r11a[0], j18[1]), (-2.85, j18[1]), (-2.85, q1g[1]), q1g], 0.12)
    track("EPD_GDR", [(r11a[0], j18[1]), r11a], 0.12)
    track("EPD_RESE", [j17, (tail + 0.3, j17[1]), (-3.15, j17[1]), (-3.15, q1s[1] + 0.42), (q1s[0], q1s[1] + 0.42), q1s], 0.12)
    track("EPD_RESE", [(q1s[0], q1s[1] + 0.42), pad_xy(fps["R12"], "1")], 0.12)
    c26a = pad_xy(fps["C26"], "1")
    track("EPD_VSHR", [j16, (tail + 0.3, j16[1]), (-3.45, j16[1]), (-3.45, c26a[1]), c26a], 0.12)
    # the mic stays where the case duct expects it
    put(fps["MIC1"], S.MIC_X, S.MIC_Y, 180)
    # MIC_VDD: C31 at the mic's NE corner, then down the 0.5 mm channel between the pad columns to VDD (pad 4, SW corner;
    # top-port part, plain underside); DATA and CLK take the west side and the north end
    m4, m5, m6 = (pad_xy(fps["MIC1"], n) for n in "456"); mx = (m4[0] + pad_xy(fps["MIC1"], "1")[0]) / 2
    pp("C31", "1", 0.0, m6[1] + 0.31, "+y")                     # MIC_VDD cap east of the mic's GND column
    c31a = pad_xy(fps["C31"], "1")
    p43, p44, p45 = up(43), up(44), up(45)
    yd, yc, yv = m6[1] - 0.95, m6[1] - 0.74, m6[1] - 0.53       # three tracks above the mic, 0.21 mm pitch
    track("MIC_DATA", [p43, (p43[0], yd), (m5[0] - 0.52, yd), (m5[0] - 0.52, m5[1]), m5], 0.1)
    track("MIC_CLK", [p44, (p44[0], yc), (m6[0], yc), m6], 0.1)
    track("MIC_VDD", [p45, (p45[0], yv), (c31a[0], yv), (mx, yv), (mx, m4[1]), m4], 0.1)
    track("MIC_VDD", [(c31a[0], yv), c31a], 0.1)
    # --- J1 contacts 9..15 (VCI + EPD SPI) fan out under the connector body to two staggered via columns
    for num in range(9, 16):
        jx, jy = pad_xy(j1, str(num)); net_ = j1_net(num)
        vx = jx - (1.55 if num % 2 else 0.95)
        track(net_, [(jx, jy), (vx, jy)], 0.2 if num == 9 else 0.12)
        via(net_, vx, jy)
    # --- display rail caps in a column right at J1's contacts
    for ref, num in (("C27", "7"), ("C28", "5"), ("C29", "3"), ("C30", "1")):
        jx, jy = pad_xy(j1, num)
        pp(ref, "1", jx + 1.14, jy, "+x")
        track(j1_net(int(num)), [(jx, jy), pad_xy(fps[ref], "1")], 0.15)
    # --- buck cell (TI fig. 62 style) in the +Y corner: CIN east of VIN/EN, L straight out of SW, COUT past L, VSET up;
    # the motor switch and its flyback diode west of it, over the battery and motor pads
    bx, by = -10.2, 6.75
    put(fps["U3"], bx, by, 90)
    pp("C15", "1", bx + 1.07, by - 0.33, "+y")                 # VIN cap east of the VBAT balls
    pp("L5", "1", bx - 1.45, by - 1.0, "+y")                   # SW pad north, +3V3 pad south
    l5b = pad_xy(fps["L5"], "2")
    pp("C17", "1", l5b[0] - 1.2, l5b[1] + 0.38, "-y")          # COUT west of L5, +3V3 pad south
    pp("R6", "1", bx - 0.15, by - 1.2, "+x")                   # VSET just north of C2
    u3 = {n: pad_xy(fps["U3"], n) for n in ("A1", "A2", "B1", "B2", "C1", "C2")}
    track("VBAT", [u3["B1"], u3["C1"], pad_xy(fps["C15"], "1")], 0.15)
    track("GND", [u3["A1"], pad_xy(fps["C15"], "2")], 0.12)
    c15b = pad_xy(fps["C15"], "2")
    track("GND", [c15b, (c15b[0] - 0.57, c15b[1] + 0.17)], 0.15)
    via("GND", c15b[0] - 0.57, c15b[1] + 0.17)
    track("BUCK_SW", [u3["B2"], (u3["B2"][0] - 0.2, u3["B2"][1]), (u3["B2"][0] - 0.6, u3["B2"][1] - 0.4), pad_xy(fps["L5"], "1")], 0.2)
    track("+3V3", [u3["A2"], (u3["A2"][0] - 0.45, u3["A2"][1]), pad_xy(fps["L5"], "2")], 0.2)
    track("BUCK_VSET", [u3["C2"], pad_xy(fps["R6"], "1")], 0.12)
    l5b_ = pad_xy(fps["L5"], "2")
    track("+3V3", [l5b_, (l5b_[0], l5b_[1] + 0.6)], 0.3)
    via("+3V3", l5b_[0], l5b_[1] + 0.6)
    track("+3V3", [pad_xy(fps["C17"], "1"), l5b_], 0.3)
    # buck output to the rest of the rail: In2 hop past the VBAT trunk, then F.Cu across the empty FPC lane to J1's VCI via
    v2 = (l5b_[0] + 0.85, 4.85)                                  # clear of the TP3 pogo pad on B.Cu
    track("+3V3", [(l5b_[0], l5b_[1] + 0.6), v2], 0.3, pcbnew.In2_Cu)
    via("+3V3", *v2)
    j9v = (pad_xy(j1, "9")[0] - 1.55, pad_xy(j1, "9")[1])
    d_ = v2[1] - j9v[1] - 0.75
    track("+3V3", [v2, (v2[0] + d_ - 0.75, v2[1] - d_ + 0.75), (j9v[0], j9v[1] + 0.75), j9v], 0.3)
    # motor: switch with its gate/source facing the FPC lane (vias/tracks may run under the ribbon), flyback below it,
    # MOT_N/VBAT reach the motor and battery pads on B.Cu right underneath
    place3("Q2", -14.2, 5.75, "1", "2")                       # gate/source north (gate east), drain south
    pp("D4", "2", -14.2, 6.55, "+y")                          # anode (MOT_N) up at the drain, cathode (VBAT) down
    track("MOT_N", [pad_xy(fps["Q2"], "3"), pad_xy(fps["D4"], "2")], 0.3)
    d4k = pad_xy(fps["D4"], "1")
    track("VBAT", [d4k, (d4k[0] + 0.7, d4k[1] + 0.15)], 0.3)
    via("VBAT", d4k[0] + 0.7, d4k[1] + 0.15)                  # lands inside TP5 (battery +) on B.Cu
    track("VBAT", [(d4k[0] + 0.7, d4k[1] + 0.15), BOTTOM["TP5"]], 0.3, pcbnew.B_Cu)
    # the motor's switched lead: off the battery pad on F.Cu, down a via, across on an inner layer to TP8
    d4a = pad_xy(fps["D4"], "2")
    track("MOT_N", [d4a, (-15.05, d4a[1])], 0.3)
    via("MOT_N", -15.05, d4a[1])
    via("MOT_N", *BOTTOM["TP8"])                              # inside the motor pad (no part above: FPC lane)
    pp("R3", "1", -8.05, 6.92, "-y")                          # battery divider top on VBAT, next to the buck's input cap
    r3a = pad_xy(fps["R3"], "1")
    track("VBAT", [pad_xy(fps["C15"], "1"), r3a, (r3a[0], r3a[1] + 0.63)], 0.2)
    via("VBAT", r3a[0], r3a[1] + 0.63)
    track("VBAT", [(r3a[0], r3a[1] + 0.63), (r3a[0] - 0.5, r3a[1] + 0.13), (-12.9, r3a[1] + 0.13), BOTTOM["TP5"]], 0.3, pcbnew.B_Cu)

    # --- charger in the -Y corner: row A (OUT/IN) south, B (TS/ISET) middle, C (CHG/GND) north
    cxg, cyg = -12.95, -6.85
    put(fps["U2"], cxg, cyg, 90)
    u2 = {n: pad_xy(fps["U2"], n) for n in ("A1", "A2", "B1", "B2", "C1", "C2")}
    pp("C13", "1", u2["A2"][0] - 0.3, -5.52, "-x")                 # IN 4.7 uF/25 V, 0402, just SW of A2
    pp("C14", "1", u2["A1"][0] + 0.15, -5.7, "+x")                 # OUT 1 uF, just SE of A1
    pp("R7", "1", u2["B2"][0] - 0.57, u2["B2"][1] - 0.05, "-x")     # ISET RC: 2.7k west of B2 ...
    pp("C19", "1", u2["B2"][0] - 1.21, u2["B2"][1] - 0.7, "+x")     # ... into 10 nF to GND (north of it)
    pp("R2", "1", u2["B2"][0] - 0.57, u2["B2"][1] + 0.6, "-x")      # ISET 6.8k to GND (south of it)
    pp("R5", "1", u2["B1"][0] + 0.52, u2["B1"][1] + 0.1, "+x")      # TS 10k east of B1
    put(fps["U4"], -9.95, -6.55, 0)                                # ESD between the pogo pads and the charger
    pp("R13", "1", 11.05, -5.9, "-y")                              # motor gate pull-down (anywhere on VIB): NE corner strip
    r13a = pad_xy(fps["R13"], "1")
    track("VIB", [r13a, (r13a[0] + 0.05, r13a[1] + 0.63)], 0.12)
    via("VIB", r13a[0] + 0.05, r13a[1] + 0.63)

    track("CHG_ISET_RC", [pad_xy(fps["R7"], "2"), pad_xy(fps["C19"], "1")], 0.12)
    track("VBAT", [u2["A1"], pad_xy(fps["C14"], "1")], 0.15)        # necked ball connections
    track("VBUS", [u2["A2"], pad_xy(fps["C13"], "1")], 0.15)
    c13a, u4v = pad_xy(fps["C13"], "1"), pad_xy(fps["U4"], "5")
    track("VBUS", [c13a, (c13a[0] + 0.45, -4.45), (u4v[0] + 0.58, -4.45), (u4v[0] + 0.58, u4v[1]), u4v], 0.2)
    # VBAT trunk on B.Cu down the -X end (under the FPC, clear of the pogo and motor pads): charger out -> motor + -> battery +
    c14a = pad_xy(fps["C14"], "1")
    track("VBAT", [c14a, (c14a[0], c14a[1] + 0.55)], 0.2)
    via("VBAT", c14a[0], c14a[1] + 0.55)
    tp5, tp7 = BOTTOM["TP5"], BOTTOM["TP7"]
    track("VBAT", [(c14a[0], c14a[1] + 0.55), (-13.0, -4.75), (-13.6, -4.15), (-13.6, tp7[1]), (-13.6, 5.6), tp5], 0.3, pcbnew.B_Cu)
    track("VBAT", [(-13.6, tp7[1]), tp7], 0.3, pcbnew.B_Cu)
    track("CHG_ISET", [pad_xy(fps["R2"], "1"), pad_xy(fps["R7"], "1"), u2["B2"]], 0.12)
    track("CHG_TS", [u2["B1"], pad_xy(fps["R5"], "1")], 0.12)
    track("GND", [u2["C2"], (u2["C2"][0] - 0.3, u2["C2"][1] - 0.3), pad_xy(fps["C19"], "2")], 0.12)   # TI: <= 2/3 of the land
    track("CHG_STAT", [u2["C1"], (u2["C1"][0] + 0.8, u2["C1"][1] - 0.05)], 0.12)
    via("CHG_STAT", u2["C1"][0] + 0.8, u2["C1"][1] - 0.05)
    track("GND", [u2["C2"], (u2["C2"][0], Y0 + 0.28), (u2["C1"][0] + 1.5, Y0 + 0.28), (u2["C1"][0] + 1.5, Y0 + 0.43)], 0.12)
    via("GND", u2["C1"][0] + 1.5, Y0 + 0.43)                     # the GND ball's (and C19's) way out, along the board edge

    placed = [box(fps[r]) for r in ("U1", "J1", "C11", "L3", "C12", "C3", "L2", "C10", "R14", "R15", "R16", "R17", "C6", "C36",
                                    "C34", "C20", "C8", "C9", "L1", "Y1", "C1", "C2", "Y2", "C32", "C33", "U6", "C7", "C18",
                                    "L4", "Q1", "R12", "R11", "D2", "C35", "C26", "R1", "C5", "D3", "C22", "D1", "C27", "C28", "C29", "C30",
                                    "MIC1", "C31", "U3", "C15", "L5", "C17", "R6", "Q2", "D4", "R3", "U2", "C13", "C14", "R2", "R7", "C19", "R5", "U4", "R13")]
    touch_e = [(x - S.TOUCH_L / 2, y - S.TOUCH_W / 2, x + S.TOUCH_L / 2, y + S.TOUCH_W / 2) for x, y, _ in (PIN[t] for t in ("TCH1", "TCH2", "TCH3", "TCH4"))]
    touch_keep = [(a - TOUCH_KEEP, b - TOUCH_KEEP, c + TOUCH_KEEP, d + TOUCH_KEEP) for a, b, c, d in touch_e]
    placed += touch_keep
    placed.append((rx, ry - 0.3, fx + 0.3, ry2 + 0.3)); placed.append((fx - 0.3, ry2, fx + 0.3, fy))   # keep parts off the feed
    placed.append((ae2[0] - 1.1, ae2[1] - 0.4, ae2[0], ae2[1] + 0.4))   # and off the antenna short stub + via
    j1_lane = (-4.85, pad_xy(j1, "15")[1] - 0.2, -3.7, pad_xy(j1, "9")[1] + 0.25)   # J1's EPD/VCI pads fan out to vias here
    keep = [(ANT_KEEP_X - 0.15, Y0 - 1, X1 + 1, Y1 + 1), (ant_cu_x - 0.3, fy - 0.6, X1 + 1, Y1 + 1), FPC_LANE, j1_lane, fanout] + LEDGES + tab_rects(TAB_PART_BACK, TAB_PART_BACK)
    pre = []                                   # hand-routed copper the legalized parts must stay off (pad boxes stay 0.1 clear)
    for t in board.GetTracks():
        if t.GetLayer() == pcbnew.F_Cu or t.GetClass() == "PCB_VIA":
            bb = t.GetBoundingBox(); m_ = 0.1 - 0.15         # boxes already carry 0.15 mm around the pads
            pre.append((pcbnew.ToMM(bb.GetLeft()) - OX - m_, pcbnew.ToMM(bb.GetTop()) - OY - m_,
                        pcbnew.ToMM(bb.GetRight()) - OX + m_, pcbnew.ToMM(bb.GetBottom()) - OY + m_))
    def legal(b):  # courtyards may touch, not overlap
        return (b[0] >= X0 + EDGE and b[2] <= X1 - EDGE and b[1] >= Y0 + EDGE and b[3] <= Y1 - EDGE
                and not any(overlap(b, k, 0) for k in keep)
                and not any(overlap(b, p, 0.0) for p in placed)
                and not any(overlap(b, t, 0.0) for t in pre))
    area = lambda r: (lambda b: (b[2] - b[0]) * (b[3] - b[1]))(box(fps[r]))
    drift = []
    for ref in sorted(TARGET, key=lambda r: -area(r)):          # biggest first
        fp, (tx, ty) = fps[ref], TARGET[ref]
        done = False
        for rad in [i * 0.05 for i in range(0, 41)]:
            steps = max(1, int(2 * math.pi * rad / 0.05))
            for k in range(steps):
                a = 2 * math.pi * k / steps
                for rot in (0, 90):
                    put(fp, tx + rad * math.cos(a), ty + rad * math.sin(a), rot)
                    b = box(fp)
                    if legal(b):
                        placed.append(b); done = True; break
                if done: break
            if done: break
        if not done:
            put(fp, tx, ty, 0); rad = 99
        drift.append((rad, ref))
    bad = [(round(d, 2), r) for d, r in drift if d > DRIFT_MAX]
    print("legalizer drift (mm):", ", ".join(f"{r} {d:.2f}" for d, r in sorted(drift, reverse=True)[:8]))
    if bad:
        print(f"PLACEMENT FAILED: parts > {DRIFT_MAX} mm from their targets: {bad}")

    # polarity marks on F.Silkscreen: a 0.35 mm dot off pin 1 (diodes: a bar beside the cathode), >= 0.15 from any pad
    all_pads = [q for f in fps.values() if not f.IsFlipped() for q in f.Pads() if q.IsOnLayer(pcbnew.F_Cu)]
    def clear_of_pads(sh, m):
        return not any(sh.Collide(q.GetEffectiveShape(pcbnew.F_Cu), MM(m)) for q in all_pads)
    for ref, num in POLAR.items():
        f = fps[ref]; cx, cy = P(f.GetPosition())
        q = [p for p in f.Pads() if p.GetNumber() == num][0]
        qx, qy = P(q.GetPosition()); bb = q.GetBoundingBox()
        hw, hh = pcbnew.ToMM(bb.GetWidth()) / 2, pcbnew.ToMM(bb.GetHeight()) / 2
        dx, dy = qx - cx, qy - cy
        cands = []
        sx_, sy_ = math.copysign(1, dx or 1), math.copysign(1, dy or 1)
        for d in (0.33, 0.45, 0.6, 0.8, 1.0, 1.2):     # outward from pin 1 first, then sideways
            for ux, uy in ((sx_, 0), (0, sy_), (sx_, sy_), (-sx_, sy_), (sx_, -sy_), (-sx_, 0), (0, -sy_)):
                cands.append((qx + ux * (hw + d), qy + uy * (hh + d)))
        for x, y in cands:
            if not (X0 + 0.4 < x < X1 - 0.4 and Y0 + 0.4 < y < Y1 - 0.4):
                continue
            s = pcbnew.PCB_SHAPE(board); s.SetShape(pcbnew.SHAPE_T_CIRCLE); s.SetLayer(pcbnew.F_SilkS); s.SetFilled(True)
            s.SetCenter(V(x, y)); s.SetEnd(V(x + 0.1, y)); s.SetWidth(MM(0.15))
            if clear_of_pads(s.GetEffectiveShape(pcbnew.F_SilkS), 0.15):
                board.Add(s); break
        else:
            print(f"no room for a polarity mark at {ref}")

    # zones and rule areas
    def rect_zone(layer, net, x0, y0, x1, y1, prio=0, pts=None):
        z = pcbnew.ZONE(board); z.SetLayer(layer); z.SetNet(net) if net else None
        o = z.Outline(); o.NewOutline()
        for x, y in pts or ((x0, y0), (x1, y0), (x1, y1), (x0, y1)):
            o.Append(MM(OX + x), MM(OY + y))
        z.SetAssignedPriority(prio); z.SetMinThickness(MM(0.1)); z.SetLocalClearance(MM(0.1))
        z.SetPadConnection(pcbnew.ZONE_CONNECTION_FULL)   # Espressif: full contact for chip/RF grounds (0201 spokes: route.py)
        board.Add(z); return z
    def rule_area(name, layers, x0, y0, x1, y1, tracks=False, vias=True, fills=True, pts=None):
        z = rect_zone(pcbnew.F_Cu, None, x0, y0, x1, y1, pts=pts)
        z.SetIsRuleArea(True); ls = pcbnew.LSET()
        for l in layers: ls.AddLayer(l)
        z.SetLayerSet(ls)
        z.SetDoNotAllowTracks(tracks); z.SetDoNotAllowVias(vias); z.SetDoNotAllowZoneFills(fills)
        z.SetDoNotAllowPads(False); z.SetDoNotAllowFootprints(False); z.SetZoneName(name)
        return z
    INNER = [pcbnew.In1_Cu, pcbnew.In2_Cu, pcbnew.B_Cu]
    ALL = [pcbnew.F_Cu] + INNER
    board.SetLayerType(pcbnew.In1_Cu, pcbnew.LT_POWER)
    rect_zone(pcbnew.In1_Cu, nets["GND"], X0, Y0, ANT_KEEP_X, Y1)
    rule_area("antenna keep-out", ALL, ANT_KEEP_X, Y0 - 0.5, X1 + 0.5, Y1 + 0.5, tracks=True)
    # touch: no copper of other nets within TOUCH_KEEP of an electrode on any layer; on F.Cu its own stub leaves through a
    # 0.4 mm channel on the electrode's inner long side (east end), every other track is kept out
    for n, (ref, (a, b, c, d)) in enumerate(zip(("TCH1", "TCH2", "TCH3", "TCH4"), touch_e)):
        k = TOUCH_KEEP
        rule_area(f"touch {n + 1} keep-out", INNER, a - k, b - k, c + k, d + k, tracks=True)
        rule_area(f"touch {n + 1} no-pour", [pcbnew.F_Cu], a - k, b - k, c + k, d + k, tracks=False)
        inner_y, out_y = (d, d + k + 0.55) if b < 0 else (b, b - k - 0.55)
        sx = {"TCH1": a + 0.5, "TCH2": c - 0.8, "TCH3": a + 1.6, "TCH4": a + 1.6}[ref]   # where each trace can arrive
        o0, o1 = (b - k, b) if b < 0 else (d, d + k)              # outer side (toward the board edge)
        i0, i1 = (d, d + k) if b < 0 else (b - k, b)              # inner side, split by the stub's 0.4 mm channel
        for nm, r_ in (("W", (a - k, b - k, a, d + k)), ("E", (c, b - k, c + k, d + k)), ("out", (a, o0, c, o1)),
                       ("in W", (a, i0, sx - 0.2, i1)), ("in E", (sx + 0.2, i0, c, i1))):
            rule_area(f"touch {n + 1} ring {nm}", [pcbnew.F_Cu], *r_, tracks=True, vias=True, fills=True)
        net_ = fps[ref].Pads()[0].GetNetname(); cxy = P(fps[ref].GetPosition())
        track(net_, [cxy, (sx, cxy[1]), (sx, out_y)], 0.12)
        via(net_, sx, out_y)
    # nothing under the crystals or the accelerometer (Espressif HDG 1.4.3, ST TN0018)
    for ref, layers in (("Y1", INNER), ("Y2", INNER), ("U6", INNER)):
        a, b, c, d = box(fps[ref])
        rule_area(f"{ref} keep-out", layers, a + 0.1, b + 0.1, c - 0.1, d - 0.1, tracks=True, vias=True, fills=False)
    a, b, c, d = box(fps["U6"])
    rule_area("U6 top keep-out", [pcbnew.F_Cu], a + 0.48, b + 0.48, c - 0.48, d - 0.48, tracks=True, vias=True, fills=True)
    # panel tabs: pours pulled back from the edge, tracks and vias further
    for x0_, y0_, x1_, y1_ in tab_rects(TAB_POUR_BACK, TAB_POUR_BACK):
        rule_area("tab pull-back", ALL, x0_, y0_, x1_, y1_, tracks=True, vias=True, fills=True)
    for (ax, ay), (bx, by) in TABS:   # everything within TAB_COPPER_BACK of a tab (a stadium), 0.8 at the -X end (pogo pads)
        r_ = 0.8 if ax == bx else TAB_COPPER_BACK
        ux, uy = (bx - ax) / math.hypot(bx - ax, by - ay), (by - ay) / math.hypot(bx - ax, by - ay)
        pts = [(bx + r_ * (ux * math.cos(t) - uy * math.sin(t)), by + r_ * (uy * math.cos(t) + ux * math.sin(t)))
               for t in [math.radians(-90 + 15 * k) for k in range(13)]]
        pts += [(ax - r_ * (ux * math.cos(t) - uy * math.sin(t)), ay - r_ * (uy * math.cos(t) + ux * math.sin(t)))
                for t in [math.radians(-90 + 15 * k) for k in range(13)]]
        rule_area("tab keep-out", ALL, 0, 0, 0, 0, tracks=True, vias=True, fills=False, pts=pts)

    # GND escape vias: every top-side SMD GND pad gets its own via to the In1 plane before routing
    gnd_net = nets["GND"]
    obst = [p for f in fps.values() for p in f.Pads() if p.GetNetCode() != gnd_net.GetNetCode()]
    obst_gap = lambda o: 0.32 if o.GetNetname() in TOUCH_NETS else 0.12
    holes = [p for f in fps.values() for p in f.Pads() if p.GetAttribute() == pcbnew.PAD_ATTRIB_NPTH]
    gnd_smd = [p for f in fps.values() if not f.IsFlipped() for p in f.Pads() if p.GetNetCode() == gnd_net.GetNetCode()]
    locked = [t for t in board.GetTracks()]
    gap_to = lambda t: 0.32 if t.GetNetname() in TOUCH_NETS else 0.12     # touch stubs keep the Touch clearance
    new_vias = [t for t in locked if t.GetClass() == "PCB_VIA"]
    def ok_via(v):
        if any(z.GetIsRuleArea() and z.GetDoNotAllowVias() and z.Outline().Collide(v.GetPosition(), MM(VIA_D / 2 + 0.05)) for z in board.Zones()):
            return False
        for lay in (pcbnew.F_Cu, pcbnew.B_Cu):
            vs = v.GetEffectiveShape(lay)
            if any(o.IsOnLayer(lay) and vs.Collide(o.GetEffectiveShape(lay), MM(obst_gap(o))) for o in obst):
                return False
        hole = pcbnew.SHAPE_CIRCLE(v.GetPosition(), MM(VIA_H / 2))
        if any(q.IsOnLayer(pcbnew.F_Cu) and q.GetEffectiveShape(pcbnew.F_Cu).Collide(hole, MM(0.15)) for q in gnd_smd):
            return False   # no via holes in or within 0.15 mm of pads (solder wicking)
        if any(t.GetNetCode() != gnd_net.GetNetCode() and v.GetEffectiveShape(t.GetLayer()).Collide(t.GetEffectiveShape(t.GetLayer()), MM(gap_to(t)))
               for t in locked if t.GetClass() == "PCB_TRACK"):
            return False                                   # hand-routed tracks on any layer
        if any(v.GetEffectiveShape(pcbnew.F_Cu).Collide(h.GetEffectiveShape(pcbnew.F_Cu), MM(0.3)) for h in holes):
            return False
        return all(math.hypot(pcbnew.ToMM(v.GetPosition().x - w.GetPosition().x), pcbnew.ToMM(v.GetPosition().y - w.GetPosition().y))
                   >= (0.77 if w.GetNetname() in TOUCH_NETS else 0.46 if w.GetNetCode() == gnd_net.GetNetCode() else 0.56) for w in new_vias)
    n_esc = 0
    no_track_f = [z.Outline() for z in board.Zones() if z.GetIsRuleArea() and z.GetDoNotAllowTracks() and z.IsOnLayer(pcbnew.F_Cu)]
    def stub_ok(t):
        a_, b_ = t.GetStart(), t.GetEnd()
        if any(o.Collide(pcbnew.VECTOR2I(int(a_.x + (b_.x - a_.x) * k / 4), int(a_.y + (b_.y - a_.y) * k / 4)), t.GetWidth() // 2)
               for o in no_track_f for k in range(5)):
            return False                                    # keep-outs (panel tabs, touch rings)
        return not any(o.IsOnLayer(pcbnew.F_Cu) and t.GetEffectiveShape(pcbnew.F_Cu).Collide(o.GetEffectiveShape(pcbnew.F_Cu), MM(obst_gap(o))) for o in obst) \
            and not any(t2.GetNetCode() != gnd_net.GetNetCode() and t2.GetLayer() == pcbnew.F_Cu and
                        t.GetEffectiveShape(pcbnew.F_Cu).Collide(t2.GetEffectiveShape(pcbnew.F_Cu), MM(gap_to(t2))) for t2 in locked if t2.GetClass() == "PCB_TRACK")
    def try_escape(p, px, py, wcsp, dists, angles):
        for d in dists:
            for ang in angles:
                x, y = px + d * math.cos(math.radians(ang)), py + d * math.sin(math.radians(ang))
                if not (X0 + 0.5 < x < min(X1, ANT_KEEP_X, ant_cu_x - 0.2) - 0.4 and Y0 + 0.43 < y < Y1 - 0.43):
                    continue                     # 0.2 mm copper-to-edge
                r_ = VIA_D / 2 + 0.01            # a GND via may sit right outside an electrode's 0.5 mm keep-out
                if any(a - r_ < x < c + r_ and b - r_ < y < d_ + r_ for a, b, c, d_ in touch_keep):
                    continue
                v = pcbnew.PCB_VIA(board); v.SetPosition(V(x, y)); v.SetWidth(MM(VIA_D)); v.SetDrill(MM(VIA_H)); v.SetNet(gnd_net)
                t = pcbnew.PCB_TRACK(board); t.SetStart(V(px, py)); t.SetEnd(V(x, y)); t.SetWidth(MM(0.12 if wcsp else 0.2))
                t.SetLayer(pcbnew.F_Cu); t.SetNet(gnd_net)
                if ok_via(v) and stub_ok(t):
                    v.SetLocked(True); t.SetLocked(True); board.Add(v); board.Add(t); new_vias.append(v); locked.append(t)
                    return True
        return False
    def try_join(p, px, py, wcsp):
        """Short straight stub to an existing GND via (no new via)."""
        for w in sorted(new_vias, key=lambda w: (pcbnew.ToMM(w.GetPosition().x) - OX - px) ** 2 + (pcbnew.ToMM(w.GetPosition().y) - OY - py) ** 2):
            if w.GetNetCode() != gnd_net.GetNetCode():
                continue
            wx, wy = P(w.GetPosition())
            if math.hypot(wx - px, wy - py) > 1.3:
                break
            t = pcbnew.PCB_TRACK(board); t.SetStart(V(px, py)); t.SetEnd(w.GetPosition()); t.SetWidth(MM(0.12 if wcsp else 0.15))
            t.SetLayer(pcbnew.F_Cu); t.SetNet(gnd_net)
            if stub_ok(t):
                t.SetLocked(True); board.Add(t); locked.append(t); return True
        return False
    todo = []
    for ref, f in fps.items():
        if f.IsFlipped() or ref in ("AE1", "U1", "TCH1", "TCH2", "TCH3", "TCH4"):
            continue
        wcsp = ref in ("U2", "U3")
        for p in f.Pads():
            if p.GetNetCode() != gnd_net.GetNetCode() or p.GetAttribute() != pcbnew.PAD_ATTRIB_SMD:
                continue
            px, py = P(p.GetPosition())
            half = max(pcbnew.ToMM(p.GetSize(pcbnew.F_Cu).x), pcbnew.ToMM(p.GetSize(pcbnew.F_Cu).y)) / 2
            if wcsp:   # TI SNVA009: <= 2/3 of the 0.23 land into the ball, no solid pour (it would make the ball SMD-defined)
                p.SetLocalZoneConnection(pcbnew.ZONE_CONNECTION_NONE)
            if try_escape(p, px, py, wcsp, (0.45, 0.6, 0.75) if wcsp else (half + 0.38, half + 0.55, half + 0.8), range(0, 360, 45)):
                n_esc += 1
            else:
                todo.append((ref, p, px, py, wcsp, half))
    tied = []
    for ref, p, px, py, wcsp, half in todo:   # second chance: finer and wider, then a stub to a GND via nearby
        if try_escape(p, px, py, wcsp, [half + 0.25 + 0.12 * i for i in range(9)], [22.5 * i for i in range(16)]) or try_join(p, px, py, wcsp):
            n_esc += 1
        else:
            tied.append(f"{ref}.{p.GetNumber()}")
    print(f"GND escape vias: {n_esc}; without their own (tied by a hand-routed track or the pour): {' '.join(tied)}")

    pcbnew.ZONE_FILLER(board).Fill(board.Zones())
    board.Save("horae.kicad_pcb")
    os.makedirs("out", exist_ok=True)
    export_dsn(board)
    print(f"placed {len(fps)} footprints; feed at {fx:.2f},{fy:.2f}; J1 rot {j1.GetOrientationDegrees():.0f}")
    if bad:
        raise SystemExit(1)


def export_dsn(board, path="out/horae.dsn", fat_touch=False):
    """Specctra DSN for Freerouting with the RF/Power/Touch/F.Cu-only net classes (KiCad exports only the default class)."""
    pcbnew.ExportSpecctraDSN(board, path)
    dsn = open(path).read()
    special = set(["RF_CHIP", "RF_ANT"] + POWER_NETS + SUPPLY_NETS + TOUCH_NETS + F_ONLY_NETS)
    head, rest = dsn.split("(class kicad_default", 1)
    names, tail = rest.split("(circuit", 1)
    keep_names = [n for n in names.split() if n.strip('"') not in special]
    dsn = head + "(class kicad_default " + " ".join(keep_names) + "\n      (circuit" + tail
    via_name = [l for l in dsn.split("\n") if "(use_via" in l][0].split('"')[1] if '(use_via "' in dsn else None
    def cls(name, nets_, width, clear, layers=None):
        q = lambda n: f'"{n}"' if any(ch in n for ch in "+-") else n
        lay = f'\n        (use_layer {" ".join(layers)})' if layers else ""
        return (f"    (class {name} {' '.join(q(n) for n in nets_)}\n      (circuit\n        (use_via \"{via_name}\"){lay}\n      )\n"
                f"      (rule\n        (width {int(width * 1000)})\n        (clearance {int(clear * 1000)})\n      )\n    )\n")
    extra = (cls("RF", ["RF_CHIP", "RF_ANT"], RF_W, RF_GAP) + cls("Power", POWER_NETS, POWER_W, 0.11) + cls("Supply", SUPPLY_NETS, 0.2, 0.11) +
             cls("Touch", TOUCH_NETS, 0.1, 0.3, ["B.Cu"]) + cls("FOnly", F_ONLY_NETS, 0.12, 0.11, ["F.Cu"]))   # touch: the free layer
    dsn = dsn.replace("    (class kicad_default", extra + "    (class kicad_default", 1)
    # fixed wires as 2-point segments: Freerouting only connects pads that sit on a wire's end points
    def split(m):
        lay, w, pts, rest = m.group(1), m.group(2), m.group(3).split(), m.group(4)
        xy = list(zip(pts[0::2], pts[1::2]))
        return "\n    ".join(f"(wire (path {lay} {w}  {a[0]} {a[1]}  {b[0]} {b[1]}){rest}" for a, b in zip(xy, xy[1:]))
    dsn = re.sub(r"\(wire \(path (\S+) (\S+)\s+([-\d.\s]+?)\)(\(net [^)]*\)\(type fix\)\))", split, dsn)
    # Freerouting keeps only the router-side class clearance (0.11) to fixed copper: fatten the fixed touch wires and vias
    # so later passes stay 0.3 mm away from them (DSN only; the board keeps the real 0.1 mm / 0.45 mm copper)
    fat = 2 * (0.3 - 0.11) if fat_touch else 0.0
    tn = "|".join(TOUCH_NETS)
    dsn = re.sub(r"\(wire \(path (\S+) (\d+)(\s[^)]*\)\(net (?:%s)\)\(type fix\)\))" % tn,
                 lambda m: f"(wire (path {m.group(1)} {int(int(m.group(2)) + fat * 1000)}{m.group(3)}", dsn)
    dsn = re.sub(r'\(via "(Via[^"]*)"(\s+[-\d.]+\s+[-\d.]+ \(net (?:%s)\)\(type fix\)\))' % tn, r'(via "TouchVia"\2', dsn)
    d_ = int((VIA_D + fat) * 1000)
    pad = "".join(f"      (shape (circle {l} {d_}))\n" for l in ("F.Cu", "In1.Cu", "In2.Cu", "B.Cu"))
    lib_end = dsn.index("\n  )\n  (network")                  # the library's closing paren
    dsn = dsn[:lib_end] + f'\n    (padstack "TouchVia"\n{pad}      (attach off)\n    )' + dsn[lib_end:]
    open(path, "w").write(dsn)


if __name__ == "__main__":
    main()
