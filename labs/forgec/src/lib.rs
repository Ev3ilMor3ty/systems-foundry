mod image;
mod native;
pub mod syntax;
pub use native::Target;
pub use syntax::{Error, Program};

pub struct Artifact {
    pub bytes: Vec<u8>,
    pub functions: Vec<(String, usize)>,
}
pub fn check(source: &str) -> syntax::Result<Program> {
    syntax::parse(source)
}
pub fn compile(source: &str, target: Target, fold: bool) -> syntax::Result<Artifact> {
    let program = check(source)?;
    let code = native::generate(&program, target, fold)?;
    let bytes = match target {
        Target::Linux => image::elf(&code.bytes),
        Target::Windows => image::pe(&code.bytes),
    };
    Ok(Artifact {
        bytes,
        functions: code.functions,
    })
}

pub fn diagnostic(source: &str, file: &str, error: &Error) -> String {
    let at = error.at.min(source.len());
    let line = source[..at].bytes().filter(|b| *b == b'\n').count() + 1;
    let start = source[..at].rfind('\n').map(|p| p + 1).unwrap_or(0);
    let column = source[start..at].chars().count() + 1;
    let end = source[at..]
        .find('\n')
        .map(|n| at + n)
        .unwrap_or(source.len());
    format!(
        "{file}:{line}:{column}: error: {}\n{}\n{}^",
        error.message,
        &source[start..end],
        " ".repeat(column - 1)
    )
}
