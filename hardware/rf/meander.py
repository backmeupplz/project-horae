"""SWRA117D meander IFA (TI, via Watchy) in footprint coordinates: trim from the open end, write the footprint.

RECTS: the untrimmed lib footprint (git 4f85a15) as rectangles (x0, x1, y0, y1), in path order from the feed/short end
to the open end; each path piece carries its run axis and the side its free end grows toward. trim(T) shortens the
path from the open end by T mm (a rectangle counts its extent along its run; the 6.64 mm rev A trim = the last two).
  python3 meander.py T   -> results/SWRA117D_new.kicad_mod (pads, net tie and polygon style of the lib footprint)
"""
import os, sys

FEED, SHORT = (14.22, 14.72, -4.4, 0.5), (16.12, 17.02, -4.4, 0.5)
PATH = [((12.02, 17.02, -4.9, -4.4), 0, -1), ((12.02, 12.52, -4.4, -1.76), 1, +1), ((10.02, 12.02, -2.26, -1.76), 0, -1),
        ((9.57, 10.07, -4.4, -1.76), 1, -1), ((7.37, 10.07, -4.9, -4.4), 0, -1), ((7.37, 7.87, -4.4, -1.76), 1, +1),
        ((5.37, 7.37, -2.26, -1.76), 0, -1), ((4.87, 5.37, -4.4, -1.76), 1, -1), ((2.67, 5.37, -4.9, -4.4), 0, -1),
        ((2.67, 3.17, -4.4, -0.46), 1, +1)]   # (rect, run axis 0 = x / 1 = y, free end at -1 = low / +1 = high side)
LIB_TRIM = 6.64   # hardware/lib/horae.pretty/SWRA117D.kicad_mod


def trim(t):
    """-> antenna copper rectangles (feed arm, short arm, meander) with t mm cut from the open end."""
    out = [list(r) for r, _, _ in PATH]
    for i in reversed(range(len(PATH))):
        if t <= 1e-9: break
        _, ax, side = PATH[i]
        r = out[i]; n = r[2 * ax + 1] - r[2 * ax]
        if t >= n - 1e-9:
            out[i] = None; t -= n
        else:
            r[2 * ax + (1 if side > 0 else 0)] -= side * t; t = 0
    return [FEED, SHORT] + [tuple(round(v, 4) for v in r) for r in out if r]


def footprint(t):
    poly = "".join(f"  (fp_poly (pts (xy {x1:g} {y0:g}) (xy {x1:g} {y1:g}) (xy {x0:g} {y1:g}) (xy {x0:g} {y0:g})\n"
                   f"    (xy {x1:g} {y0:g})) (layer F.Cu) (width 0))\n" for x0, x1, y0, y1 in trim(t))
    txt = "".join(f"  (fp_text {k} {v} (at 17.02 0) (layer F.SilkS) hide\n    (effects (font (size 1.27 1.27) (thickness 0.15)))\n  )\n"
                  for k, v in (("reference", "Ref**"), ("value", "Val**")))
    return (f"(module SWRA117D (layer F.Cu) (tedit 5EACBD31)\n"
            f"  (descr \"TI SWRA117D meander IFA (via Watchy), open end trimmed {t:g} mm for 2.44 GHz in the Horae case (openEMS, hardware/rf)\")\n"
            f"  (net_tie_pad_groups \"1, 2\")\n{txt}{poly}"
            f"  (pad 1 smd rect (at 14.47 0.25) (size 0.5 0.5) (layers F.Cu F.Paste F.Mask))\n"
            f"  (pad 2 smd rect (at 16.57 0.25) (size 0.9 0.5) (layers F.Cu F.Paste F.Mask))\n)\n")


if __name__ == "__main__":
    here = os.path.dirname(os.path.abspath(__file__))
    lib = open(os.path.join(here, "../lib/horae.pretty/SWRA117D.kicad_mod")).read()
    assert footprint(LIB_TRIM) == lib, "meander.py no longer reproduces the lib footprint at LIB_TRIM"
    assert len(trim(0)) == 12 and trim(6.64 + 1.36)[-1] == (4.87, 5.37, -3.04, -1.76)   # partial cut on the 3rd piece
    if len(sys.argv) > 1:
        t = float(sys.argv[1])
        open(os.path.join(here, "results/SWRA117D_new.kicad_mod"), "w").write(footprint(t))
        print(f"results/SWRA117D_new.kicad_mod: trim {t:g} mm ({t - LIB_TRIM:+.2f} vs the lib footprint)")
    print("ok")
