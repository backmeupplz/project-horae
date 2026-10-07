"""Case parts from cad/horae.py -> case/*.stl in the sim.py model frame, read by sim.py (env/wrist) as polyhedra.

Model frame: x as the CAD, y = KiCad y = -CAD y (KiCad Y points down), z from the PCB bottom (CAD z - spec.Z_PCB0).
Run on the host after any case change (writes nothing outside hardware/rf/case/):
  .venv/bin/python hardware/rf/case_stl.py
"""
import importlib.util, json, sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.argv = sys.argv[:1]                     # horae.py reads --thin from argv
spec = importlib.util.spec_from_file_location("horae", HERE.parents[1] / "cad" / "horae.py")
H = importlib.util.module_from_spec(spec); spec.loader.exec_module(H)
from build123d import Plane, Pos, export_stl, mirror

CP = H.case_parts()   # the CAD's installed case set (top shell with its touch pockets, bottom shell, soft parts)
PARTS = {  # stl -> (sim.py material, builder); display = sim.py's glass box, board = geom.json
    "top_shell": ("petg", lambda: CP["top_shell"]),
    "bottom_shell": ("petg", lambda: CP["bottom_shell"]),
    "tpu": ("tpu", lambda: H.union([CP[k] for k in H.SOFT if k != "vent"])),   # (the vent membrane is ~0.2 mm of ePTFE)
    "strap": ("strap", H.nato),
    "metal": ("pec", lambda: H.union([H.spring_bars(), H.rf_pin(), H.battery()[0], H.union(H.watch_magnets()),
                                      H.motor()[0]])),
}

if __name__ == "__main__":
    out = HERE / "case"; out.mkdir(exist_ok=True)
    for name, (_, build) in PARTS.items():
        s = Pos(0, 0, -H.S.Z_PCB0) * mirror(build(), Plane.XZ)
        export_stl(s, str(out / f"{name}.stl"), tolerance=0.01, angular_tolerance=0.2)
        bb = s.bounding_box()
        print(f"{name}: {s.volume:.1f} mm3, x {bb.min.X:.2f}..{bb.max.X:.2f} y {bb.min.Y:.2f}..{bb.max.Y:.2f} "
              f"z {bb.min.Z:.2f}..{bb.max.Z:.2f}")
    # the few CAD numbers sim.py meshes around (bar, strap, ears, shells)
    cad = dict(X_BAR=H.X_BAR, Z_BAR=H.Z_BAR - H.S.Z_PCB0, BAR_D=H.BAR_D, STRAP_R=H.STRAP_R, EAR_R=H.EAR_R,
               STRAP_W=H.STRAP_W, Z_LIP0=H.Z_LIP0 - H.S.Z_PCB0, Z_STEP=H.Z_STEP - H.S.Z_PCB0, Z_ROUND=H.Z_ROUND - H.S.Z_PCB0,
               SEAL_GAP=H.SEAL_GAP, materials={k: m for k, (m, _) in PARTS.items()})
    json.dump(cad, open(out / "case.json", "w"), indent=1)
    print(cad)
