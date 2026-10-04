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
    "U1": (6.0, 0.0, None),            # rotation chosen to face pin 1 at the antenna feed
    "J1": (S.FFC_X, 0.0, None),
    "SW1": (S.BUTTON_X[1], Y0 + 1.45 + S.BUTTON_INSET, 180), "SW2": (S.BUTTON_X[1], Y1 - 1.45 - S.BUTTON_INSET, 0),   # nub points outward (+y local)
    "SW3": (S.BUTTON_X[0], Y0 + 1.45 + S.BUTTON_INSET, 180), "SW4": (S.BUTTON_X[0], Y1 - 1.45 - S.BUTTON_INSET, 0),
}
POGO_Y = [(i - 1.5) * S.POGO_PITCH for i in range(4)]
BOTTOM = {  # bottom-side pads
    "TP1": (S.POGO_X, POGO_Y[0]), "TP2": (S.POGO_X, POGO_Y[1]), "TP3": (S.POGO_X, POGO_Y[2]), "TP4": (S.POGO_X, POGO_Y[3]),
    "TP5": (S.POGO_X + 0.2, -S.BATPAD_Y), "TP6": (S.POGO_X + 0.2, S.BATPAD_Y),
    "TP9": (-12.0, -2.5), "TP10": (-9.8, -2.5), "TP11": (-7.6, -2.5), "TP12": (-3.4, -2.5), "TP13": (-1.2, -2.5),
}
TARGET = {  # loose targets for the legalizer, grouped near the IC they serve
    "C1": (10.6, 5.4), "C2": (10.6, 6.6), "L1": (7.6, 4.6),
    "C3": (11.2, 1.0), "L2": (11.2, -1.0), "C5": (11.2, -2.2), "C6": (11.2, -3.3), "C7": (8.6, -6.6),
    "C8": (6.0, -5.2), "C9": (4.5, -5.2), "R1": (2.4, 1.5), "C10": (2.4, 2.6),
    
    "U2": (-13.6, -6.4), "R2": (-11.8, -6.6), "C13": (-11.8, -5.6), "C15": (-1.0, 6.4),
    "U3": (-1.5, 4.6), "C16": (-3.2, 6.4), "C17": (-5.5, 4.8), "R3": (-3.6, 4.4), "R4": (-3.6, 3.4), "C18": (-3.6, 2.4),
    "U4": (-13.6, 6.4), "R7": (-11.8, 6.6), "R8": (-11.8, 5.6),
    "U5": (0.5, -2.2), "C19": (0.5, -3.6), "U6": (0.5, 1.4), "C20": (-0.9, 0.4),
    "C24": (-7.3, -3.0), "C25": (-7.3, -2.0), "C26": (-7.3, -1.0), "C27": (-7.3, 0.0), "C28": (-7.3, 1.0), "C29": (-7.3, 2.0), "C30": (-7.3, 3.0),
    "Q1": (-4.6, -2.6), "L4": (-4.6, 0.8), "R11": (-5.6, -4.6), "R12": (-3.6, -4.6), "D1": (-2.4, -2.4), "D2": (-2.4, -0.6),
    "D3": (-2.4, 1.2), "C22": (-5.0, 3.4),
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
        fp.Reference().SetVisible(False); fp.Value().SetVisible(False)   # no silk refs on a 15 mm board
        board.Add(fp)
        fps[ref] = fp

    placed = []
    def put(fp, x, y, rot=0, flip=False):
        fp.SetPosition(V(x, y)); fp.SetOrientationDegrees(rot)
        if flip and not fp.IsFlipped():
            fp.Flip(fp.GetPosition(), pcbnew.FLIP_DIRECTION_TOP_BOTTOM)

    # antenna: long axis across the board at the +X end, feed/ground pads facing the board (-X)
    ae = fps["AE1"]
    put(ae, X1 - 5.70, -9.845, -90)   # pinned: the position the antenna was simulated and trimmed at (hardware/rf)
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
    for ref in ("SW1", "SW2", "SW3", "SW4"):
        put(fps[ref], *PIN[ref])
    for ref, (x, y) in BOTTOM.items():
        put(fps[ref], x, y, 0, flip=True)
    # RF chain in a straight line from LNA_IN: C11 shunt, L3 series, C12 shunt, then the feed (pinned by pad)
    def pin_pad(ref, num, x, y, direction):
        fp = fps[ref]
        for rot in (0, 90, 180, 270):
            put(fp, 0, 0, rot)
            a = pad_xy(fp, num); b = pad_xy(fp, "2" if num == "1" else "1")
            v = (round(b[0] - a[0], 2), round(b[1] - a[1], 2))
            if (direction == "+x" and v[0] > 0.2) or (direction == "+y" and v[1] > 0.2) or (direction == "-y" and v[1] < -0.2):
                put(fp, x - a[0], y - a[1], rot); return
        raise SystemExit(f"cannot orient {ref}")
    rx, ry = pad_xy(u1, "1")                      # LNA_IN pad centre
    fx, fy = feed
    W = 0.2                                       # 50-ohm GCPW on F.Cu over the In1 plane: 0.20 mm, 0.15 mm gap
    pin_pad("C11", "1", rx + 1.05, ry, "-y")          # shunt caps point away from the feed run
    pin_pad("L3", "1", rx + 1.55, ry, "+x")
    l3a, l3b = pad_xy(fps["L3"], "1"), pad_xy(fps["L3"], "2")
    pin_pad("C12", "1", l3b[0] + 0.42, ry, "-y")
    c11a, c12a = pad_xy(fps["C11"], "1"), pad_xy(fps["C12"], "1")
    put(fps["Y1"], 10.0, 6.3, 0)                 # crystal in the corner between SW2 and the RF feed
    def track(net, pts, w=W):
        for a, b in zip(pts, pts[1:]):
            t = pcbnew.PCB_TRACK(board); t.SetStart(V(*a)); t.SetEnd(V(*b)); t.SetWidth(MM(w))
            t.SetLayer(pcbnew.F_Cu); t.SetNet(nets[net]); t.SetLocked(True); board.Add(t)
    track("RF_CHIP", [(rx, ry), c11a, l3a])           # segments break at every pad so the router sees them connected
    track("RF_ANT", [l3b, c12a, (fx, ry), (fx, fy)])
    # RF ground vias + fence are added after routing (route.py), with collision checks
    placed = [box(fps[r]) for r in ("U1", "J1", "SW1", "SW2", "SW3", "SW4", "C11", "L3", "C12", "Y1")]
    placed.append((rx, ry - 0.35, fx + 0.35, ry + 0.35)); placed.append((fx - 0.35, ry, fx + 0.35, fy))   # keep parts off the feed
    ae_box = box(ae)

    keep = [(S.ANT_X0 - 0.2, Y0 - 1, X1 + 1, Y1 + 1), FPC_LANE] + LEDGES
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

    pcbnew.ZONE_FILLER(board).Fill(board.Zones())
    board.Save("horae.kicad_pcb")
    os.makedirs("out", exist_ok=True)
    pcbnew.ExportSpecctraDSN(board, "out/horae.dsn")
    print(f"placed {len(fps)} footprints; antenna rot {best[1]}, feed at {feed[0]:.2f},{feed[1]:.2f}; U1 rot {min(rots)[1]}")


if __name__ == "__main__":
    main()
