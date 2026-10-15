# ShardVault

Split a file into **k data fragments plus m parity fragments**. Reconstruct it
from any k distinct valid fragments in that set. With 4+2, for example, the file
survives the loss of any two of its six fragments. With 4+4, even all four data
fragments can be missing.

This is actual systematic Reed-Solomon coding over GF(256), not duplicate file
copies or XOR parity limited to a single loss. Data fragments contain the padded
original bytes; parity fragments combine them using a Vandermonde matrix made
systematic by inversion of its top square submatrix. Decoding inverts the rows
corresponding to the fragments you still have.

## Linux

Requires a C++20 compiler. From the repository root:

```bash
mkdir -p labs/shardvault/build
g++ -std=c++20 -O2 -Wall -Wextra -Wpedantic -Werror \
  labs/shardvault/src/main.cpp -o labs/shardvault/build/shardvault

labs/shardvault/build/shardvault encode YOUR-FILE.bin fragments 4 2
labs/shardvault/build/shardvault recover restored.bin \
  fragments/shard-0.sv fragments/shard-2.sv \
  fragments/shard-4.sv fragments/shard-5.sv
cmp YOUR-FILE.bin restored.bin
```

The recovery command deliberately omits fragments 1 and 3. Keep fragment copies
on genuinely separate failure domains if you are experimenting with resilience;
six files on the same lost disk do not protect each other.

## Windows

Install Visual Studio 2022 Build Tools with **Desktop development with C++** and
CMake. From a Developer PowerShell, at the repository root:

```powershell
cmake -S labs/shardvault -B labs/shardvault/build -A x64
cmake --build labs/shardvault/build --config Release
$vault = '.\labs\shardvault\build\Release\shardvault.exe'
& $vault encode YOUR-FILE.bin fragments 4 2
& $vault recover restored.bin fragments/shard-0.sv fragments/shard-2.sv fragments/shard-4.sv fragments/shard-5.sv
(Get-FileHash YOUR-FILE.bin).Hash -eq (Get-FileHash restored.bin).Hash
```

CMake also works on Linux:

```bash
cmake -S labs/shardvault -B labs/shardvault/build -DCMAKE_BUILD_TYPE=Release
cmake --build labs/shardvault/build --parallel 2
```

## Integrity and output rules

Each fragment has its own header, file size, coding parameters, index, random
set identifier and CRC32 values for the header, payload and original file. You
do not need a separate manifest. The format is documented in [FORMAT.md](FORMAT.md).

Recovery reports and skips unreadable or accidentally damaged fragments. It
requires enough valid distinct ones. Valid fragments from mixed sets and
duplicate indices are rejected. The original file checksum is checked before
creating the recovered file. Existing output files and encoding directories
are never overwritten. An I/O failure can leave partial new files; preserve the
input and retry with a different new output path.

CRC32 detects accidental damage; it is not authentication. This tool does not
encrypt data, authenticate hostile fragments, repair arbitrary errors in-place
or guarantee durability after power loss. Keep real backups. The prototype
reads data into memory, supports files up to **64 MiB**, and accepts **2..16 data
plus 1..8 parity fragments**.

## Independent checks

Requires Python 3.10+, no packages:

```bash
python3 labs/shardvault/tests/check.py labs/shardvault/build/shardvault
```

On Windows, point the test at `labs/shardvault/build/Release/shardvault.exe`.
The Python checker computes parity using Lagrange interpolation and a separate
polynomial multiplication implementation. It enumerates all surviving subsets
for small configurations, samples 16+8, rebuilds a larger binary file from
parity alone, and injects truncation, bit flips, bad metadata, mixed sets,
duplicates and output collisions.
