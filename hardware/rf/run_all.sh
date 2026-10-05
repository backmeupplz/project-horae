#!/bin/sh
# Run FDTD cases in sequence (args: case strings, e.g. "bare" "env --trim 7.5"). Results in results/, logs in logs/.
# Logs are named after the case string + v2 (logs/envtrim7.5v2.log); the v1 (0.8 mm board) logs have no v2.
cd "$(dirname "$0")"; mkdir -p logs
for a in "$@"; do
  t=$(echo "$a v2" | tr -d ' -')
  docker run --rm -v "$(cd ../.. && pwd)":/work -w /work/hardware/rf horae-openems python sim.py $a > "logs/$t.log" 2>&1
  grep -hE "efficiency|Traceback|Error" "logs/$t.log"
done
