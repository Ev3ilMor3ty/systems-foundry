#!/usr/bin/env python3
"""Package a checked Linux compiler with its exact committed source and notices."""
import argparse
import hashlib
import io
import json
from pathlib import Path
import shutil
import subprocess
import tarfile


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--compiler", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path, help="new directory")
    args = parser.parse_args()
    repo = Path(__file__).resolve().parents[3]
    if subprocess.check_output(["git", "status", "--porcelain"], cwd=repo).strip():
        parser.error("commit the checked source before packaging")
    compiler = args.compiler.resolve()
    blob = compiler.read_bytes()
    if not blob.startswith(b"\x7fELF\x02\x01"):
        parser.error("compiler must be a little-endian ELF64 Linux build")
    commit = subprocess.check_output(
        ["git", "rev-parse", "HEAD"], cwd=repo, text=True
    ).strip()
    archive = subprocess.check_output(
        ["git", "archive", "--format=tar", commit], cwd=repo
    )
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=False)
    source = output / "source"
    source.mkdir()
    with tarfile.open(fileobj=io.BytesIO(archive)) as tar:
        # The input is our own clean Git archive; reject links and unusual paths anyway.
        for entry in tar:
            path = Path(entry.name)
            if (
                path.is_absolute()
                or ".." in path.parts
                or not (entry.isdir() or entry.isfile())
            ):
                parser.error("unexpected source archive entry")
            destination = source / path
            if entry.isdir():
                destination.mkdir(parents=True, exist_ok=True)
            else:
                destination.parent.mkdir(parents=True, exist_ok=True)
                destination.write_bytes(tar.extractfile(entry).read())
    shutil.copyfile(compiler, output / "forgec")
    (output / "forgec").chmod(0o755)
    shutil.copyfile(repo / "LICENSE", output / "LICENSE")
    (output / "START-HERE.md").write_text(
        """# ForgeC portable Linux compiler

Extract the whole ZIP, including its source folder. Requirements: x86-64 Linux,
glibc 2.34+ and libgcc_s. Tested on Debian 13. No Rust, C compiler, assembler or
linker is required to use this binary. Generated Linux programs need only the
x86-64 Linux kernel.

From this directory:

```bash
chmod u+x forgec
./forgec build source/labs/forgec/examples/hello.fc -o hello --target linux
./hello
./forgec build source/labs/forgec/examples/mandelbrot.fc -o fractal --target linux
./fractal
```

Output files must be new. Use `./forgec --help`, read
source/labs/forgec/README.md and source/labs/forgec/LANGUAGE.md. Windows source
build instructions are in that README; this compiler binary itself is Linux.

All original source and test evidence is under source/. Project code is MIT;
Rust standard-library notices are in source/LICENSES/Rust-standard-library/.
Verify payload contents with `sha256sum -c SHA256SUMS.txt` before running.
"""
    )
    metadata = {
        "source_commit": commit,
        "compiler_sha256": hashlib.sha256(blob).hexdigest(),
        "host": "linux-x86_64",
        "glibc_minimum": "2.34",
        "generated_targets": ["linux-x86_64", "windows-x86_64"],
    }
    (output / "BUILD-INFO.json").write_text(json.dumps(metadata, indent=2) + "\n")
    lines = []
    for path in sorted(output.rglob("*")):
        if path.is_file():
            lines.append(
                f"{hashlib.sha256(path.read_bytes()).hexdigest()}  {path.relative_to(output).as_posix()}"
            )
    (output / "SHA256SUMS.txt").write_text("\n".join(lines) + "\n")
    print(
        json.dumps(
            {
                "ok": True,
                "source_commit": commit,
                "payload_files_checked": len(lines),
                "compiler_sha256": metadata["compiler_sha256"],
            }
        )
    )


if __name__ == "__main__":
    main()
