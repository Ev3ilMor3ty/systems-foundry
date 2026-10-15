$ErrorActionPreference = 'Stop'
$ProjectRoot = Split-Path -Parent $PSScriptRoot
foreach ($Tool in @('cargo', 'g++', 'java', 'javac', 'mvn')) {
    if (-not (Get-Command $Tool -ErrorAction SilentlyContinue)) {
        throw "Missing required tool: $Tool. See docs/INSTALL.md."
    }
}
& cargo build --manifest-path "$ProjectRoot/chronicle/Cargo.toml" --release --locked
if ($LASTEXITCODE -ne 0) { throw 'Rust build failed' }
New-Item -ItemType Directory -Force "$ProjectRoot/dispatch/build" | Out-Null
& g++ '-std=c++20' '-O2' '-Wall' '-Wextra' "-I$ProjectRoot/dispatch/src" "-I$ProjectRoot/dispatch/vendor" "$ProjectRoot/dispatch/src/main.cpp" '-o' "$ProjectRoot/dispatch/build/foundry-dispatch.exe"
if ($LASTEXITCODE -ne 0) { throw 'C++ build failed' }
& mvn '-B' '-f' "$ProjectRoot/control-api/pom.xml" 'package' '-Dtest=ServiceTest,ProofVerifierTest,HttpTest'
if ($LASTEXITCODE -ne 0) { throw 'Java build or checks failed' }
Write-Host 'Build complete. Run .\scripts\run.ps1 and open http://127.0.0.1:8090'
