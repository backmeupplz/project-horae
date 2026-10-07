#!/usr/bin/env python3
"""Assets for the landing page's 3D explorer (explorer/): every case, internal, strap and dock part as one named
GLB mesh with exact normals and box-mapped UVs, the board from KiCad's own GLB, the e-paper face, and
explorer/manifest.json (names, roles, explode offsets, colourways, finishes, board hotspots).

    .venv/bin/python cad/web.py

Frame: three.js / glTF (Y up). CAD (x, y, z) -> (x, z, -y), metres in the GLBs (the viewer scales to mm).
Meshes are meshopt-compressed with gltf-transform (npx, fetched on first run).
"""
import csv
import json
import subprocess
import sys
from pathlib import Path

import numpy as np
import trimesh

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "cad"))
import horae as H  # noqa: E402

S = H.S
OUT = ROOT / "explorer"
MODELS = OUT / "models"
GLTF_TRANSFORM = ["npx", "-y", "@gltf-transform/cli@4"]

# key -> (name, group, description); explode is (dx, dy, dz) in the viewer frame (y up), mm, at full explode
BATTERY = (f"LiPo pouch {S.BAT_T:g} x 15 x 18-19 mm with protection, 40-55 mAh; its two wire leads (red +, black -) "
           f"are soldered to two pads.")
USB = ("Adafruit 6050 sunken USB-C breakout with 5.1k CC pull-downs, so any USB-C charger gives 5 V; 4 short wires "
       "to the pins.")
PARTS = {
    "top_shell": ("Top shell", "Case", f"One PETG print: the {S.LIP:g} mm bezel lip, walls, the strap ears drilled for "
                  f"16 mm spring bars, and the snap recesses."),
    "bars": ("Spring bars", "Strap", "Standard 16 mm quick-release spring bars through the ears."),
    "rf_pin": ("Spring bars", "Strap", "Standard 16 mm quick-release spring bars through the ears."),
    "strap_l": ("Strap", "Strap", "Any two-piece 16 mm strap with spring-bar ends."),
    "strap_r": ("Strap", "Strap", "Any two-piece 16 mm strap with spring-bar ends."),
    "bezel_gasket": ("Bezel gasket", "Seals", f"TPU 90A, {S.BEZEL_GASKET:g} mm squeezed: seals the glass to the lip."),
    "vent": ("Mic vent", "Seals", "Hydrophobic membrane that lets sound in and keeps splashes out."),
    "display": ("E-paper display", "Display", f"Good Display GDEM0097T61: 0.97\" 184 x 88 e-paper, "
                f"{S.DISP_L:g} x {S.DISP_W:g} x {S.DISP_T:g} mm."),
    "fpc": ("Display ribbon", "Display", "Folds under the glass and plugs into the board's FH34SRJ connector."),
    "stiffener": ("Display ribbon", "Display", "Folds under the glass and plugs into the board's FH34SRJ connector."),
    "cushions": ("Glass cushions", "Seals", "Four TPU pads that press the glass up against the bezel gasket."),
    "mic_seal": ("Mic seal", "Seals", "Ring between the microphone and the duct to the outside."),
    "pcb": ("Main board", "Electronics", f"{S.PCB_L:g} x {S.PCB_W:g} x {S.PCB_T:g} mm, 4 layers, fully assembled by "
            f"JLCPCB: ESP32-S3, accelerometer, charger, buck regulator, e-paper booster, mic, touch pads, antenna."),
    "battery": ("Battery", "Electronics", BATTERY),
    "bat_lead_red": ("Battery", "Electronics", BATTERY),
    "bat_lead_black": ("Battery", "Electronics", BATTERY),
    "motor": ("Vibration motor", "Electronics", f"{S.MOTOR_D:g} x {S.MOTOR_T:g} mm coin motor (Vybronics "
              f"VC0625B001L), leads soldered to the board."),
    "motor_leads": ("Vibration motor", "Electronics", f"{S.MOTOR_D:g} x {S.MOTOR_T:g} mm coin motor (Vybronics "
                    f"VC0625B001L), leads soldered to the board."),
    "pogo_seals": ("Charging-pad seal", "Seals", "One TPU piece: a ring around each of the four charging pads, "
                   "joined by webs."),
    "bottom_seal": ("Shell seal ring", "Seals", "TPU 90A ring that seals between the two shells, sideways."),
    "bottom_shell": ("Bottom shell", "Case", f"One PETG print: the {S.FLOOR:g} mm floor, the motor pocket whose 4 "
                     f"sprung fingers grip the motor, and 4 snap bumps that click into the top shell."),
    "watch_magnets": ("Watch magnets", "Case", "Two 3 x 1 mm N52 magnets in the floor, one N and one S out, so the "
                      "watch only docks one way round."),
    "dock_base": ("Dock tray", "Dock", "PETG print: the floor, side lips that locate the watch, sockets for the "
                  "spring pins, magnet posts and pegs for the USB-C board."),
    "dock_lid": ("Dock lid", "Dock", "PETG plate that snaps into the tray: pin bores and magnet holes with a 0.1 mm "
                 "retaining lip. Nothing is glued."),
    "dock_pins": ("Spring pins", "Dock", "4 Mill-Max 0955 spring pins pressing about 42 g on each charging pad."),
    "dock_magnets": ("Dock magnets", "Dock", "4 x 3 x 3 mm N52: the watch snaps on the right way round; turned end for "
                     "end, it is pushed off."),
    "dock_usb": ("USB-C breakout", "Dock", USB),
    "dock_wires": ("USB-C breakout", "Dock", USB),
    "dock_feet": ("Grip pad", "Dock", "TPU 90A pad with 4 press-in stems, so the dock stays put on the desk."),
}
EXPLODE = {k: v[2] for k, v in H.EXPLODE.items()} | dict.fromkeys(("strap_l", "strap_r"), H.EXPLODE["bars"][2])
STRAP_DX = 8.0          # strap stubs also slide off the bars when exploded
DOCK_DY = -24.0         # the dock at full explode (it sits under the watch when assembled), plus H.DOCK_EXPLODE
HOTSPOTS = {  # board refs worth a label: ref -> label
    "U1": "ESP32-S3: Wi-Fi + Bluetooth LE", "J1": "Display connector", "U6": "LIS2DUX12 accelerometer",
    "MIC1": "PDM microphone", "U2": "BQ25101 charger", "U3": "TPS62840 buck regulator", "L4": "E-paper booster",
    "Y1": "40 MHz crystal", "Y2": "32 kHz clock crystal",
}


def to_view(p):
    """CAD (x, y, z) mm -> viewer (x, z, -y) mm."""
    p = np.asarray(p, float)
    return np.column_stack([p[..., 0], p[..., 2], -p[..., 1]]) if p.ndim == 2 else np.array([p[0], p[2], -p[1]])


def part_mesh(shape, name, tol=0.008):
    pm = H.pvmesh(shape, tol=tol)
    pts, nrm = np.asarray(pm.points), np.asarray(pm.point_data["Normals"])
    tri = np.asarray(pm.faces).reshape(-1, 4)[:, 1:]
    ax = np.abs(nrm).argmax(axis=1)                     # box mapping, 1 tile per 4 mm (same as the renders)
    uv = np.where(ax[:, None] == 2, pts[:, [0, 1]], np.where(ax[:, None] == 1, pts[:, [0, 2]], pts[:, [1, 2]])) / 4.0
    v, n = to_view(pts) / 1000.0, to_view(nrm)
    m = trimesh.Trimesh(vertices=v, faces=tri, vertex_normals=n, process=False)
    m.visual = trimesh.visual.TextureVisuals(uv=uv, material=trimesh.visual.material.PBRMaterial(
        name=name, baseColorFactor=[200, 200, 200, 255], metallicFactor=0.0, roughnessFactor=0.5))
    return m


def solids_by_side(shape):
    """Split a two-stub strap into its -X and +X halves."""
    neg, pos = [], []
    for s in shape.solids():
        (neg if s.center().X < 0 else pos).append(s)
    return H.union(neg), H.union(pos)


def export_case(m):
    scene = trimesh.Scene()
    manifest = []
    items = [(k, m[k]) for k in PARTS if k in m and k != "pcb" and not k.startswith("strap")]
    if m.get("strap") is not None:
        left, right = solids_by_side(m["strap"])
        items += [("strap_l", left), ("strap_r", right)]
    for key, shape in items:
        mesh = part_mesh(shape, key)
        role = H.ROLE.get(key, H.ROLE.get("strap") if key.startswith("strap") else "plastic")
        name, group, desc = PARTS[key]
        dy = EXPLODE.get(key, DOCK_DY + H.DOCK_EXPLODE.get(key, (0, 0, 0))[2] if group == "Dock" else 0)
        dx = -STRAP_DX if key == "strap_l" else STRAP_DX if key == "strap_r" else 0
        scene.add_geometry(mesh, node_name=key, geom_name=key)
        bb = shape.bounding_box()
        manifest.append(dict(key=key, name=name, group=group, desc=desc, role=role, explode=[dx, dy, 0],
                             tris=int(len(mesh.faces)), size=[round(bb.size.X, 2), round(bb.size.Y, 2), round(bb.size.Z, 2)]))
        print(f"  {key:14s} {len(mesh.faces):7d} tris")
    raw = MODELS / "case_raw.glb"
    raw.write_bytes(scene.export(file_type="glb", include_normals=True))
    return raw, manifest


def export_pcb():
    raw = MODELS / "pcb_raw.glb"
    subprocess.run([str(ROOT / "hardware" / "kicad"), "kicad-cli", "pcb", "export", "glb", "--subst-models",
                    "--include-pads", "--include-soldermask", "--include-silkscreen", "--force",
                    "-o", f"/work/explorer/models/{raw.name}", "horae.kicad_pcb"],
                   cwd=ROOT / "hardware", check=True, capture_output=True)
    return raw


def fix_kicad_materials(path):
    """KiCad's GLB writes sRGB colours into the (linear) baseColorFactor and omits metallic/roughness, which glTF then
    reads as fully metallic: convert the colours and make everything dielectric except the gold/copper finishes."""
    import struct
    data = path.read_bytes()
    jlen = struct.unpack("<I", data[12:16])[0]
    doc = json.loads(data[20:20 + jlen])
    lin = lambda c: c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4
    for m in doc.get("materials", []):
        pbr = m.setdefault("pbrMetallicRoughness", {})
        r, g, b, a = pbr.get("baseColorFactor", [1, 1, 1, 1])
        gold = r > 0.5 and r - b > 0.3
        pbr["baseColorFactor"] = [lin(r), lin(g), lin(b), max(a, 0.9) if a < 1 else a]
        if "metallicFactor" not in pbr:
            pbr["metallicFactor"], pbr["roughnessFactor"] = (1.0, 0.3) if gold else (0.0, 0.5)
    js = json.dumps(doc, separators=(",", ":")).encode()
    js += b" " * (-len(js) % 4)
    rest = data[20 + jlen:]
    out = struct.pack("<4sII", b"glTF", 2, 12 + 8 + len(js) + len(rest)) + struct.pack("<I4s", len(js), b"JSON") + js + rest
    path.write_bytes(out)


def compress(raw, out, whole=False):
    """meshopt + quantization. Case parts stay separate meshes (no dedup/join), the board may be merged."""
    if whole:
        fix_kicad_materials(raw)
        cmd = GLTF_TRANSFORM + ["optimize", str(raw), str(out), "--compress", "meshopt", "--simplify", "false",
                                "--palette", "false"]   # a lossy palette texture smears the part colours
    else:
        cmd = GLTF_TRANSFORM + ["meshopt", str(raw), str(out), "--level", "medium"]
    subprocess.run(cmd, check=True, capture_output=True)
    raw.unlink()
    print(f"  {out.name}: {out.stat().st_size / 1e6:.2f} MB")


def hotspots():
    """Board component positions from the JLC placement file: gerber frame, y up, board centre at (100, -100)."""
    spots = []
    for row in csv.DictReader(open(ROOT / "hardware" / "out" / "jlc-cpl.csv")):
        ref = row["Designator"]
        if ref in HOTSPOTS:
            x, y = float(row["Mid X"].rstrip("mm")) - 100, float(row["Mid Y"].rstrip("mm")) + 100
            spots.append(dict(ref=ref, label=HOTSPOTS[ref], pos=to_view((x, y, S.Z_PCB1 + 1.0)).round(3).tolist()))
    ant = (S.PCB_L / 2 - 2.9, 0.0, S.Z_PCB1)                       # antenna meander centre (gen_pcb pins it there)
    spots.append(dict(ref="AE1", label="2.4 GHz antenna (meander)", pos=to_view(ant).round(3).tolist()))
    for i, x in enumerate(S.TOUCH_X):
        spots.append(dict(ref=f"TCH{i}", label="Touch pad", pos=to_view((x, S.PCB_W / 2 - 1.1, S.Z_PCB1)).round(3).tolist()))
    return spots


def face_png():
    from PIL import Image
    tex = H.face_texture()
    img = Image.fromarray(np.asarray(tex.to_array()))
    img.save(OUT / "face.png", optimize=True)
    centre = to_view((H.AA_CX, 0.0, S.Z_DISP1 + 0.01))
    return dict(file="face.png", center=centre.round(3).tolist(), size=[S.DISP_AA_L, S.DISP_AA_W])


def main():
    MODELS.mkdir(parents=True, exist_ok=True)
    m, *_ = H.build()
    print("case parts:")
    raw, parts = export_case(m)
    compress(raw, MODELS / "case.glb")
    print("board:")
    compress(export_pcb(), MODELS / "pcb.glb", whole=True)
    parts.append(dict(key="pcb", name=PARTS["pcb"][0], group="Electronics", desc=PARTS["pcb"][2], role="pcb",
                      explode=[0, EXPLODE["pcb"], 0], size=[S.PCB_L, S.PCB_W, S.PCB_T + S.PART_H]))
    manifest = dict(
        units="mm", generated_from="cad/horae.py + hardware/horae.kicad_pcb (cad/web.py)",
        case=dict(L=S.CASE_L, W=S.CASE_W, T=round(S.CASE_T, 2)),
        files=dict(case="models/case.glb", pcb="models/pcb.glb"),
        pcb_offset=[-100.0, S.Z_PCB0, -100.0],          # KiCad GLB is in page coordinates, board bottom at y = 0
        face=face_png(), parts=parts, hotspots=hotspots(), hero=H.HERO,
        dock=dict(desk=round(H.dock_levels()["desk"], 2),
                  low=min((p["explode"][1] for p in parts if p["group"] == "Dock"), default=DOCK_DY)),
        colorways={k: dict(case=v[0], case_hex=v[1], case_finish=v[2], tpu=v[3], tpu_hex=v[4], tpu_finish=v[5],
                           strap=v[6], strap_hex=v[7], inserts=H.INSERTS.get(k)) for k, v in H.COLORWAYS.items()},
        finishes={k: dict(metallic=v[0], roughness=v[1], texture=v[2], opacity=v[3]) for k, v in H.FINISH.items()},
        tech={k: v for k, v in H.COLORS.items()},
    )
    (OUT / "manifest.json").write_text(json.dumps(manifest, indent=1))
    total = sum(f.stat().st_size for f in OUT.rglob("*") if f.is_file())
    print(f"explorer assets: {total / 1e6:.2f} MB in {OUT.relative_to(ROOT)}/")


if __name__ == "__main__":
    main()
