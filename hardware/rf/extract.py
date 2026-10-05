"""Dump placed antenna copper, pads, GND fills and board outline near the antenna to geom.json.
Run: cd hardware && ./kicad python3 rf/extract.py [--pour]
--pour: what-if for route.py's intent (on 2026-10-04 its ANT_KEEP_X is the first rule area = a touch no-pour zone, so
the F/In2/B GND pours stop at x = -7.5): those pours run to the antenna keep-out, plus route.py-style 0.8 mm grid
stitching vias near the antenna where they fit; refilled in memory (the board file is untouched) -> rf/geom_pour.json"""
import json, sys, pcbnew
b = pcbnew.LoadBoard("horae.kicad_pcb")
mm = pcbnew.ToMM
if "--pour" in sys.argv:
    MM, OX, OY = pcbnew.FromMM, 100.0, 100.0
    ko = [z for z in b.Zones() if z.GetIsRuleArea() and z.GetZoneName() == "antenna keep-out"][0].Outline().BBox().GetLeft()
    for z in b.Zones():
        if not z.GetIsRuleArea() and z.GetNetname() == "GND" and z.GetLayer() in (pcbnew.F_Cu, pcbnew.In2_Cu, pcbnew.B_Cu):
            bb = z.Outline().BBox(); o = z.Outline(); o.RemoveAllContours(); o.NewOutline()
            for x, y in ((bb.GetLeft(), bb.GetTop()), (ko, bb.GetTop()), (ko, bb.GetBottom()), (bb.GetLeft(), bb.GetBottom())):
                o.Append(x, y)
    gnd = b.FindNet("GND")
    others = [t for t in b.GetTracks() if t.GetNetCode() != gnd.GetNetCode()]
    others += [p for f in b.GetFootprints() for p in f.Pads() if p.GetNetCode() != gnd.GetNetCode()]
    ae = b.FindFootprintByReference("AE1")
    x_max = min(mm(p.GetBoundingBox().GetLeft()) for p in ae.Pads()) - OX - 0.6           # route.py via_allowed()
    x0, y0, y1 = [mm(v) for v in (b.GetBoardEdgesBoundingBox().GetLeft(), b.GetBoardEdgesBoundingBox().GetTop(),
                                  b.GetBoardEdgesBoundingBox().GetBottom())]
    x0, y0, y1 = x0 - OX, y0 - OY, y1 - OY
    lays = [pcbnew.F_Cu, pcbnew.In1_Cu, pcbnew.In2_Cu, pcbnew.B_Cu]
    n = 0
    for i in range(1, 200):
        for j in range(1, 100):
            x, y = x0 + 0.8 * i, y0 + 0.8 * j
            if not (x_max - 4 < x <= x_max and y0 + 0.6 < y < y1 - 0.6): continue
            v = pcbnew.PCB_VIA(b); v.SetPosition(pcbnew.VECTOR2I(MM(OX + x), MM(OY + y)))
            v.SetWidth(MM(0.4)); v.SetDrill(MM(0.2)); v.SetNet(gnd)
            if any(o.IsOnLayer(l) and v.GetEffectiveShape(l).Collide(o.GetEffectiveShape(l), MM(0.13)) for l in lays for o in others):
                continue
            if any((mm(w.GetPosition().x) - OX - x) ** 2 + (mm(w.GetPosition().y) - OY - y) ** 2 < 0.6 ** 2
                   for w in b.GetTracks() if w.GetClass() == "PCB_VIA"):
                continue
            b.Add(v); n += 1
    pcbnew.ZONE_FILLER(b).Fill(b.Zones())
    print(f"pour what-if: pours to x = {mm(ko) - OX:.2f}, {n} stitching vias near the antenna")
def poly(sps):
    out = []
    for i in range(sps.OutlineCount()):
        o = sps.Outline(i)
        out.append([(mm(o.CPoint(j).x), mm(o.CPoint(j).y)) for j in range(o.PointCount())])
    return out
g = {"ant": [], "pads": {}, "fills": {}, "tracks": [], "vias": []}
fp = b.FindFootprintByReference("AE1")
for it in fp.GraphicalItems():
    if it.GetLayer() == pcbnew.F_Cu:
        s = pcbnew.SHAPE_POLY_SET(); it.TransformShapeToPolygon(s, pcbnew.F_Cu, 0, 5000, pcbnew.ERROR_INSIDE)
        g["ant"] += poly(s)
for p in fp.Pads():
    s = pcbnew.SHAPE_POLY_SET(); p.TransformShapeToPolygon(s, pcbnew.F_Cu, 0, 5000, pcbnew.ERROR_INSIDE)
    g["pads"][p.GetNumber()] = poly(s)
for z in b.Zones():
    if z.GetIsRuleArea():
        if z.GetZoneName() == "antenna keep-out": g["keepout"] = poly(z.Outline())
        continue
    for L in z.GetLayerSet().CuStack():
        name = b.GetLayerName(L)
        g["fills"].setdefault(name, []).extend(poly(z.GetFilledPolysList(L)))
for t in b.GetTracks():
    st, en = t.GetStart(), t.GetEnd()
    if mm(max(st.x, en.x)) < 104: continue
    d = dict(net=t.GetNetname(), layer=b.GetLayerName(t.GetLayer()), a=(mm(st.x), mm(st.y)), b=(mm(en.x), mm(en.y)), w=mm(t.GetWidth(pcbnew.F_Cu) if t.Type() == pcbnew.PCB_VIA_T else t.GetWidth()))
    (g["vias"] if t.Type() == pcbnew.PCB_VIA_T else g["tracks"]).append(d)
fps = []
for f in b.GetFootprints():
    if f.GetReference() in ("C11", "C12", "L3", "U1", "AE1"):
        fps.append((f.GetReference(), mm(f.GetPosition().x), mm(f.GetPosition().y), f.GetOrientationDegrees(),
                    [(p.GetNumber(), p.GetNetname(), mm(p.GetPosition().x), mm(p.GetPosition().y), mm(p.GetSize().x), mm(p.GetSize().y)) for p in f.Pads()] if f.GetReference() != "U1" else []))
g["fps"] = fps
s = pcbnew.SHAPE_POLY_SET(); b.GetBoardPolygonOutlines(s, True); g["outline"] = poly(s)
json.dump(g, open("rf/geom_pour.json" if "--pour" in sys.argv else "rf/geom.json", "w"), indent=1)
print(len(g["ant"]), {k: len(v) for k, v in g["fills"].items()}, fps)
