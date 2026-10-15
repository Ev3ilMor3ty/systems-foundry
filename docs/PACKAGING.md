# Portable packaging

The Linux preview contains the tested native executables, shaded Java JAR, frontend, complete committed source, project/library notices, a build identity and per-file checksums. Java 21 is installed separately. This is a platform-specific preview, not a universal binary.

Build all components and complete the relevant checks first. From a clean committed checkout with Rust 1.85.1 and the documented Linux toolchain:

```bash
mkdir -p .run
cargo metadata --manifest-path chronicle/Cargo.toml --locked --format-version 1 \
  --filter-platform x86_64-unknown-linux-gnu > .run/packaging-metadata.json
python3 scripts/package_linux.py --output ../foundry-linux-preview \
  --cargo-metadata .run/packaging-metadata.json
python3 scripts/package_smoke.py --package ../foundry-linux-preview
```

The metadata must describe the selected Linux platform. Notices are collected from the runtime/build dependency closure; test-only and unrelated-target crates are not redistributed. Missing discovered license text stops packaging. Upstream Rust standard-library license texts and Apache/nlohmann notices are included as well.

The generator refuses an existing destination and refuses a dirty Git checkout. It copies committed source bytes to keep newline conversion from changing the source identity. `BUILD-INFO.json` records the source commit and binary hashes; `SHA256SUMS.txt` covers the payload. The smoke test checks the contents, copies the package into a fresh path with spaces, launches its own service, makes a real dispatch and verifies the proof.

The current Linux build requires glibc 2.38+ and libstdc++ with GLIBCXX_3.4.32. It was tested on Debian 13 x86-64. Rebuild the source for an older Linux runtime. Native Windows has a passing source-build CI job and its own PowerShell guide; this Linux package does not contain Windows executables.

GitHub-generated package ZIPs add one outer repository/tag folder. Extract the whole ZIP, open that folder, read `START-HERE.md` and run `bash start.sh`. Check content hashes inside the package; GitHub's generated outer ZIP is a different container from any locally made archive.
