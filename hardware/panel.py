"""1-up JLC assembly panel around the routed board -> out/panel/horae-panel.kicad_pcb. Run: ./kicad python3 panel.py
70 x 70 mm frame; a 2 mm milled slot round the board except at the four tabs (gen_pcb.TABS), each with 5 x 0.6 mm NPTH
mouse bites at 0.95 mm pitch whose holes reach 1/3 into the board (JLC mouse-bite guide), so no nub stands proud of the
outline; 3 fiducials (1 mm copper, 2 mm mask opening, mask edge >= 3.35 mm from the frame edge); 4 x 1.152 mm NPTH
tooling holes (0.148 mm mask expansion) in the corners; "JLCJLCJLCJLC" on the rail for the order number.
The board keeps its absolute position, so its gerber-frame CPL is also the panel's."""
import os, sys
import pcbnew
pcbnew.KIID.SeedGenerator(4)
sys.path.insert(0, "..")
from gen_pcb import OX, OY, MM, TABS, TAB_GAP, TAB_HOLE, TAB_PITCH, TAB_HOLES

PANEL = 70.0
board = pcbnew.LoadBoard("horae.kicad_pcb")
V = lambda x, y: pcbnew.VECTOR2I(MM(OX + x), MM(OY + y))


def rect(x0, y0, x1, y1):   # (x0, y0) - (x1, y1), board-centred mm
    p = pcbnew.SHAPE_POLY_SET(); p.NewOutline()
    for x, y in ((x0, y0), (x1, y0), (x1, y1), (x0, y1)):
        p.Append(MM(OX + x), MM(OY + y))
    return p


# material = frame - (slot round the board) + tabs; its contours become Edge.Cuts
pcb = pcbnew.SHAPE_POLY_SET(); assert board.GetBoardPolygonOutlines(pcb, False)
slot = pcbnew.SHAPE_POLY_SET(pcb); slot.Inflate(MM(TAB_GAP), pcbnew.CORNER_STRATEGY_ROUND_ALL_CORNERS, MM(0.002))
slot.BooleanSubtract(pcb)
for (ax, ay), (bx, by) in TABS:
    if ax == bx:   # short edge (s: outward); the bridge reaches 0.3 mm into the board (the -X corners curve away)
        s = -1 if ax < 0 else 1
        x0_, x1_ = sorted((ax - s * 0.3, ax + s * (TAB_GAP + 0.5)))
        slot.BooleanSubtract(rect(x0_, min(ay, by), x1_, max(ay, by)))
    else:
        s = -1 if ay < 0 else 1
        y0_, y1_ = sorted((ay - s * 0.3, ay + s * (TAB_GAP + 0.5)))
        slot.BooleanSubtract(rect(min(ax, bx), y0_, max(ax, bx), y1_))
h = PANEL / 2
material = rect(-h, -h, h, h); material.BooleanSubtract(slot)
for d in [d for d in board.GetDrawings() if d.GetLayer() == pcbnew.Edge_Cuts]:
    board.Delete(d)   # (Remove() + Python GC corrupts SWIG state)
def contour(k, j=-1):   # outline k (j = -1) or its hole j, as Edge.Cuts segments
    pts = [material.CVertex(i, k, j) for i in range(material.VertexCount(k, j))]
    for a, b in zip(pts, pts[1:] + pts[:1]):
        s = pcbnew.PCB_SHAPE(board); s.SetShape(pcbnew.SHAPE_T_SEGMENT); s.SetLayer(pcbnew.Edge_Cuts)
        s.SetStart(pcbnew.VECTOR2I(a)); s.SetEnd(pcbnew.VECTOR2I(b)); s.SetWidth(MM(0.05)); board.Add(s)
for k in range(material.OutlineCount()):
    contour(k)
    for j in range(material.HoleCount(k)):
        contour(k, j)
print(f"panel outline: {material.OutlineCount()} part, {sum(material.HoleCount(k) for k in range(material.OutlineCount()))} slots")


def holder(ref, x, y):
    fp = pcbnew.FOOTPRINT(board); fp.SetReference(ref); fp.SetValue(ref); fp.SetPosition(V(x, y))
    fp.Reference().SetVisible(False); fp.Value().SetVisible(False)
    fp.SetAttributes(pcbnew.FP_EXCLUDE_FROM_BOM | pcbnew.FP_EXCLUDE_FROM_POS_FILES | pcbnew.FP_BOARD_ONLY)
    board.Add(fp); return fp


def npth(fp, x, y, d, mask=0.0):
    p = pcbnew.PAD(fp); p.SetAttribute(pcbnew.PAD_ATTRIB_NPTH); p.SetShape(pcbnew.PAD_SHAPE_CIRCLE)
    p.SetSize(pcbnew.VECTOR2I(MM(d), MM(d))); p.SetDrillSize(pcbnew.VECTOR2I(MM(d), MM(d)))
    p.SetLayerSet(p.UnplatedHoleMask()); p.SetLocalSolderMaskMargin(MM(mask))
    fp.Add(p); p.SetPosition(V(x, y))


# mouse bites: hole centres 0.1 mm outside the edge (0.2 mm of each 0.6 mm hole inside the board)
for n, ((ax, ay), (bx, by)) in enumerate(TABS):
    mx, my = (ax + bx) / 2, (ay + by) / 2
    fp = holder(f"MB{n + 1}", mx, my)
    for k in range(TAB_HOLES):
        t = (k - (TAB_HOLES - 1) / 2) * TAB_PITCH
        if ax == bx:
            npth(fp, ax + (-0.1 if ax < 0 else 0.1), my + t, TAB_HOLE)
        else:
            npth(fp, mx + t, ay + (-0.1 if ay < 0 else 0.1), TAB_HOLE)
    span = (TAB_HOLES - 1) * TAB_PITCH + TAB_HOLE
    assert span <= abs(bx - ax) + abs(by - ay) + 1e-6, "mouse bites longer than the tab"

# tooling holes in the four corners, fiducials on three of them (asymmetric so the panel can't be loaded rotated)
for n, (sx, sy) in enumerate(((-1, -1), (1, -1), (1, 1), (-1, 1))):
    npth(holder(f"TH{n + 1}", sx * (h - 3.0), sy * (h - 3.0)), sx * (h - 3.0), sy * (h - 3.0), 1.152, 0.148)
for n, (sx, sy) in enumerate(((-1, -1), (1, -1), (-1, 1))):
    x, y = sx * (h - 8.0), sy * (h - 4.5)
    fp = holder(f"FID{n + 1}", x, y)
    p = pcbnew.PAD(fp); p.SetAttribute(pcbnew.PAD_ATTRIB_SMD); p.SetShape(pcbnew.PAD_SHAPE_CIRCLE)
    p.SetSize(pcbnew.VECTOR2I(MM(1.0), MM(1.0)))
    ls = pcbnew.LSET(); ls.AddLayer(pcbnew.F_Cu); ls.AddLayer(pcbnew.F_Mask); p.SetLayerSet(ls)
    p.SetLocalSolderMaskMargin(MM(0.5)); fp.Add(p); p.SetPosition(V(x, y))
t = pcbnew.PCB_TEXT(board); t.SetText("JLCJLCJLCJLC"); t.SetLayer(pcbnew.F_SilkS)
t.SetTextSize(pcbnew.VECTOR2I(MM(1.0), MM(1.0))); t.SetTextThickness(MM(0.15)); t.SetPosition(V(0, h - 4.5)); board.Add(t)

os.makedirs("out/panel", exist_ok=True)
board.Save("out/panel/horae-panel.kicad_pcb")
print(f"panel {PANEL:g} x {PANEL:g} mm: {len(TABS)} tabs x {TAB_HOLES} mouse bites, 4 tooling holes, 3 fiducials")
