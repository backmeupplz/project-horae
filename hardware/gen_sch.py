"""Generate horae.kicad_sch from design.py: every symbol placed by block, pins joined by net labels.

Run inside the KiCad container: ./kicad python3 gen_sch.py
"""
import copy, os, uuid
from sexpr import parse, dump, q, uq, find, first
from design import PARTS, POWER_NETS

SYMDIR = "/usr/share/kicad/symbols"
ROOT = str(uuid.uuid5(uuid.NAMESPACE_URL, "projecthorae.com/rev-a"))
_libs = {}


def uid(*k):
    return str(uuid.uuid5(uuid.NAMESPACE_URL, "horae/" + "/".join(map(str, k))))


def lib(name):
    if name not in _libs:
        path = "lib/horae.kicad_sym" if name == "horae" else f"{SYMDIR}/{name}.kicad_sym"
        _libs[name] = parse(open(path).read())
    return _libs[name]


def load_symbol(lib_id):
    """Return a flattened copy of the library symbol, renamed to lib_id for embedding."""
    libname, name = lib_id.split(":")
    syms = {uq(s[1]): s for s in find(lib(libname), "symbol")}
    s = copy.deepcopy(syms[name])
    ext = first(s, "extends")
    if ext:
        parent = copy.deepcopy(syms[uq(ext[1])])
        pname = uq(ext[1])
        props = {uq(p[1]): p for p in find(s, "property")}
        body = []
        for e in parent[2:]:
            if isinstance(e, list) and e[0] == "property" and uq(e[1]) in props:
                body.append(props.pop(uq(e[1])))
            elif isinstance(e, list) and e[0] == "symbol":
                e[1] = q(uq(e[1]).replace(pname, name, 1))
                body.append(e)
            else:
                body.append(e)
        s = [s[0], s[1]] + list(props.values()) + body
    s[1] = q(lib_id)
    if libname == "horae":  # LCSC-imported symbols leave pin types unspecified
        for sub in find(s, "symbol"):
            for p in find(sub, "pin"):
                if p[1] == "unspecified":
                    p[1] = "passive"
    return s


def pins(sym):
    out = []
    for sub in find(sym, "symbol"):
        unit = uq(sub[1]).rsplit("_", 2)[-2]
        if unit not in ("0", "1"):
            continue
        for p in find(sub, "pin"):
            at = first(p, "at")
            out.append((uq(first(p, "number")[1]), float(at[1]), float(at[2]), int(float(at[3]))))
    return out


def bbox(sym):
    xs, ys = [], []
    for sub in find(sym, "symbol"):
        for g in sub:
            if not isinstance(g, list):
                continue
            if g[0] == "pin":
                at = first(g, "at"); xs.append(float(at[1])); ys.append(float(at[2]))
            for key in ("start", "end", "xy", "center"):
                for pt in ([first(g, key)] if key != "xy" else [x for pl in find(g, "pts") for x in find(pl, "xy")]):
                    if pt:
                        xs.append(float(pt[1])); ys.append(float(pt[2]))
    return (min(xs), min(ys), max(xs), max(ys)) if xs else (-2.54, -2.54, 2.54, 2.54)


def snap(v, g=1.27):
    return round(round(v / g) * g, 4)


def prop(name, val, x, y, hide=False, justify="left"):
    eff = ["effects", ["font", ["size", "1.27", "1.27"]], ["justify", justify]]
    if hide:
        eff.append(["hide", "yes"])
    return ["property", q(name), q(val), ["at", f"{x:.2f}", f"{y:.2f}", "0"], eff]


BLOCKS = {  # x0, y0, width (mm, A2 sheet)
    "mcu": (20, 25, 200, "ESP32-S3 + clock"), "rf": (20, 250, 200, "RF match + antenna"),
    "power": (235, 25, 160, "Power: pogo USB, charger, LDO"), "sensors": (235, 220, 160, "RTC + accelerometer"),
    "display": (410, 25, 170, "E-paper connector + booster"), "ui": (410, 260, 170, "Buttons + haptics"),
    "pads": (20, 345, 560, "Pads (bottom side): pogo, battery, motor, test"),
}


def main():
    lib_symbols, items, used = [], [], {}
    cursor = {b: [x0, y0 + 10, y0 + 10] for b, (x0, y0, w, t) in BLOCKS.items()}  # x, y, row bottom
    for b, (x0, y0, w, title) in BLOCKS.items():
        items.append(["text", q(title), ["exclude_from_sim", "no"], ["at", str(x0), str(y0), "0"],
                      ["effects", ["font", ["size", "2.5", "2.5"], ["bold", "yes"]], ["justify", "left", "bottom"]],
                      ["uuid", q(uid("t", b))]])
    flags = [(f"#FLG{i+1}", "power:PWR_FLAG", "PWR_FLAG", "", "", {"1": n}, "power") for i, n in enumerate(POWER_NETS)]
    for ref, lib_id, value, fp, lcsc, pinmap, block in PARTS + flags:
        if lib_id not in used:
            used[lib_id] = load_symbol(lib_id)
            lib_symbols.append(used[lib_id])
        sym = used[lib_id]
        x0, y0, w, _ = BLOCKS[block]
        minx, miny, maxx, maxy = bbox(sym)
        lab = 2 + 1.1 * max([len(n) for n in pinmap.values()] + [4])
        cw, ch = (maxx - minx) + 2 * lab, (maxy - miny) + 9
        cx, cy, rowb = cursor[block]
        if cx + cw > x0 + w and cx > x0:
            cx, cy = x0, rowb + 2
        X, Y = snap(cx + lab - minx, 2.54), snap(cy + 4 + maxy, 2.54)
        cursor[block] = [cx + cw, cy, max(rowb, cy + ch)]

        inst = ["symbol", ["lib_id", q(lib_id)], ["at", f"{X:.2f}", f"{Y:.2f}", "0"], ["unit", "1"],
                ["exclude_from_sim", "no"], ["in_bom", "no" if ref.startswith(("#", "TP")) else "yes"],
                ["on_board", "no" if ref.startswith("#") else "yes"], ["dnp", "yes" if value.startswith("DNP") else "no"], ["uuid", q(uid("s", ref))],
                prop("Reference", ref, X + minx, Y - maxy - 1.5, hide=ref.startswith("#")),
                prop("Value", value, X + minx, Y - miny + 2.5, hide=ref.startswith("#")),
                prop("Footprint", fp, X, Y, hide=True), prop("Datasheet", "", X, Y, hide=True)]
        if lcsc:
            inst.append(prop("LCSC", lcsc, X, Y, hide=True))
        seen = {}
        for num, px, py, ang in pins(sym):
            inst.append(["pin", q(num), ["uuid", q(uid("p", ref, num))]])
            sx, sy = round(X + px, 4), round(Y - py, 4)
            net = pinmap.get(num)
            key = (sx, sy)
            if key in seen and seen[key] != net:
                raise SystemExit(f"{ref}: stacked pins at {key} have different nets {seen[key]} / {net}")
            if key in seen:
                continue
            seen[key] = net
            if net is None:
                items.append(["no_connect", ["at", f"{sx}", f"{sy}"], ["uuid", q(uid("nc", ref, num))]])
                continue
            la = {0: 180, 180: 0, 90: 270, 270: 90}[ang % 360]
            just = "left" if la in (0, 90) else "right"
            items.append(["label", q(net), ["at", f"{sx}", f"{sy}", str(la)], ["fields_autoplaced", "yes"],
                          ["effects", ["font", ["size", "1", "1"]], ["justify", just, "bottom"]],
                          ["uuid", q(uid("l", ref, num))]])
        missing = set(pinmap) - {p[0] for p in pins(sym)}
        if missing:
            raise SystemExit(f"{ref} ({lib_id}) has no pins {missing}")
        inst.append(["instances", ["project", q("horae"), ["path", q("/" + ROOT), ["reference", q(ref)], ["unit", "1"]]]])
        items.append(inst)

    sch = ["kicad_sch", ["version", "20231120"], ["generator", q("horae_gen_sch")], ["generator_version", q("8.0")],
           ["uuid", q(ROOT)], ["paper", q("A2")],
           ["title_block", ["title", q("Project Horae rev A")], ["date", q("2026-10-03")], ["rev", q("A")],
            ["company", q("projecthorae.com")], ["comment", "1", q("Generated by hardware/gen_sch.py from design.py; edit design.py, not this file")]],
           ["lib_symbols"] + lib_symbols] + items + [["sheet_instances", ["path", q("/"), ["page", q("1")]]]]
    open("horae.kicad_sch", "w").write(dump(sch) + "\n")
    print(f"wrote horae.kicad_sch: {len(PARTS)} parts, {len(lib_symbols)} lib symbols")


if __name__ == "__main__":
    main()
