$ErrorActionPreference = 'Stop'
$ProjectRoot = Split-Path -Parent $PSScriptRoot
& java '-jar' "$ProjectRoot/control-api/target/control-api-0.1.0.jar" '--root' "$ProjectRoot" @args
exit $LASTEXITCODE
