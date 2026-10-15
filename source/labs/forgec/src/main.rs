use forgec::{check, compile, diagnostic, Target};
use std::fs::{File, OpenOptions};
use std::io::{Read, Write};

fn main() {
    if let Err(message) = run() {
        eprintln!("{message}");
        std::process::exit(1);
    }
}
fn run() -> Result<(), String> {
    let args: Vec<String> = std::env::args().skip(1).collect();
    if args.is_empty() || args[0] == "--help" {
        println!("ForgeC 0.1.0 — C-like source to native x86-64\nforgec check INPUT.fc\nforgec build INPUT.fc -o NEW_OUTPUT [--target linux|windows] [--no-fold]\nNo assembler/linker/backend dependency. Sources limited to 64 KiB.");
        return Ok(());
    }
    if args.len() < 2 {
        return Err("forgec: expected an input file".into());
    }
    let mut input = Vec::new();
    File::open(&args[1])
        .map_err(|e| e.to_string())?
        .take(65537)
        .read_to_end(&mut input)
        .map_err(|e| e.to_string())?;
    if input.len() > 65536 {
        return Err("forgec: source exceeds 64 KiB".into());
    }
    let source = String::from_utf8(input).map_err(|_| "forgec: source must be UTF-8")?;
    if args[0] == "check" {
        if args.len() != 2 {
            return Err("forgec: check takes one input".into());
        }
        let program = check(&source).map_err(|e| diagnostic(&source, &args[1], &e))?;
        println!("{{\"ok\":true,\"functions\":{}}}", program.functions.len());
        return Ok(());
    }
    if args[0] != "build" {
        return Err("forgec: unknown command; use --help".into());
    }
    let mut output = None;
    let mut target = if cfg!(windows) {
        Target::Windows
    } else {
        Target::Linux
    };
    let mut fold = true;
    let mut i = 2;
    while i < args.len() {
        if args[i] == "--no-fold" {
            fold = false;
            i += 1;
            continue;
        }
        if i + 1 == args.len() {
            return Err("forgec: option is missing its value".into());
        }
        match args[i].as_str() {
            "-o" if output.is_none() => output = Some(&args[i + 1]),
            "--target" => {
                target = match args[i + 1].as_str() {
                    "linux" => Target::Linux,
                    "windows" => Target::Windows,
                    _ => return Err("forgec: target must be linux or windows".into()),
                }
            }
            _ => return Err("forgec: unknown or duplicate output option".into()),
        }
        i += 2;
    }
    let output = output.ok_or("forgec: use -o with a new output path")?;
    let artifact = compile(&source, target, fold).map_err(|e| diagnostic(&source, &args[1], &e))?;
    let mut file = OpenOptions::new()
        .write(true)
        .create_new(true)
        .open(output)
        .map_err(|e| format!("forgec: cannot create {output}: {e}"))?;
    file.write_all(&artifact.bytes)
        .map_err(|e| format!("forgec: output write failed: {e}"))?;
    #[cfg(unix)]
    {
        use std::os::unix::fs::PermissionsExt;
        file.set_permissions(std::fs::Permissions::from_mode(0o755))
            .map_err(|e| e.to_string())?;
    }
    let name = if target == Target::Linux {
        "linux-x86_64"
    } else {
        "windows-x86_64"
    };
    println!("{{\"ok\":true,\"target\":\"{name}\",\"bytes\":{},\"functions\":{},\"constant_folding\":{fold}}}",artifact.bytes.len(),artifact.functions.len());
    Ok(())
}
