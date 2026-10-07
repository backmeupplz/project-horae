#!/bin/sh
# Rebuild everything from design.py + spec.py: schematic, ERC, placement, staged autoroute, pours, DRC, JLC probe, STEP,
# gerbers, BOM/CPL, 1-up assembly panel, renders.
set -e
cd "$(dirname "$0")"
JAVA=$(ls -d "$HOME"/.local/jdk/jdk-25*/Contents/Home 2>/dev/null | head -1)/bin/java
FR="$HOME/.local/freerouting/freerouting.jar"
mkdir -p out

./kicad python3 gen_sch.py
./kicad kicad-cli sch erc --format json --severity-all -o out/erc.json horae.kicad_sch >/dev/null
./kicad kicad-cli sch export pdf -o out/horae-schematic.pdf horae.kicad_sch >/dev/null

# Staged Freerouting. Stage 1 routes the four touch traces alone (B.Cu, 0.3 mm class); every later stage sees the earlier
# copper as locked (stage.py) and routes its group; the last stage routes all remaining signals (GND is pours + vias).
# Deterministic: gen_pcb/stage.py seed KiCad's UUIDs (stable DSN order) and the optimiser runs on one thread. The first
# plan that leaves no signal unrouted wins.
fr() { rm -f "$2"; "$JAVA" -Djava.awt.headless=true -jar "$FR" -de "$1" -do "$2" -mp "$3" -mt 1 --gui.enabled=false > "$4" 2>&1 < /dev/null; sleep 1; }
unrouted() { grep -E "^\s+Net '" "$1" | grep -vc "Net 'GND'" || true; }   # grep -c exits 1 on a perfect route
EPD="EPD_MOSI EPD_SCK EPD_CS EPD_DC EPD_RES EPD_BUSY"
REST="PREVGL PREVGH +3V3 CHG_STAT VIB I2C_SCL I2C_SDA USB_DM USB_DP BAT_ADC USB_DP_POGO USB_DM_POGO MOT_N VBAT TXD0 RXD0 EN BOOT"
n=1; plan_no=0
for plan in "$EPD $REST" "$EPD|$REST" "PREVGL PREVGH|+3V3 $EPD CHG_STAT VIB I2C_SCL I2C_SDA USB_DM USB_DP BAT_ADC USB_DP_POGO USB_DM_POGO MOT_N VBAT TXD0 RXD0 EN BOOT" \
            "+3V3|PREVGL PREVGH $EPD CHG_STAT VIB I2C_SCL I2C_SDA USB_DM USB_DP BAT_ADC USB_DP_POGO USB_DM_POGO MOT_N VBAT TXD0 RXD0 EN BOOT"; do
  plan_no=$((plan_no + 1))
  ./kicad python3 gen_pcb.py
  python3 dsn_only.py out/horae.dsn out/stage1.dsn TOUCH_UP_E TOUCH_DOWN_E TOUCH_MENU_E TOUCH_BACK_E > /dev/null
  fr out/stage1.dsn out/stage1.ses 40 out/stage1.log
  ./kicad python3 stage.py out/stage1.ses < /dev/null
  i=2; IFS='|'
  for grp in $plan; do
    IFS=' '
    python3 dsn_only.py out/horae.dsn out/stage$i.dsn $grp > /dev/null
    fr out/stage$i.dsn out/stage$i.ses 60 out/stage$i.log
    ./kicad python3 stage.py out/stage$i.ses < /dev/null
    i=$((i + 1)); IFS='|'
  done
  IFS=' '
  python3 dsn_only.py out/horae.dsn out/stage9.dsn --except GND > /dev/null
  fr out/stage9.dsn out/horae.ses 80 out/freerouting.log
  n=$(unrouted out/freerouting.log)
  poured=0
  if [ "$n" -eq 0 ]; then   # routed: pours, stitching, then DRC decides (Freerouting can leave a conflict it reports as routed)
    ./kicad python3 route.py; poured=1
    ./kicad kicad-cli pcb drc --format json --severity-all -o out/drc.json horae.kicad_pcb >/dev/null
    n=$(python3 -c "import json; d = json.load(open('out/drc.json')); print(len(d['violations']) + len(d.get('unconnected_items', [])))")
    echo "router plan $plan_no: routed, $n DRC items"
  else
    echo "router plan $plan_no: $n signal connections unrouted"
  fi
  [ "$n" -eq 0 ] && break
done
grep -E "Optimization stage completed" out/freerouting.log | sed -E 's/.*(final score)/router \1/' | cut -c1-70
if [ "$poured" = 0 ]; then   # no plan routed everything: finish the last one anyway so the summary shows what is left
  ./kicad python3 route.py
  ./kicad kicad-cli pcb drc --format json --severity-all -o out/drc.json horae.kicad_pcb >/dev/null
fi

# JLC probes on copies of the board: "jlc" holds every rule at JLC's multilayer limit (must report nothing); "min" uses
# deliberately impossible rules so the violations report the real minimums (KiCad caps each list, so they are indicative)
probe() {   # name, rules...
  d=out/probe-$1; rm -rf $d && mkdir -p $d && cp horae.kicad_pcb $d/p.kicad_pcb && cp horae.kicad_pro $d/p.kicad_pro
  shift; printf '%s\n' '(version 1)' "$@" > $d/p.kicad_dru
  ./kicad kicad-cli pcb drc --format json --severity-all -o $d/drc.json $d/p.kicad_pcb >/dev/null
}
probe jlc '(rule c (constraint clearance (min 0.09mm)))' '(rule h (constraint hole_clearance (min 0.2mm)))' \
  '(rule hh (constraint hole_to_hole (min 0.2mm)))' '(rule e (constraint edge_clearance (min 0.2mm)))' \
  '(rule w (constraint track_width (min 0.09mm)))' '(rule r (constraint annular_width (min 0.05mm)))' \
  "(rule smd (condition \"A.Type == 'Pad' && B.Type == 'Pad' && A.Pad_Type == 'SMD' && B.Pad_Type == 'SMD'\") (constraint clearance (min 0.15mm)))"
probe min '(rule c (constraint clearance (min 0.25mm)))' '(rule h (constraint hole_clearance (min 0.45mm)))' \
  '(rule hh (constraint hole_to_hole (min 0.7mm)))' '(rule e (constraint edge_clearance (min 0.8mm)))' \
  '(rule w (constraint track_width (min 0.25mm)))' '(rule r (constraint annular_width (min 0.2mm)))'

./kicad kicad-cli pcb export step --subst-models --force -o out/horae.step horae.kicad_pcb >/dev/null
LAYERS=F.Cu,In1.Cu,In2.Cu,B.Cu,F.Paste,F.Silkscreen,B.Silkscreen,F.Mask,B.Mask,Edge.Cuts   # no B.Paste: nothing on the bottom
gerbers() {   # board, dir, zip
  rm -rf "$2" && mkdir -p "$2"
  ./kicad kicad-cli pcb export gerbers --layers $LAYERS -o "$2/" "$1" >/dev/null
  ./kicad kicad-cli pcb export drill --format excellon --excellon-separate-th -o "$2/" "$1" >/dev/null
  (cd "$2" && rm -f "$3" && zip -q "$3" *)
}
gerbers horae.kicad_pcb out/gerbers ../horae-gerbers.zip
./kicad python3 fab.py
./kicad python3 panel.py
gerbers out/panel/horae-panel.kicad_pcb out/panel/gerbers ../../panel-gerbers.zip
./kicad python3 fab.py out/panel/horae-panel.kicad_pcb out/jlc-cpl-panel.csv
for side in top bottom; do
  ./kicad kicad-cli pcb render --side $side --width 2000 --height 1000 --quality high -o out/pcb-$side.png horae.kicad_pcb >/dev/null
done
./kicad kicad-cli pcb render --rotate "-35,0,25" --zoom 1.1 --width 2000 --height 1200 --quality high -o out/pcb-3d.png horae.kicad_pcb >/dev/null
./kicad kicad-cli pcb render --side top --width 1400 --height 1400 --quality basic -o out/panel-top.png out/panel/horae-panel.kicad_pcb >/dev/null
python3 - <<'EOF'
import json, collections, re
e = json.load(open("out/erc.json")); d = json.load(open("out/drc.json"))
erc = sum(len(s["violations"]) for s in e["sheets"])
errs = [v for v in d["violations"] if v["severity"] == "error"]
print(f"ERC {erc} | DRC errors {len(errs)}, warnings {len(d['violations']) - len(errs)}, unconnected {len(d.get('unconnected_items', []))}")
for (t, n) in collections.Counter(v["type"] for v in errs).most_common():
    print(f"  {n:3d} {t}")
# JLC probes
TYPES = ("clearance", "hole_clearance", "hole_to_hole", "copper_edge_clearance", "track_width", "annular_width")
bad = [v for v in json.load(open("out/probe-jlc/drc.json"))["violations"] if v["type"] in TYPES]
mins = collections.defaultdict(lambda: 9.0)
for v in json.load(open("out/probe-min/drc.json"))["violations"]:
    m = re.search(r"actual ([0-9.]+) mm", v["description"])
    if m and v["type"] in TYPES:
        mins[v["type"]] = min(mins[v["type"]], float(m.group(1)))
print(f"JLC probe: {len(bad)} below JLC limits (copper 0.09, SMD pad-pad 0.15, hole-copper 0.2, hole-hole 0.2, edge 0.2, "
      f"track 0.09, ring 0.05); measured minimums: " + ", ".join(f"{t} {mins[t]:.3f}" for t in TYPES))
for v in bad[:10]:
    print("  ", v["description"][:90], "|", "; ".join(i["description"][:50] for i in v["items"]))
EOF
