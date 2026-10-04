"""Dump placed antenna copper, pads, GND fills and board outline near the antenna to geom.json.
Run: cd hardware && ./kicad python3 rf/extract.py"""
import json, pcbnew
b = pcbnew.LoadBoard("horae.kicad_pcb")
mm = pcbnew.ToMM
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
json.dump(g, open("rf/geom.json", "w"), indent=1)
print(len(g["ant"]), {k: len(v) for k, v in g["fills"].items()}, fps)
