#!/usr/bin/env python3
"""Independent Lagrange-interpolation parity checks and actual file-loss tests."""
import argparse
import hashlib
import itertools
import json
from pathlib import Path
import random
import struct
import subprocess
import tempfile
import time
import zlib


def multiply(a, b):
    product = 0
    for bit in range(8):
        if b & (1 << bit):
            product ^= a << bit
    for bit in range(14, 7, -1):
        if product & (1 << bit):
            product ^= 0x11D << (bit - 8)
    return product


def inverse(x):
    # This slow enumeration is deliberately different from production exponentiation.
    return next(y for y in range(1, 256) if multiply(x, y) == 1)


def weights(k, x):
    result = []
    for j in range(1, k + 1):
        numerator = denominator = 1
        for t in range(1, k + 1):
            if t != j:
                numerator = multiply(numerator, x ^ t)
                denominator = multiply(denominator, j ^ t)
        result.append(multiply(numerator, inverse(denominator)))
    return result


def check(binary):
    started = time.monotonic()
    rng = random.Random(20261015)
    recovered = parity_checked = rejected = corruption_recoveries = 0
    with tempfile.TemporaryDirectory(prefix="shard vault tests ") as name:
        root = Path(name)

        def invoke(*args, ok=True):
            result = subprocess.run(
                [str(binary), *map(str, args)], capture_output=True, timeout=30
            )
            if ok:
                assert result.returncode == 0, result.stderr.decode(errors="replace")
                return json.loads(result.stdout)
            assert result.returncode != 0, "invalid operation unexpectedly succeeded"
            return result

        configs = [
            (2, 2, 0),
            (2, 2, 1),
            (3, 3, 37),
            (4, 2, 257),
            (4, 4, 129),
            (8, 3, 97),
            (16, 8, 257),
        ]
        sets = []
        for case, (k, m, size) in enumerate(configs):
            original = rng.randbytes(size)
            source = root / f"input-{case}.bin"
            source.write_bytes(original)
            directory = root / f"fragments-{case}"
            invoke("encode", source, directory, k, m)
            paths = [directory / f"shard-{i}.sv" for i in range(k + m)]
            sets.append((source, paths))
            payloads = []
            for index, path in enumerate(paths):
                blob = path.read_bytes()
                assert blob[:8] == b"FNDYRS01"
                assert tuple(blob[8:11]) == (k, m, index)
                assert struct.unpack_from("<Q", blob, 12)[0] == size
                assert struct.unpack_from("<I", blob, 28)[0] == zlib.crc32(original)
                assert struct.unpack_from("<I", blob, 48)[0] == zlib.crc32(blob[64:])
                assert struct.unpack_from("<I", blob, 52)[0] == zlib.crc32(blob[:52])
                payloads.append(blob[64:])
            chunk = len(payloads[0])
            padded = original.ljust(k * chunk, b"\0")
            data = [padded[i * chunk : (i + 1) * chunk] for i in range(k)]
            assert payloads[:k] == data
            for index in range(k, k + m):
                coeff = weights(k, index + 1)
                expected = bytearray(chunk)
                for j in range(k):
                    for at, value in enumerate(data[j]):
                        expected[at] ^= multiply(coeff[j], value)
                assert payloads[index] == expected, (case, index)
                parity_checked += 1
            combinations = (
                list(itertools.combinations(range(k + m), k))
                if k <= 8
                else [tuple(sorted(rng.sample(range(k + m), k))) for _ in range(40)]
            )
            for trial, indices in enumerate(combinations):
                output = root / f"restored-{case}-{trial}.bin"
                invoke("recover", output, *(paths[i] for i in indices))
                assert output.read_bytes() == original, (case, indices)
                recovered += 1
            insufficient = root / f"insufficient-{case}"
            invoke("recover", insufficient, *paths[: k - 1], ok=False)
            assert not insufficient.exists()
            rejected += 1
            invoke("recover", source, *paths[:k], ok=False)
            assert source.read_bytes() == original
            rejected += 1
            invoke("encode", source, directory, k, m, ok=False)
            rejected += 1

        source, paths = sets[3]  # four data, two parity
        good = paths[0].read_bytes()
        mutations = [
            good[:20],
            good + b"trailing",
            b"badmagic" + good[8:],
            good[:64] + bytes([good[64] ^ 1]) + good[65:],
        ]
        for n, content in enumerate(mutations):
            bad = root / f"corrupt-{n}.sv"
            bad.write_bytes(content)
            output = root / f"corruption-recovery-{n}"
            invoke("recover", output, bad, *paths[1:])
            assert output.read_bytes() == source.read_bytes()
            corruption_recoveries += 1
            fail = root / f"corruption-fail-{n}"
            invoke("recover", fail, bad, *paths[1:4], ok=False)
            assert not fail.exists()
            rejected += 1

        for args in [
            (paths[0], paths[0], paths[1], paths[2]),
            (paths[0], paths[1], paths[2], sets[4][1][0]),
        ]:
            out = root / f"invalid-set-{rejected}"
            invoke("recover", out, *args, ok=False)
            assert not out.exists()
            rejected += 1

        # Payload CRC can be recomputed by an attacker. Final file CRC still catches
        # this particular inconsistent fragment; CRC is not authentication.
        forged = bytearray(good)
        forged[64] ^= 0x80
        struct.pack_into("<I", forged, 48, zlib.crc32(forged[64:]))
        struct.pack_into("<I", forged, 52, zlib.crc32(forged[:52]))
        forgery = root / "inconsistent.sv"
        forgery.write_bytes(forged)
        out = root / "must-not-write"
        invoke("recover", out, forgery, *paths[1:4], ok=False)
        assert not out.exists()
        rejected += 1

        # Header CRC alone must not authorize huge allocations or invalid counts.
        for offset, encoded in [
            (12, struct.pack("<Q", 2**64 - 1)),
            (20, struct.pack("<Q", 2**64 - 1)),
            (8, b"\x00"),
            (10, b"\xff"),
            (56, b"\x01"),
        ]:
            blob = bytearray(good)
            blob[offset : offset + len(encoded)] = encoded
            struct.pack_into("<I", blob, 52, zlib.crc32(blob[:52]))
            path = root / f"bad-metadata-{offset}.sv"
            path.write_bytes(blob)
            out = root / f"metadata-output-{offset}"
            invoke("recover", out, path, *paths[1:4], ok=False)
            assert not out.exists()
            rejected += 1

        # A larger real binary input checks block reads and parity-only recovery.
        large = root / "large.bin"
        large.write_bytes(rng.randbytes(2 * 1024 * 1024 + 17))
        directory = root / "large-fragments"
        invoke("encode", large, directory, 4, 4)
        out = root / "large-restored.bin"
        invoke("recover", out, *(directory / f"shard-{i}.sv" for i in range(4, 8)))
        assert out.read_bytes() == large.read_bytes()
        recovered += 1
        for k, m in [(0, 2), (17, 1), (4, 0), (4, 9), (-1, 2), ("2garbage", 2)]:
            invoke("encode", source, root / "invalid-count", k, m, ok=False)
            rejected += 1
        # Sparse oversized file: rejected before encoding, with no output directory.
        huge = root / "oversize.bin"
        with huge.open("wb") as stream:
            stream.truncate(64 * 1024 * 1024 + 1)
        invoke("encode", huge, root / "oversize-fragments", 4, 2, ok=False)
        assert not (root / "oversize-fragments").exists()
        rejected += 1
    return {
        "ok": True,
        "binary_sha256": hashlib.sha256(binary.read_bytes()).hexdigest(),
        "exact_recoveries": recovered,
        "independent_parity_checks": parity_checked,
        "corrupt_fragment_recoveries": corruption_recoveries,
        "rejected_invalid_operations": rejected,
        "seconds": round(time.monotonic() - started, 3),
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("binary", type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    result = check(args.binary.resolve())
    rendered = json.dumps(result, indent=2) + "\n"
    if args.output:
        args.output.write_text(rendered)
    print(rendered, end="")
