"""Generate horae.kicad_pcb from design.py + spec.py: outline, stack, placement, nets, zones, keep-outs.

Run inside the KiCad container: ./kicad python3 gen_pcb.py
Critical parts are pinned; the rest go to the free spot nearest their target (greedy legalizer).
"""
import math, os, sys
import pcbnew
sys.path.insert(0, "..")
import spec as S
from design import PARTS
from gen_sch import uid

MM = pcbnew.FromMM
OX, OY = 100.0, 100.0                 # board centre on the KiCad canvas
X0, X1 = -S.PCB_L / 2, S.PCB_L / 2
Y0, Y1 = -S.PCB_W / 2, S.PCB_W / 2
EDGE = 0.15                            # courtyard-to-edge margin
ANT_KEEP_X = S.ANT_X0                  # copper keep-out from here to the +X edge (antenna pads excepted)
FPC_LANE = (X0 - 1, -S.FPC_W / 2 - 0.3, S.FFC_X - 1.5, S.FPC_W / 2 + 0.3)    # FPC runs here just above the board
LEDGES = [(X0 - 1, Y0 - 1, S.DISP_X0 + S.LEDGE, -S.LEDGE_Y), (X0 - 1, S.LEDGE_Y, S.DISP_X0 + S.LEDGE, Y1 + 1)]  # case ledges rest here

# Targets (KiCad coords, mm from board centre, y down). Pinned parts are placed exactly.
PIN = {
    "U1": (4.8, 0.0, None),            # rotation chosen to face pin 1 at the antenna feed; leaves room for the RF chain
    "J1": (S.FFC_X, 0.0, None),
    # capacitive touch electrodes along the long edges (TCH1 UP, TCH2 DOWN at +X; TCH3 MENU, TCH4 BACK at -X)
    "TCH1": (S.TOUCH_X[1], Y0 + S.TOUCH_W / 2 + 0.3, 0), "TCH2": (S.TOUCH_X[1], Y1 - S.TOUCH_W / 2 - 0.3, 0),
    "TCH3": (S.TOUCH_X[0], Y0 + S.TOUCH_W / 2 + 0.3, 0), "TCH4": (S.TOUCH_X[0], Y1 - S.TOUCH_W / 2 - 0.3, 0),
}
BOTTOM = {  # bottom-side pads (no parts): dock pogo pads, battery wire pads, motor springs, test pads
    **{tp: next(p[:2] for p in S.POGO_PADS if p[2] == net) for tp, net in (("TP1", "VBUS"), ("TP2", "USB_DM"), ("TP3", "USB_DP"), ("TP4", "GND"))},
    "TP5": (S.BATPAD_X, S.BATPAD_Y), "TP6": (S.BATPAD_X, -S.BATPAD_Y),   # VBAT next to the charger, GND next to the ESD
    "TP7": (S.MOTOR_X - S.MOTOR_PAD_DX, 0.0), "TP8": (S.MOTOR_X + S.MOTOR_PAD_DX, 0.0),   # under the motor: spring fingers or wires
    "TP9": (-4.4, -3.5), "TP10": (-2.2, -3.5), "TP11": (0.0, -3.5), "TP12": (2.2, -3.5), "TP13": (4.4, -3.5),   # over the battery pouch, clear of the motor can
}
TARGET = {  # loose targets for the legalizer, grouped near the IC they serve (U1 pins 1-14 face +X, 15-28 face -Y, 43-56 face +Y)
    # ESP32 support: 40 MHz crystal caps south-east, VDD3P3 LC + EN RC east, VDD_SPI west, 32 kHz crystal + accelerometer north-east
    "C1": (9.9, 5.2), "C2": (9.9, 6.3), "L1": (6.4, 4.4),
    "C3": (9.4, 1.5), "L2": (9.4, 0.7), "C5": (9.4, -1.9), "C6": (7.8, 4.4), "C7": (2.4, -4.4),
    "C8": (0.2, -2.8), "C9": (0.2, -2.0), "R1": (9.4, -0.2), "C10": (9.4, -1.0),
    "U6": (7.2, -5.6), "C20": (6.0, -4.5),
    "Y2": (9.8, -5.0), "C32": (9.0, -6.9), "C33": (10.4, -6.9),
    "R3": (2.0, 4.6), "R4": (3.0, 4.6), "C18": (4.0, 4.6),   # battery divider (DC; the long ADC trace is fine with C18 at the divider)
    # dock ESD + charger in the -Y corner (VBUS / D- pogo pads below), motor switch beside J1's -Y end (buck: hand-placed, +Y corner)
    "U4": (-12.2, -6.7), "U2": (-14.0, -6.2), "R2": (-14.2, -7.4), "R5": (-13.2, -7.4), "C13": (-10.9, -6.0),
    "Q2": (-9.2, -6.4), "R13": (-8.4, -7.4), "D4": (-9.2, -7.5),
    # display: rail caps right of J1, booster core next to J1's GDR/RESE end (-Y), pump diodes between the booster and U1
    "C24": (-5.9, -3.0), "C25": (-5.9, -2.0), "C26": (-5.9, -1.0), "C27": (-5.9, 0.0), "C28": (-5.9, 1.0), "C29": (-5.9, 2.0), "C30": (-5.9, 3.0),
    "Q1": (-4.2, -3.6), "R11": (-5.4, -4.7), "R12": (-3.0, -4.6), "L4": (-3.4, -0.6),
    "D3": (-1.3, -1.6), "C22": (-1.3, 0.0), "D1": (-1.3, 1.5), "D2": (-1.3, 2.6),
    "C31": (0.3, 6.6),
}


def fp_path(lib):
    return "lib/horae.pretty" if lib == "horae" else f"/usr/share/kicad/footprints/{lib}.pretty"


def V(x, y):
    return pcbnew.VECTOR2I(MM(OX + x), MM(OY + y))


def box(fp):
    lay = pcbnew.B_CrtYd if fp.IsFlipped() else pcbnew.F_CrtYd
    fp.BuildCourtyardCaches()          # cached outline does not follow SetPosition otherwise
    cy = fp.GetCourtyard(lay)
    b = cy.BBox() if cy.OutlineCount() else fp.GetBoundingBox(False)
    r = [pcbnew.ToMM(b.GetLeft()) - OX, pcbnew.ToMM(b.GetTop()) - OY, pcbnew.ToMM(b.GetRight()) - OX, pcbnew.ToMM(b.GetBottom()) - OY]
    for pad in fp.Pads():              # some imported courtyards do not cover their pads; pads + 0.15 mm always count
        pb = pad.GetBoundingBox()
        r = [min(r[0], pcbnew.ToMM(pb.GetLeft()) - OX - 0.15), min(r[1], pcbnew.ToMM(pb.GetTop()) - OY - 0.15),
             max(r[2], pcbnew.ToMM(pb.GetRight()) - OX + 0.15), max(r[3], pcbnew.ToMM(pb.GetBottom()) - OY + 0.15)]
    return tuple(r)


def overlap(a, b, m=0.05):
    return a[0] < b[2] + m and b[0] < a[2] + m and a[1] < b[3] + m and b[1] < a[3] + m


def main():
    board = pcbnew.NewBoard("horae.kicad_pcb")
    board.SetCopperLayerCount(4)
    ds = board.GetDesignSettings()
    ds.SetBoardThickness(MM(S.PCB_T))
    ds.m_TrackMinWidth, ds.m_MinClearance = MM(0.09), MM(0.09)   # JLC multilayer 0.09/0.09
    ds.m_ViasMinSize, ds.m_MinThroughDrill = MM(0.4), MM(0.2)
    nc = ds.m_NetSettings.GetDefaultNetclass()
    nc.SetTrackWidth(MM(0.1)); nc.SetClearance(MM(0.11))  # 0.01 margin for widening necked wires; 0.4/0.2 vias: 0.1 annular + 0.1 = JLC 0.2 hole-to-copper; no small-hole fee
    nc.SetViaDiameter(MM(0.4)); nc.SetViaDrill(MM(0.2))

    nets = {}
    for p in PARTS:
        for n in p[5].values():
            if n not in nets:
                nets[n] = pcbnew.NETINFO_ITEM(board, n)
                board.Add(nets[n])

    # outline: rounded rectangle
    r = S.PCB_CORNER_R
    def seg(a, b):
        s = pcbnew.PCB_SHAPE(board); s.SetShape(pcbnew.SHAPE_T_SEGMENT); s.SetLayer(pcbnew.Edge_Cuts)
        s.SetStart(V(*a)); s.SetEnd(V(*b)); s.SetWidth(MM(0.1)); board.Add(s)
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
        for it in fp.GraphicalItems():                                   # no silk at all (unreadable at this size; JLC needs none):
            if it.GetLayer() in (pcbnew.F_SilkS, pcbnew.B_SilkS):        # keep the marks on the fab layer for reference
                it.SetLayer(pcbnew.F_Fab if it.GetLayer() == pcbnew.F_SilkS else pcbnew.B_Fab)
        board.Add(fp)
        fps[ref] = fp

    placed = []
    def put(fp, x, y, rot=0, flip=False):
        fp.SetPosition(V(x, y)); fp.SetOrientationDegrees(rot)
        if flip and not fp.IsFlipped():
            fp.Flip(fp.GetPosition(), pcbnew.FLIP_DIRECTION_TOP_BOTTOM)

    # antenna: long axis across the board at the +X end, feed/ground pads facing the board (-X)
    ae = fps["AE1"]
    put(ae, X1 - 5.20, -9.845, -90)   # pinned 0.3 mm from the +X edge
    cu = [gr.GetBoundingBox() for gr in ae.GraphicalItems() if gr.GetLayer() == pcbnew.F_Cu] + [p.GetBoundingBox() for p in ae.Pads()]
    cy0 = (min(pcbnew.ToMM(b.GetTop()) for b in cu) + max(pcbnew.ToMM(b.GetBottom()) for b in cu)) / 2 - OY
    put(ae, X1 - 5.20, -9.845 - cy0, -90)   # centre the (trimmed, asymmetric) copper across the board
    cu_x1 = max([pcbnew.ToMM(gr.GetBoundingBox().GetRight()) for gr in ae.GraphicalItems() if gr.GetLayer() == pcbnew.F_Cu] +
                [pcbnew.ToMM(p.GetBoundingBox().GetRight()) for p in ae.Pads()]) - OX
    put(ae, X1 - 5.20 + (X1 - 0.35 - cu_x1), -9.845 - cy0, -90)   # meander tip 0.35 mm from the +X edge
    ant_cu_x = min([pcbnew.ToMM(gr.GetBoundingBox().GetLeft()) for gr in ae.GraphicalItems() if gr.GetLayer() == pcbnew.F_Cu] +
                   [pcbnew.ToMM(p.GetBoundingBox().GetLeft()) for p in ae.Pads()]) - OX
    best = (None, -90)
    feed = [p for p in ae.Pads() if p.GetNumber() == "1"][0].GetPosition()
    feed = (pcbnew.ToMM(feed.x) - OX, pcbnew.ToMM(feed.y) - OY)
    global ANT_KEEP_X
    ANT_KEEP_X = feed[0] + 0.45      # ground and tracks may reach the feed/short pads; the meander stays clear

    # ESP32: pick the rotation that puts pin 1 (LNA_IN) closest to the antenna feed
    u1 = fps["U1"]
    def pad_xy(fp, num):
        p = [q for q in fp.Pads() if q.GetNumber() == num][0].GetPosition()
        return pcbnew.ToMM(p.x) - OX, pcbnew.ToMM(p.y) - OY
    rots = []
    for rot in (0, 90, 180, 270):
        put(u1, *PIN["U1"][:2], rot)
        px, py = pad_xy(u1, "1")
        rots.append((math.hypot(px - feed[0], py - feed[1]), rot))
    put(u1, *PIN["U1"][:2], min(rots)[1])

    # FFC: pad row facing the FPC bend (-X)
    j1 = fps["J1"]
    for rot in (90, 270):
        put(j1, *PIN["J1"][:2], rot)
        if pad_xy(j1, "1")[0] < PIN["J1"][0]:
            break
    for ref in ("TCH1", "TCH2", "TCH3", "TCH4"):
        put(fps[ref], *PIN[ref])
    for ref, (x, y) in BOTTOM.items():
        put(fps[ref], x, y, 0, flip=True)
    for txt, ref in (("+", "TP5"), ("-", "TP6")):     # battery polarity next to the wire pads (the only silk on the board)
        bx_, by_ = BOTTOM[ref]
        t = pcbnew.PCB_TEXT(board); t.SetText(txt); t.SetLayer(pcbnew.B_SilkS); t.SetMirrored(True)
        t.SetTextSize(pcbnew.VECTOR2I(MM(1.2), MM(1.2))); t.SetTextThickness(MM(0.2))
        t.SetPosition(V(bx_ + 1.9, by_)); board.Add(t)
    # RF chain in a straight line from LNA_IN: C11 shunt, L3 series, C12 shunt, then the feed (pinned by pad)
    def pin_pad(ref, num, x, y, direction):
        fp = fps[ref]
        for rot in (0, 90, 180, 270):
            put(fp, 0, 0, rot)
            a = pad_xy(fp, num); b = pad_xy(fp, "2" if num == "1" else "1")
            v = (round(b[0] - a[0], 2), round(b[1] - a[1], 2))
            if (direction == "+x" and v[0] > 0.2) or (direction == "-x" and v[0] < -0.2) or (direction == "+y" and v[1] > 0.2) or (direction == "-y" and v[1] < -0.2):
                put(fp, x - a[0], y - a[1], rot); return
        raise SystemExit(f"cannot orient {ref}")
    rx, ry = pad_xy(u1, "1")                      # LNA_IN pad centre
    fx, fy = feed
    W = 0.2                                       # 50-ohm GCPW on F.Cu over the In1 plane: 0.20 mm, 0.15 mm gap
    pin_pad("C11", "1", rx + 1.05, ry, "+y")          # shunt caps point south: free board there for their ground vias
    pin_pad("L3", "1", rx + 1.55, ry, "+x")
    l3a, l3b = pad_xy(fps["L3"], "1"), pad_xy(fps["L3"], "2")
    pin_pad("C12", "1", l3b[0] + 0.42, ry, "-y")   # (not fitted) points north, clear of the feed pad
    c11a, c12a = pad_xy(fps["C11"], "1"), pad_xy(fps["C12"], "1")
    put(fps["Y1"], 8.1, 5.9, 90)                 # crystal below the ESP32, between the +X touch pad and the RF feed
    # buck cell, hand-placed in the +Y strip south of J1, TI-style: the VOS/SW/VSET column faces west (inductor straight out of SW,
    # VSET resistor up, VOS runs under the inductor to its output end), the GND/VIN/EN column faces east into the input cap
    bx, by = -10.0, 6.6
    put(fps["U3"], bx, by, 90)
    pin_pad("C15", "1", bx + 1.06, by - 0.28, "+y")   # VBAT pad beside VIN/EN, GND pad beside A1
    pin_pad("L5", "1", bx - 1.15, by, "-x")           # SW pad straight west of B2, +3V3 end further west
    pin_pad("C17", "1", bx - 3.6, by - 0.48, "+y")    # output cap past L5's +3V3 end
    pin_pad("R6", "1", bx - 0.75, by - 1.1, "-x")     # VSET resistor north-west of C2
    put(fps["MIC1"], S.MIC_X, S.MIC_Y, 180)      # 180: KiCad 3D-model Y is flipped vs the footprint, port must face the edge; top-port mic at the long edge; port in the strip the glass does not cover (case: duct + vent)
    def track(net, pts, w=W):
        for a, b in zip(pts, pts[1:]):
            t = pcbnew.PCB_TRACK(board); t.SetStart(V(*a)); t.SetEnd(V(*b)); t.SetWidth(MM(w))
            t.SetLayer(pcbnew.F_Cu); t.SetNet(nets[net]); t.SetLocked(True); board.Add(t)
    ae2 = pad_xy(ae, "2")                         # IFA short to ground: make sure the pour reaches it
    track("GND", [ae2, (ae2[0] - 0.75, ae2[1])], w=0.3)
    sv = pcbnew.PCB_VIA(board); sv.SetPosition(V(ae2[0] - 0.75, ae2[1])); sv.SetWidth(MM(0.4)); sv.SetDrill(MM(0.2))
    sv.SetNet(nets["GND"]); sv.SetLocked(True); board.Add(sv)          # IFA short goes straight to the plane
    track("RF_CHIP", [(rx, ry), c11a, l3a])           # segments break at every pad so the router sees them connected
    track("RF_ANT", [l3b, c12a, (fx, ry), (fx, fy)])
    # RF ground vias + fence are added after routing (route.py), with collision checks
    touch_keep = [(x - S.TOUCH_L / 2 - 0.4, y - S.TOUCH_W / 2 - 0.4, x + S.TOUCH_L / 2 + 0.4, y + S.TOUCH_W / 2 + 0.4)
                  for x, y, _ in (PIN[t] for t in ("TCH1", "TCH2", "TCH3", "TCH4"))]   # parts stay 0.4 mm off the electrodes
    placed = [box(fps[r]) for r in ("U1", "J1", "C11", "L3", "C12", "Y1", "MIC1", "U3", "C15", "L5", "C17", "R6")] + touch_keep
    placed.append((rx, ry - 0.35, fx + 0.35, ry + 0.35)); placed.append((fx - 0.35, ry, fx + 0.35, fy))   # keep parts off the feed
    placed.append((ae2[0] - 1.1, ae2[1] - 0.4, ae2[0], ae2[1] + 0.4))   # and off the antenna short stub + via
    ae_box = box(ae)

    keep = [(min(S.ANT_X0 - 0.2, ant_cu_x - 0.3), Y0 - 1, X1 + 1, Y1 + 1), FPC_LANE] + LEDGES   # parts stop at the GND pour edge (feed/short pads)
    small = lambda b: (b[2] - b[0]) * (b[3] - b[1]) < 4
    def legal(b):  # courtyards may touch, not overlap
        return (b[0] >= X0 + EDGE and b[2] <= X1 - EDGE and b[1] >= Y0 + EDGE and b[3] <= Y1 - EDGE
                and not any(overlap(b, k, 0) for k in keep)
                and not any(overlap(b, p, 0.0) for p in placed))
    first = ["C24", "C25", "C26", "C27", "C28", "C29", "C30", "C3", "L2", "C5", "C6", "C7", "C8", "C9"]   # pin-critical caps first
    order = sorted(TARGET, key=lambda r: (-(lambda b: (b[2] - b[0]) * (b[3] - b[1]))(box(fps[r])) if box(fps[r])[2] - box(fps[r])[0] > 2.2 else 0,
                                          first.index(r) if r in first else len(first)))
    for ref in order:
        fp, (tx, ty) = fps[ref], TARGET[ref]
        done = False
        for rad in [i * 0.25 for i in range(0, 60)]:
            steps = max(1, int(2 * math.pi * rad / 0.25))
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
            put(fp, tx, ty, 0); b = box(fp)
            print(f"COULD NOT PLACE {ref} (left at target, overlapping)")

    # GND escape vias: every top-side SMD GND pad gets its own via to the In1 plane before routing
    gnd_net = nets["GND"]
    obst = [p for f in fps.values() for p in f.Pads() if p.GetNetCode() != gnd_net.GetNetCode()]
    holes = [p for f in fps.values() for p in f.Pads() if p.GetAttribute() == pcbnew.PAD_ATTRIB_NPTH]
    new_vias = []
    def ok_via(v):
        for lay in (pcbnew.F_Cu, pcbnew.B_Cu):
            vs = v.GetEffectiveShape(lay)
            if any(o.IsOnLayer(lay) and vs.Collide(o.GetEffectiveShape(lay), MM(0.12)) for o in obst):
                return False
        if any(v.GetEffectiveShape(pcbnew.F_Cu).Collide(h.GetEffectiveShape(pcbnew.F_Cu), MM(0.3)) for h in holes):
            return False
        return all(abs(pcbnew.ToMM(v.GetPosition().x - w.GetPosition().x)) > 0.6 or abs(pcbnew.ToMM(v.GetPosition().y - w.GetPosition().y)) > 0.6 for w in new_vias)
    n_esc = 0
    for ref, f in fps.items():
        if f.IsFlipped() or ref in ("AE1", "U1"):        # U1's exposed pad already has thermal vias
            continue
        for p in f.Pads():
            if p.GetNetCode() != gnd_net.GetNetCode() or p.GetAttribute() != pcbnew.PAD_ATTRIB_SMD:
                continue
            px, py = pad_xy(f, p.GetNumber()) if False else (pcbnew.ToMM(p.GetPosition().x) - OX, pcbnew.ToMM(p.GetPosition().y) - OY)
            half = max(pcbnew.ToMM(p.GetSize().x), pcbnew.ToMM(p.GetSize().y)) / 2
            done_ = False
            for d in (half + 0.35, half + 0.55, half + 0.8):
                for ang in range(0, 360, 45):
                    x, y = px + d * math.cos(math.radians(ang)), py + d * math.sin(math.radians(ang))
                    if not (X0 + 0.5 < x < min(X1, ANT_KEEP_X, ant_cu_x - 0.2) - 0.4 and Y0 + 0.5 < y < Y1 - 0.5):
                        continue
                    if any(a - 0.3 < x < c + 0.3 and b - 0.3 < y < d + 0.3 for a, b, c, d in touch_keep):
                        continue   # no vias near the touch electrodes
                    v = pcbnew.PCB_VIA(board); v.SetPosition(V(x, y)); v.SetWidth(MM(0.4)); v.SetDrill(MM(0.2)); v.SetNet(gnd_net)
                    t = pcbnew.PCB_TRACK(board); t.SetStart(V(px, py)); t.SetEnd(V(x, y)); t.SetWidth(MM(0.2))
                    t.SetLayer(pcbnew.F_Cu); t.SetNet(gnd_net)
                    if ok_via(v) and not any(o.IsOnLayer(pcbnew.F_Cu) and t.GetEffectiveShape(pcbnew.F_Cu).Collide(o.GetEffectiveShape(pcbnew.F_Cu), MM(0.12)) for o in obst):
                        v.SetLocked(True); t.SetLocked(True); board.Add(v); board.Add(t); new_vias.append(v); n_esc += 1; done_ = True
                        break
                if done_: break
            if not done_:
                print(f"no escape via for {ref}.{p.GetNumber()}")
    print(f"GND escape vias: {n_esc}")

    # zones: GND on all four layers, keep-out over the antenna
    def rect_zone(layer, net, x0, y0, x1, y1, prio=0):
        z = pcbnew.ZONE(board); z.SetLayer(layer); z.SetNet(net) if net else None
        o = z.Outline(); o.NewOutline()
        for x, y in ((x0, y0), (x1, y0), (x1, y1), (x0, y1)):
            o.Append(MM(OX + x), MM(OY + y))
        z.SetAssignedPriority(prio); z.SetMinThickness(MM(0.1)); z.SetLocalClearance(MM(0.1))
        z.SetPadConnection(pcbnew.ZONE_CONNECTION_FULL)   # solid: 0201 pads starve thermal spokes
        board.Add(z); return z
    # In1 is the solid GND plane the router drops vias into; the other pours are added after routing (route.py)
    board.SetLayerType(pcbnew.In1_Cu, pcbnew.LT_POWER)
    rect_zone(pcbnew.In1_Cu, nets["GND"], X0, Y0, ANT_KEEP_X, Y1)
    k = rect_zone(pcbnew.F_Cu, None, ANT_KEEP_X, Y0 - 0.5, X1 + 0.5, Y1 + 0.5)
    k.SetIsRuleArea(True); k.SetLayerSet(pcbnew.LSET.AllCuMask())
    k.SetDoNotAllowTracks(True); k.SetDoNotAllowVias(True); k.SetDoNotAllowZoneFills(True)
    k.SetDoNotAllowPads(False); k.SetDoNotAllowFootprints(False)
    k.SetZoneName("antenna keep-out")
    for n, (x0_, y0_, x1_, y1_) in enumerate(touch_keep):
        t_ = rect_zone(pcbnew.F_Cu, None, x0_ + 0.1, y0_ + 0.1, x1_ - 0.1, y1_ - 0.1)
        t_.SetIsRuleArea(True); t_.SetLayerSet(pcbnew.LSET.AllCuMask())
        t_.SetDoNotAllowZoneFills(True); t_.SetDoNotAllowTracks(False); t_.SetDoNotAllowVias(True)
        t_.SetDoNotAllowPads(False); t_.SetDoNotAllowFootprints(False); t_.SetZoneName(f"touch {n + 1} no-pour")

    pcbnew.ZONE_FILLER(board).Fill(board.Zones())
    board.Save("horae.kicad_pcb")
    os.makedirs("out", exist_ok=True)
    pcbnew.ExportSpecctraDSN(board, "out/horae.dsn")
    dsn = open("out/horae.dsn").read()
    for n in ("RF_CHIP", "RF_ANT"):
        dsn = dsn.replace(f" {n} ", " ", 1) if f" {n} " in dsn.split("(class kicad_default", 1)[1].split("(circuit", 1)[0] else dsn
    rf_class = '    (class RF RF_CHIP RF_ANT\n      (circuit\n        (use_via "Via[0-3]_400:200_um")\n      )\n      (rule\n        (width 200)\n        (clearance 150)\n      )\n    )\n'
    dsn = dsn.replace("    (class kicad_default", rf_class + "    (class kicad_default", 1)
    open("out/horae.dsn", "w").write(dsn)
    print(f"placed {len(fps)} footprints; antenna rot {best[1]}, feed at {feed[0]:.2f},{feed[1]:.2f}; U1 rot {min(rots)[1]}")


if __name__ == "__main__":
    main()
