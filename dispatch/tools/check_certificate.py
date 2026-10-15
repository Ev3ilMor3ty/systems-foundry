#!/usr/bin/env python3
"""Check optimality witnesses without running an optimizer.

Usage: python3 tools/check_certificate.py request.json response.json
   or: python3 tools/check_certificate.py exported-dashboard-proof.json

The check uses integer arithmetic and remains enabled under `python -O`.
"""
import json
import sys


def require(condition, message):
    if not condition:
        raise ValueError(message)


def verify(problem, response):
    def integer(x):
        return isinstance(x, int) and not isinstance(x, bool)

    w, t = problem["workers"], problem["tasks"]
    require(
        integer(w) and integer(t) and 0 <= w <= 256 and 0 <= t <= 256,
        "invalid dimensions",
    )
    edges = {}
    for edge in problem["edges"]:
        a, b, c = edge["worker"], edge["task"], edge["cost"]
        require(
            all(map(integer, (a, b, c)))
            and 0 <= a < w
            and 0 <= b < t
            and 0 <= c <= 10**9,
            "invalid problem edge",
        )
        require((a, b) not in edges, "duplicate problem edge")
        edges[a, b] = c
    matching = response["optimal"]
    pairs = matching["pairs"]
    chosen, ws, ts = set(), set(), set()
    cost = 0
    for edge in pairs:
        a, b, c = edge["worker"], edge["task"], edge["cost"]
        require(all(map(integer, (a, b, c))), "noninteger matching edge")
        require(
            a not in ws and b not in ts and edges.get((a, b)) == c,
            "infeasible matching",
        )
        ws.add(a)
        ts.add(b)
        chosen.add((a, b))
        cost += c
    require(
        integer(matching["cardinality"]) and integer(matching["cost"]),
        "noninteger matching totals",
    )
    require(
        matching["cardinality"] == len(pairs) and matching["cost"] == cost,
        "incorrect matching totals",
    )
    proof = response["certificate"]
    require(
        integer(proof["schema"]) and proof["schema"] == 1,
        "unsupported certificate schema",
    )
    source = w + t
    sink = source + 1
    n = sink + 1
    potential = proof["potential"]
    raw_side = proof["source_side"]
    require(
        isinstance(potential, list) and len(potential) == n, "wrong potential dimension"
    )
    require(
        all(integer(x) and abs(x) <= 10**15 for x in potential), "invalid potential"
    )
    require(
        isinstance(raw_side, list) and all(integer(x) and 0 <= x < n for x in raw_side),
        "invalid cut vertices",
    )
    side = set(raw_side)
    require(len(side) == len(raw_side), "repeated cut vertex")
    require(
        source in side and sink not in side, "cut does not separate source and sink"
    )
    original, residual = [], []

    def add(a, b, c, used):
        original.append((a, b, c))
        residual.append((b, a, -c) if used else (a, b, c))

    for a in range(w):
        add(source, a, 0, a in ws)
    for (a, b), c in edges.items():
        add(a, w + b, c, (a, b) in chosen)
    for b in range(t):
        add(w + b, sink, 0, b in ts)
    # A closed residual cut proves maximum flow; nonnegative reduced costs
    # exclude every improving residual cycle and prove minimum cost.
    require(
        all(not (a in side and b not in side) for a, b, _ in residual),
        "residual path crosses cut",
    )
    require(
        all(c + potential[a] - potential[b] >= 0 for a, b, c in residual),
        "invalid dual potential",
    )
    cut = sum(a in side and b not in side for a, b, _ in original)
    require(
        integer(proof["cut_capacity"]) and cut == proof["cut_capacity"] == len(pairs),
        "cut capacity does not match flow",
    )
    return {
        "ok": True,
        "cardinality": len(pairs),
        "cost": cost,
        "checked_residual_arcs": len(residual),
    }


if __name__ == "__main__":
    try:
        if len(sys.argv) == 2:
            with open(sys.argv[1]) as file:
                bundle = json.load(file)
            problem, response = bundle["problem"], bundle["response"]
        elif len(sys.argv) == 3:
            with open(sys.argv[1]) as file:
                problem = json.load(file)
            with open(sys.argv[2]) as file:
                response = json.load(file)
        else:
            raise ValueError(__doc__)
        print(json.dumps(verify(problem, response)))
    except (KeyError, TypeError, ValueError, OSError) as error:
        print("invalid certificate: " + str(error), file=sys.stderr)
        sys.exit(1)
