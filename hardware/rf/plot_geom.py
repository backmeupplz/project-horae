"""Plot the extracted antenna-end copper (geom.json, or the file given) -> geom.png / <file>.png."""
import json, sys, matplotlib; matplotlib.use("Agg"); import matplotlib.pyplot as plt
src = sys.argv[1] if len(sys.argv) > 1 else "geom.json"
g = json.load(open(src))
fig, axs = plt.subplots(1, 2, figsize=(14, 8))
for ax, L in zip(axs, ["F.Cu", "In1.Cu"]):
    for p in g["outline"]: ax.plot(*zip(*p + p[:1]), "k-", lw=0.8)
    for p in g["fills"].get(L, []): ax.fill(*zip(*p), color="#9ab", alpha=0.6, lw=0)
    if L == "F.Cu":
        for p in g["ant"]: ax.fill(*zip(*p), color="#c84", lw=0)
        for n, ps in g["pads"].items():
            for p in ps: ax.fill(*zip(*p), color="r" if n == "1" else "g", lw=0)
        for t in g["tracks"]:
            if t["layer"] == "F.Cu": ax.plot([t["a"][0], t["b"][0]], [t["a"][1], t["b"][1]], "m-" if t["net"].startswith("RF") else "b-", lw=1)
        for f in g["fps"]: ax.annotate(f[0], (f[1], f[2]), fontsize=8)
    ax.set_xlim(104, 119.5); ax.set_ylim(109, 91); ax.set_aspect("equal"); ax.set_title(L); ax.grid(alpha=.3)
plt.tight_layout(); plt.savefig(src[:-5] + ".png", dpi=110)
