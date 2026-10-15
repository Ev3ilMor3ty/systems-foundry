# ForgeC portable Linux compiler

Extract the whole ZIP, including its source folder. Requirements: x86-64 Linux,
glibc 2.34+ and libgcc_s. Tested on Debian 13. No Rust, C compiler, assembler or
linker is required to use this binary. Generated Linux programs need only the
x86-64 Linux kernel.

From this directory:

```bash
chmod u+x forgec
./forgec build source/labs/forgec/examples/hello.fc -o hello --target linux
./hello
./forgec build source/labs/forgec/examples/mandelbrot.fc -o fractal --target linux
./fractal
```

Output files must be new. Use `./forgec --help`, read
source/labs/forgec/README.md and source/labs/forgec/LANGUAGE.md. Windows source
build instructions are in that README; this compiler binary itself is Linux.

All original source and test evidence is under source/. Project code is MIT;
Rust standard-library notices are in source/LICENSES/Rust-standard-library/.
Verify payload contents with `sha256sum -c SHA256SUMS.txt` before running.
