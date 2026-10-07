"""Write a DSN that asks Freerouting to route only some nets: dsn_only.py in.dsn out.dsn NET [NET ...]
(other nets' pins stay as obstacles; their fixed wiring stays)."""
import re, sys
src, dst, args = sys.argv[1], sys.argv[2], sys.argv[3:]
dsn = open(src).read()
if args and args[0] == "--except":            # every net but these
    drop = set(args[1:])
    keep = set(m.strip('"') for m in re.findall(r"\(net (\S+)\n\s*\(pins", dsn)) - drop
else:
    keep = set(args)
i0 = dsn.index("(network"); i1 = dsn.index("(class", i0)
body = dsn[i0:i1]
out = re.sub(r"\(net (\S+)\n\s*\(pins[^)]*\)\n\s*\)\n\s*", lambda m: m.group(0) if m.group(1).strip('"') in keep else "", body)
tail = dsn[i1:]
def fix_class(m):
    names = [n for n in m.group(2).split() if n.strip('"') in keep]
    return f"(class {m.group(1)} " + " ".join(names) + m.group(3)
tail = re.sub(r"\(class (\S+) ([^(]*)(\n\s*\(circuit)", fix_class, tail)
open(dst, "w").write(dsn[:i0] + out + tail)
print(len(re.findall(r"\(net ", out)), "nets kept")
