# Installation

## Choose a route

- **Linux source build:** use the commands below. This is the locally tested route.
- **Windows source build:** use PowerShell with a C++20 toolchain, or WSL2 with the Linux instructions. Native Windows checks are reported separately; Linux crash-test tooling is not a Windows test.
- **Portable packages:** if a release includes a platform package, use only the package matching your OS/architecture and follow its own `START-HERE.md`. A Linux executable does not run directly on an iPhone, iPad or Windows.

No website account, cloud service, API key, Docker daemon or database server is required. The first source build downloads pinned Maven/Cargo dependencies and therefore needs network access. Runtime assets are local.

## Linux

On Ubuntu 24.04 or a current Debian installation:

```bash
sudo apt update
sudo apt install git build-essential openjdk-21-jdk maven python3 nodejs npm
```

Install Rust 1.85 or newer using your distribution or the official instructions at https://www.rust-lang.org/tools/install. Check your tools:

```bash
java -version
javac -version
cargo --version
g++ --version
mvn -version
```

Clone, build and run:

```bash
git clone https://github.com/Ev3ilMor3ty/systems-foundry.git
cd systems-foundry
./scripts/build.sh
./scripts/run.sh
```

Open **http://127.0.0.1:8090** in a browser on the same computer. Keep the terminal open. Press **Ctrl+C** to stop the service. Starting it again restores the last committed workspace.

The default data directory is `.run/`. Choose another location or port explicitly:

```bash
./scripts/run.sh --data "$HOME/foundry-workspace" --port 8091
```

The caller must provision a durable parent directory for power-loss durability. The ledger syncs each appended record, and on Unix also syncs its parent directory on open. Filesystem/storage guarantees still apply.

## Windows: WSL2

Install WSL2 and an Ubuntu distribution using Microsoft's instructions. Run the Linux setup commands inside the Ubuntu terminal. Keep the checkout in the Linux filesystem, such as `~/systems-foundry`, rather than a shared drive for the most predictable file-lock behavior. Open the printed localhost address in your Windows browser.

## Windows: native PowerShell build

Install these from their official distributors and add their `bin` directories to PATH:

1. Git for Windows.
2. A JDK 21 distribution such as Eclipse Temurin.
3. Rust 1.85+ and its Windows build tools.
4. Maven 3.8.7+.
5. A recent MinGW-w64 G++ supporting C++20. MSYS2's UCRT64 environment is one way to obtain it.

In a fresh PowerShell window:

```powershell
git clone https://github.com/Ev3ilMor3ty/systems-foundry.git
cd systems-foundry
.\scripts\build.ps1
.\scripts\run.ps1
```

The C++ executable is `dispatch\build\foundry-dispatch.exe`; Rust produces `chronicle\target\release\foundry-chronicle.exe`. Java selects the `.exe` names automatically on Windows. The PowerShell build runs portable Java tests. The process-kill integration harness and kernel VM scripts require Linux.

If your PowerShell execution policy blocks a local script, inspect it and follow your administrator's approved way of running scripts, or run the documented Cargo/G++/Maven commands directly. Do not disable organisation-wide policy for this demo.

## Independent tools

### C++ optimizer

```bash
make -C dispatch
./dispatch/build/foundry-dispatch < dispatch/examples/rematching.json
```

### Rust ledger

```bash
cargo build --release --locked --manifest-path chronicle/Cargo.toml
./chronicle/target/release/foundry-chronicle append events.jsonl example-1 '{"message":"hello"}'
./chronicle/target/release/foundry-chronicle verify events.jsonl
```

On Windows, use the `.exe` name and your shell's JSON quoting rules, or send requests through a JSONL file. See the component READMEs for the stdio protocols.

## Tests

```bash
./scripts/check.sh
./scripts/check.sh --integration
cd control-room
npm ci --ignore-scripts
npm test
npm run format:check
```

The optional browser suite needs Python Playwright and Chromium. Install them in your own virtual environment, then run:

```bash
python3 scripts/ui_test.py --chromium /usr/bin/chromium
```

Browser automation defaults to a Linux Chromium path; override it explicitly if needed. Automated WCAG checks cover only the tested states and do not replace manual assistive-technology testing.

## Troubleshooting

| Symptom | What to check |
| --- | --- |
| `UnsupportedClassVersionError` | `java -version` must report 21 or newer. `JAVA_HOME` and PATH should select the same JDK. |
| `cargo` or `mvn` is missing | Reopen the terminal after installation and check PATH. |
| C++ compile errors about `contains` | Use `-std=c++20` with a recent G++. |
| Port already in use | Stop your earlier instance or pass `--port 8091`. |
| Ledger lock unavailable | Only one API instance may own a data directory. Do not delete the lock or edit the active event file. |
| Broken sequence/hash/torn tail | Stop. Preserve the file and any independent head anchor. Restore a known-good backup or use a new workspace; startup never silently discards evidence. |
| Dependency unavailable / uncertain durability | Stop and restart to verify/replay the journal. Retrying the same command ID avoids duplicate committed changes. |
| 64 MiB limit reached | Stop the workspace, preserve/export the ledger and use a new `--data` directory. No automatic history deletion occurs. |
| Browser says reconnecting | Check the Java terminal and `/api/health`, then refresh after the service recovers. |

A reset clears only the current fictional scenario. It appends a new ledger event and preserves the preceding history.
