"""Live JLC cost estimate from out/jlc-bom.csv (run after build.sh): parts per board + Standard PCBA fees.

    python3 cost.py [boards]      # default 2 assembled boards
"""
import csv, json, sys, urllib.request

API = "https://jlcpcb.com/api/overseas-pcb-order/v1/shoppingCart/smtGood/selectSmtComponentList"
BOARDS = int(sys.argv[1]) if len(sys.argv) > 1 else 2
# JLC Standard PCBA, single-sided (help/article/pcb-assembly-price, 2026): setup, stencil, panel, per-joint, per extended line.
# Standard is required: Economic stops at 0402 parts and 0.5 mm BGA pitch (this board has 0201s and 0.4 mm WCSPs).
SETUP, STENCIL, PANEL, EXT_FEE = 25.0, 7.86, 7.81, 3.0   # plus $0.0016 per solder joint


def jlc(code):
    req = urllib.request.Request(API, json.dumps({"keyword": code, "currentPage": 1, "pageSize": 5}).encode(),
                                 {"Content-Type": "application/json", "User-Agent": "Mozilla/5.0"})
    hits = json.load(urllib.request.urlopen(req, timeout=20))["data"]["componentPageInfo"]["list"] or []
    return next((c for c in hits if c["componentCode"] == code), None)


rows = list(csv.DictReader(open("out/jlc-bom.csv")))
lines, per_board, ext = [], 0.0, 0
for r in rows:
    c, n = jlc(r["LCSC Part #"]), len(r["Designator"].split(","))
    unit = (c.get("componentPrices") or [{}])[0].get("productPrice") or 0
    extended = c["componentLibraryType"] == "expand" and not c.get("preferredComponentFlag")
    ext += extended; per_board += unit * n
    lines.append((r["Comment"][:16], r["Designator"][:30], r["LCSC Part #"], "extended" if extended else "basic/pref", n, unit, c["stockCount"]))
lines.sort(key=lambda l: -l[4] * l[5])
for l in lines:
    print(f"{l[0]:16s} {l[1]:30s} {l[2]:10s} {l[3]:10s} {l[4]:2d} x ${l[5]:.4f}  stock {l[6]}")
fees = SETUP + STENCIL + PANEL + EXT_FEE * ext
print(f"\n{len(rows)} BOM lines ({ext} extended), parts ${per_board:.2f}/board")
print(f"Standard PCBA fees: setup ${SETUP} + stencil ${STENCIL} + panel ${PANEL} + {ext} x ${EXT_FEE} extended = ${fees:.2f}")
print(f"{BOARDS} boards: parts ${per_board * BOARDS:.2f} + fees ${fees:.2f} = ${per_board * BOARDS + fees:.2f} (+ bare PCB, joints, shipping, tax)")
json.dump({"fees": fees, "per_board": per_board, "extended": ext, "lines": lines}, open("out/cost.json", "w"), indent=1)
