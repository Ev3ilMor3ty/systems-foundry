# Chronicle

A Rust append-only JSON event ledger with SHA-256 chaining, durable appends, a nonblocking exclusive writer lock and idempotent IDs. It runs as a CLI or bounded JSONL stdio worker; no database service is needed.

```bash
cargo build --release --locked
./target/release/foundry-chronicle append events.jsonl example-1 '{"kind":"created","value":42}'
./target/release/foundry-chronicle verify events.jsonl
./target/release/foundry-chronicle export events.jsonl
```

`verify FILE TRUSTED_HEAD` requires the complete current chain to end at that independently stored hash. A valid shorter history passes internal verification but fails a mismatching trusted anchor. A legitimate later append also changes the head; anchors refer to a specific checkpoint.

## Stdio worker

```bash
./target/release/foundry-chronicle serve events.jsonl
```

Send one JSON object per line. Every response is one flushed JSON line:

```json
{"op":"append","id":"command-1","event":{"kind":"created","value":42}}
{"op":"lookup","id":"command-1"}
{"op":"status"}
{"op":"get","seq":1}
```

Append returns `record` and `replayed`; status returns record count, head and last record. Lookup/get return a record or null. Reusing an ID with identical event content replays the record; different content is rejected. IDs are 1..128 ASCII letters, digits, dash, underscore, period or colon.

The process verifies the entire file before accepting commands and retains its exclusive writer lock until it exits. Another writer or standalone verifier fails immediately rather than waiting or racing it.

## Failure behavior

- A failed append I/O operation can have an uncertain outcome. The writer then refuses more appends. Restart and verify the file; retry the same ID after recovery.
- Torn tails, malformed records and inconsistent hashes are errors. There is no silent truncation or repair.
- A full ledger is preserved. Archive it and start another file when the 64 MiB or 100,000-record limit is reached.
- Records and protocol lines are capped at 1 MiB. Memory use grows with the bounded verified history and index.
- Hashes detect corruption relative to a trusted checkpoint, not a complete recomputation by someone controlling the file. No signatures or remote anchoring service are implied.

See [the precise format and durability scope](../docs/ARCHITECTURE.md#ledger-boundary).

## Tests

```bash
cargo test --locked
python3 tests/process_failures.py
```

The Python suite requires Linux and the release executable. It injects a real short write using a file-size limit, kills a writer after acknowledgements, checks cross-process locks, rejects an incomplete input line and confirms that corrupt evidence is retained. Unit tests cover reopened IDs, tampering, reordering, truncation and bounds.
