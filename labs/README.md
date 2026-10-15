# Foundry Labs

Two standalone command-line projects. They do not need Java, the dashboard or the
original dispatch services.

| Tool | Useful for | Implementation |
| --- | --- | --- |
| [RV32](rv32/) | Learn how machine instructions execute; assemble small programs, inspect register changes and reproduce traps | Dependency-free Rust RV32I interpreter, Python assembler and independent checks |
| [ShardVault](shardvault/) | Split a file into redundant fragments and reconstruct it after fragments are lost or accidentally damaged | C++20 systematic Reed-Solomon coding with an independently checked binary format |

Both are MIT. Source, examples, tests and English Linux/Windows instructions live
in each directory. These are bounded prototypes with documented limits, rather
than an operating system emulator or a production backup product.

## Linux quick start

Install Rust 1.85+, a C++20 compiler and Python 3.10+. Run from the repository root:

```bash
cargo build --release --manifest-path labs/rv32/Cargo.toml
mkdir -p labs/shardvault/build
g++ -std=c++20 -O2 -Wall -Wextra -Wpedantic -Werror \
  labs/shardvault/src/main.cpp -o labs/shardvault/build/shardvault

labs/rv32/target/release/rv32 demo fibonacci
python3 labs/rv32/tests/check_cli.py labs/rv32/target/release/rv32
python3 labs/shardvault/tests/check.py labs/shardvault/build/shardvault
```

CMake 3.20+ can replace the direct G++ command. Windows instructions use Rust's
MSVC toolchain and Visual Studio C++ Build Tools with CMake. No downloaded Python
packages are required.

See [measured validation](VALIDATION.md) for exactly which tests were run and
which tool/binary they cover.
