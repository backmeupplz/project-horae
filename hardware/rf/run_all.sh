#!/bin/sh
# Run FDTD cases in sequence (args: case strings, e.g. "bare" "env --dl -1.5"). Results in results/, logs in logs/.
cd "$(dirname "$0")"; mkdir -p logs
for a in "$@"; do
  t=$(echo $a | tr -d ' -')
  docker run --rm -v "$(cd ../.. && pwd)":/work -w /work/hardware/rf horae-openems python sim.py $a > "logs/$t.log" 2>&1
  grep -hE "efficiency|Traceback|Error" "logs/$t.log"
done
