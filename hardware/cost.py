"""Live JLC cost estimate from out/jlc-bom.csv (run after build.sh): parts with JLC's attrition and minimum quantities,
plus the Standard PCBA fees (jlcpcb.com/help/article/pcb-assembly-price, updated 2026-09-09). The bare PCB and shipping
come from JLC's quote (see README).

    python3 cost.py [boards]      # default 2 assembled boards (one board per 70 x 70 mm frame)
"""
import csv, json, sys, urllib.request

API = "https://jlcpcb.com/api/overseas-pcb-order/v1/shoppingCart/smtGood/selectSmtComponentList"
BOARDS = int(sys.argv[1]) if len(sys.argv) > 1 else 2
# Standard PCBA is required: Economic allows only 0.8-1.6 mm boards, 0402 and up, 0.5 mm BGA pitch. On Standard every BOM
# line pays the feeder fee, basic and extended alike, so basic parts save nothing here.
SETUP, STENCIL, FEEDER, FIXTURES, CONFIRM, PACKING, JOINT = 25.56, 8.21, 1.53, 2 * 8.21, 0.45, 0.50, 0.0016
LEADLESS = ("QFN", "LGA", "DSBGA", "MIC-SMD")      # parts JLC X-rays: $1.64 each for 1-10, $0.82 for 11-50 per order


def jlc(code):
    req = urllib.request.Request(API, json.dumps({"keyword": code, "currentPage": 1, "pageSize": 5}).encode(),
                                 {"Content-Type": "application/json", "User-Agent": "Mozilla/5.0"})
    hits = json.load(urllib.request.urlopen(req, timeout=20))["data"]["componentPageInfo"]["list"] or []
    return next((c for c in hits if c["componentCode"] == code), None)


def buy(c, n):
    """JLC buys qty for all boards + its attrition, at least the line's minimum; price from the matching tier."""
    q = max(n * BOARDS + (c.get("lossNumber") or 0), c.get("leastPatchNumber") or 0, c.get("minPurchaseNum") or 0)
    tiers = sorted(c.get("componentPrices") or [{"startNumber": 1, "productPrice": 0}], key=lambda p: p["startNumber"])
    return q, q * next((p["productPrice"] for p in reversed(tiers) if q >= p["startNumber"]), tiers[0]["productPrice"])


def xray(pcs):
    return pcs * (1.64 if pcs <= 10 else 0.82 if pcs <= 50 else 0.49)


rows = list(csv.DictReader(open("out/jlc-bom.csv")))
lines, parts, xr = [], 0.0, 0
for r in rows:
    c, n = jlc(r["LCSC Part #"]), len(r["Designator"].split(","))
    q, cost = buy(c, n)
    parts += cost
    xr += n * any(k in r["Footprint"] for k in LEADLESS)
    lines.append((r["Comment"][:16], r["Designator"][:30], r["LCSC Part #"], c["componentLibraryType"], q, cost, c["stockCount"]))
lines.sort(key=lambda l: -l[5])
for l in lines:
    print(f"{l[0]:16s} {l[1]:30s} {l[2]:10s} {l[3]:7s} buy {l[4]:4d}  ${l[5]:7.3f}  stock {l[6]}")
fees = SETUP + STENCIL + FEEDER * len(rows) + FIXTURES + CONFIRM + PACKING + xray(xr * BOARDS)
print(f"\n{len(rows)} BOM lines; parts for {BOARDS} boards incl. attrition/minimums ${parts:.2f}")
print(f"Standard PCBA fees: setup {SETUP} + stencil {STENCIL} + {len(rows)} feeders x {FEEDER} + fixtures {FIXTURES} + "
      f"X-ray {xr * BOARDS} x + confirm/packing = ${fees:.2f} (+ ${JOINT}/joint)")
print(f"{BOARDS} boards assembled: ${parts + fees:.2f} + bare PCB + shipping + tax")
json.dump({"boards": BOARDS, "fees": round(fees, 2), "parts": round(parts, 2), "lines": lines}, open("out/cost.json", "w"), indent=1)
