use rv32::{demo, mnemonic, Machine};
use std::fs::{self, OpenOptions};
use std::io::{BufWriter, Read, Write};

fn main() {
    if let Err(error) = run() {
        eprintln!("rv32: {error}");
        std::process::exit(1);
    }
}

fn run() -> Result<(), Box<dyn std::error::Error>> {
    let args: Vec<String> = std::env::args().skip(1).collect();
    if args.is_empty() || args[0] == "--help" {
        println!("rv32 demo fibonacci|memory-sum [--max-steps N] [--trace NEW.jsonl]\nrv32 run PROGRAM.bin [--memory BYTES] [--max-steps N] [--trace NEW.jsonl]\nrv32 disasm PROGRAM.bin\nrv32 export-demo fibonacci|memory-sum NEW.bin\nRaw little-endian RV32I at PC=0; EBREAK stops, ECALL a7=93 exits. No ELF loader.");
        return Ok(());
    }
    if args.len() < 2 {
        return Err("missing program or demo name".into());
    }
    let command = args[0].as_str();
    let program = if command == "demo" || command == "export-demo" {
        demo(&args[1]).ok_or("unknown demo")?
    } else if command == "run" || command == "disasm" {
        let mut bytes = Vec::new();
        fs::File::open(&args[1])?
            .take(1024 * 1024 + 1)
            .read_to_end(&mut bytes)?;
        if bytes.len() > 1024 * 1024 {
            return Err("program exceeds 1 MiB".into());
        }
        bytes
    } else {
        return Err("unknown command; use --help".into());
    };
    if program.len() % 4 != 0 {
        return Err("program size is not a multiple of four".into());
    }
    if command == "export-demo" {
        if args.len() != 3 {
            return Err("export-demo needs one new output path".into());
        }
        OpenOptions::new()
            .write(true)
            .create_new(true)
            .open(&args[2])?
            .write_all(&program)?;
        return Ok(());
    }
    if command == "disasm" {
        if args.len() != 2 {
            return Err("disasm takes one input".into());
        }
        for (i, bytes) in program.chunks_exact(4).enumerate() {
            let word = u32::from_le_bytes(bytes.try_into().unwrap());
            println!("{:08x}  {word:08x}  {}", i * 4, mnemonic(word));
        }
        return Ok(());
    }
    let mut memory = 65536usize;
    let mut max_steps = 100000u64;
    let mut trace_path = None;
    let mut i = 2;
    while i < args.len() {
        if i + 1 == args.len() {
            return Err("option is missing its value".into());
        }
        match args[i].as_str() {
            "--memory" => memory = args[i + 1].parse()?,
            "--max-steps" => max_steps = args[i + 1].parse()?,
            "--trace" if trace_path.is_none() => trace_path = Some(args[i + 1].clone()),
            _ => return Err("unknown or duplicate trace option".into()),
        }
        i += 2;
    }
    if max_steps == 0 || max_steps > 10_000_000 {
        return Err("max-steps must be 1..10000000".into());
    }
    let mut machine = Machine::new(&program, memory)?;
    let mut trace = trace_path
        .map(|path| {
            OpenOptions::new()
                .write(true)
                .create_new(true)
                .open(path)
                .map(BufWriter::new)
        })
        .transpose()?;
    for _ in 0..max_steps {
        let step = machine.step()?;
        if let Some(writer) = trace.as_mut() {
            let reg = step
                .register_write
                .map(|(r, v)| format!("[{},{}]", r, v))
                .unwrap_or("null".into());
            let mem = step
                .memory_write
                .map(|(a, v, n)| format!("[{}, {}, {}]", a, v, n))
                .unwrap_or("null".into());
            writeln!(writer, "{{\"step\":{},\"pc\":{},\"instruction\":{},\"op\":\"{}\",\"next_pc\":{},\"register_write\":{},\"memory_write\":{}}}",
                machine.steps, step.pc, step.instruction, mnemonic(step.instruction), step.next_pc, reg, mem)?;
        }
        if machine.halted.is_some() {
            break;
        }
    }
    if let Some(writer) = trace.as_mut() {
        writer.flush()?;
    }
    let halt = machine.halted.as_ref().ok_or(rv32::Trap::StepLimit)?;
    let reason = match halt {
        rv32::Halt::Breakpoint => "breakpoint",
        rv32::Halt::Exit(_) => "exit",
    };
    println!(
        "{{\"halt\":\"{reason}\",\"steps\":{},\"pc\":{},\"a0\":{},\"registers\":{:?}}}",
        machine.steps, machine.pc, machine.registers[10], machine.registers
    );
    Ok(())
}
