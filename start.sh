#!/usr/bin/env bash
set -euo pipefail
FOUNDRY_PACKAGE=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
command -v java >/dev/null || { printf 'Install Java 21 or newer first. See START-HERE.md.\n' >&2; exit 1; }
chmod u+x "$FOUNDRY_PACKAGE/bin/foundry-chronicle" "$FOUNDRY_PACKAGE/bin/foundry-dispatch"
exec java -jar "$FOUNDRY_PACKAGE/app/control-api.jar" --root "$FOUNDRY_PACKAGE/source" --chronicle "$FOUNDRY_PACKAGE/bin/foundry-chronicle" --dispatch "$FOUNDRY_PACKAGE/bin/foundry-dispatch" --data "$FOUNDRY_PACKAGE/data" "$@"
