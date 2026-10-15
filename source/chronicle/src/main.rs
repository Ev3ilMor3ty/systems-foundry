use foundry_chronicle::{verify_file, Ledger, MAX_RECORD_BYTES};
use serde_json::{json, Value};
use std::io::{self, BufRead, Read, Write};

fn execute() -> Result<(), String> {
    let args: Vec<String> = std::env::args().collect();
    if args.len() < 3 {
        return Err(
            "usage: foundry-chronicle <serve|append|verify|export> FILE [ID JSON | TRUSTED_HEAD]"
                .into(),
        );
    }
    match args[1].as_str() {
        "verify" | "export" => {
            let records = verify_file(&args[2], args.get(3).map(String::as_str))?;
            if args[1] == "export" {
                for r in records {
                    println!("{}", serde_json::to_string(&r).unwrap());
                }
            } else {
                println!(
                    "{}",
                    json!({"ok":true,"records":records.len(),"head":records.last().map_or(foundry_chronicle::GENESIS, |r| &r.hash),"externally_anchored":args.len()>3})
                );
            }
        }
        "append" => {
            if args.len() != 5 {
                return Err("append requires ID and JSON event".into());
            }
            let mut ledger = Ledger::open(&args[2])?;
            let (r, replay) = ledger.append(
                &args[3],
                serde_json::from_str(&args[4]).map_err(|e| e.to_string())?,
            )?;
            println!("{}", json!({"ok":true,"record":r,"replayed":replay}));
        }
        "serve" => {
            let mut ledger = Ledger::open(&args[2])?;
            let stdin = io::stdin();
            let mut input = stdin.lock();
            let stdout = io::stdout();
            let mut out = stdout.lock();
            loop {
                let mut line = Vec::new();
                let n = input
                    .by_ref()
                    .take((MAX_RECORD_BYTES + 2) as u64)
                    .read_until(b'\n', &mut line)
                    .map_err(|e| e.to_string())?;
                if n == 0 {
                    break;
                }
                if line.len() > MAX_RECORD_BYTES || line.last() != Some(&b'\n') {
                    return Err("input too large or incomplete".into());
                }
                let result = (|| -> Result<Value, String> {
                    let request: Value =
                        serde_json::from_slice(&line).map_err(|e| e.to_string())?;
                    match request["op"].as_str() {
                        Some("append") => {
                            let id = request["id"].as_str().ok_or("missing id")?;
                            let event = request.get("event").ok_or("missing event")?.clone();
                            let (record, replayed) = ledger.append(id, event)?;
                            Ok(json!({"ok":true,"record":record,"replayed":replayed}))
                        }
                        Some("lookup") => {
                            let id = request["id"].as_str().ok_or("missing id")?;
                            Ok(json!({"ok":true,"record":ledger.find(id)}))
                        }
                        Some("status") => Ok(
                            json!({"ok":true,"records":ledger.records().len(),"head":ledger.head(),"last":ledger.records().last()}),
                        ),
                        // Lookup avoids exporting an unbounded array over the protocol.
                        Some("get") => {
                            let seq = request["seq"].as_u64().ok_or("missing positive seq")?;
                            let record = seq
                                .checked_sub(1)
                                .and_then(|i| ledger.records().get(i as usize));
                            Ok(json!({"ok":true,"record":record}))
                        }
                        _ => Err("unknown operation".into()),
                    }
                })();
                let response = result.unwrap_or_else(|e| json!({"ok":false,"error":e}));
                writeln!(out, "{response}")
                    .and_then(|_| out.flush())
                    .map_err(|e| e.to_string())?;
            }
        }
        _ => return Err("unknown command".into()),
    }
    Ok(())
}
fn main() {
    if let Err(e) = execute() {
        eprintln!("chronicle: {e}");
        std::process::exit(1);
    }
}
