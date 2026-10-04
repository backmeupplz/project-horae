"""Query JLC for in-stock 0201 C0G caps and 0201 RF inductors per value -> jlc_parts.json (best pick per value)."""
import json, re, urllib.request
API = "https://jlcpcb.com/api/overseas-pcb-order/v1/shoppingCart/smtGood/selectSmtComponentList"
CAPS = [0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 1.0, 1.1, 1.2, 1.3, 1.5, 1.6, 1.8, 2.0, 2.2, 2.4, 2.7, 3.0, 3.3, 3.6, 3.9, 4.3, 4.7, 5.1, 5.6, 6.2, 6.8, 7.5, 8.2, 10]
INDS = [0.6, 0.8, 1.0, 1.2, 1.5, 1.8, 2.0, 2.2, 2.4, 2.7, 3.0, 3.3, 3.6, 3.9, 4.3, 4.7, 5.1, 5.6, 6.2, 6.8, 7.5, 8.2, 9.1, 10, 12, 15]

def query(kw):
    req = urllib.request.Request(API, json.dumps({"keyword": kw, "currentPage": 1, "pageSize": 50}).encode(),
                                 {"Content-Type": "application/json"})
    return json.load(urllib.request.urlopen(req, timeout=30))["data"]["componentPageInfo"]["list"] or []

def fmt(v): return f"{v:g}"

def best(kw, unit, v):
    hits = []
    for c in query(kw):
        d = c.get("describe", "") + " " + (c.get("componentSpecificationEn") or "")
        m = re.search(r"(\d+(?:\.\d+)?)\s*" + unit + r"\b", c.get("describe", ""))
        if "0201" not in d or not m or abs(float(m.group(1)) - v) > 1e-6 or c["stockCount"] < 100: continue
        if unit == "pF" and not re.search(r"C0G|NP0", d): continue
        hits.append(c)
    hits.sort(key=lambda c: (c["componentLibraryType"] != "base", -c["stockCount"]))
    return [dict(lcsc=c["componentCode"], lib=c["componentLibraryType"], stock=c["stockCount"], desc=c["describe"][:110]) for c in hits[:3]]

if __name__ == "__main__":
    out = {"C": {fmt(v): best(f"{fmt(v)}pF 0201", "pF", v) for v in CAPS},
           "L": {fmt(v): best(f"{fmt(v)}nH 0201", "nH", v) for v in INDS}}
    json.dump(out, open("jlc_parts.json", "w"), indent=1)
    for k, d in out.items():
        print(k, "available:", [v for v, h in d.items() if h])
