"""Import the Freerouting session, add GND pours on F/In2/B, refill, save. Run: ./kicad python3 route.py"""
import pcbnew, sys, functools
print = functools.partial(print, flush=True)
sys.path.insert(0, "..")
from gen_pcb import X0, Y0, Y1, OX, OY, MM, S

import re
ses = open("out/horae.ses").read()
ses = re.sub(r"\(path (\S+) 750(\s)", r"(path \1 900\2", ses)   # Freerouting necks some wires to 0.075; JLC minimum is 0.09
from sexpr import parse, dump, find
tree = parse(ses)
nets_out = find(find(find(tree, "routes")[0], "network_out")[0], "net")
other_vias = [(float(v[2]) / 1e4, float(v[3]) / 1e4) for n in nets_out if n[1] not in ("GND", '"GND"') for v in find(n, "via")]
def seg_dist(p, a, b):
    (px, py), (ax, ay), (bx, by) = p, a, b
    dx, dy = bx - ax, by - ay
    t = max(0, min(1, ((px - ax) * dx + (py - ay) * dy) / (dx * dx + dy * dy or 1)))
    return ((px - ax - t * dx) ** 2 + (py - ay - t * dy) ** 2) ** 0.5
for net in nets_out:
    if net[1] not in ("GND", '"GND"'):
        continue
    keep = []
    for e in net:
        if isinstance(e, list) and e[0] == "wire":
            path = e[1]; w = float(path[2]) / 1e4
            pts = [(float(path[i]) / 1e4, float(path[i + 1]) / 1e4) for i in range(3, len(path) - 1, 2)]
            # drop GND wires closer than JLC's 0.2 mm hole-to-copper to another net's via hole (pours reconnect)
            if any(seg_dist(v, pts[i], pts[i + 1]) < 0.075 + 0.2 + w / 2 for v in other_vias for i in range(len(pts) - 1)):
                continue
        keep.append(e)
    net[:] = keep
open("out/horae-fixed.ses", "w").write(dump(tree))
board = pcbnew.LoadBoard("horae.kicad_pcb")
if not pcbnew.ImportSpecctraSES(board, "out/horae-fixed.ses"):
    raise SystemExit("SES import failed")
gnd = board.FindNet("GND")
ANT_KEEP_X = [pcbnew.ToMM(z.Outline().BBox().GetLeft()) - OX for z in board.Zones() if z.GetIsRuleArea()][0]
for lay in (pcbnew.F_Cu, pcbnew.In2_Cu, pcbnew.B_Cu):
    z = pcbnew.ZONE(board); z.SetLayer(lay); z.SetNet(gnd)
    o = z.Outline(); o.NewOutline()
    for x, y in ((X0, Y0), (ANT_KEEP_X, Y0), (ANT_KEEP_X, Y1), (X0, Y1)):
        o.Append(MM(OX + x), MM(OY + y))
    z.SetMinThickness(MM(0.15)); z.SetLocalClearance(MM(0.15))
    z.SetPadConnection(pcbnew.ZONE_CONNECTION_FULL)
    z.SetIslandRemovalMode(pcbnew.ISLAND_REMOVAL_MODE_ALWAYS)
    board.Add(z)
pcbnew.ZONE_FILLER(board).Fill(board.Zones())

# GND stitching: a via wherever one fits clear of other nets on every layer, so no pour island floats
lay_all = [pcbnew.F_Cu, pcbnew.In1_Cu, pcbnew.In2_Cu, pcbnew.B_Cu]
others = [t for t in board.GetTracks() if t.GetNetCode() != gnd.GetNetCode()]
others += [p for fp in board.GetFootprints() for p in fp.Pads() if p.GetNetCode() != gnd.GetNetCode()]
holes = [p for fp in board.GetFootprints() for p in fp.Pads() if p.GetAttribute() == pcbnew.PAD_ATTRIB_NPTH]
gnd_pads = [p for fp in board.GetFootprints() for p in fp.Pads() if p.GetNetCode() == gnd.GetNetCode()]   # no grid vias inside pads
added = 0
step = 0.8
nx, ny = int((ANT_KEEP_X - X0) / step), int((Y1 - Y0) / step)
for i in range(1, nx):
    for j in range(1, ny):
        x, y = X0 + i * step, Y0 + j * step
        v = pcbnew.PCB_VIA(board); v.SetPosition(pcbnew.VECTOR2I(MM(OX + x), MM(OY + y)))
        v.SetWidth(MM(0.3)); v.SetDrill(MM(0.15)); v.SetNet(gnd)
        ok = True
        for lay in lay_all:
            vs = v.GetEffectiveShape(lay)
            for o in others:
                if o.IsOnLayer(lay) and vs.Collide(o.GetEffectiveShape(lay), MM(0.13)):
                    ok = False; break
            if not ok: break
        if ok and any(v.GetEffectiveShape(pcbnew.F_Cu).Collide(h.GetEffectiveShape(pcbnew.F_Cu), MM(0.3)) for h in holes):
            ok = False
        if ok and any(p.IsOnLayer(lay) and v.GetEffectiveShape(lay).Collide(p.GetEffectiveShape(lay), MM(0.05)) for p in gnd_pads for lay in (pcbnew.F_Cu, pcbnew.B_Cu)):
            ok = False
        if ok and (x < X0 + 0.6 or y < Y0 + 0.6 or y > Y1 - 0.6):
            ok = False
        rc = S.PCB_CORNER_R
        for cx, cy in ((X0 + rc, Y0 + rc), (X0 + rc, Y1 - rc)):   # rounded corners at -X (+X is antenna keep-out)
            if ok and abs(x - cx) <= rc and abs(y - cy) <= rc and (x - cx) * (cx - X0 - rc) >= 0 and ((x - cx) ** 2 + (y - cy) ** 2) ** 0.5 > rc - 0.6 \
                    and ((x < cx) and ((y < cy and cy < 0) or (y > cy and cy > 0))):
                ok = False
        if ok:
            board.Add(v); others_v = v; added += 1
pcbnew.ZONE_FILLER(board).Fill(board.Zones())

print("grid stitching done")
# any top/bottom GND island still without a via gets one at the first free spot inside it
def fits(x, y):
    v = pcbnew.PCB_VIA(board); v.SetPosition(pcbnew.VECTOR2I(MM(OX + x), MM(OY + y)))
    v.SetWidth(MM(0.3)); v.SetDrill(MM(0.15)); v.SetNet(gnd)
    for lay in lay_all:
        vs = v.GetEffectiveShape(lay)
        if any(o.IsOnLayer(lay) and vs.Collide(o.GetEffectiveShape(lay), MM(0.13)) for o in others):
            return None
    return v
vias = [t for t in board.GetTracks() if t.GetClass() == "PCB_VIA" and t.GetNetCode() == gnd.GetNetCode()]
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
                if out.PointInside(pcbnew.VECTOR2I(MM(OX + x), MM(OY + y))) and out.SquaredDistance(pcbnew.VECTOR2I(MM(OX + x), MM(OY + y))) > MM(0.16) ** 2:
                    placed_v = fits(x, y)
                    if placed_v: break
            if placed_v: break
        if not placed_v:   # fallback: via-in-pad on the island's GND pad (JLC: filled + capped)
            pads = [p for fp in board.GetFootprints() for p in fp.Pads()
                    if p.GetNetCode() == gnd.GetNetCode() and p.IsOnLayer(z.GetLayer()) and out.PointInside(p.GetPosition())]
            for p in sorted(pads, key=lambda p: -p.GetSize().x * p.GetSize().y):
                v = pcbnew.PCB_VIA(board); v.SetPosition(p.GetPosition())
                v.SetWidth(MM(0.25)); v.SetDrill(MM(0.15)); v.SetNet(gnd)
                if all(not (o.IsOnLayer(lay) and v.GetEffectiveShape(lay).Collide(o.GetEffectiveShape(lay), MM(0.1)))
                       for lay in lay_all for o in others):
                    placed_v = v
                    print(f"via-in-pad: {p.GetParentFootprint().GetReference()}.{p.GetNumber()}")
                    break
        if placed_v:
            board.Add(placed_v); vias.append(placed_v); added += 1
        else:
            print(f"island without via on {z.GetLayerName()} near {pcbnew.ToMM(bb.Centre().x)-OX:.2f},{pcbnew.ToMM(bb.Centre().y)-OY:.2f}")
pcbnew.ZONE_FILLER(board).Fill(board.Zones())
print(f"stitching vias: {added}")
# routed at 0.125 mm; widening necked wires to JLC's 0.09 mm minimum eats up to 0.0075 mm of that
board.GetDesignSettings().m_NetSettings.GetDefaultNetclass().SetClearance(MM(0.12))
board.Save("horae.kicad_pcb")
tracks = [t for t in board.GetTracks()]
print(f"imported: {sum(1 for t in tracks if t.GetClass()=='PCB_TRACK')} tracks, {sum(1 for t in tracks if t.GetClass()=='PCB_VIA')} vias")
