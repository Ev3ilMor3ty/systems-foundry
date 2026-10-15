# What was measured

These results apply to the tool identities in [evidence/](evidence/). They do not
inherit any result from the original application, chess engine or kernel module.
The local development host had a two-core CPU quota. These are correctness
checks, not throughput claims or certification.

## RV32

- Ten Rust test groups cover register and immediate operations on edge values,
  signed/unsigned branches in both directions, link-register aliasing, JALR
  low-bit clearing, upper immediates, little-endian loads/stores, sign extension,
  x0 behavior, instruction/access alignment, illegal extensions, atomic trap
  behavior, EBREAK/ECALL conventions, FENCE and exhausted instruction budgets.
- A separate Python arithmetic model checks every final register for 120 seeded
  programs containing 28,800 randomized register-ALU operations. Initialization
  and host-exit instructions are additional to that count.
- The same programs execute in real QEMU RISC-V user mode. Their mixed-result
  eight-bit exit statuses match in all 120 cases. This comparison is weaker than
  comparing all QEMU registers and does not cover the whole ISA by itself.
- All 757 successful instruction trace entries across Euclid, Fibonacci and
  memory-sum are replayed to reconstruct final registers and written memory.
- Seventeen malformed assembly/input, instruction-budget and output-collision
  checks are rejected.
- The example assembler's Fibonacci and memory-sum encodings match the separately
  embedded raw-word demos exactly.

The optional QEMU test first exposed an executable-permission omission in the
generated ELF fixture. That fixture was corrected; the interpreter did not need
an instruction change. QEMU is a separate test dependency, not bundled code.

## ShardVault

- 323 byte-identical recoveries across zero-byte, one-byte, odd-size and larger
  binary inputs. All surviving k-subsets are enumerated for the tested 2+2,
  3+3, 4+2, 4+4 and 8+3 inputs; 40 subsets are sampled for 16+8.
- Twenty-four parity payloads match independent Lagrange-interpolation checks.
  The checker uses polynomial multiplication/reduction rather than the C++
  implementation's shift-and-reduce routine and matrix inversion.
- A 2 MiB + 17 byte binary file is recovered using only its four parity shards.
- Four corrupt/truncated/trailing-data fragments are skipped while enough other
  fragments recover the original file.
- Forty invalid operations are rejected: insufficient fragments, duplicate
  indices, mixed sets, invalid counts, checksum failures, forged huge metadata,
  reserved fields, oversize input and existing-output collisions.
- The complete harness also passes with AddressSanitizer and
  UndefinedBehaviorSanitizer. The sanitized binary has a separate hash.

CRC32 is accidental-corruption detection, not cryptographic authentication.
These tests do not demonstrate tolerance of coordinated malicious fragments,
all possible byte corruptions, storage power loss or arbitrarily large files.

## Reproduce

Use each project's README for build commands, then:

```bash
cargo test --manifest-path labs/rv32/Cargo.toml --locked
python3 labs/rv32/tests/check_cli.py labs/rv32/target/release/rv32
python3 labs/shardvault/tests/check.py labs/shardvault/build/shardvault
```

Linux sanitizer command:

```bash
g++ -std=c++20 -g -O1 -Wall -Wextra -Wpedantic -Werror \
  -fsanitize=address,undefined -fno-omit-frame-pointer -fno-pie -no-pie \
  labs/shardvault/src/main.cpp -o labs/shardvault/build/shardvault-sanitized
python3 labs/shardvault/tests/check.py labs/shardvault/build/shardvault-sanitized
```

The dedicated [Labs workflow](../.github/workflows/labs.yml) runs native Linux and
Windows builds and checks. Its Linux job also runs QEMU and sanitizers. Consult
the workflow's actual conclusion for the commit you download; a workflow file
alone is not evidence that a platform passed.
