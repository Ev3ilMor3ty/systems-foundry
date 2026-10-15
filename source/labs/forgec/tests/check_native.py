#!/usr/bin/env python3
"""Compile programs, execute native output and compare with independent arithmetic."""
import argparse
import hashlib
import json
import math
import os
from pathlib import Path
import random
import subprocess
import tempfile
import time

ROOT = Path(__file__).resolve().parents[1]
MASK = (1 << 64) - 1
OPS = [
    "+",
    "-",
    "*",
    "/",
    "%",
    "<<",
    ">>",
    "&",
    "|",
    "^",
    "==",
    "!=",
    "<",
    "<=",
    ">",
    ">=",
    "&&",
    "||",
]


def signed(value):
    value &= MASK
    return value if value < (1 << 63) else value - (1 << 64)


def operation(op, a, b):
    if op in ("/", "%"):
        q = abs(a) // abs(b)
        if (a < 0) != (b < 0):
            q = -q
        return signed(q if op == "/" else a - q * b)
    return signed(
        {
            "+": lambda: a + b,
            "-": lambda: a - b,
            "*": lambda: a * b,
            "<<": lambda: a << (b & 63),
            ">>": lambda: a >> (b & 63),
            "&": lambda: a & b,
            "|": lambda: a | b,
            "^": lambda: a ^ b,
            "==": lambda: int(a == b),
            "!=": lambda: int(a != b),
            "<": lambda: int(a < b),
            "<=": lambda: int(a <= b),
            ">": lambda: int(a > b),
            ">=": lambda: int(a >= b),
            "&&": lambda: int(a != 0 and b != 0),
            "||": lambda: int(a != 0 or b != 0),
        }[op]()
    )


def check(binary, target, runner, cases):
    started = time.monotonic()
    rng = random.Random(20261015)
    programs = executions = comparisons = rejects = fuzz_checks = cross_formats = 0
    with tempfile.TemporaryDirectory(prefix="forge compiler checks ") as name:
        root = Path(name)

        def invoke(*args, success=True):
            result = subprocess.run(
                [str(binary), *map(str, args)], capture_output=True, timeout=15
            )
            assert result.returncode == (0 if success else 1), result.stderr.decode(
                errors="replace"
            )
            return result

        def execute(source, expected, status=0):
            nonlocal programs, executions, comparisons
            path = root / f"program-{programs}.fc"
            path.write_text(source, encoding="utf-8")
            invoke("check", path)
            for fold in [True, False]:
                output = root / f"program-{programs}-{fold}.exe"
                options = [] if fold else ["--no-fold"]
                invoke("build", path, "-o", output, "--target", target, *options)
                command = ([str(runner)] if runner else []) + [str(output)]
                result = subprocess.run(command, capture_output=True, timeout=15)
                assert result.returncode == status, (
                    programs,
                    fold,
                    result.returncode,
                    result.stderr,
                )
                assert result.stdout == expected.encode("utf-8"), (
                    programs,
                    fold,
                    result.stdout,
                    expected,
                    source,
                )
                executions += 1
                comparisons += len(expected.splitlines())
            programs += 1

        for example, expected in [
            (
                "hello",
                "Hello from ForgeC.\nThis executable was emitted directly from my language.\n",
            ),
            ("fibonacci", "Fibonacci(20):\n6765\n"),
            (
                "primes",
                "Primes below 100:\n"
                + "".join(
                    f"{n}\n"
                    for n in range(2, 100)
                    if all(n % d for d in range(2, math.isqrt(n) + 1))
                ),
            ),
        ]:
            execute((ROOT / "examples" / f"{example}.fc").read_text(), expected)

        rows = []
        for y in range(-12, 12):
            row = []
            for x in range(-40, 40):
                cx, cy = operation("/", x * 256, 24) - 128, operation("/", y * 256, 12)
                zx = zy = iterations = 0
                while zx * zx + zy * zy < 262144 and iterations < 32:
                    next_x = zx * zx // 256 - zy * zy // 256 + cx
                    zy = operation("/", 2 * zx * zy, 256) + cy
                    zx = next_x
                    iterations += 1
                row.append(
                    "#"
                    if iterations == 32
                    else "+" if iterations > 12 else "." if iterations > 5 else " "
                )
            rows.append("".join(row))
        execute((ROOT / "examples/mandelbrot.fc").read_text(), "\n".join(rows) + "\n")
        execute(
            "int main(){put(65);put(322);put(10);put(0);put(10);return 0;}", "AB\n\0\n"
        )

        execute(
            """
int mark(int n){ print(n); return n; }
int combine(int a,int b,int c){return 100*a+10*b+c;}
int main(){
 print(combine(mark(1),mark(2),mark(3)));
 print(mark(4)-mark(5));
 print(0&&mark(7)); print(1||mark(8));
 print(2&&mark(9)); print(0||mark(10));
 int a=5; {int a=a+1;print(a);} print(a);
 print("UTF-8: λ and café"); return 0;
}""",
            "1\n2\n3\n123\n4\n5\n-1\n0\n1\n9\n1\n10\n1\n6\n5\nUTF-8: λ and café\n",
        )
        execute(
            """
int odd(int n){if(n==0){return 0;}return even(n-1);}
int even(int n){if(n==0){return 1;}return odd(n-1);}
int eight(int a,int b,int c,int d,int e,int f,int g,int h){return a+2*b+3*c+4*d+5*e+6*f+7*g+8*h;}
int main(){
 print(odd(37));print(even(38));print(eight(1,2,3,4,5,6,7,8));
 int n=0;int total=0;
 while(n<30){n=n+1;if(n==4){continue;}if(n==12){break;}total=total+n;}
 print(total);
 int x=0; int count=0;
 while(x<4){int y=0;while(y<5){y=y+1;if(y==2){continue;}if(y==4){break;}count=count+1;}x=x+1;}
 print(count);return 0;
}""",
            "1\n1\n204\n62\n8\n",
        )
        execute(
            "int main(){print(2+3*4);print(1<<2+1);print(1|2&4);print(3<4==1);print(2&1==0);print(1||0&&0);return 23;}",
            "14\n8\n1\n1\n0\n1\n",
            23,
        )

        values = [0, 1, -1, 63, 64, -(1 << 63), (1 << 63) - 1, -123456789]
        statements, expected = [], []
        for a in values:
            for b in values:
                for op in OPS:
                    if op in ("/", "%") and b == 0:
                        continue
                    # Locals ensure the default optimizer cannot fold these operations.
                    statements.append(
                        f"{{int a=0x{a&MASK:x};int b=0x{b&MASK:x};print(a{op}b);}}"
                    )
                    expected.append(str(operation(op, a, b)))
                    if (
                        len(statements) == 100
                    ):  # respect the documented local-slot bound
                        execute(
                            "int main(){" + "".join(statements) + "return 0;}",
                            "\n".join(expected) + "\n",
                        )
                        statements, expected = [], []
        if statements:
            execute(
                "int main(){" + "".join(statements) + "return 0;}",
                "\n".join(expected) + "\n",
            )
        execute(
            "int main(){print(-9223372036854775808);print(9223372036854775807);print(-9223372036854775808/-1);print(-9223372036854775808%-1);print(0&&(1/0));print(1||(1/0));return 0;}",
            "-9223372036854775808\n9223372036854775807\n-9223372036854775808\n0\n0\n1\n",
        )

        for _ in range(cases):
            a, b = signed(rng.getrandbits(64)), signed(rng.getrandbits(64))

            def expr(depth):
                if depth == 0 or rng.random() < 0.25:
                    if rng.random() < 0.5:
                        return ("a", a) if rng.random() < 0.5 else ("b", b)
                    value = signed(rng.getrandbits(64))
                    return f"0x{value&MASK:x}", value
                if rng.random() < 0.2:
                    text, value = expr(depth - 1)
                    op = rng.choice(["-", "!", "~", "+"])
                    answer = {
                        "-": lambda: -value,
                        "!": lambda: int(value == 0),
                        "~": lambda: ~value,
                        "+": lambda: value,
                    }[op]()
                    return f"({op}{text})", signed(answer)
                left, x = expr(depth - 1)
                right, y = expr(depth - 1)
                op = rng.choice(OPS)
                if op in ("/", "%") and y == 0:
                    right = f"({right}|1)"
                    y = 1
                return f"({left}{op}{right})", operation(op, x, y)

            expressions = [expr(4) for _ in range(8)]
            body = f"int a=0x{a&MASK:x};int b=0x{b&MASK:x};" + "".join(
                f"print({text});" for text, _ in expressions
            )
            execute(
                "int main(){" + body + "return 0;}",
                "".join(f"{value}\n" for _, value in expressions),
            )

        for op in ["/", "%"]:
            for denominator in ["0", "zero"]:
                execute(
                    f'int main(){{int zero=0;print("before");print(4{op}{denominator});return 0;}}',
                    "before\n",
                    70,
                )

        source = root / "valid.fc"
        source.write_text('int main(){print("deterministic");return 0;}')
        for backend, magic in [("linux", b"\x7fELF"), ("windows", b"MZ")]:
            paths = [root / f"deterministic-{backend}-{i}" for i in range(2)]
            for path in paths:
                invoke("build", source, "-o", path, "--target", backend)
            assert paths[0].read_bytes() == paths[1].read_bytes()
            assert paths[0].read_bytes().startswith(magic)
            cross_formats += 1
        existing = root / "existing"
        existing.write_bytes(b"keep me")
        invoke("build", source, "-o", existing, success=False)
        assert existing.read_bytes() == b"keep me"
        rejects += 1
        bad = root / "bad.fc"
        invalid = [
            "int main(){return missing;}",
            "int main(){break;}",
            "int main(){return 1}",
            'int main(){print("\\x");}',
            "int main(){return foo();}",
            "int main(){int x=x;}",
            "int main(){int x=0;int x=1;}",
            "int f(){return 0;}",
            "int main(int n){return n;}",
            "int main(){return 0x;}",
            "int main(){return 18446744073709551616;}",
            "int main(){return " + "(" * 80 + "1" + ")" * 80 + ";}",
            "int main(){return " + "1+" * 80 + "1;}",
            " " * 65537,
        ]
        for n, text in enumerate(invalid):
            bad.write_text(text)
            output = root / f"must-not-exist-{n}"
            invoke("build", bad, "-o", output, success=False)
            assert not output.exists()
            rejects += 1
        bad.write_text("int main() {\n  return missing;\n}\n")
        result = invoke("check", bad, success=False)
        assert b":2:10: error:" in result.stderr and b"^" in result.stderr
        rejects += 1
        for _ in range(200):
            text = "".join(
                rng.choice('int main(){};0123456789+-*/<>!&|^=, \n"\\_abc')
                for _ in range(rng.randrange(0, 300))
            )
            bad.write_text(text)
            result = subprocess.run(
                [str(binary), "check", str(bad)], capture_output=True, timeout=10
            )
            assert result.returncode in [0, 1] and b"panicked" not in result.stderr
            fuzz_checks += 1
    return {
        "ok": True,
        "compiler_sha256": hashlib.sha256(binary.read_bytes()).hexdigest(),
        "target": target,
        "runner": "native" if not runner else runner.name,
        "source_programs": programs,
        "executions_with_and_without_folding": executions,
        "compared_output_lines": comparisons,
        "deterministic_cross_target_formats": cross_formats,
        "rejected_invalid_operations": rejects,
        "parser_fuzz_inputs": fuzz_checks,
        "seconds": round(time.monotonic() - started, 3),
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("compiler", type=Path)
    parser.add_argument(
        "--target",
        choices=["linux", "windows"],
        default="windows" if os.name == "nt" else "linux",
    )
    parser.add_argument("--runner", type=Path)
    parser.add_argument("--cases", type=int, default=80)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    result = check(
        args.compiler.resolve(),
        args.target,
        args.runner.resolve() if args.runner else None,
        args.cases,
    )
    text = json.dumps(result, indent=2) + "\n"
    if args.output:
        args.output.write_text(text)
    print(text, end="")
