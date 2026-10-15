#!/usr/bin/env bash
set -euo pipefail
FOUNDRY_ROOT=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)
cargo test --manifest-path "$FOUNDRY_ROOT/chronicle/Cargo.toml" --locked
make -C "$FOUNDRY_ROOT/dispatch" -j"${FOUNDRY_JOBS:-2}" test
mvn -B -f "$FOUNDRY_ROOT/control-api/pom.xml" test
node --test "$FOUNDRY_ROOT/control-room/ui-model.test.mjs"
if [[ "${1:-}" == '--integration' ]]; then
  python3 "$FOUNDRY_ROOT/chronicle/tests/process_failures.py"
  python3 "$FOUNDRY_ROOT/scripts/integration_test.py"
fi
