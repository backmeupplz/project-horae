"""Minimal S-expression reader/writer for KiCad files. Strings stay quoted ('"x"'), atoms are bare."""
import re

_TOK = re.compile(r'\s*(\(|\)|"(?:\\.|[^"\\])*"|[^\s()"]+)')


def parse(text):
    stack, cur = [], []
    for m in _TOK.finditer(text):
        t = m.group(1)
        if t == "(":
            stack.append(cur)
            cur = []
        elif t == ")":
            done, cur = cur, stack.pop()
            cur.append(done)
        else:
            cur.append(t)
    return cur[0]


def dump(x, ind=0):
    if not isinstance(x, list):
        return x
    if all(not isinstance(e, list) for e in x):
        return "(" + " ".join(x) + ")"
    pad = "  " * (ind + 1)
    out = "(" + x[0]
    for e in x[1:]:
        out += ("\n" + pad + dump(e, ind + 1)) if isinstance(e, list) else (" " + e)
    return out + ")"


def q(s):
    return '"' + str(s).replace("\\", "\\\\").replace('"', '\\"') + '"'


def uq(s):
    return s[1:-1].replace('\\"', '"').replace("\\\\", "\\") if s.startswith('"') else s


def find(x, head):
    return [e for e in x if isinstance(e, list) and e and e[0] == head]


def first(x, head):
    r = find(x, head)
    return r[0] if r else None
