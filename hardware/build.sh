#!/bin/sh
# Rebuild everything from design.py + spec.py: schematic, ERC, placement, autoroute, pours, DRC, renders, STEP.
set -e
cd "$(dirname "$0")"
JAVA=$(ls -d "$HOME"/.local/jdk/jdk-25*/Contents/Home 2>/dev/null | head -1)/bin/java
FR="$HOME/.local/freerouting/freerouting.jar"
mkdir -p out

./kicad python3 gen_sch.py
./kicad kicad-cli sch erc --format json --severity-all -o out/erc.json horae.kicad_sch >/dev/null
./kicad kicad-cli sch export pdf -o out/horae-schematic.pdf horae.kicad_sch >/dev/null
./kicad python3 gen_pcb.py
for strategy in prioritized random sequential; do   # retry until only GND (handled by pours) is left unrouted
  "$JAVA" -Djava.awt.headless=true -jar "$FR" -de out/horae.dsn -do out/horae.ses -mp 50 -is $strategy --gui.enabled=false > out/freerouting.log 2>&1
  grep -E "^\s+Net '" out/freerouting.log | grep -qv "Net 'GND'" || break
  echo "router ($strategy) left signal nets unrouted; retrying"
done
grep -E "Optimization stage completed" out/freerouting.log | sed -E 's/.*(final score)/router \1/' | cut -c1-70
./kicad python3 route.py
./kicad kicad-cli pcb drc --format json --severity-all -o out/drc.json horae.kicad_pcb >/dev/null
./kicad kicad-cli pcb export step --subst-models --force -o out/horae.step horae.kicad_pcb >/dev/null
rm -rf out/gerbers && mkdir -p out/gerbers
./kicad kicad-cli pcb export gerbers --layers F.Cu,In1.Cu,In2.Cu,B.Cu,F.Paste,B.Paste,F.Silkscreen,B.Silkscreen,F.Mask,B.Mask,Edge.Cuts -o out/gerbers/ horae.kicad_pcb >/dev/null
./kicad kicad-cli pcb export drill --format excellon --excellon-separate-th -o out/gerbers/ horae.kicad_pcb >/dev/null
(cd out/gerbers && rm -f ../horae-gerbers.zip && zip -q ../horae-gerbers.zip *)
./kicad python3 fab.py
for side in top bottom; do
  ./kicad kicad-cli pcb render --side $side --width 2000 --height 1000 --quality high -o out/pcb-$side.png horae.kicad_pcb >/dev/null
done
./kicad kicad-cli pcb render --rotate "-35,0,25" --zoom 1.1 --width 2000 --height 1200 --quality high -o out/pcb-3d.png horae.kicad_pcb >/dev/null
python3 - <<'EOF'
import json, collections
e = json.load(open("out/erc.json")); d = json.load(open("out/drc.json"))
erc = sum(len(s["violations"]) for s in e["sheets"])
errs = [v for v in d["violations"] if v["severity"] == "error"]
print(f"ERC {erc} | DRC errors {len(errs)}, warnings {len(d['violations']) - len(errs)}, unconnected {len(d.get('unconnected_items', []))}")
for (t, n) in collections.Counter(v["type"] for v in errs).most_common():
    print(f"  {n:3d} {t}")
EOF
