"""Quasi-static Z0 / eps_eff of the RF feed trace cross-section (2D finite-difference Laplace solve).

  RF feed (U1 -> C11 -> L3 -> C12 -> AE1): F.Cu over In1 (0.0994 mm 3313 prepreg, er 4.1; same in the 0.8 and 0.6 mm
          JLC stacks), solder mask 20 um er 3.8. GCPW with 0.15 mm gaps to the F.Cu GND pour: 0.15 mm trace since
          2026-10-06 (0.20 before); microstrip = the 2026-10-04 board, which had no F.Cu pour along the feed.
Z0 = 1 / (c * sqrt(C * C_air)); eps_eff = C / C_air.
"""
import numpy as np
from scipy.sparse import coo_matrix
from scipy.sparse.linalg import spsolve

H = 0.005  # mm grid

def solve(eps, cond, fixed):
    """eps: cell permittivity grid; cond: bool mask of conductor cells; fixed: their potential. -> C/eps0 (per unit length)."""
    ny, nx = eps.shape
    idx = -np.ones(eps.shape, int); free = ~cond; idx[free] = np.arange(free.sum())
    rows, cols, vals = [], [], []; b = np.zeros(free.sum())
    for dy, dx in ((0, 1), (0, -1), (1, 0), (-1, 0)):
        e2 = np.roll(np.roll(eps, -dy, 0), -dx, 1); ef = 2 * eps * e2 / (eps + e2)   # face eps (harmonic mean)
        nb_cond = np.roll(np.roll(cond, -dy, 0), -dx, 1); nb_v = np.roll(np.roll(fixed, -dy, 0), -dx, 1)
        nb_idx = np.roll(np.roll(idx, -dy, 0), -dx, 1)
        edge = np.zeros_like(cond)   # domain boundary acts as ground (box is far enough)
        if dy == 1: edge[-1, :] = True
        if dy == -1: edge[0, :] = True
        if dx == 1: edge[:, -1] = True
        if dx == -1: edge[:, 0] = True
        m = free
        rows += [idx[m]]; cols += [idx[m]]; vals += [ef[m]]
        mi = m & ~nb_cond & ~edge
        rows += [idx[mi]]; cols += [nb_idx[mi]]; vals += [-ef[mi]]
        mb = m & nb_cond & ~edge
        np.add.at(b, idx[mb], ef[mb] * nb_v[mb])
    A = coo_matrix((np.concatenate(vals), (np.concatenate(rows), np.concatenate(cols)))).tocsr()
    phi = fixed.astype(float).copy(); phi[free] = spsolve(A, b)
    ex = np.diff(phi, axis=1); ey = np.diff(phi, axis=0)
    exf = 2 * eps[:, 1:] * eps[:, :-1] / (eps[:, 1:] + eps[:, :-1])
    eyf = 2 * eps[1:, :] * eps[:-1, :] / (eps[1:, :] + eps[:-1, :])
    return (exf * ex ** 2).sum() + (eyf * ey ** 2).sum()   # C/eps0 = 2W/V^2 (h cancels in 2D)

def z0(build):
    out = []
    for diel in (True, False):
        eps, cond, sig = build(diel)
        out.append(solve(eps, cond, sig))
    c, ca = out
    return 1 / (2.998e8 * 8.854e-12 * np.sqrt(c * ca)), c / ca

def grid(w, h):
    nx, ny = int(round(w / H)), int(round(h / H))
    y, x = np.mgrid[0:ny, 0:nx] * H + H / 2
    return x, y, np.ones((ny, nx)), np.zeros((ny, nx), bool), np.zeros((ny, nx))

def gcpw(diel, w=0.2, gap=0.15):   # x across, y up; In1 at y=0.2 (box bottom below is just more ground)
    x, y, eps, cond, sig = grid(3.0, 1.6)
    yi, yt, xc, t = 0.2, 0.3, 1.5, 0.035
    if diel:
        eps[(y > yi) & (y < yt)] = 4.1
        eps[(y >= yt) & (y < yt + t + 0.02)] = 3.8                       # mask (approx: conformal over everything)
    cond |= y <= yi
    lay = (y >= yt) & (y < yt + t)
    tr = (abs(x - xc) < w / 2) & lay
    cond |= (abs(x - xc) > w / 2 + gap) & lay
    cond |= tr; sig[tr] = 1
    return eps, cond, sig

def ms(diel, w=0.2):   # microstrip: no coplanar ground; bigger box so its walls stay out of the fringing field
    x, y, eps, cond, sig = grid(5.0, 3.0)
    yi, yt, xc, t = 0.2, 0.3, 2.5, 0.035
    if diel:
        eps[(y > yi) & (y < yt)] = 4.1
        eps[(y >= yt) & (y < yt + t + 0.02)] = 3.8
    cond |= y <= yi
    tr = (abs(x - xc) < w / 2) & (y >= yt) & (y < yt + t)
    cond |= tr; sig[tr] = 1
    return eps, cond, sig

if __name__ == "__main__":
    for w in (0.15, 0.20):
        z, ee = z0(lambda d: gcpw(d, w=w))
        print(f"RF feed {w:.2f}/0.15 GCPW: Z0 = {z:.1f} ohm, eps_eff = {ee:.2f}")
    z, ee = z0(ms)
    print(f"RF feed 0.20 microstrip: Z0 = {z:.1f} ohm, eps_eff = {ee:.2f}")
