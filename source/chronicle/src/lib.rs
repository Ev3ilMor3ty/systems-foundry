//! A single-writer, durable, hash-chained event file.
//!
//! Hashes detect corruption relative to a trusted head. Someone who can replace
//! the entire file can recompute the chain; keep head anchors separately.
use fs2::FileExt;
use serde::{Deserialize, Serialize};
use serde_json::Value;
use sha2::{Digest, Sha256};
use std::collections::HashMap;
use std::fs::{File, OpenOptions};
use std::io::{BufRead, BufReader, Read, Seek, SeekFrom, Write};
use std::path::Path;

pub const GENESIS: &str = "0000000000000000000000000000000000000000000000000000000000000000";
pub const MAX_RECORD_BYTES: usize = 1024 * 1024;
pub const MAX_RECORDS: usize = 100_000;
pub const MAX_LEDGER_BYTES: u64 = 64 * 1024 * 1024;
pub type Result<T> = std::result::Result<T, String>;

#[derive(Clone, Debug, Serialize, Deserialize, PartialEq)]
#[serde(deny_unknown_fields)]
pub struct Record {
    pub seq: u64,
    pub prev: String,
    pub id: String,
    pub event: Value,
    pub hash: String,
}

fn digest(seq: u64, prev: &str, id: &str, event: &Value) -> Result<String> {
    // serde_json's default Map sorts keys; framing is a JSON array, so fields
    // cannot be ambiguously concatenated. Domain/version prefix is explicit.
    let payload = serde_json::to_vec(&serde_json::json!([
        "foundry-chronicle-v1",
        seq,
        prev,
        id,
        event
    ]))
    .map_err(|e| e.to_string())?;
    Ok(format!("{:x}", Sha256::digest(payload)))
}

fn validate_id(id: &str) -> Result<()> {
    if id.is_empty()
        || id.len() > 128
        || !id
            .bytes()
            .all(|c| c.is_ascii_alphanumeric() || b"-_.:".contains(&c))
    {
        return Err(
            "id must be 1..128 ASCII letters, digits, dash, underscore, period or colon".into(),
        );
    }
    Ok(())
}

/// Read bounded lines and verify every predecessor, sequence number and hash.
/// An incomplete last line is an error, including when its JSON would parse.
pub fn read_verified(mut input: impl BufRead, anchor: Option<&str>) -> Result<Vec<Record>> {
    let mut records = Vec::new();
    let mut head = GENESIS.to_owned();
    let mut ids = std::collections::HashSet::new();
    let mut total_bytes = 0u64;
    loop {
        let mut line = Vec::new();
        let n = input
            .by_ref()
            .take((MAX_RECORD_BYTES + 2) as u64)
            .read_until(b'\n', &mut line)
            .map_err(|e| format!("read: {e}"))?;
        if n == 0 {
            break;
        }
        total_bytes += n as u64;
        if total_bytes > MAX_LEDGER_BYTES {
            return Err("ledger exceeds 64 MiB; archive it and start a new ledger".into());
        }
        if line.len() > MAX_RECORD_BYTES || line.last() != Some(&b'\n') {
            return Err(format!(
                "record {} exceeds limit or has a torn tail",
                records.len() + 1
            ));
        }
        if records.len() == MAX_RECORDS {
            return Err("record limit reached".into());
        }
        let r: Record = serde_json::from_slice(&line)
            .map_err(|e| format!("record {}: {e}", records.len() + 1))?;
        validate_id(&r.id)?;
        if r.seq != records.len() as u64 + 1 || r.prev != head {
            return Err(format!("broken sequence/predecessor at {}", r.seq));
        }
        if !ids.insert(r.id.clone()) {
            return Err(format!("duplicate id {}", r.id));
        }
        if r.hash != digest(r.seq, &r.prev, &r.id, &r.event)? {
            return Err(format!("hash mismatch at {}", r.seq));
        }
        head.clone_from(&r.hash);
        records.push(r);
    }
    if anchor.is_some_and(|a| a != head) {
        return Err("trusted head does not match (rollback or replacement possible)".into());
    }
    Ok(records)
}

pub struct Ledger {
    file: File,
    records: Vec<Record>,
    index: HashMap<String, usize>,
    poisoned: bool,
    bytes: u64,
}
impl Ledger {
    /// Acquires a nonblocking OS lock and verifies the file before any writes.
    /// Every append fsyncs data. An I/O error poisons this instance: restart and
    /// verify before retrying, as the record may already have reached the file.
    pub fn open(path: impl AsRef<Path>) -> Result<Self> {
        let mut file = OpenOptions::new()
            .read(true)
            .write(true)
            .create(true)
            .truncate(false)
            .open(path.as_ref())
            .map_err(|e| format!("open: {e}"))?;
        FileExt::try_lock_exclusive(&file)
            .map_err(|e| format!("ledger already locked or lock unavailable: {e}"))?;
        if file.metadata().map_err(|e| e.to_string())?.len() > MAX_LEDGER_BYTES {
            return Err("ledger exceeds 64 MiB".into());
        }
        let records = read_verified(BufReader::new(&mut file), None)?;
        // Make the filename durable as well as its contents on Unix filesystems.
        // The caller is responsible for provisioning a durable parent directory.
        #[cfg(unix)]
        {
            let parent = path
                .as_ref()
                .parent()
                .filter(|p| !p.as_os_str().is_empty())
                .unwrap_or_else(|| Path::new("."));
            File::open(parent)
                .and_then(|d| d.sync_all())
                .map_err(|e| format!("sync parent directory: {e}"))?;
        }
        let bytes = file.metadata().map_err(|e| e.to_string())?.len();
        file.seek(SeekFrom::End(0)).map_err(|e| e.to_string())?;
        let index = records
            .iter()
            .enumerate()
            .map(|(i, r)| (r.id.clone(), i))
            .collect();
        Ok(Self {
            file,
            records,
            index,
            poisoned: false,
            bytes,
        })
    }
    pub fn records(&self) -> &[Record] {
        &self.records
    }
    pub fn find(&self, id: &str) -> Option<&Record> {
        self.index.get(id).map(|i| &self.records[*i])
    }
    pub fn head(&self) -> &str {
        self.records.last().map_or(GENESIS, |r| &r.hash)
    }
    pub fn append(&mut self, id: &str, event: Value) -> Result<(Record, bool)> {
        if self.poisoned {
            return Err("ledger is degraded after I/O failure; restart and verify".into());
        }
        validate_id(id)?;
        if let Some(i) = self.index.get(id) {
            let previous = &self.records[*i];
            return if previous.event == event {
                Ok((previous.clone(), true))
            } else {
                Err("idempotency conflict: same id, different event".into())
            };
        }
        if self.records.len() == MAX_RECORDS {
            return Err("record limit reached".into());
        }
        let seq = self.records.len() as u64 + 1;
        let prev = self.head().to_owned();
        let hash = digest(seq, &prev, id, &event)?;
        let record = Record {
            seq,
            prev,
            id: id.to_owned(),
            event,
            hash,
        };
        let mut bytes = serde_json::to_vec(&record).map_err(|e| e.to_string())?;
        bytes.push(b'\n');
        if self.bytes + bytes.len() as u64 > MAX_LEDGER_BYTES {
            return Err("ledger reached 64 MiB; archive it and start a new ledger".into());
        }
        if bytes.len() > MAX_RECORD_BYTES {
            return Err("record exceeds 1 MiB limit".into());
        }
        if let Err(e) = self
            .file
            .write_all(&bytes)
            .and_then(|_| self.file.sync_data())
        {
            self.poisoned = true;
            return Err(format!(
                "durability outcome uncertain: {e}; restart and verify"
            ));
        }
        self.bytes += bytes.len() as u64;
        self.index.insert(id.to_owned(), self.records.len());
        self.records.push(record.clone());
        Ok((record, false))
    }
}

/// Verify under a shared lock, failing instead of racing an active writer.
pub fn verify_file(path: impl AsRef<Path>, anchor: Option<&str>) -> Result<Vec<Record>> {
    let file = File::open(path).map_err(|e| e.to_string())?;
    FileExt::try_lock_shared(&file).map_err(|e| format!("ledger busy: {e}"))?;
    read_verified(BufReader::new(file), anchor)
}
