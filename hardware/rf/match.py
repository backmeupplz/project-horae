"""Pi match (C11 shunt chip side, L3 series, C12 shunt antenna side) from the FDTD antenna impedance -> plots + report.

Circuit, chip pin -> antenna pad 1, hand-routed F.Cu 0.20/0.15 GCPW (Z0 43.9 ohm, eps_eff 3.21 from lines.py;
lengths from geom.json):  chip -- 1.05 mm -- C11 -- 0.5 mm -- L3 -- 0.42 mm -- C12 -- 2.4 mm -- antenna pad 1
Parts: 0201 C0G, ESL 0.2 nH, ESR 0.3 ohm, + 0.1 nH to In1 through the GND pad vias; 0201 thick-film L, Q 20 at
2.44 GHz (R ~ sqrt f), C_par 0.08 pF.
Run on the host: ../../.venv/bin/python match.py [tag suffix, e.g. _dl-2.0]
"""
import itertools, json
import numpy as np
import matplotlib; matplotlib.use("Agg"); import matplotlib.pyplot as plt

Z0, C0 = 50.0, 2.998e8
FA, FB = 2.40e9, 2.48e9
PARTS = json.load(open("jlc_parts.json"))
CAPS = sorted(float(v) for v, h in PARTS["C"].items() if h)
INDS = sorted(float(v) for v, h in PARTS["L"].items() if h)
LINE = (43.9, 3.21)    # lines.py

def tl(f, l_mm, z, ee):
    b = 2 * np.pi * f * np.sqrt(ee) / C0 * l_mm * 1e-3
    return np.array([[np.cos(b), 1j * z * np.sin(b)], [1j * np.sin(b) / z, np.cos(b)]])

def ser(Z): Z = np.asarray(Z, complex); o = np.ones_like(Z); return np.array([[o, Z], [0 * o, o]])
def sh(Y): Y = np.asarray(Y, complex); o = np.ones_like(Y); return np.array([[o, 0 * o], [Y, o]])
def mm(*ms):
    out = ms[0]
    for m in ms[1:]: out = np.einsum("ij...,jk...->ik...", out, m)
    return out
def zin(abcd, zl):
    return (abcd[0, 0] * zl + abcd[0, 1]) / (abcd[1, 0] * zl + abcd[1, 1])

def zcap(f, c_pf, esl=0.2e-9, esr=0.3, lvia=0.1e-9):
    w = 2 * np.pi * f
    return esr + 1j * w * (esl + lvia) + 1 / (1j * w * c_pf * 1e-12)
def zind(f, l_nh, q=20.0, cpar=0.08e-12):
    w = 2 * np.pi * f; L = l_nh * 1e-9
    zl = w * L / q * np.sqrt(f / 2.44e9) + 1j * w * L    # R ~ sqrt(f) (skin) around the Q spec point
    return 1 / (1 / zl + 1j * w * cpar)

def chain(f, c11, l3, c12):
    t = lambda l: tl(f, l, *LINE)
    return mm(t(1.05), sh(1 / zcap(f, c11)), t(0.5), ser(zind(f, l3)), t(0.42), sh(1 / zcap(f, c12)), t(2.4))

def net_loss_db(f, zl, c):
    """Dissipation in the match parts (dB) = P_in / P_load for the given load."""
    A = chain(f, c[0] or 1e-6, c[1], c[2] or 1e-6); il = 1 / zl
    vi, ii = A[0, 0] + A[0, 1] * il, A[1, 0] + A[1, 1] * il
    return 10 * np.log10(np.real(vi * np.conj(ii)) / np.real(np.conj(il)))

def s11(z): return (z - Z0) / (z + Z0)
db = lambda g: 20 * np.log10(np.abs(g))

def load(tag):
    d = np.load(f"results/{tag}.npz"); return d["f"], d["zin"], float(d["rad_eff_2g44"])

def tloss_db(A, zl):
    """Transducer loss (dB) chip (50 ohm source) -> antenna terminals: mismatch + dissipation in the match parts."""
    il = 1 / zl
    vs = A[0, 0] + A[0, 1] * il + Z0 * (A[1, 0] + A[1, 1] * il)
    return -10 * np.log10(0.5 * np.real(il) / (np.abs(vs) ** 2 / (8 * Z0)))

def best(fs, zants, weights):
    """Minimax over the band of the transducer loss (a lossy match can look like a good S11), weighted over
    environments. Discrete JLC values only. -> [(worst loss dB, worst S11 dB, C11, L3, C12)], best first."""
    band = (fs >= FA) & (fs <= FB); fb = fs[band]
    res = []
    for c11, l3, c12 in itertools.product(CAPS + [0.0], INDS, CAPS + [0.0]):
        A = chain(fb, c11 or 1e-6, l3, c12 or 1e-6)
        worst = max(w * tloss_db(A, za[band]).max() for za, w in zip(zants, weights))
        ws = max(db(s11(zin(A, za[band]))).max() for za in zants)
        res.append((worst, ws, c11, l3, c12))
    res.sort()
    return res

def bw(fs, g, lim=-10):
    ok = db(g) < lim
    if not ok.any(): return None
    i = np.argmin(np.abs(g)); lo = hi = i
    while lo > 0 and ok[lo - 1]: lo -= 1
    while hi < len(fs) - 1 and ok[hi + 1]: hi += 1
    return (fs[lo] / 1e9, fs[hi] / 1e9) if ok[i] else None

def smith(ax):
    t = np.linspace(0, 2 * np.pi, 400)
    ax.plot(np.cos(t), np.sin(t), "k", lw=0.8)
    for r in (0.2, 0.5, 1, 2, 5):
        ax.plot(r / (1 + r) + np.cos(t) / (1 + r), np.sin(t) / (1 + r), color="0.85", lw=0.6)
    for x in (0.2, 0.5, 1, 2, 5):
        for s in (1, -1):
            g = s11(Z0 * (np.linspace(0, 50, 2000) + 1j * s * x)); ax.plot(g.real, g.imag, color="0.85", lw=0.6)
    ax.plot([-1, 1], [0, 0], color="0.85", lw=0.6)
    t = np.linspace(0, 2 * np.pi, 200); r = 10 ** (-10 / 20)
    ax.plot(r * np.cos(t), r * np.sin(t), "--", color="0.6", lw=0.8, label="|S11| = -10 dB")
    ax.set_aspect("equal"); ax.set_xlim(-1.05, 1.05); ax.set_ylim(-1.05, 1.05); ax.axis("off")

if __name__ == "__main__":
    import os, sys
    sfx = sys.argv[1] if len(sys.argv) > 1 else ""
    name = f" (meander trimmed {sfx.split('trim')[1]} mm)" if "trim" in sfx else " (as drawn)"
    tags = [t for t in ("bare", "env", "wrist") if os.path.exists(f"results/{t}{sfx}.npz")]
    data = {t: load(t + sfx) for t in tags}
    fs = data[tags[0]][0]
    M = lambda f, z, c: zin(chain(f, c[0] or 1e-6, c[1], c[2] or 1e-6), z)
    band = (fs >= FA) & (fs <= FB)
    rep = [f"# Antenna{sfx or ''} at pad 1 (vs In1), 50 ohm reference\n"]
    for t, (f, z, eff) in data.items():
        g = s11(z); i = np.argmin(np.abs(g)); x0 = f[np.where(np.diff(np.sign(z.imag)) > 0)[0]] / 1e9
        zs = ", ".join(f"{fx/1e9:.2f}: {np.interp(fx, f, z.real):.1f}{np.interp(fx, f, z.imag):+.1f}j"
                       for fx in (FA, 2.44e9, FB))
        rep.append(f"{t}: series resonance (X=0, rising) at {np.round(x0, 3)} GHz; S11 min {db(g[i]):.1f} dB at "
                   f"{f[i]/1e9:.3f} GHz; -10 dB band {bw(f, g)}; Z [{zs}]; rad. eff. @2.44 {eff:.2f}")
    envs = [t for t in ("env", "wrist") if t in data] or tags
    r = best(fs, [data[t][1] for t in envs], [1.0] * len(envs))
    design = r[0][2:]
    rep.append(f"\n## minimax over {envs}: top 8 (worst in-band transducer loss dB, worst S11 dB, C11 pF / L3 nH / C12 pF)")
    rep += [f"  {w:5.2f}  {ws:6.1f}  {a:g} / {b:g} / {c:g}" for w, ws, a, b, c in r[:8]]
    for lbl, c in (("recommended", design), ("Watchy 3/7.5/3", (3.0, 7.5, 3.0))):
        for t in tags:
            g = s11(M(fs, data[t][1], c))
            rep.append(f"  {lbl} -> {t}: band S11 worst {db(g[band]).max():.1f} dB, best {db(g[band]).min():.1f}; "
                       f"-10 dB band {bw(fs, g)}; worst mismatch loss {-10*np.log10(1-np.abs(g[band]).max()**2):.2f} dB; "
                       f"part loss @2.44 {np.interp(2.44e9, fs, net_loss_db(fs, data[t][1], c)):.2f} dB; "
                       f"worst in-band transducer loss {tloss_db(chain(fs[band], c[0] or 1e-6, c[1], c[2] or 1e-6), data[t][1][band]).max():.2f} dB")
    rep.append("\nrobustness of the recommended values (band worst S11 dB): antenna resonance shifted -3% / +3%, parts at tolerance")
    for t in envs:
        z = data[t][1]; out = []
        for k in (0.97, 1.03):   # resonance shift by k: Z_new(f) = Z(f / k)
            zs = np.interp(fs / k, fs, z.real) + 1j * np.interp(fs / k, fs, z.imag)
            out.append(f"{db(s11(M(fs, zs, design)))[band].max():.1f}")
        c11, l3, c12 = design
        corners = [db(s11(M(fs, z, (max(c11 + a, 0), l3 * (1 + b), max(c12 + c, 0)))))[band].max()
                   for a in (-0.1, 0.1) for b in (-0.05, 0.05) for c in (-0.1, 0.1)]
        rep.append(f"  {t}: shift {out[0]} / {out[1]}; C +-0.1 pF, L +-5% corners worst {max(corners):.1f}")
    pick = lambda kind, v: (PARTS[kind][f"{v:g}"] or [{}])[0] if v else {"lcsc": "DNP"}
    c11, l3, c12 = design
    rep.append(f"\nC11 {c11:g} pF {pick('C', c11)}\nL3  {l3:g} nH {pick('L', l3)}\nC12 {c12:g} pF {pick('C', c12)}")
    open(f"results/report{sfx}.txt", "w").write("\n".join(rep) + "\n"); print("\n".join(rep))

    # ---- plots
    col = {"bare": "#1f77b4", "env": "#d62728", "wrist": "#2ca02c"}
    lab = {"bare": "bare board", "env": "in case", "wrist": "in case, on wrist"}
    fig, ax = plt.subplots(figsize=(8, 4.8))
    ax.axvspan(FA / 1e9, FB / 1e9, color="0.92"); ax.axhline(-10, color="0.6", ls="--", lw=0.8)
    for t, (f, z, _) in data.items():
        k = (f >= 2e9) & (f <= 3e9)
        ax.plot(f[k] / 1e9, db(s11(z[k])), color=col[t], ls=":", label=f"{lab[t]}: antenna alone")
        ax.plot(f[k] / 1e9, db(s11(M(f[k], z[k], design))), color=col[t], label=f"{lab[t]}: with match")
    if sfx and os.path.exists("results/env.npz"):   # reference: the antenna as drawn (untrimmed), in case
        f, z, _ = load("env"); k = (f >= 2e9) & (f <= 3e9)
        ax.plot(f[k] / 1e9, db(s11(z[k])), color="0.5", ls="-.", label="as drawn (untrimmed), in case: antenna alone")
    ax.set_xlabel("frequency (GHz)"); ax.set_ylabel("S11 (dB, 50 Ω)"); ax.set_ylim(-30, 0); ax.set_xlim(2, 3)
    ax.set_title(f"Horae antenna{name}, openEMS FDTD; match C11 {c11:g} pF / L3 {l3:g} nH / C12 {c12:g} pF", fontsize=10)
    ax.legend(fontsize=7, loc="lower right"); ax.grid(alpha=0.3); fig.tight_layout(); fig.savefig(f"rf-s11{sfx}.png", dpi=130)

    fig, ax = plt.subplots(figsize=(7, 7.4)); smith(ax)
    for t, (f, z, _) in data.items():
        k = (f >= 2e9) & (f <= 3e9); b = (f >= FA) & (f <= FB)
        g0 = s11(z); g1 = s11(M(f, z, design))
        ax.plot(g0[k].real, g0[k].imag, color=col[t], ls=":", lw=1, label=f"{lab[t]}: antenna, 2-3 GHz")
        ax.plot(g0[b].real, g0[b].imag, color=col[t], lw=3, alpha=0.45)
        ax.plot(g1[k].real, g1[k].imag, color=col[t], lw=1, label=f"{lab[t]}: matched, at chip pin")
        ax.plot(g1[b].real, g1[b].imag, color=col[t], lw=3.5)
    if sfx and os.path.exists("results/env.npz"):
        f, z, _ = load("env"); k = (f >= 2e9) & (f <= 3e9); b = (f >= FA) & (f <= FB); g0 = s11(z)
        ax.plot(g0[k].real, g0[k].imag, color="0.5", ls="-.", lw=1, label="as drawn (untrimmed), in case: antenna")
        ax.plot(g0[b].real, g0[b].imag, color="0.5", lw=3, alpha=0.6)
    ax.plot([], [], color="k", lw=3.5, label="thick = 2.40-2.48 GHz")
    ax.legend(fontsize=7, loc="upper left", bbox_to_anchor=(-0.02, 1.0), framealpha=0.9)
    ax.set_title(f"Smith{name}, 50 Ω: before / after C11 {c11:g} pF, L3 {l3:g} nH, C12 {c12:g} pF", fontsize=10)
    fig.tight_layout(); fig.savefig(f"rf-smith{sfx}.png", dpi=130)
