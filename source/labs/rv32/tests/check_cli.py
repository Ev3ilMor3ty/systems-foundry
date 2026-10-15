#!/usr/bin/env python3
"""Seeded independent arithmetic model, trace replay and optional QEMU checks."""
import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
import random
import struct
import subprocess
import tempfile
import time

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location(
    "assembler", ROOT / "tools" / "assemble.py"
)
assembler = importlib.util.module_from_spec(spec)
spec.loader.exec_module(assembler)
MASK = 0xFFFFFFFF


def signed(x):
    return x if x < 0x80000000 else x - 0x100000000


def elf32(code):
    ident = b"\x7fELF\x01\x01\x01" + bytes(9)
    header = ident + struct.pack(
        "<HHIIIIIHHHHHH", 2, 243, 1, 0x10000, 52, 0, 0, 52, 32, 1, 0, 0, 0
    )
    segment = struct.pack(
        "<IIIIIIII", 1, 4096, 0x10000, 0x10000, len(code), len(code), 5, 4096
    )
    return (header + segment).ljust(4096, b"\0") + code


def check(binary, qemu=None):
    started = time.monotonic()
    rng = random.Random(20261015)
    programs = arithmetic = qemu_checks = trace_steps = rejects = 0
    with tempfile.TemporaryDirectory(prefix="rv32 model checks ") as name:
        root = Path(name)

        def run(*args, ok=True):
            result = subprocess.run(
                [str(binary), *map(str, args)], capture_output=True, timeout=10
            )
            assert (result.returncode == 0) == ok, result.stderr.decode(
                errors="replace"
            )
            return result

        for example, answer in [("gcd", 21), ("fibonacci", 6765), ("memory-sum", 4950)]:
            raw = assembler.assemble((ROOT / "examples" / f"{example}.s").read_text())
            path = root / f"{example}.bin"
            path.write_bytes(raw)
            trace = root / f"{example}.jsonl"
            state = json.loads(run("run", path, "--trace", trace).stdout)
            assert state["a0"] == answer
            registers = [0] * 32
            registers[2] = 65536
            pc = 0
            memory = bytearray(65536)
            memory[: len(raw)] = raw
            for number, row in enumerate(trace.read_text().splitlines(), 1):
                step = json.loads(row)
                assert step["step"] == number and step["pc"] == pc
                assert step["instruction"] == int.from_bytes(
                    memory[pc : pc + 4], "little"
                )
                if step["register_write"]:
                    reg, value = step["register_write"]
                    assert reg != 0
                    registers[reg] = value
                if step["memory_write"]:
                    address, value, width = step["memory_write"]
                    memory[address : address + width] = value.to_bytes(4, "little")[
                        :width
                    ]
                pc = step["next_pc"]
                trace_steps += 1
            assert registers == state["registers"] and pc == state["pc"]
            run("run", path, "--trace", trace, ok=False)  # exclusive trace output
            rejects += 1
            listing = run("disasm", path).stdout.decode()
            assert "ebreak" in listing and "illegal" not in listing
            if example != "gcd":
                exported = root / f"export-{example}.bin"
                run("export-demo", example, exported)
                assert exported.read_bytes() == raw
                run("export-demo", example, exported, ok=False)
                rejects += 1

        ops = ["add", "sub", "sll", "slt", "sltu", "xor", "srl", "sra", "or", "and"]
        # Encode instructions directly here; do not use the example assembler.
        for trial in range(120):
            words, expected = [], [0] * 32
            expected[2] = 65536
            for reg in range(5, 17):
                value = rng.getrandbits(32)
                lower = value & 4095
                low = lower if lower < 2048 else lower - 4096
                upper = ((value - low) & MASK) >> 12
                words += [
                    (upper << 12) | (reg << 7) | 0x37,
                    ((low & 4095) << 20) | (reg << 15) | (reg << 7) | 0x13,
                ]
                expected[reg] = value
            for _ in range(240):
                rd, ra, rb = [rng.randrange(5, 17) for _ in range(3)]
                a, b = expected[ra], expected[rb]
                op = rng.choice(ops)
                f3, f7 = {
                    "add": (0, 0),
                    "sub": (0, 32),
                    "sll": (1, 0),
                    "slt": (2, 0),
                    "sltu": (3, 0),
                    "xor": (4, 0),
                    "srl": (5, 0),
                    "sra": (5, 32),
                    "or": (6, 0),
                    "and": (7, 0),
                }[op]
                result = {
                    "add": lambda: a + b,
                    "sub": lambda: a - b,
                    "sll": lambda: a << (b % 32),
                    "slt": lambda: int(signed(a) < signed(b)),
                    "sltu": lambda: int(a < b),
                    "xor": lambda: a ^ b,
                    "srl": lambda: a >> (b % 32),
                    "sra": lambda: signed(a) >> (b % 32),
                    "or": lambda: a | b,
                    "and": lambda: a & b,
                }[op]()
                words.append(
                    (f7 << 25) | (rb << 20) | (ra << 15) | (f3 << 12) | (rd << 7) | 0x33
                )
                expected[rd] = result & MASK
                arithmetic += 1
            # Mix the result words for a separate real-QEMU Linux exit-status check.
            words.append(0x00000A13)  # x20=0
            for reg in range(5, 17):
                words.append((reg << 20) | (20 << 15) | (4 << 12) | (20 << 7) | 0x33)
            mixed = 0
            for reg in range(5, 17):
                mixed ^= expected[reg]
            expected[20] = mixed
            words += [0x000A0513, 0x05D00893, 0x00000073]  # a0=x20;a7=93;ecall
            expected[10], expected[17] = mixed, 93
            raw = struct.pack(f"<{len(words)}I", *words)
            path = root / "random.bin"
            path.write_bytes(raw)
            state = json.loads(run("run", path).stdout)
            assert state["registers"] == expected, trial
            assert state["halt"] == "exit"
            if qemu:
                elf = root / "random.elf"
                elf.write_bytes(elf32(raw))
                elf.chmod(0o700)
                result = subprocess.run(
                    [str(qemu), str(elf)], capture_output=True, timeout=10
                )
                assert result.returncode == (mixed & 255), (
                    trial,
                    result.returncode,
                    mixed & 255,
                    result.stderr,
                )
                qemu_checks += 1
            programs += 1

        loop = root / "loop.bin"
        loop.write_bytes(struct.pack("<I", 0x0000006F))
        run("run", loop, "--max-steps", "20", ok=False)
        rejects += 1
        for n, blob in enumerate(
            [b"x", bytes(4), struct.pack("<I", 0x020283B3), b"x" * (1024 * 1024 + 1)]
        ):
            path = root / f"invalid-{n}.bin"
            path.write_bytes(blob)
            run("run", path, ok=False)
            rejects += 1
        for source in [
            "x: addi x1,x0,1\nx: ebreak",
            "addi x32,x0,0",
            "slli x1,x0,32",
            "jal x0,2",
            "addi x1,x0,2048",
            "bad x1,x2,x3",
            "lui x1,-1",
        ]:
            try:
                assembler.assemble(source)
            except ValueError:
                rejects += 1
            else:
                raise AssertionError(f"invalid assembly accepted: {source}")
    return {
        "ok": True,
        "binary_sha256": hashlib.sha256(binary.read_bytes()).hexdigest(),
        "modeled_programs": programs,
        "random_alu_operations": arithmetic,
        "trace_steps_replayed": trace_steps,
        "qemu_exit_status_checks": qemu_checks,
        "rejected_invalid_operations": rejects,
        "seconds": round(time.monotonic() - started, 3),
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("binary", type=Path)
    parser.add_argument("--qemu", type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    result = check(args.binary.resolve(), args.qemu.resolve() if args.qemu else None)
    text = json.dumps(result, indent=2) + "\n"
    if args.output:
        args.output.write_text(text)
    print(text, end="")
