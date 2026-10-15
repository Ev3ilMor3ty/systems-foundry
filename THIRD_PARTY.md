# Third-party components

The implementations use existing toolchains and libraries; this repository does not claim those components as original work.

| Component | Version / location | License |
| --- | --- | --- |
| nlohmann/json | 3.12.0, `dispatch/vendor/json.hpp` | MIT; complete notice in `dispatch/vendor/LICENSE.nlohmann-json` and the header |
| Gson | 2.13.1, pinned in `control-api/pom.xml` | Apache-2.0 |
| Error Prone annotations | 2.38.0, transitive Gson dependency | Apache-2.0 |
| JUnit | 5.12.2, test dependency | EPL-2.0 |
| Rust dependencies | Exact versions and registry checksums in `chronicle/Cargo.lock` | See each crate's license metadata and packaged license texts |
| Prettier | 3.6.2, development only | MIT |
| axe-core | 4.10.3, development only | MPL-2.0 |

The application has no third-party CDN or analytics dependency at runtime. Portable distributions preserve applicable library license files. Dependencies obtained during source builds retain their upstream notices. Toolchain licenses apply to the toolchains themselves.

The companion WorkPulse kernel module is separately licensed GPL-2.0-only. It is not linked into the MIT application.

Bundled nlohmann/json header SHA-256: `aaf127c04cb31c406e5b04a63f1ae89369fccde6d8fa7cdda1ed4f32dfc5de63`.
