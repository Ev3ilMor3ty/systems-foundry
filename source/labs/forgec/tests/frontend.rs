use forgec::{check, compile, diagnostic, Target};

#[test]
fn functions_scopes_and_forward_calls_resolve() {
    let p =
        check("int main(){int a=f(4);{int a=a+1;print(a);}return a;} int f(int n){return n*2;}")
            .unwrap();
    assert_eq!(p.functions.len(), 2);
    assert_eq!(p.functions[0].locals, 2);
}

#[test]
fn rejects_unknown_names_arities_and_invalid_control_flow() {
    let cases = [
        ("int main(){return x;}", "unknown variable"),
        ("int main(){x=1;return 0;}", "unknown variable"),
        ("int main(){return f(1);}", "unknown function"),
        (
            "int f(int a){return a;}int main(){return f();}",
            "expects 1",
        ),
        ("int main(){int x=1;int x=2;}", "duplicate variable"),
        ("int main(){break;}", "enclosing while"),
        ("int main(){continue;}", "enclosing while"),
        ("int main(){if(1){int x=1;}return x;}", "unknown variable"),
        ("int main(){int x=x;}", "unknown variable"),
        (
            "int f(int a,int a){return a;}int main(){}",
            "duplicate parameter",
        ),
        ("int main(){}int main(){}", "duplicate function"),
        ("int main(int n){return n;}", "must not take"),
        ("int f(){return 0;}", "needs int main"),
    ];
    for (source, message) in cases {
        let err = check(source).err().unwrap();
        assert!(err.message.contains(message), "{}", err.message);
    }
}

#[test]
fn diagnostics_have_line_column_and_context() {
    let source = "int main() {\n  return missing;\n}\n";
    let e = check(source).err().unwrap();
    let text = diagnostic(source, "test.fc", &e);
    assert!(text.starts_with("test.fc:2:10: error:"));
    assert!(text.contains("  return missing;"));
    assert!(text.ends_with("         ^"));
}

#[test]
fn bad_lexical_syntax_is_rejected() {
    for source in [
        "int main(){print(\"unterminated);}",
        "/* never closed",
        "int main(){return 18446744073709551616;}",
        "int main(){return 0x;}",
        "int main(){print(\"\\q\");}",
        "int main(){print(\"line\nbreak\");}",
        "int main(){int if=0;}",
        "int main(){return 0}",
        "int main(){if(1)return 0;}",
        "int main(){return 0;",
        "int main(){return é;}",
    ] {
        assert!(check(source).is_err(), "accepted {source}");
    }
}

#[test]
fn resource_bounds_fail_cleanly() {
    let source = format!(
        "int main(){{return {}1{};}}",
        "(".repeat(80),
        ")".repeat(80)
    );
    assert!(check(&source).is_err());
    let source = format!("int main(){{return {}1;}}", "1+".repeat(80));
    assert!(check(&source).is_err());
    let source = format!(
        "int main(){{{}return 0;{}}}",
        "{".repeat(40),
        "}".repeat(40)
    );
    assert!(check(&source).is_err());
    let source = format!(
        "int main(){{{}return 0;}}",
        (0..260).map(|n| format!("int a{n}=0;")).collect::<String>()
    );
    assert!(check(&source).is_err());
    assert!(check(&" ".repeat(65537)).is_err());
}

#[test]
fn executable_formats_are_deterministic_and_separate_code_permissions() {
    let source = "int main(){print(\"hello\");return 3;}";
    for target in [Target::Linux, Target::Windows] {
        let a = compile(source, target, true).unwrap();
        let b = compile(source, target, true).unwrap();
        assert_eq!(a.bytes, b.bytes);
        assert_eq!(a.functions.len(), 1);
        if target == Target::Linux {
            assert_eq!(&a.bytes[..4], b"\x7fELF");
            assert_eq!(u32::from_le_bytes(a.bytes[68..72].try_into().unwrap()), 5);
        } else {
            assert_eq!(&a.bytes[..2], b"MZ");
            assert_eq!(&a.bytes[0x80..0x84], b"PE\0\0");
            assert!(a.bytes.windows(13).any(|w| w == b"KERNEL32.dll\0"));
        }
    }
}

#[test]
fn constant_folding_reduces_code_without_hiding_name_errors() {
    let source = "int main(){return (2+3)*(7+4);}";
    assert!(
        compile(source, Target::Linux, true).unwrap().bytes.len()
            < compile(source, Target::Linux, false).unwrap().bytes.len()
    );
    assert!(compile("int main(){return 0&&missing;}", Target::Linux, true).is_err());
}
