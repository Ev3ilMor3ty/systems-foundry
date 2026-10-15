# FNDYRS01 fragment format

All integers are unsigned little-endian. The header is 64 bytes, followed by
exactly `shard_size` payload bytes. Trailing bytes are rejected.

| Offset | Bytes | Meaning |
| --- | --- | --- |
| 0 | 8 | ASCII `FNDYRS01` |
| 8 | 1 | Number of data fragments k, 2..16 |
| 9 | 1 | Number of parity fragments m, 1..8 |
| 10 | 1 | Fragment index, 0..k+m-1 |
| 11 | 1 | Reserved, zero |
| 12 | 8 | Original file size, at most 64 MiB |
| 20 | 8 | Fragment payload size: max(1, ceil(original_size/k)) |
| 28 | 4 | CRC32 of original file |
| 32 | 16 | Random set identifier |
| 48 | 4 | CRC32 of this payload |
| 52 | 4 | CRC32 of bytes 0..51 |
| 56 | 8 | Reserved, zero |
| 64 | shard_size | Payload |

CRC32 is the IEEE reflected algorithm with polynomial `0xedb88320`, initial
state `0xffffffff` and final XOR `0xffffffff`, matching Python `zlib.crc32`.

The finite field is GF(2^8) using irreducible polynomial `0x11d`. Addition is
XOR. Let V[i,j] = (i+1)^j in that field for 0 <= i < k+m, 0 <= j < k.
The generator matrix is G = V * inverse(V[0:k,0:k]). Its top k rows are the
identity. Divide the padded original byte stream into k contiguous equal-size
blocks. Payload i is the bytewise field-linear combination specified by G[i].

Any k distinct row points are invertible. Recovery uses their inverse to obtain
the original k blocks, concatenates them, trims to the original length and
checks the original CRC32 before opening a new output file. A zero-length input
uses one zero padding byte per fragment and recovers as an empty file.

The random identifier prevents accidental set mixing; it is not a secret or
cryptographic identity. CRC values are not signatures.
