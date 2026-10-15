//! RV32I unprivileged integer interpreter. No devices, CSRs or extensions.
use std::fmt;

#[derive(Debug, Clone, PartialEq, Eq)]
pub enum Trap {
    InstructionMisaligned(u32),
    AccessFault(u32),
    LoadMisaligned(u32),
    StoreMisaligned(u32),
    IllegalInstruction(u32),
    UnsupportedEcall(u32),
    AlreadyHalted,
    StepLimit,
}

impl fmt::Display for Trap {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        write!(f, "{self:?}")
    }
}
impl std::error::Error for Trap {}

#[derive(Debug, Clone, PartialEq, Eq)]
pub enum Halt {
    Breakpoint,
    Exit(u32),
}

#[derive(Debug, Clone)]
pub struct Step {
    pub pc: u32,
    pub instruction: u32,
    pub next_pc: u32,
    pub register_write: Option<(usize, u32)>,
    pub memory_write: Option<(u32, u32, usize)>,
}

pub struct Machine {
    pub registers: [u32; 32],
    pub pc: u32,
    pub halted: Option<Halt>,
    pub steps: u64,
    memory: Vec<u8>,
}

fn sext(value: u32, bits: u32) -> u32 {
    ((value << (32 - bits)) as i32 >> (32 - bits)) as u32
}

impl Machine {
    pub fn new(program: &[u8], memory_size: usize) -> Result<Self, &'static str> {
        if !(16..=16 * 1024 * 1024).contains(&memory_size) || program.len() > memory_size {
            return Err("memory must be 16 bytes..16 MiB and contain the program");
        }
        if program.len() % 4 != 0 {
            return Err("RV32I program length must be a multiple of four bytes");
        }
        let mut memory = vec![0; memory_size];
        memory[..program.len()].copy_from_slice(program);
        let mut registers = [0; 32];
        registers[2] = (memory_size & !15) as u32;
        Ok(Self {
            registers,
            pc: 0,
            halted: None,
            steps: 0,
            memory,
        })
    }

    pub fn memory(&self) -> &[u8] {
        &self.memory
    }

    fn range(&self, address: u32, size: usize) -> Result<usize, Trap> {
        let start = address as usize;
        match start.checked_add(size) {
            Some(end) if end <= self.memory.len() => Ok(start),
            _ => Err(Trap::AccessFault(address)),
        }
    }

    fn load(&self, address: u32, size: usize) -> Result<u32, Trap> {
        if address % size as u32 != 0 {
            return Err(Trap::LoadMisaligned(address));
        }
        let start = self.range(address, size)?;
        Ok(self.memory[start..start + size]
            .iter()
            .enumerate()
            .fold(0, |word, (i, b)| word | ((*b as u32) << (8 * i))))
    }

    pub fn step(&mut self) -> Result<Step, Trap> {
        if self.halted.is_some() {
            return Err(Trap::AlreadyHalted);
        }
        if self.pc % 4 != 0 {
            return Err(Trap::InstructionMisaligned(self.pc));
        }
        let start = self.range(self.pc, 4)?;
        let insn = u32::from_le_bytes(self.memory[start..start + 4].try_into().unwrap());
        let op = insn & 127;
        let rd = ((insn >> 7) & 31) as usize;
        let f3 = (insn >> 12) & 7;
        let rs1 = ((insn >> 15) & 31) as usize;
        let rs2 = ((insn >> 20) & 31) as usize;
        let f7 = insn >> 25;
        // x0 is hard-wired even if a debugger has written the public register array.
        let a = if rs1 == 0 { 0 } else { self.registers[rs1] };
        let b = if rs2 == 0 { 0 } else { self.registers[rs2] };
        let imm = sext(insn >> 20, 12);
        let illegal = || Trap::IllegalInstruction(insn);
        let mut next = self.pc.wrapping_add(4);
        let mut write = None;
        let mut store = None;
        let mut halt = None;
        match op {
            0x37 => write = Some(insn & 0xfffff000),
            0x17 => write = Some(self.pc.wrapping_add(insn & 0xfffff000)),
            0x6f => {
                let offset = sext(
                    ((insn >> 31) << 20)
                        | (((insn >> 12) & 255) << 12)
                        | (((insn >> 20) & 1) << 11)
                        | (((insn >> 21) & 1023) << 1),
                    21,
                );
                write = Some(next);
                next = self.pc.wrapping_add(offset);
            }
            0x67 if f3 == 0 => {
                write = Some(next);
                next = a.wrapping_add(imm) & !1;
            }
            0x63 => {
                let take = match f3 {
                    0 => a == b,
                    1 => a != b,
                    4 => (a as i32) < (b as i32),
                    5 => (a as i32) >= (b as i32),
                    6 => a < b,
                    7 => a >= b,
                    _ => return Err(illegal()),
                };
                if take {
                    let offset = sext(
                        ((insn >> 31) << 12)
                            | (((insn >> 7) & 1) << 11)
                            | (((insn >> 25) & 63) << 5)
                            | (((insn >> 8) & 15) << 1),
                        13,
                    );
                    next = self.pc.wrapping_add(offset);
                }
            }
            0x03 => {
                let address = a.wrapping_add(imm);
                write = Some(match f3 {
                    0 => sext(self.load(address, 1)?, 8),
                    1 => sext(self.load(address, 2)?, 16),
                    2 => self.load(address, 4)?,
                    4 => self.load(address, 1)?,
                    5 => self.load(address, 2)?,
                    _ => return Err(illegal()),
                });
            }
            0x23 => {
                let offset = sext(((insn >> 25) << 5) | ((insn >> 7) & 31), 12);
                let address = a.wrapping_add(offset);
                let size = match f3 {
                    0 => 1,
                    1 => 2,
                    2 => 4,
                    _ => return Err(illegal()),
                };
                if address % size as u32 != 0 {
                    return Err(Trap::StoreMisaligned(address));
                }
                self.range(address, size)?;
                store = Some((address, b, size));
            }
            0x13 => {
                write = Some(match f3 {
                    0 => a.wrapping_add(imm),
                    2 => ((a as i32) < (imm as i32)) as u32,
                    3 => (a < imm) as u32,
                    4 => a ^ imm,
                    6 => a | imm,
                    7 => a & imm,
                    1 if f7 == 0 => a << rs2,
                    5 if f7 == 0 => a >> rs2,
                    5 if f7 == 32 => ((a as i32) >> rs2) as u32,
                    _ => return Err(illegal()),
                });
            }
            0x33 => {
                write = Some(match (f3, f7) {
                    (0, 0) => a.wrapping_add(b),
                    (0, 32) => a.wrapping_sub(b),
                    (1, 0) => a << (b & 31),
                    (2, 0) => ((a as i32) < (b as i32)) as u32,
                    (3, 0) => (a < b) as u32,
                    (4, 0) => a ^ b,
                    (5, 0) => a >> (b & 31),
                    (5, 32) => ((a as i32) >> (b & 31)) as u32,
                    (6, 0) => a | b,
                    (7, 0) => a & b,
                    _ => return Err(illegal()),
                });
            }
            // FENCE is a no-op in a single-threaded, device-free interpreter.
            0x0f if f3 == 0 => {}
            0x73 if insn == 0x00100073 => halt = Some(Halt::Breakpoint),
            0x73 if insn == 0x00000073 => {
                if self.registers[17] != 93 {
                    return Err(Trap::UnsupportedEcall(self.registers[17]));
                }
                halt = Some(Halt::Exit(self.registers[10]));
            }
            _ => return Err(illegal()),
        }
        if next % 4 != 0 {
            return Err(Trap::InstructionMisaligned(next));
        }
        // Commit only after all checks; a trapping instruction leaves architectural state intact.
        if let Some((address, value, size)) = store {
            let bytes = value.to_le_bytes();
            self.memory[address as usize..address as usize + size].copy_from_slice(&bytes[..size]);
        }
        let register_write = write.filter(|_| rd != 0).map(|value| (rd, value));
        if let Some((reg, value)) = register_write {
            self.registers[reg] = value;
        }
        self.registers[0] = 0;
        let result = Step {
            pc: self.pc,
            instruction: insn,
            next_pc: next,
            register_write,
            memory_write: store,
        };
        self.pc = next;
        self.halted = halt;
        self.steps += 1;
        Ok(result)
    }

    pub fn run(&mut self, max_steps: u64) -> Result<Halt, Trap> {
        for _ in 0..max_steps {
            self.step()?;
            if let Some(halt) = &self.halted {
                return Ok(halt.clone());
            }
        }
        Err(Trap::StepLimit)
    }
}

pub fn words_to_bytes(words: &[u32]) -> Vec<u8> {
    words.iter().flat_map(|w| w.to_le_bytes()).collect()
}

pub fn demo(name: &str) -> Option<Vec<u8>> {
    let words: &[u32] = match name {
        // a0=0,a1=1,t0=20; t1=a0+a1; a0=a1; a1=t1; --t0; loop; break.
        "fibonacci" => &[
            0x00000513, 0x00100593, 0x01400293, 0x00b50333, 0x00058513, 0x00030593, 0xfff28293,
            0xfe0298e3, 0x00100073,
        ],
        // Store 0..99 at 0x1000, sum by loading them, leave a0=4950.
        "memory-sum" => &[
            0x000012b7, 0x06400313, 0x00000393, 0x00000513, 0x0072a023, 0x0002ae03, 0x01c50533,
            0x00428293, 0x00138393, 0xfe63c6e3, 0x00100073,
        ],
        _ => return None,
    };
    Some(words_to_bytes(words))
}

pub fn mnemonic(insn: u32) -> &'static str {
    match (insn & 127, (insn >> 12) & 7, insn >> 25) {
        (0x37, _, _) => "lui",
        (0x17, _, _) => "auipc",
        (0x6f, _, _) => "jal",
        (0x67, 0, _) => "jalr",
        (0x63, f, _) => match f {
            0 => "beq",
            1 => "bne",
            4 => "blt",
            5 => "bge",
            6 => "bltu",
            7 => "bgeu",
            _ => "illegal",
        },
        (0x03, f, _) => match f {
            0 => "lb",
            1 => "lh",
            2 => "lw",
            4 => "lbu",
            5 => "lhu",
            _ => "illegal",
        },
        (0x23, f, _) => match f {
            0 => "sb",
            1 => "sh",
            2 => "sw",
            _ => "illegal",
        },
        (0x13, 0, _) => "addi",
        (0x13, 2, _) => "slti",
        (0x13, 3, _) => "sltiu",
        (0x13, 4, _) => "xori",
        (0x13, 6, _) => "ori",
        (0x13, 7, _) => "andi",
        (0x13, 1, 0) => "slli",
        (0x13, 5, 0) => "srli",
        (0x13, 5, 32) => "srai",
        (0x33, 0, 0) => "add",
        (0x33, 0, 32) => "sub",
        (0x33, 1, 0) => "sll",
        (0x33, 2, 0) => "slt",
        (0x33, 3, 0) => "sltu",
        (0x33, 4, 0) => "xor",
        (0x33, 5, 0) => "srl",
        (0x33, 5, 32) => "sra",
        (0x33, 6, 0) => "or",
        (0x33, 7, 0) => "and",
        (0x0f, 0, _) => "fence",
        _ if insn == 0x00100073 => "ebreak",
        _ if insn == 0x00000073 => "ecall",
        _ => "illegal",
    }
}
