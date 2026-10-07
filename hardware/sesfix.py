"""Clean a Freerouting session before KiCad imports it (used by stage.py and route.py)."""
import re
from sexpr import parse, dump, find
VIA_H = 0.2


def seg_dist(p, a, b):
    (px, py), (ax, ay), (bx, by) = p, a, b
    dx, dy = bx - ax, by - ay
    t = max(0, min(1, ((px - ax) * dx + (py - ay) * dy) / (dx * dx + dy * dy or 1)))
    return ((px - ax - t * dx) ** 2 + (py - ay - t * dy) ** 2) ** 0.5


def fix_ses(src, dst):
    ses = open(src).read()
    ses = re.sub(r"\(path (\S+) (\d{1,3})(\s)", r"(path \1 1000\3", ses)   # Freerouting necks wires below 0.1 mm at pads
    tree = parse(ses)
    nets_out = find(find(find(tree, "routes")[0], "network_out")[0], "net")
    other_vias = [(float(v[2]) / 1e4, float(v[3]) / 1e4) for n in nets_out if n[1] not in ("GND", '"GND"') for v in find(n, "via")]
    for net in nets_out:
        if net[1] not in ("GND", '"GND"'):
            continue
        keep = []
        for e in net:
            if isinstance(e, list) and e[0] == "wire":
                path = e[1]; w = float(path[2]) / 1e4
                pts = [(float(path[i]) / 1e4, float(path[i + 1]) / 1e4) for i in range(3, len(path) - 1, 2)]
                # drop GND wires closer than JLC's 0.2 mm hole-to-copper to another net's via hole (pours reconnect)
                if any(seg_dist(v, pts[i], pts[i + 1]) < VIA_H / 2 + 0.2 + w / 2 for v in other_vias for i in range(len(pts) - 1)):
                    continue
            keep.append(e)
        net[:] = keep
    open(dst, "w").write(dump(tree))
