# ForgeC

**A small original C-like language that compiles directly to native x86-64.**

ForgeC has its own lexer, precedence parser, scope and function checks, constant
folder, machine-code generator and executable writers. It emits a Linux ELF64
or Windows PE32+ program itself. Compiling a `.fc` file does not invoke GCC,
Clang, LLVM, an assembler, a linker or a C runtime.

The inspiration is the hands-on language-building spirit of Terry A. Davis's
HolyC work. ForgeC is an original, separate language with its own syntax and a
batch ahead-of-time compiler. It is a small first release, not HolyC-compatible.

```c
int fib(int n) {
    if (n < 2) { return n; }
    return fib(n - 1) + fib(n - 2);
}

int main() {
    print("Fibonacci(20):");
    print(fib(20));
    return 0;
}
```

Actual output:

```text
Fibonacci(20):
6765
```

## Linux

Build the compiler once with **Rust 1.85+** and its normal platform linker
(for example Linux `build-essential`). There are no third-party Rust crates.
The resulting ForgeC compiler needs none of these build tools to compile `.fc`
programs. From the repository root:

```bash
cargo build --release --manifest-path labs/forgec/Cargo.toml --locked
labs/forgec/target/release/forgec check labs/forgec/examples/fibonacci.fc
labs/forgec/target/release/forgec build labs/forgec/examples/fibonacci.fc \
  -o fibonacci --target linux
./fibonacci
```

The generated program runs on x86-64 Linux using kernel write/exit syscalls. It
has no dynamic loader, libc or ForgeC runtime installation dependency.

## Windows

Install Rust's MSVC toolchain and Visual Studio Build Tools with the C++ workload
to build the Rust compiler executable. Open Developer PowerShell at the
repository root:

```powershell
cargo build --release --manifest-path labs/forgec/Cargo.toml --locked
$fc = '.\labs\forgec\target\release\forgec.exe'
& $fc check labs/forgec/examples/fibonacci.fc
& $fc build labs/forgec/examples/fibonacci.fc -o fibonacci.exe --target windows
.\fibonacci.exe
```

Once built, `forgec.exe` can compile its language without Visual Studio or Rust
installed on the machine. Generated PE programs use only Windows KERNEL32
imports for standard output and process exit. Text output is UTF-8.

Both compiler builds can emit either target format. A Linux compiler can create
`hello.exe` using `--target windows`; the output still needs Windows or a suitable
compatibility runtime to execute. A Windows compiler can create a Linux ELF.

Outputs must be **new paths**. ForgeC never overwrites an existing file. Delete
an earlier output yourself or choose a different name when recompiling.

## Language features

- Signed 64-bit `int`, initialized local variables and lexical block scopes.
- Functions with up to eight parameters, forward calls, recursion and mutual
  recursion; left-to-right operand/argument evaluation.
- `if` / `else if` / `else`, `while`, nested blocks, `break`, `continue`, `return`.
- Integer arithmetic, comparisons, bitwise operators and short-circuit logic.
- `print(integer)` or `print("text")`, each followed by a newline.
- `put(integer)` for a raw output byte, used by the Mandelbrot console example.
- Source diagnostics with filename, line, column, source text and a caret.
- Optional constant folding. `--no-fold` selects the same semantics without
  folding, and the executable tests compare both paths.

The compiler intentionally has one integer type. See the complete
[language contract](LANGUAGE.md) for overflow, shifts, division, limits and
unsupported C constructs. There are no pointers, arrays, string variables,
modules, external functions, preprocessor or standard C compatibility.

## Pipeline

```text
UTF-8 .fc source
  -> bounded lexer
  -> precedence parser / syntax tree
  -> lexical name resolution and function-arity checks
  -> optional pure-expression constant evaluation
  -> original x86-64 instruction emission and relative-address fixups
  -> ELF64 or PE32+ container
  -> native executable
```

The generated internal function convention uses stack arguments and private
stack-frame slots. It is not a C ABI. Windows OS calls receive the required
shadow space, stack alignment and imported function pointers. Linux code and
literal data are in an RX segment with a non-executable stack request; PE has an
RX text section and an RW import section. PE uses a fixed image base and has no
relocation/unwind/debug metadata. There is no native execution budget or managed
runtime: unbounded loops and recursion behave like ordinary native programs.

## Check the compiler

```bash
cargo test --manifest-path labs/forgec/Cargo.toml --locked
python3 labs/forgec/tests/check_native.py labs/forgec/target/release/forgec
```

On Windows use `python` and the compiler path ending in `.exe`. The checker
executes the emitted programs on that OS, checks against independent integer
arithmetic, exercises recursion, scopes and evaluation order, compares folding
on/off, and rejects malformed sources. Linux and Windows CI are separate from
Wine compatibility checks. See [validation and limits](VALIDATION.md).
