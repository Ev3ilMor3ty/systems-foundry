use rv32::{demo, mnemonic, words_to_bytes, Halt, Machine, Trap};

fn machine(words: &[u32]) -> Machine {
    Machine::new(&words_to_bytes(words), 8192).unwrap()
}
fn r(f3: u32, f7: u32) -> u32 {
    (f7 << 25) | (6 << 20) | (5 << 15) | (f3 << 12) | (7 << 7) | 0x33
}
fn i(f3: u32, immediate: u32) -> u32 {
    ((immediate & 4095) << 20) | (5 << 15) | (f3 << 12) | (7 << 7) | 0x13
}
fn branch(f3: u32, offset: i32) -> u32 {
    let x = offset as u32;
    ((x >> 12 & 1) << 31)
        | ((x >> 5 & 63) << 25)
        | (6 << 20)
        | (5 << 15)
        | (f3 << 12)
        | ((x >> 1 & 15) << 8)
        | ((x >> 11 & 1) << 7)
        | 0x63
}

#[test]
fn all_register_integer_operations_on_edges() {
    let values: [u32; 8] = [0, 1, 31, 32, 0x7fffffff, 0x80000000, 0xffffffff, 0x12345678];
    for a in values {
        for b in values {
            let cases = [
                ((0, 0), a.wrapping_add(b)),
                ((0, 32), a.wrapping_sub(b)),
                ((1, 0), a << (b & 31)),
                ((2, 0), ((a as i32) < (b as i32)) as u32),
                ((3, 0), (a < b) as u32),
                ((4, 0), a ^ b),
                ((5, 0), a >> (b & 31)),
                ((5, 32), ((a as i32) >> (b & 31)) as u32),
                ((6, 0), a | b),
                ((7, 0), a & b),
            ];
            for ((f3, f7), expected) in cases {
                let mut m = machine(&[r(f3, f7)]);
                m.registers[5] = a;
                m.registers[6] = b;
                m.step().unwrap();
                assert_eq!(m.registers[7], expected, "f3={f3} f7={f7} a={a} b={b}");
            }
        }
    }
}

#[test]
fn immediate_operations_and_sign_extension() {
    for a in [0u32, 1, 0x80000000, 0xffffffff] {
        for imm in [-2048i32, -1, 0, 1, 2047] {
            let b = imm as u32;
            for (f3, expected) in [
                (0, a.wrapping_add(b)),
                (2, ((a as i32) < imm) as u32),
                (3, (a < b) as u32),
                (4, a ^ b),
                (6, a | b),
                (7, a & b),
            ] {
                let mut m = machine(&[i(f3, b)]);
                m.registers[5] = a;
                m.step().unwrap();
                assert_eq!(m.registers[7], expected);
            }
            for shift in [0, 1, 31] {
                for (f3, encoded, expected) in [
                    (1, shift, a << shift),
                    (5, shift, a >> shift),
                    (5, 0x400 | shift, ((a as i32) >> shift) as u32),
                ] {
                    let mut m = machine(&[i(f3, encoded)]);
                    m.registers[5] = a;
                    m.step().unwrap();
                    assert_eq!(m.registers[7], expected);
                }
            }
        }
    }
}

#[test]
fn branches_signed_unsigned_taken_and_not_taken() {
    for a in [0u32, 1, 0x80000000, 0xffffffff] {
        for b in [0u32, 1, 0xffffffff] {
            for (f3, take) in [
                (0, a == b),
                (1, a != b),
                (4, (a as i32) < (b as i32)),
                (5, (a as i32) >= (b as i32)),
                (6, a < b),
                (7, a >= b),
            ] {
                for offset in [-4, 8] {
                    let mut m = machine(&[branch(f3, offset)]);
                    m.registers[5] = a;
                    m.registers[6] = b;
                    m.step().unwrap();
                    assert_eq!(m.pc, if take { offset as u32 } else { 4 });
                }
            }
        }
    }
}

#[test]
fn jal_and_jalr_links_aliasing_and_low_bit() {
    let mut m = machine(&[0x008002ef]); // jal x5,+8
    m.step().unwrap();
    assert_eq!((m.pc, m.registers[5]), (8, 4));
    let mut m = machine(&[0x001282e7]); // jalr x5,1(x5), source must precede dest write
    m.registers[5] = 8;
    m.step().unwrap();
    assert_eq!((m.pc, m.registers[5]), (8, 4));
    let mut m = machine(&[0x00000297, 0xabcde337]);
    m.step().unwrap();
    m.step().unwrap();
    assert_eq!(m.registers[5], 0);
    assert_eq!(m.registers[6], 0xabcde000);
    let mut m = machine(&[0x00000013, 0xfffff297]);
    m.step().unwrap();
    m.step().unwrap();
    assert_eq!(m.registers[5], 0xfffff004);
}

#[test]
fn loads_and_stores_are_little_endian_and_sign_extend() {
    // sw x6,0(x5); lb/lbu/lh/lhu/lw x7,0(x5)
    for (f3, expected) in [
        (0, 0xffffff80),
        (4, 0x80),
        (1, 0xfffffe80),
        (5, 0xfe80),
        (2, 0x1234fe80),
    ] {
        let load = (5 << 15) | (f3 << 12) | (7 << 7) | 0x03;
        let mut m = machine(&[0x0062a023, load]);
        m.registers[5] = 4096;
        m.registers[6] = 0x1234fe80;
        m.step().unwrap();
        m.step().unwrap();
        assert_eq!(m.registers[7], expected);
        assert_eq!(&m.memory()[4096..4100], &[0x80, 0xfe, 0x34, 0x12]);
    }
    for (store, expected) in [
        (0x00628023, vec![0x80, 0, 0, 0]),
        (0x00629023, vec![0x80, 0xfe, 0, 0]),
    ] {
        let mut m = machine(&[store]);
        m.registers[5] = 4096;
        m.registers[6] = 0x1234fe80;
        m.step().unwrap();
        assert_eq!(&m.memory()[4096..4100], expected);
    }
    let mut m = machine(&[0xfe62ae23, 0xffc2a383]); // sw x6,-4(x5);lw x7,-4(x5)
    m.registers[5] = 4100;
    m.registers[6] = 123;
    m.step().unwrap();
    m.step().unwrap();
    assert_eq!(m.registers[7], 123);
}

#[test]
fn traps_do_not_partially_commit() {
    for instruction in [0x00000000, 0x020283b3, 0x02029393, 0x0000100f] {
        let mut m = machine(&[instruction]);
        let before = m.registers;
        assert!(matches!(m.step(), Err(Trap::IllegalInstruction(_))));
        assert_eq!(m.pc, 0);
        assert_eq!(m.steps, 0);
        assert_eq!(m.registers, before);
    }
    let mut m = machine(&[0x002002ef]); // jal x5,2: no link write on misaligned target
    let before = m.registers;
    assert!(matches!(m.step(), Err(Trap::InstructionMisaligned(2))));
    assert_eq!(m.registers, before);
}

#[test]
fn memory_and_fetch_traps_at_boundaries() {
    let mut m = machine(&[0x0002a383]);
    m.registers[5] = 8192;
    assert!(matches!(m.step(), Err(Trap::AccessFault(8192))));
    m.registers[5] = 8191;
    assert!(matches!(m.step(), Err(Trap::LoadMisaligned(8191))));
    let mut m = machine(&[0x0062a023]);
    m.registers[5] = 8191;
    assert!(matches!(m.step(), Err(Trap::StoreMisaligned(8191))));
    m.registers[5] = 0xfffffffc;
    assert!(matches!(m.step(), Err(Trap::AccessFault(_))));
    m.pc = 2;
    assert!(matches!(m.step(), Err(Trap::InstructionMisaligned(2))));
    m.pc = 8192;
    assert!(matches!(m.step(), Err(Trap::AccessFault(8192))));
    assert!(Machine::new(&[1], 8192).is_err());
    assert!(Machine::new(&[0; 20], 16).is_err());
}

#[test]
fn x0_writes_discarded_but_loads_still_trap() {
    let mut m = machine(&[0x00a00013, 0x00002283]);
    m.step().unwrap();
    assert_eq!(m.registers[0], 0);
    let mut m = machine(&[0x0002a003]);
    m.registers[5] = 8192;
    assert!(matches!(m.step(), Err(Trap::AccessFault(_))));
}

#[test]
fn breakpoint_ecall_fence_and_fuel() {
    let mut m = machine(&[0x0000000f, 0x00100073]);
    assert_eq!(m.run(2), Ok(Halt::Breakpoint));
    assert!(matches!(m.step(), Err(Trap::AlreadyHalted)));
    let mut m = machine(&[0x00000073]);
    m.registers[17] = 93;
    m.registers[10] = 17;
    assert_eq!(m.run(1), Ok(Halt::Exit(17)));
    let mut m = machine(&[0x00000073]);
    assert!(matches!(m.step(), Err(Trap::UnsupportedEcall(0))));
    let mut m = machine(&[0x0000006f]);
    assert_eq!(m.run(100), Err(Trap::StepLimit));
    assert_eq!(m.steps, 100);
}

#[test]
fn demos_match_mathematical_results() {
    for (name, answer, steps) in [("fibonacci", 6765, 104), ("memory-sum", 4950, 605)] {
        let mut m = Machine::new(&demo(name).unwrap(), 65536).unwrap();
        assert_eq!(m.run(1000), Ok(Halt::Breakpoint));
        assert_eq!(m.registers[10], answer);
        assert_eq!(m.steps, steps);
    }
    assert_eq!(mnemonic(0x00100073), "ebreak");
    assert_eq!(mnemonic(0x020283b3), "illegal");
}
