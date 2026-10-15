#!/usr/bin/env python3
"""Two-pass assembler for the RV32I examples. No macros, relaxation or ELF."""
import argparse
from pathlib import Path
import re
import struct

ABI = dict(
    zip(
        "zero ra sp gp tp t0 t1 t2 s0 s1 a0 a1 a2 a3 a4 a5 a6 a7 s2 s3 s4 s5 s6 s7 s8 s9 s10 s11 t3 t4 t5 t6".split(),
        range(32),
    )
)
ABI["fp"] = 8
REG = {**ABI, **{f"x{i}": i for i in range(32)}}


def register(name):
    if name not in REG:
        raise ValueError(f"unknown register {name}")
    return REG[name]


def immediate(text, bits):
    value = int(text, 0)
    if not -(1 << (bits - 1)) <= value < (1 << (bits - 1)):
        raise ValueError(f"immediate {text} does not fit signed {bits} bits")
    return value & ((1 << bits) - 1)


def encode(line, pc, labels):
    parts = re.split(r"[\s,()]+", line.strip())
    parts = [p for p in parts if p]
    op, args = parts[0], parts[1:]
    counts = {
        "ebreak": 0,
        "ecall": 0,
        "fence": 0,
        ".word": 1,
        "lui": 2,
        "auipc": 2,
        "jal": 2,
    }
    expected = counts.get(op, 3)
    if len(args) != expected:
        raise ValueError(f"{op} needs {expected} operands")
    if op in ("ebreak", "ecall", "fence"):
        return {"ebreak": 0x00100073, "ecall": 0x73, "fence": 0x0F}[op]
    if op == ".word":
        value = int(args[0], 0)
        if not 0 <= value <= 0xFFFFFFFF:
            raise ValueError(".word must be an unsigned 32-bit integer")
        return value
    if op in ("lui", "auipc"):
        value = int(args[1], 0)
        if not 0 <= value < (1 << 20):
            raise ValueError("upper immediate must be unsigned 20-bit")
        return (
            (value << 12) | (register(args[0]) << 7) | (0x37 if op == "lui" else 0x17)
        )
    if op == "jal" or op in ("beq", "bne", "blt", "bge", "bltu", "bgeu"):
        target = args[-1]
        offset = labels[target] - pc if target in labels else int(target, 0)
        bits = 21 if op == "jal" else 13
        value = immediate(str(offset), bits)
        if offset % 4:
            raise ValueError("RV32I branch/jump target must be four-byte aligned")
        if op == "jal":
            return (
                (((value >> 20) & 1) << 31)
                | (((value >> 1) & 1023) << 21)
                | (((value >> 11) & 1) << 20)
                | (((value >> 12) & 255) << 12)
                | (register(args[0]) << 7)
                | 0x6F
            )
        f3 = {"beq": 0, "bne": 1, "blt": 4, "bge": 5, "bltu": 6, "bgeu": 7}[op]
        return (
            (((value >> 12) & 1) << 31)
            | (((value >> 5) & 63) << 25)
            | (register(args[1]) << 20)
            | (register(args[0]) << 15)
            | (f3 << 12)
            | (((value >> 1) & 15) << 8)
            | (((value >> 11) & 1) << 7)
            | 0x63
        )
    if op in ("lb", "lh", "lw", "lbu", "lhu", "sb", "sh", "sw", "jalr"):
        reg, offset, base = args
        imm = immediate(offset, 12)
        f3 = {
            "lb": 0,
            "lh": 1,
            "lw": 2,
            "lbu": 4,
            "lhu": 5,
            "sb": 0,
            "sh": 1,
            "sw": 2,
            "jalr": 0,
        }[op]
        common = (register(base) << 15) | (f3 << 12)
        if op in ("sb", "sh", "sw"):
            return (
                ((imm >> 5) << 25)
                | (register(reg) << 20)
                | common
                | ((imm & 31) << 7)
                | 0x23
            )
        return (
            (imm << 20) | common | (register(reg) << 7) | (0x67 if op == "jalr" else 3)
        )
    registers = {
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
    }
    if op in registers:
        f3, f7 = registers[op]
        return (
            (f7 << 25)
            | (register(args[2]) << 20)
            | (register(args[1]) << 15)
            | (f3 << 12)
            | (register(args[0]) << 7)
            | 0x33
        )
    immediates = {
        "addi": 0,
        "slti": 2,
        "sltiu": 3,
        "xori": 4,
        "ori": 6,
        "andi": 7,
        "slli": 1,
        "srli": 5,
        "srai": 5,
    }
    if op in immediates:
        if op in ("slli", "srli", "srai"):
            imm = int(args[2], 0)
            if not 0 <= imm <= 31:
                raise ValueError("shift must be 0..31")
            if op == "srai":
                imm |= 0x400
        else:
            imm = immediate(args[2], 12)
        return (
            (imm << 20)
            | (register(args[1]) << 15)
            | (immediates[op] << 12)
            | (register(args[0]) << 7)
            | 0x13
        )
    raise ValueError(f"unknown instruction {op}")


def assemble(source):
    labels, lines = {}, []
    for number, raw in enumerate(source.splitlines(), 1):
        line = raw.split("#", 1)[0].strip()
        if ":" in line:
            label, line = map(str.strip, line.split(":", 1))
            if not re.fullmatch(r"[A-Za-z_][A-Za-z_0-9]*", label) or label in labels:
                raise ValueError(f"line {number}: invalid or duplicate label")
            labels[label] = len(lines) * 4
        if line:
            lines.append((number, line))
    if len(lines) > 262144:
        raise ValueError("program exceeds 1 MiB")
    output = bytearray()
    for pc, (number, line) in enumerate(lines):
        try:
            output += struct.pack("<I", encode(line, pc * 4, labels))
        except (ValueError, KeyError) as error:
            raise ValueError(f"line {number}: {error}") from error
    return bytes(output)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path)
    parser.add_argument("output", type=Path, help="new raw little-endian binary")
    args = parser.parse_args()
    try:
        with args.source.open("rb") as stream:
            content = stream.read(8 * 1024 * 1024 + 1)
        if len(content) > 8 * 1024 * 1024:
            raise ValueError("assembly source exceeds 8 MiB")
        program = assemble(content.decode("utf-8"))
        with args.output.open("xb") as stream:
            stream.write(program)
    except (OSError, ValueError) as error:
        parser.exit(1, f"assemble: {error}\n")
