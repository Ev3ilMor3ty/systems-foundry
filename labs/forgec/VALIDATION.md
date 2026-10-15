# Compiler checks and limits

The committed Linux evidence covers the exact compiler hash in
[evidence/linux-native.json](evidence/linux-native.json). Native Windows checks
run separately in [the compiler workflow](../../.github/workflows/forgec.yml).
Wine compatibility checks are separate from those native results.

## What runs

- Seven Rust test groups cover parsing, scope resolution, forward functions,
  arity, invalid control flow, diagnostics, lexical errors, resource limits,
  deterministic image headers and constant folding that preserves name errors.
- The independent Python harness builds and executes 105 source programs,
  each with constant folding enabled and disabled: **210 native executions**.
- **3,738 output-line comparisons** cover all integer operators on signed edge
  values, 80 seeded random programs with eight expressions each, function
  argument order, recursion/mutual recursion, eight-argument calls, variable
  scopes, nested loop breaks/continues, precedence, UTF-8, zero bytes and raw
  character output.
- Both folded and unfolded output reproduce a 24×80 fixed-point Mandelbrot
  reference computed independently in Python.
- Both targets are emitted twice and compared byte for byte. Linux ELF and
  Windows PE output have distinct valid format signatures.
- Runtime division/remainder by zero exits with status 70. MIN/-1 wraps and
  MIN%-1 returns zero in both optimization modes, without a native divide fault.
- Sixteen invalid CLI/source/output operations are rejected, existing outputs
  are preserved, and 200 seeded malformed lexer/parser inputs cause no panic.

The oracle uses Python integer arithmetic with explicit 64-bit normalization
and truncation-toward-zero division. It does not reuse the compiler's parser,
syntax tree, folder or x86-64 emitter. These are finite generated checks, not a
formal proof of compiler correctness.

The earlier pre-character-output Windows backend also passed 70 executions
under Wine, with 12 random cases. That was an earlier compiler hash; it is
preserved privately and is not evidence for the final character-output feature
or a native Windows test. Consult the current hosted Windows job conclusion.

## Scope

ForgeC is an ahead-of-time compiler for its own small language. It is not a C,
C++, HolyC or operating-system compiler compatibility claim. Generated code has
no sandbox, execution budget, garbage collector, unwinder, debugger metadata or
standard C ABI. Windows PE images have a fixed base and no relocations. Native
stack exhaustion and unbounded programs remain ordinary process behavior.

Building the Rust implementation requires Rust and a platform linker. Running
the finished compiler on `.fc` sources does not invoke an external assembler,
linker or compiler backend. Linux outputs use syscalls; Windows outputs import
KERNEL32. No LLVM, GCC, HolyC or TempleOS source was copied into this project.
