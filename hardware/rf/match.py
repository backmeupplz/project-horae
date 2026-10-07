"""Pi match (C11 shunt chip side, L3 series, C12 shunt antenna side) from the FDTD antenna impedance -> plots + report.

Circuit, chip pin -> antenna pad 1 on F.Cu over In1: chip -- l0 -- C11 -- l1 -- L3 -- l2 -- C12 -- l3 -- pad 1 edge (the
pad is in the FDTD). sim.py stores each run's feed (pour, trace width, l0..l3 along the tracks); Z0 / eps_eff from
lines.py: v4 0.15/0.15 GCPW 50.2 ohm / 3.20 (l = 1.457, 0.58, 0.58, 0.175 mm); v3 0.20/0.15 GCPW 43.9 / 3.21 (1.05,
0.5, 0.42, 1.215); v2 0.20 microstrip 46.5 / 3.28. Cap grounds: 0.1 nH into the pour (v2: C11 0.1, C12 0.2 nH).
Parts: 0201 C0G, ESL 0.2 nH, ESR 0.3 ohm; 0201 thick-film L, Q 20 at 2.44 GHz (R ~ sqrt f), C_par 0.08 pF.
Run on the host: ../../.venv/bin/python match.py SUFFIX [--plots DIR]
  SUFFIX e.g. _v3_trim6.64 -> results/{bare,env,wrist}_v3_trim6.64.npz; every results/{env,wrist}SUFFIX_*.npz (mesh,
  pours, ...) is evaluated as a robustness case. --plots DIR: rf-s11.png / rf-smith.png there. "As built" = the C11 /
  L3 / C12 values in ../design.py; --match C11/L3/C12 (e.g. 0.3/1.2/DNP) evaluates and plots those instead of the pick.
"""
import glob, itertools, json, os, re, sys
import numpy as np
import matplotlib; matplotlib.use("Agg"); import matplotlib.pyplot as plt

Z0, C0 = 50.0, 2.998e8
np.seterr(invalid="ignore")   # FDTD R dips below 0 at the 1.6 GHz excitation edge (bare): NaN there, never in band
FA, FB = 2.40e9, 2.48e9
PARTS = json.load(open("jlc_parts.json"))
CAPS = sorted(float(v) for v, h in PARTS["C"].items() if h)
INDS = sorted(float(v) for v, h in PARTS["L"].items() if h)
LINES = {(True, 0.15): (50.2, 3.20), (True, 0.2): (43.9, 3.21), (False, 0.2): (46.5, 3.28)}   # (pour, w): Z0, eps_eff
GND_L = {True: (0.1e-9, 0.1e-9), False: (0.1e-9, 0.2e-9)}   # C11 / C12 ground path, with / without the F.Cu pour
_d = open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "../design.py")).read()
NOW = tuple(float((re.search(rf'"{r}",\s*(?:"Device:L",\s*)?"([\d.]+|DNP)', _d).group(1)).replace("DNP", "0"))
            for r in ("C11", "L3", "C12"))           # rev A as built (design.py)

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
    return esr + 1j * w * (esl + lvia) + 1 / (1j * w * (c_pf or 1e-6) * 1e-12)   # 0 = DNP
def zind(f, l_nh, q=20.0, cpar=0.08e-12):
    w = 2 * np.pi * f; L = l_nh * 1e-9
    zl = w * L / q * np.sqrt(f / 2.44e9) + 1j * w * L    # R ~ sqrt(f) (skin) around the Q spec point
    return 1 / (1 / zl + 1j * w * cpar)

def chain(f, c, feed):
    pour, w, seg = feed
    (z, ee), (g11, g12) = LINES[pour, w], GND_L[pour]
    t = lambda l: tl(f, l, z, ee)
    return mm(t(seg[0]), sh(1 / zcap(f, c[0], lvia=g11)), t(seg[1]), ser(zind(f, c[1])), t(seg[2]),
              sh(1 / zcap(f, c[2], lvia=g12)), t(seg[3]))

def s11(z): return (z - Z0) / (z + Z0)
db = lambda g: 20 * np.log10(np.abs(g))

def feed_of(tag):   # (pour, trace width, line lengths) as stored by sim.py; older runs: v3 / v2 values
    d = np.load(f"results/{tag}.npz")
    if "feed_seg" in d:
        return bool(d["pour"]), round(float(d["feed_w"]), 3), tuple(float(v) for v in d["feed_seg"])
    return (bool(d["pour"]) if "pour" in d else "pour" in tag), 0.2, (1.05, 0.5, 0.42, 1.215)

def load(tag):
    d = np.load(f"results/{tag}.npz")
    eff = d["rad_eff"] if "rad_eff" in d else np.full(3, float(d["rad_eff_2g44"]))
    return d["f"], d["zin"], eff

def tloss_db(A, zl):
    """Transducer loss (dB) chip (50 ohm source) -> antenna terminals: mismatch + dissipation in the match parts."""
    il = 1 / zl
    vs = A[0, 0] + A[0, 1] * il + Z0 * (A[1, 0] + A[1, 1] * il)
    return -10 * np.log10(0.5 * np.real(il) / (np.abs(vs) ** 2 / (8 * Z0)))

def best(fs, zants, feed):
    """Minimax over the band and the environments of the transducer loss (a lossy match can look like a good S11).
    Discrete JLC values only. -> [(worst loss dB, worst S11 dB, C11, L3, C12)], best first."""
    band = (fs >= FA) & (fs <= FB); fb = fs[band]
    res = []
    for c in itertools.product(CAPS + [0.0], INDS, CAPS + [0.0]):
        A = chain(fb, c, feed)
        res.append((max(tloss_db(A, za[band]).max() for za in zants),
                    max(db(s11(zin(A, za[band]))).max() for za in zants)) + c)
    res.sort()
    return res

def bw(fs, g, lim=-10):
    ok = db(g) < lim
    i = np.argmin(np.abs(g)); lo = hi = i
    if not ok[i]: return None
    while lo > 0 and ok[lo - 1]: lo -= 1
    while hi < len(fs) - 1 and ok[hi + 1]: hi += 1
    return f"{fs[lo] / 1e9:.3f}-{fs[hi] / 1e9:.3f}"

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
    sfx = sys.argv[1]
    pdir = sys.argv[sys.argv.index("--plots") + 1] if "--plots" in sys.argv else None
    trim = sfx.split("trim")[1].split("_")[0]
    name = f", 0.6 mm board, trim {trim} mm"
    tags = [t for t in ("bare", "env", "wrist") if os.path.exists(f"results/{t}{sfx}.npz")]
    feed = feed_of(tags[0] + sfx)
    data = {t: load(t + sfx) for t in tags}
    variants = sorted(os.path.basename(p)[:-4] for p in glob.glob(f"results/env{sfx}_*.npz") + glob.glob(f"results/wrist{sfx}_*.npz"))
    fs = data[tags[0]][0]
    band = (fs >= FA) & (fs <= FB)
    M = lambda f, z, c, p=feed: zin(chain(f, c, p), z)
    rep = [f"# Antenna{sfx} at pad 1 (vs In1), 50 ohm reference; rad. eff. = P_rad / P_accepted at 2.40 / 2.44 / 2.48 GHz\n"]
    for t, (f, z, eff) in [(t, data[t]) for t in tags] + [(v, load(v)) for v in variants]:
        g = s11(z); i = np.argmin(np.abs(g)); x0 = f[np.where(np.diff(np.sign(z.imag)) > 0)[0]] / 1e9
        zs = ", ".join(f"{fx/1e9:.2f}: {np.interp(fx, f, z.real):.1f}{np.interp(fx, f, z.imag):+.1f}j" for fx in (FA, 2.44e9, FB))
        rep.append(f"{t}: X=0 rising at {np.round(x0, 3)} GHz; S11 min {db(g[i]):.1f} dB at {f[i]/1e9:.3f}; "
                   f"Z [{zs}]; rad. eff. {' / '.join(f'{e:.2f}' for e in eff)}")
    envs = [t for t in ("env", "wrist") if t in data] or tags
    r = best(fs, [data[t][1] for t in envs], feed)
    design = r[0][2:]
    if "--match" in sys.argv:   # evaluate / plot these values instead of the minimax pick, e.g. --match 0.3/1.2/DNP
        design = tuple(float(v.replace("DNP", "0")) for v in sys.argv[sys.argv.index("--match") + 1].split("/"))
    rep.append(f"\n## minimax over {envs}: top 8 (worst in-band transducer loss dB, worst S11 dB, C11 pF / L3 nH / C12 pF)")
    rep += [f"  {w:5.2f}  {ws:6.1f}  {a:g} / {b:g} / {c:g}" for w, ws, a, b, c in r[:8]]
    now = "/".join(f"{v:g}" if v else "DNP" for v in NOW)
    for lbl, c in (("--match" in sys.argv and "chosen" or "minimax pick", design), (f"rev A as built {now}", NOW)):
        for t in tags:
            z, eff = data[t][1], data[t][2]
            g = s11(M(fs, z, c)); tl_ = tloss_db(chain(fs, c, feed), z)
            tot = [eff[k] * 10 ** (-np.interp(fe, fs, tl_) / 10) for k, fe in enumerate((FA, 2.44e9, FB))]
            rep.append(f"  {lbl} -> {t}: band S11 {db(g[band]).max():.1f} .. {db(g[band]).min():.1f} dB; -10 dB band {bw(fs, g)}; "
                       f"worst in-band transducer loss {tl_[band].max():.2f} dB; total eff. (rad x transducer) "
                       f"{' / '.join(f'{e:.2f}' for e in tot)}")
    rep.append("\nrobustness of these values (band worst S11 dB): antenna resonance -3% / +3%; parts at tolerance "
               "(C +-0.1 pF, L +-max(5%, 0.1 nH)); model variants")
    c11, l3, c12 = design
    dl = max(0.05 * l3, 0.1)
    for t in envs:
        z = data[t][1]; out = []
        for k in (0.97, 1.03):   # resonance shift by k: Z_new(f) = Z(f / k)
            zs = np.interp(fs / k, fs, z.real) + 1j * np.interp(fs / k, fs, z.imag)
            out.append(f"{db(s11(M(fs, zs, design)))[band].max():.1f}")
        corners = [db(s11(M(fs, z, (max(c11 + a, 0), l3 + b, max(c12 + c, 0)))))[band].max()
                   for a in (-0.1, 0.1) for b in (-dl, dl) for c in ((-0.1, 0.1) if c12 else (0,))]
        rep.append(f"  {t}: shift {out[0]} / {out[1]}; part corners worst {max(corners):.1f}")
    for v in variants:
        f, z, eff = load(v); p = feed_of(v)
        g = s11(M(f, z, design, p)); tl_ = tloss_db(chain(f, design, p), z)
        rep.append(f"  {v}: band S11 {db(g[band]).max():.1f} .. {db(g[band]).min():.1f} dB; worst transducer loss "
                   f"{tl_[band].max():.2f} dB; rad. eff. {' / '.join(f'{e:.2f}' for e in eff)}")
    pick = lambda kind, v: (PARTS[kind][f"{v:g}"] or [{}])[0] if v else {"lcsc": "DNP"}
    rep.append(f"\nC11 {c11:g} pF {pick('C', c11)}\nL3  {l3:g} nH {pick('L', l3)}\nC12 {c12:g} pF {pick('C', c12)}")
    open(f"results/report{sfx}.txt", "w").write("\n".join(rep) + "\n"); print("\n".join(rep))

    # ---- plots: antenna alone (dotted), with the recommended match (solid), rev A as built on this board (dash-dot)
    col = {"bare": "#1f77b4", "env": "#d62728", "wrist": "#2ca02c"}
    lab = {"bare": "bare board", "env": "in case", "wrist": "in case, on wrist"}
    before = {t: data[t][:2] for t in envs} if tuple(design) != NOW else {}   # same antenna, as-built values
    out = lambda n: os.path.join(pdir, f"{n}.png") if pdir else f"{n}{sfx}.png"
    fig, ax = plt.subplots(figsize=(8, 4.8))
    ax.axvspan(FA / 1e9, FB / 1e9, color="0.92"); ax.axhline(-10, color="0.6", ls="--", lw=0.8)
    for t, (f, z, _) in data.items():
        k = (f >= 2e9) & (f <= 3e9)
        ax.plot(f[k] / 1e9, db(s11(z[k])), color=col[t], ls=":", label=f"{lab[t]}: antenna alone")
        ax.plot(f[k] / 1e9, db(s11(M(f[k], z[k], design))), color=col[t], label=f"{lab[t]}: with match")
    for t, (f, z) in before.items():
        k = (f >= 2e9) & (f <= 3e9)
        ax.plot(f[k] / 1e9, db(s11(M(f[k], z[k], NOW))), color=col[t], ls="-.", lw=1,
                label=f"{lab[t]}: before (rev A as built: {now})")
    ax.set_xlabel("frequency (GHz)"); ax.set_ylabel("S11 (dB, 50 Ω)"); ax.set_ylim(-30, 0); ax.set_xlim(2, 3)
    parts = f"C11 {c11:g} pF / L3 {l3:g} nH / C12 {f'{c12:g} pF' if c12 else 'DNP'}"
    ax.set_title(f"Horae antenna{name} (openEMS FDTD); match {parts}", fontsize=10)
    ax.legend(fontsize=7, loc="lower right"); ax.grid(alpha=0.3); fig.tight_layout(); fig.savefig(out("rf-s11"), dpi=130)

    fig, ax = plt.subplots(figsize=(7, 7.4)); smith(ax)
    for t, (f, z, _) in data.items():
        k = (f >= 2e9) & (f <= 3e9); b = (f >= FA) & (f <= FB)
        g0 = s11(z); g1 = s11(M(f, z, design))
        ax.plot(g0[k].real, g0[k].imag, color=col[t], ls=":", lw=1, label=f"{lab[t]}: antenna, 2-3 GHz")
        ax.plot(g0[b].real, g0[b].imag, color=col[t], lw=3, alpha=0.45)
        ax.plot(g1[k].real, g1[k].imag, color=col[t], lw=1, label=f"{lab[t]}: matched, at chip pin")
        ax.plot(g1[b].real, g1[b].imag, color=col[t], lw=3.5)
    for t, (f, z) in before.items():
        b = (f >= FA) & (f <= FB); g = s11(M(f, z, NOW))
        ax.plot(g[b].real, g[b].imag, color=col[t], ls="-.", lw=1.5, label=f"{lab[t]}: before (rev A as built), band")
    ax.plot([], [], color="k", lw=3.5, label="thick = 2.40-2.48 GHz")
    ax.legend(fontsize=7, loc="upper left", bbox_to_anchor=(-0.02, 1.0), framealpha=0.9)
    ax.set_title(f"Smith, 50 Ω{name}: {'before / after ' if before else 'with '}{parts}", fontsize=10)
    fig.tight_layout(); fig.savefig(out("rf-smith"), dpi=130)
