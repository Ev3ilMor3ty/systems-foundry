#!/usr/bin/env bash
set -euo pipefail
FOUNDRY_ROOT=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)
exec java -jar "$FOUNDRY_ROOT/control-api/target/control-api-0.1.0.jar" --root "$FOUNDRY_ROOT" "$@"
