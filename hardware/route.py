"""Import the Freerouting session, add GND pours on F/In2/B, stitching vias, thermal spokes, refill, save.
Run: ./kicad python3 route.py"""
import pcbnew, sys, functools
pcbnew.KIID.SeedGenerator(3)   # reproducible UUIDs
print = functools.partial(print, flush=True)
sys.path.insert(0, "..")
from gen_pcb import X0, Y0, Y1, OX, OY, MM, S, VIA_D, VIA_H, TOUCH_NETS
TOUCH_E = set(TOUCH_NETS)

from sesfix import fix_ses
fix_ses("out/horae.ses", "out/horae-fixed.ses")
board = pcbnew.LoadBoard("horae.kicad_pcb")
if not pcbnew.ImportSpecctraSES(board, "out/horae-fixed.ses"):
    raise SystemExit("SES import failed")
gnd = board.FindNet("GND")


def prune_unused():
    """Drop the pre-routed escape vias the router left unused (copper on one layer only) and the stubs that fed them.
    Geometry is copied into plain tuples first (calling SWIG getters in the inner loop is slow and was flaky)."""
    LAYS = (pcbnew.F_Cu, pcbnew.In2_Cu, pcbnew.B_Cu)
    pads = []
    for fp in board.GetFootprints():
        for p in fp.Pads():
            if p.GetNetCode() != gnd.GetNetCode():
                bb = p.GetBoundingBox()
                pads.append((p.GetNetCode(), [l for l in LAYS if p.IsOnLayer(l)], bb.GetLeft(), bb.GetTop(), bb.GetRight(), bb.GetBottom()))
    removed = 0
    while True:
        objs = []
        for t in board.GetTracks():
            if t.GetNetCode() == gnd.GetNetCode():
                continue
            if t.GetClass() == "PCB_VIA":
                c = t.GetPosition(); objs.append((t, t.GetNetCode(), list(LAYS), (c.x, c.y), (c.x, c.y), t.GetWidth(pcbnew.F_Cu) / 2))
            else:
                a_, b_ = t.GetStart(), t.GetEnd()
                objs.append((t, t.GetNetCode(), [t.GetLayer()], (a_.x, a_.y), (b_.x, b_.y), t.GetWidth() / 2))
        def seg_d(p, a, b):
            dx, dy = b[0] - a[0], b[1] - a[1]
            u = max(0.0, min(1.0, ((p[0] - a[0]) * dx + (p[1] - a[1]) * dy) / float(dx * dx + dy * dy or 1)))
            return ((p[0] - a[0] - u * dx) ** 2 + (p[1] - a[1] - u * dy) ** 2) ** 0.5
        def touching(pt, layer, net, skip):
            if any(o[0] is not skip and o[1] == net and layer in o[2] and seg_d(pt, o[3], o[4]) <= o[5] for o in objs):
                return True
            return any(q[0] == net and layer in q[1] and q[2] <= pt[0] <= q[4] and q[3] <= pt[1] <= q[5] for q in pads)
        dead = []
        for o in objs:
            t, net, lays, a_, b_, r = o
            if t.GetClass() == "PCB_VIA":
                if sum(1 for l in LAYS if touching(a_, l, net, t)) < 2:
                    dead.append(t)
            elif not touching(a_, lays[0], net, t) or not touching(b_, lays[0], net, t):
                dead.append(t)
        if not dead:
            return removed
        for t in dead:
            board.Delete(t); removed += 1


print(f"pruned {prune_unused()} unused pre-routed vias/stubs")
ANT_KEEP_X = [pcbnew.ToMM(z.Outline().BBox().GetLeft()) - OX for z in board.Zones() if z.GetZoneName() == "antenna keep-out"][0]

# thermal spokes on the GND pads of the non-critical 0201s (tombstoning); the ESP32 decoupling, crystal and RF parts keep
# full contact (Espressif HDG 1.4.2)
FULL = {"C1", "C2", "C3", "C6", "C7", "C8", "C9", "C10", "C11", "C12", "C19", "C20", "C34", "C36", "L1", "L2", "L3"}
n_spoke = 0
for fp in board.GetFootprints():
    ref = fp.GetReference()
    if ref in FULL or not str(fp.GetFPID().GetLibItemName()).endswith("0201_0603Metric"):
        continue
    for p in fp.Pads():
        if p.GetNetCode() == gnd.GetNetCode():
            p.SetLocalZoneConnection(pcbnew.ZONE_CONNECTION_THERMAL)
            n_spoke += 1
print(f"thermal spokes on {n_spoke} 0201 GND pads")

for lay in (pcbnew.F_Cu, pcbnew.In2_Cu, pcbnew.B_Cu):
    z = pcbnew.ZONE(board); z.SetLayer(lay); z.SetNet(gnd)
    o = z.Outline(); o.NewOutline()
    for x, y in ((X0, Y0), (ANT_KEEP_X, Y0), (ANT_KEEP_X, Y1), (X0, Y1)):
        o.Append(MM(OX + x), MM(OY + y))
    z.SetMinThickness(MM(0.1)); z.SetLocalClearance(MM(0.1))   # RF keeps 0.15 via horae.kicad_dru
    z.SetPadConnection(pcbnew.ZONE_CONNECTION_FULL)
    z.SetThermalReliefGap(MM(0.15)); z.SetThermalReliefSpokeWidth(MM(0.15))
    z.SetIslandRemovalMode(pcbnew.ISLAND_REMOVAL_MODE_ALWAYS)
    board.Add(z)
pcbnew.ZONE_FILLER(board).Fill(board.Zones())

lay_all = [pcbnew.F_Cu, pcbnew.In1_Cu, pcbnew.In2_Cu, pcbnew.B_Cu]
no_via = [z.Outline() for z in board.Zones() if z.GetIsRuleArea() and z.GetDoNotAllowVias()]   # antenna, touch, crystal, tab areas
ae = board.FindFootprintByReference("AE1")
ANT_CU_X = min([pcbnew.ToMM(g.GetBoundingBox().GetLeft()) for g in ae.GraphicalItems() if g.GetLayer() == pcbnew.F_Cu] +
               [pcbnew.ToMM(p.GetBoundingBox().GetLeft()) for p in ae.Pads()]) - OX
others = [t for t in board.GetTracks() if t.GetNetCode() != gnd.GetNetCode()]
others += [p for fp in board.GetFootprints() for p in fp.Pads() if p.GetNetCode() != gnd.GetNetCode()]
holes = [p for fp in board.GetFootprints() for p in fp.Pads() if p.GetAttribute() == pcbnew.PAD_ATTRIB_NPTH]
smd_pads = [p for fp in board.GetFootprints() for p in fp.Pads() if p.GetAttribute() == pcbnew.PAD_ATTRIB_SMD]
FEED_Y = pcbnew.ToMM([p for p in ae.Pads() if p.GetNumber() == "1"][0].GetPosition().y) - OY
def via_allowed(x, y):
    pt = pcbnew.VECTOR2I(MM(OX + x), MM(OY + y))
    if x > ANT_CU_X - 0.6 and not (y < FEED_Y - 0.8 and x < ANT_KEEP_X - 0.4):
        return False   # clear of the antenna feed/short bars; north of them the meander starts 1.5 mm further out
    return not any(o.Contains(pt) or o.SquaredDistance(pt) < MM(VIA_D / 2 + 0.05) ** 2 for o in no_via)
def make_via(x, y):
    """A GND via at (x, y) if it clears every other net on every layer, every pad (no via-in/near-pad: 0.15 mm hole to pad
    edge), NPTH holes and other vias (JLC 0.2 mm hole-to-hole -> 0.65 mm pitch)."""
    if not via_allowed(x, y):
        return None
    v = pcbnew.PCB_VIA(board); v.SetPosition(pcbnew.VECTOR2I(MM(OX + x), MM(OY + y)))
    v.SetWidth(MM(VIA_D)); v.SetDrill(MM(VIA_H)); v.SetNet(gnd)
    for lay in lay_all:
        vs = v.GetEffectiveShape(lay)
        if any(o.IsOnLayer(lay) and vs.Collide(o.GetEffectiveShape(lay), MM(0.32 if o.GetNetname() in TOUCH_E else 0.12)) for o in others):
            return None   # touch traces keep the Touch clearance
    hole = pcbnew.SHAPE_CIRCLE(v.GetPosition(), MM(VIA_H / 2))
    if any(p.GetEffectiveShape(pcbnew.F_Cu if p.IsOnLayer(pcbnew.F_Cu) else pcbnew.B_Cu).Collide(hole, MM(0.15 + 0.0)) for p in smd_pads
           if (p.IsOnLayer(pcbnew.F_Cu) or p.IsOnLayer(pcbnew.B_Cu))):
        return None
    if any(v.GetEffectiveShape(pcbnew.F_Cu).Collide(h.GetEffectiveShape(pcbnew.F_Cu), MM(0.3)) for h in holes):
        return None
    if any((pcbnew.ToMM(w.GetPosition().x) - OX - x) ** 2 + (pcbnew.ToMM(w.GetPosition().y) - OY - y) ** 2 <
           (0.77 if w.GetNetname() in TOUCH_E else 0.46 if w.GetNetCode() == gnd.GetNetCode() else 0.56) ** 2
           for w in board.GetTracks() if w.GetClass() == "PCB_VIA"):
        return None                     # JLC: 0.2 mm hole to hole; 0.1 mm ring to ring between nets; Touch keeps 0.3
    pp = [p for fp in board.GetFootprints() for p in fp.Pads() if p.GetAttribute() == pcbnew.PAD_ATTRIB_PTH]
    if any((pcbnew.ToMM(p.GetPosition().x) - OX - x) ** 2 + (pcbnew.ToMM(p.GetPosition().y) - OY - y) ** 2 < 0.65 ** 2 for p in pp):
        return None
    return v

added = 0
# RF: shunt-cap ground vias right at the pads
ring = [(dx * 0.1, dy * 0.1) for r_ in range(4, 10) for dx, dy in ((0, r_), (r_, 0), (-r_, 0), (0, -r_), (r_, r_), (-r_, r_), (r_, -r_), (-r_, -r_))]
for ref in ("C11", "C12"):
    pad = [p for p in board.FindFootprintByReference(ref).Pads() if p.GetNumber() == "2"][0]
    px, py = pcbnew.ToMM(pad.GetPosition().x) - OX, pcbnew.ToMM(pad.GetPosition().y) - OY
    for dx, dy in ring:
        v = make_via(px + dx, py + dy)
        if v:
            t = pcbnew.PCB_TRACK(board); t.SetStart(pad.GetPosition()); t.SetEnd(v.GetPosition()); t.SetWidth(MM(0.2))
            t.SetLayer(pcbnew.F_Cu); t.SetNet(gnd)
            if not any(o.IsOnLayer(pcbnew.F_Cu) and t.GetEffectiveShape(pcbnew.F_Cu).Collide(o.GetEffectiveShape(pcbnew.F_Cu), MM(0.15)) for o in others):
                board.Add(v); board.Add(t); added += 1; print(f"RF via {ref}: ok"); break
    else:
        print(f"RF via {ref}: no room (the pad joins the F.Cu pour)")
# GND stitching: a via wherever one fits on a 0.8 mm grid, so no pour island floats
step = 0.8
nx, ny = int((ANT_KEEP_X - X0) / step), int((Y1 - Y0) / step)
rc = S.PCB_CORNER_R
for i in range(1, nx):
    for j in range(1, ny):
        x, y = X0 + i * step, Y0 + j * step
        if x < X0 + 0.6 or y < Y0 + 0.6 or y > Y1 - 0.6:
            continue
        if any(abs(x - cx) <= rc and abs(y - cy) <= rc and ((x - cx) ** 2 + (y - cy) ** 2) ** 0.5 > rc - 0.6 and (x - cx) * cx > 0 and (y - cy) * cy > 0
               for cx, cy in ((X0 + rc, Y0 + rc), (X0 + rc, Y1 - rc))):
            continue   # rounded -X corners
        v = make_via(x, y)
        if v:
            board.Add(v); added += 1
pcbnew.ZONE_FILLER(board).Fill(board.Zones())
print("grid stitching done")
# any top/bottom GND island still without a via gets one at the first free spot inside it
vias = [t for t in board.GetTracks() if t.GetClass() == "PCB_VIA" and t.GetNetCode() == gnd.GetNetCode()]
vias += [p for fp in board.GetFootprints() for p in fp.Pads() if p.GetNetCode() == gnd.GetNetCode() and p.GetAttribute() == pcbnew.PAD_ATTRIB_PTH]
for z in [z for z in board.Zones() if not z.GetIsRuleArea() and z.GetLayer() in (pcbnew.F_Cu, pcbnew.B_Cu)]:
    polys = z.GetFilledPolysList(z.GetLayer())
    for k in range(polys.OutlineCount()):
        out = polys.Outline(k)
        if any(out.PointInside(v.GetPosition()) for v in vias):
            continue
        bb = out.BBox(); placed_v = None
        xs = [pcbnew.ToMM(bb.GetLeft()) - OX + 0.1 * i for i in range(int(pcbnew.ToMM(bb.GetWidth()) / 0.1) + 1)]
        ys = [pcbnew.ToMM(bb.GetTop()) - OY + 0.1 * j for j in range(int(pcbnew.ToMM(bb.GetHeight()) / 0.1) + 1)]
        for x in xs:
            for y in ys:
                if out.PointInside(pcbnew.VECTOR2I(MM(OX + x), MM(OY + y))) and out.SquaredDistance(pcbnew.VECTOR2I(MM(OX + x), MM(OY + y))) > MM(0.2) ** 2:
                    placed_v = make_via(x, y)
                    if placed_v: break
            if placed_v: break
        if placed_v:
            board.Add(placed_v); vias.append(placed_v); added += 1
        else:
            print(f"island without via on {z.GetLayerName()} near {pcbnew.ToMM(bb.Centre().x)-OX:.2f},{pcbnew.ToMM(bb.Centre().y)-OY:.2f}")
pcbnew.ZONE_FILLER(board).Fill(board.Zones())
print(f"stitching vias: {added}")
# the touch fan-out at the ESP32: a named area for horae.kicad_dru (0.2 mm Touch clearance inside); added only now because
# KiCad exports every rule area to the DSN as a keepout
fx0, fy0, fx1, fy1 = map(float, open("out/fanout.txt").read().split())
fz = pcbnew.ZONE(board); fz.SetIsRuleArea(True); fz.SetZoneName("touch fan-out"); fz.SetLayer(pcbnew.F_Cu)
fz.SetDoNotAllowTracks(False); fz.SetDoNotAllowVias(False); fz.SetDoNotAllowZoneFills(False); fz.SetDoNotAllowPads(False); fz.SetDoNotAllowFootprints(False)
o = fz.Outline(); o.NewOutline()
for x, y in ((fx0, fy0), (fx1, fy0), (fx1, fy1), (fx0, fy1)):
    o.Append(MM(OX + x), MM(OY + y))
board.Add(fz)
board.GetDesignSettings().m_NetSettings.GetDefaultNetclass().SetClearance(MM(0.10))   # routed at 0.11; widening to 0.10 eats 0.005
board.Save("horae.kicad_pcb")
tracks = [t for t in board.GetTracks()]
print(f"imported: {sum(1 for t in tracks if t.GetClass()=='PCB_TRACK')} tracks, {sum(1 for t in tracks if t.GetClass()=='PCB_VIA')} vias")
