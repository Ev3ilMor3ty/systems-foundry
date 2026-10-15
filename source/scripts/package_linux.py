#!/usr/bin/env python3
"""Make a Linux portable directory with the tested binaries, source and notices.

Requires a clean Git checkout, built components and `cargo metadata` JSON for the
locked ledger dependencies filtered for x86_64-unknown-linux-gnu. The package needs Java 21, not a Rust/C++ toolchain.
"""
import argparse, hashlib, json, os, pathlib, platform, shutil, subprocess

ROOT = pathlib.Path(__file__).resolve().parents[1]


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--output", required=True, type=pathlib.Path)
    p.add_argument("--cargo-metadata", required=True, type=pathlib.Path)
    a = p.parse_args()
    if platform.system() != "Linux" or platform.machine() not in ["x86_64", "amd64"]:
        raise SystemExit("This packager targets Linux x86-64")
    if a.output.exists():
        raise SystemExit(
            "Choose a new output directory; existing packages are preserved"
        )
    dirty = subprocess.check_output(
        ["git", "-C", str(ROOT), "status", "--porcelain"], text=True
    )
    if dirty.strip():
        raise SystemExit(
            "Commit the source first so the package has an exact source revision"
        )
    a.output.mkdir(parents=True)
    source = a.output / "source"
    source.mkdir()
    files = subprocess.check_output(["git", "-C", str(ROOT), "ls-files", "-z"]).split(
        b"\0"
    )
    for entry in files:
        if not entry:
            continue
        relative = pathlib.Path(os.fsdecode(entry))
        destination = source / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        # Read the committed bytes, not platform checkout newline conversions.
        data = subprocess.check_output(
            ["git", "-C", str(ROOT), "show", "HEAD:" + relative.as_posix()]
        )
        destination.write_bytes(data)
        if relative.suffix == ".sh":
            destination.chmod(0o755)
    (a.output / "bin").mkdir()
    (a.output / "app").mkdir()
    native = {
        "foundry-chronicle": ROOT / "chronicle/target/release/foundry-chronicle",
        "foundry-dispatch": ROOT / "dispatch/build/foundry-dispatch",
    }
    for name, path in native.items():
        shutil.copy2(path, a.output / "bin" / name)
        (a.output / "bin" / name).chmod(0o755)
    shutil.copy2(
        ROOT / "control-api/target/control-api-0.1.0.jar",
        a.output / "app/control-api.jar",
    )
    notices = a.output / "THIRD-PARTY-LICENSES"
    notices.mkdir()
    shutil.copytree(ROOT / "LICENSES", notices / "project-library-notices")
    shutil.copy2(
        ROOT / "dispatch/vendor/LICENSE.nlohmann-json",
        notices / "nlohmann-json-MIT.txt",
    )
    metadata = json.loads(a.cargo_metadata.read_text())
    # Cargo metadata includes test-only and other-target packages. Distribute
    # notices for the selected platform's actual runtime/build closure.
    nodes = {node["id"]: node for node in metadata["resolve"]["nodes"]}
    selected = set()
    pending = [metadata["resolve"]["root"]]
    while pending:
        package_id = pending.pop()
        if package_id in selected:
            continue
        selected.add(package_id)
        for dependency in nodes[package_id]["deps"]:
            if any(kind["kind"] in [None, "build"] for kind in dependency["dep_kinds"]):
                pending.append(dependency["pkg"])
    dependencies = []
    for package in metadata["packages"]:
        if package["id"] not in selected:
            continue
        if package.get("source") is None:
            continue
        name = f"{package['name']}-{package['version']}"
        if pathlib.Path(name).name != name:
            raise ValueError("Invalid crate name")
        crate = pathlib.Path(package["manifest_path"]).parent.resolve()
        texts = []
        for path in crate.iterdir():
            if path.is_file() and path.name.upper().startswith(
                ("LICENSE", "LICENCE", "COPYRIGHT", "NOTICE")
            ):
                texts.append(path)
        if package.get("license_file"):
            path = pathlib.Path(package["license_file"])
            path = path if path.is_absolute() else crate / path
            if (
                path.resolve().is_relative_to(crate)
                and path.is_file()
                and path not in texts
            ):
                texts.append(path)
        if not texts:
            raise ValueError("Missing license text for " + name)
        destination = notices / "rust-crates" / name
        destination.mkdir(parents=True)
        for path in texts:
            shutil.copy2(path, destination / path.name)
        dependencies.append(
            {
                "name": package["name"],
                "version": package["version"],
                "license": package.get("license"),
                "notices": [x.name for x in texts],
            }
        )
    (notices / "rust-dependencies.json").write_text(
        json.dumps(dependencies, indent=2) + "\n"
    )
    shutil.copy2(ROOT / "LICENSE", a.output / "LICENSE")
    (a.output / "start.sh").write_text(
        """#!/usr/bin/env bash
set -euo pipefail
FOUNDRY_PACKAGE=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
command -v java >/dev/null || { printf 'Install Java 21 or newer first. See START-HERE.md.\\n' >&2; exit 1; }
chmod u+x "$FOUNDRY_PACKAGE/bin/foundry-chronicle" "$FOUNDRY_PACKAGE/bin/foundry-dispatch"
exec java -jar "$FOUNDRY_PACKAGE/app/control-api.jar" --root "$FOUNDRY_PACKAGE/source" --chronicle "$FOUNDRY_PACKAGE/bin/foundry-chronicle" --dispatch "$FOUNDRY_PACKAGE/bin/foundry-dispatch" --data "$FOUNDRY_PACKAGE/data" "$@"
"""
    )
    (a.output / "start.sh").chmod(0o755)
    (a.output / "START-HERE.md").write_text(
        """# Systems Foundry — Linux x86-64 portable preview

1. Extract the entire package into a folder you own. Keep its subfolders together.
2. Install a Java 21+ runtime. On Ubuntu 24.04/Debian 13: `sudo apt install openjdk-21-jre`.
3. Open a terminal in this folder and run `bash start.sh`.
4. Open **http://127.0.0.1:8090** in a browser on the same computer.
5. Click **Optimize & dispatch**, then advance ticks or use **Auto run**. Press Ctrl+C in the terminal to stop.

The package was tested on Debian 13 x86-64. Its native files require glibc 2.38+ and libstdc++ exporting GLIBCXX_3.4.32; install your distribution's `libstdc++6` package if needed. Older Linux systems should build the included source locally. This is not a Windows executable package; Windows has a CI-tested source build in `source/docs/INSTALL.md`.

No Rust, C++ compiler, Maven, Node, account or API key is needed to run this package. The Java runtime is installed separately. The source build and test instructions are under `source/`; all committed code is included. Library notices are under `THIRD-PARTY-LICENSES/`.

Scenario data is created in `data/` at first launch. Reset appends an event; it does not delete history. Preserve your data directory when upgrading. Only one instance may own a data directory.

Use `bash start.sh --port 8091` for another port. The app remains a local fictional simulation, with no public-service authentication. Endurance evidence and its limits are in `source/docs/VALIDATION.md`.
"""
    )
    files = sorted(x for x in a.output.rglob("*") if x.is_file())
    identity = {
        "source_commit": subprocess.check_output(
            ["git", "-C", str(ROOT), "rev-parse", "HEAD"], text=True
        ).strip(),
        "platform": "Linux x86-64",
        "requirements": "Java21+, glibc2.38+, GLIBCXX3.4.32",
        "binary_sha256": {
            str(x.relative_to(a.output)): hashlib.sha256(x.read_bytes()).hexdigest()
            for x in files
            if x.parent in [a.output / "bin", a.output / "app"]
        },
    }
    (a.output / "BUILD-INFO.json").write_text(json.dumps(identity, indent=2) + "\n")
    files = sorted(x for x in a.output.rglob("*") if x.is_file())
    (a.output / "SHA256SUMS.txt").write_text(
        "".join(
            hashlib.sha256(x.read_bytes()).hexdigest()
            + "  "
            + x.relative_to(a.output).as_posix()
            + "\n"
            for x in files
        )
    )
    print(
        json.dumps(
            {
                "ok": True,
                "output": str(a.output),
                "files": len(files) + 1,
                "source_commit": identity["source_commit"],
            }
        )
    )


if __name__ == "__main__":
    main()
