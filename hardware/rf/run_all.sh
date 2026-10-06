#!/bin/sh
# Run FDTD cases in sequence (args: case strings, e.g. "bare" "env --trim 7.5"). Results in results/, logs in logs/.
# Logs are named after the case string + the model version (logs/envtrim7.5v3.log; v2 = 2026-10-04, none = v1).
cd "$(dirname "$0")"; mkdir -p logs
for a in "$@"; do
  t=$(echo "$a v3" | tr -d ' -')
  docker run --rm -v "$(cd ../.. && pwd)":/work -w /work/hardware/rf horae-openems python sim.py $a > "logs/$t.log" 2>&1
  grep -hE "efficiency|Traceback|Error" "logs/$t.log"
done
