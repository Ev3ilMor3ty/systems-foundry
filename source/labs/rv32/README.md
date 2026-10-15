# RV32

Run real 32-bit RISC-V integer machine instructions in a small, inspectable
interpreter. Use it to understand registers, sign extension, branches, memory,
call/return links and the instruction that caused a trap.

The engine supports the RV32I integer computational, load/store, control-flow and
FENCE instructions. It uses little-endian unified memory, wrapping 32-bit
arithmetic and a hard-wired x0 register. Each instruction stages its changes;
invalid instructions, misalignment and failed accesses do not partially commit.
This is an interpreter for the unprivileged base ISA, not a cycle-accurate CPU or
an operating system.

## Build and run

From the repository root, install Rust 1.85+ and run:

```bash
cargo build --release --manifest-path labs/rv32/Cargo.toml
labs/rv32/target/release/rv32 demo fibonacci
labs/rv32/target/release/rv32 demo memory-sum
```

The results are `a0: 6765` and `a0: 4950`. The final JSON includes all registers,
the number of executed instructions, PC and halt reason.

On **Windows**, install Rust with the MSVC toolchain and Visual Studio C++ Build
Tools. The same Cargo command works in PowerShell; run:

```powershell
.\labs\rv32\target\release\rv32.exe demo fibonacci
```

## Write a program

The bundled Python 3.10+ assembler accepts numeric x-registers, ABI register
names, labels, comments, all supported base instruction mnemonics and `.word`.
It checks operand counts, immediate ranges, registers and target alignment. It
does not implement pseudo-instructions, sections, relocations or macros.

```bash
python3 labs/rv32/tools/assemble.py labs/rv32/examples/gcd.s gcd.bin
labs/rv32/target/release/rv32 disasm gcd.bin
labs/rv32/target/release/rv32 run gcd.bin --trace gcd-trace.jsonl
```

Euclid's subtraction algorithm leaves `gcd(1071,462) = 21` in a0. The disassembly
command lists instruction addresses, raw words and mnemonics. The trace records
each successful instruction's PC, next PC, register write and optional memory
write. A memory-write value is the source register word; only its low `width`
bytes are stored. The checker independently replays traces from all three
examples and compares final registers with the reported result.

Use `python` instead of `python3` on Windows if that is your interpreter command.
Use `.\labs\rv32\target\release\rv32.exe` for each executable command there.

Trace files, demo exports and assembler outputs must be new paths. Existing
files are not overwritten. A trace from a failed run is partial evidence, not a
completed execution.

## Execution contract

- Raw instruction bytes are loaded at address zero; entry PC is zero.
- Default memory is 64 KiB; `--memory BYTES` accepts 16 bytes through 16 MiB.
  The initial stack pointer is the highest 16-byte-aligned address at/below the
  memory size. Other initial registers are zero.
- Input programs are limited to 1 MiB and must be a multiple of four bytes.
- The default instruction budget is 100,000; `--max-steps` accepts 1..10,000,000.
  An exhausted budget returns an error rather than running forever.
- Instructions and taken control-flow targets must be four-byte aligned.
  Halfword/word loads and stores must be naturally aligned.
- EBREAK stops with `breakpoint`. ECALL with a7=93 stops with `exit` and the guest
  exit value in a0. These are host conventions. Other ECALLs return a trap.
- CLI exit status zero means the guest reached a supported halt; the guest a0
  value is reported in JSON, not used as the CLI's own exit status.
- No privileged mode, ELF loader, MMU, interrupts, devices, compressed
  instructions, multiply/divide, atomics, floating point, CSRs or FENCE.I.
  FENCE is a no-op in this single-threaded, device-free execution model.

## Check it

```bash
cargo test --manifest-path labs/rv32/Cargo.toml --locked
python3 labs/rv32/tests/check_cli.py labs/rv32/target/release/rv32
```

If you separately install `qemu-riscv32`, add `--qemu /path/to/qemu-riscv32`.
The checker wraps its generated programs in minimal ELF files for QEMU. It
compares the interpreter's full register state with an independent arithmetic
model, plus each real-QEMU program's mixed-result exit status. The exit-status
comparison covers eight bits and is not a full architectural differential test.
No QEMU code or binary is shipped in this project.
