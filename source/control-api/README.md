# Control API

Java 21's HTTP server coordinates the fictional logistics state, a C++ matching subprocess and a Rust durable ledger. Virtual threads serve local requests and bounded live snapshot streams; state transitions are serialized and revision-checked.

Build from the repository root using `./scripts/build.sh`, then `./scripts/run.sh`. Maven can run the Java unit and HTTP checks independently:

```bash
mvn -B -f control-api/pom.xml test
```

A command looks like:

```json
{"commandId":"client-unique-1","expectedRevision":0,"ticks":5}
```

Send it with `Content-Type: application/json` to `/api/advance`. Use a new command ID for a genuinely new action. Retry the exact same operation and request with its original ID when an acknowledgement is lost. A stale revision produces HTTP 409, a validation error HTTP 400, and an unavailable native dependency HTTP 503.

The server binds to `127.0.0.1`; it is a local demonstration with no authentication service. See [installation](../docs/INSTALL.md) and [HTTP, state and process contracts](../docs/ARCHITECTURE.md).

The Java tests include real HTTP requests, competing edits, durable-publication ordering, idempotency across restart, malformed/stalled native peers and independent proof verification. The Python integration suite uses the actual Java, C++ and Rust executables for crash and dependency-failure checks.
