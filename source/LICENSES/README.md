# Library notices

The Java application uses Gson (Google and Gson contributors) and Error Prone annotations (Google and contributors), under Apache-2.0. The complete license is included here. The shaded application JAR does not embed their license text, so portable packages include this directory alongside the JAR.

The nlohmann/json MIT notice is in `dispatch/vendor/LICENSE.nlohmann-json`. Rust portable packages include license/notice texts collected from the exact locked dependency sources, plus the Rust standard-library MIT/Apache license texts. Source builds obtain those crates through Cargo using the registry checksums in Cargo.lock.

The included Rust standard-library license texts are from the upstream Rust 1.85.1 tag. Portable package generation also collects the exact locked crate notices from Cargo metadata; it stops if a crate has no discovered license text.
