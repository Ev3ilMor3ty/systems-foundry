use foundry_chronicle::{read_verified, verify_file, Ledger, GENESIS};
use serde_json::json;
use std::io::Cursor;

#[test]
fn durable_reopen_idempotency_and_conflict() {
    let dir = tempfile::tempdir().unwrap();
    let path = dir.path().join("events.jsonl");
    let head;
    {
        let mut l = Ledger::open(&path).unwrap();
        let (r, replay) = l.append("job-1", json!({"b":2,"a":1})).unwrap();
        assert!(!replay);
        head = r.hash;
        assert!(l.append("job-1", json!({"a":1,"b":2})).unwrap().1);
        assert!(l.append("job-1", json!({"a":3})).is_err());
        assert!(Ledger::open(&path).is_err());
        assert!(verify_file(&path, None).is_err());
    }
    let records = verify_file(&path, Some(&head)).unwrap();
    assert_eq!(records.len(), 1);
    assert!(verify_file(&path, Some(GENESIS)).is_err());
    let mut l = Ledger::open(&path).unwrap();
    assert!(l.append("job-1", json!({"a":1,"b":2})).unwrap().1);
    assert_eq!(l.append("job-2", json!({"x":true})).unwrap().0.seq, 2);
}
#[test]
fn detects_corruption_reordering_truncation_and_torn_tail() {
    let dir = tempfile::tempdir().unwrap();
    let path = dir.path().join("events");
    let mut l = Ledger::open(&path).unwrap();
    for i in 0..3 {
        l.append(&format!("r{i}"), json!({"value":i})).unwrap();
    }
    let head = l.head().to_owned();
    drop(l);
    let original = std::fs::read_to_string(&path).unwrap();
    let changed = original.replacen("\"value\":1", "\"value\":9", 1);
    assert!(read_verified(Cursor::new(changed), None).is_err());
    let lines: Vec<_> = original.lines().collect();
    let reordered = format!("{}\n{}\n{}\n", lines[1], lines[0], lines[2]);
    assert!(read_verified(Cursor::new(reordered), None).is_err());
    let shortened = format!("{}\n{}\n", lines[0], lines[1]);
    assert!(read_verified(Cursor::new(&shortened), None).is_ok());
    assert!(read_verified(Cursor::new(shortened), Some(&head)).is_err());
    assert!(read_verified(Cursor::new(original.trim_end()), None).is_err());
    assert!(read_verified(Cursor::new(format!("{original}{{\"seq\":")), None).is_err());
}
#[test]
fn refuses_invalid_ids_and_limits_without_mutating_file() {
    let dir = tempfile::tempdir().unwrap();
    let path = dir.path().join("events");
    let mut l = Ledger::open(&path).unwrap();
    for id in ["", "with spaces", "../path", "\n"] {
        assert!(l.append(id, json!(null)).is_err());
    }
    assert!(l.append("huge", json!("x".repeat(1024 * 1024))).is_err());
    assert_eq!(l.records().len(), 0);
    assert_eq!(std::fs::metadata(path).unwrap().len(), 0);
}
#[test]
fn many_records_reopen_with_exact_head() {
    let dir = tempfile::tempdir().unwrap();
    let path = dir.path().join("events");
    let mut l = Ledger::open(&path).unwrap();
    for i in 0..200 {
        l.append(
            &format!("event:{i}"),
            json!({"nested":[i,{"state":"ready"}]}),
        )
        .unwrap();
    }
    let head = l.head().to_owned();
    drop(l);
    assert_eq!(verify_file(&path, Some(&head)).unwrap().len(), 200);
}
