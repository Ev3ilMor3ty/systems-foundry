import json, subprocess
from pathlib import Path

import argparse

ROOT = Path(__file__).resolve().parents[1]
parser = argparse.ArgumentParser()
parser.add_argument("--binary", type=Path, default=ROOT / "build/foundry-dispatch")
binary = parser.parse_args().binary
cases = [
    (
        {
            "workers": 2,
            "tasks": 2,
            "edges": [
                {"worker": 0, "task": 0, "cost": 1},
                {"worker": 0, "task": 1, "cost": 2},
                {"worker": 1, "task": 0, "cost": 2},
            ],
        },
        True,
    ),
    ({"workers": 0, "tasks": 0, "edges": []}, True),
    ({"workers": -1, "tasks": 1, "edges": []}, False),
    ({"workers": 1.5, "tasks": 1, "edges": []}, False),
    ({"workers": True, "tasks": 1, "edges": []}, False),
    (
        {"workers": 1, "tasks": 1, "edges": [{"worker": 0, "task": 0, "cost": 1.1}]},
        False,
    ),
    (
        {"workers": 1, "tasks": 1, "edges": [{"worker": 0, "task": 0, "cost": 2**63}]},
        False,
    ),
    ({"workers": 256, "tasks": 256, "edges": []}, True),
    (None, False),
    ({}, False),
]
p = subprocess.run(
    [binary, "--serve"],
    input="\n".join(json.dumps(x) for x, _ in cases)
    + "\n{bad json}\n"
    + json.dumps(cases[0][0])
    + "\n",
    text=True,
    capture_output=True,
    check=True,
)
responses = [json.loads(x) for x in p.stdout.splitlines()]
assert len(responses) == len(cases) + 2
for response, (_, expected) in zip(responses, cases):
    assert response["ok"] == expected, response
assert responses[0]["optimal"]["cardinality"] == 2
assert responses[0]["greedy"]["cardinality"] == 1
assert not responses[-2]["ok"] and responses[-1]["ok"]
print("PASS protocol validation and recovery across malformed requests")
import sys, copy, random

sys.path.insert(0, str(ROOT / "tools"))
from check_certificate import verify

for i in [0, 1, 7]:
    assert verify(cases[i][0], responses[i])["ok"]
broken = copy.deepcopy(responses[0])
broken["certificate"]["potential"] = [0] * 6
try:
    verify(cases[0][0], broken)
except ValueError:
    pass
else:
    raise AssertionError("incorrect dual witness accepted")
rng = random.Random(47102)
problems = []
for _ in range(350):
    w = rng.randrange(1, 30)
    t = rng.randrange(1, 30)
    problems.append(
        {
            "workers": w,
            "tasks": t,
            "edges": [
                {"worker": a, "task": b, "cost": rng.randrange(10**9)}
                for a in range(w)
                for b in range(t)
                if rng.random() < 0.45
            ],
        }
    )
p = subprocess.run(
    [binary, "--serve"],
    input="".join(json.dumps(x) + "\n" for x in problems),
    text=True,
    capture_output=True,
    check=True,
)
for problem, response in zip(problems, p.stdout.splitlines(), strict=True):
    assert verify(problem, json.loads(response))["ok"]
print("PASS 350 independently checked primal/dual certificates and tamper rejection")

pretty = subprocess.run(
    [binary],
    input=json.dumps(cases[0][0], indent=2),
    text=True,
    capture_output=True,
    check=True,
)
assert json.loads(pretty.stdout)["ok"]
deep = "[" * 200 + "0" + "]" * 200
p = subprocess.run(
    [binary, "--serve"],
    input=deep + "\n" + json.dumps(cases[0][0]) + "\n",
    text=True,
    capture_output=True,
    check=True,
)
assert [json.loads(x)["ok"] for x in p.stdout.splitlines()] == [False, True]
print("PASS pretty-printed CLI input and bounded nesting with server recovery")

# Depth is counted in containers, including the top-level object.
for nested, expected in [(31, True), (32, False)]:
    problem = cases[0][0].copy()
    value = 0
    for _ in range(nested):
        value = [value]
    problem["metadata"] = value
    response = subprocess.run(
        [binary], input=json.dumps(problem), capture_output=True, text=True
    )
    assert json.loads(response.stdout)["ok"] == expected
special = cases[0][0].copy()
special["metadata"] = '[braces] {inside} \\"quotes\\" \u2603'
assert json.loads(
    subprocess.run(
        [binary], input=json.dumps(special), capture_output=True, text=True, check=True
    ).stdout
)["ok"]
oversized = "x" * (8 * 1024 * 1024 + 1)
p = subprocess.run(
    [binary, "--serve"],
    input=oversized + "\n" + json.dumps(cases[0][0]) + "\n",
    capture_output=True,
    text=True,
    check=True,
    timeout=20,
)
assert [json.loads(x)["ok"] for x in p.stdout.splitlines()] == [False, True]
print("PASS exact depth boundary, quoted delimiters, oversized-line recovery")
