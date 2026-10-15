#!/usr/bin/env bash
set -euo pipefail
FOUNDRY_ROOT=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)
for tool in cargo g++ make java javac mvn; do
  command -v "$tool" >/dev/null || { printf 'Missing required tool: %s\n' "$tool" >&2; exit 1; }
done
cargo build --manifest-path "$FOUNDRY_ROOT/chronicle/Cargo.toml" --release --locked
make -C "$FOUNDRY_ROOT/dispatch" -j"${FOUNDRY_JOBS:-2}" all
mvn -B -f "$FOUNDRY_ROOT/control-api/pom.xml" package
printf '\nBuild complete. Run ./scripts/run.sh and open http://127.0.0.1:8090\n'
