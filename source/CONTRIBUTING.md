# Contributing

Build and run the documented checks before proposing a change. Keep optimizer changes separate from UI changes so failures can be traced to one boundary.

- C++ matching changes need brute-force small-instance comparisons and independently checked certificates.
- IPC or persistence changes need actual process/failure tests, not only mocks.
- Java concurrency changes must pass the single-carrier regression.
- UI changes should preserve keyboard access, reduced-motion behavior, responsive layouts and safe text rendering.
- Record benchmark inputs, versions and scope. Keep interrupted/failed endurance evidence; do not turn a partial run into a pass.

Use Rustfmt for Rust, Google Java Format for Java, Clang Format (LLVM style, column limit 100) for C++, Prettier for frontend files and Black for Python tools. Runtime code must not depend on development-only formatting or browser-test packages.

The companion kernel repository has a separate VM-only boundary. Never add host module-loading commands to the application build or tests.
