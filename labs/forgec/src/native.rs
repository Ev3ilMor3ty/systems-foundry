use crate::syntax::{constant, error, Expr, ExprKind, Program, Result, Stmt};
use std::collections::HashMap;

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum Target {
    Linux,
    Windows,
}
pub struct Code {
    pub bytes: Vec<u8>,
    pub functions: Vec<(String, usize)>,
}
struct Generator {
    bytes: Vec<u8>,
    labels: HashMap<usize, usize>,
    fixups: Vec<(usize, usize)>,
    next: usize,
    functions: Vec<usize>,
    print_int: usize,
    print_bytes: usize,
    divide_error: usize,
    io_error: usize,
    data: Vec<(usize, Vec<u8>)>,
    iat: Vec<usize>,
    fold: bool,
    target: Target,
}
impl Generator {
    fn label(&mut self) -> usize {
        let n = self.next;
        self.next += 1;
        n
    }
    fn mark(&mut self, label: usize) {
        assert!(self.labels.insert(label, self.bytes.len()).is_none());
    }
    fn raw(&mut self, b: &[u8]) {
        self.bytes.extend_from_slice(b);
    }
    fn u32(&mut self, n: u32) {
        self.raw(&n.to_le_bytes());
    }
    fn imm(&mut self, n: i64) {
        self.raw(&[0x48, 0xb8]);
        self.raw(&n.to_le_bytes());
    }
    fn relative(&mut self, prefix: &[u8], label: usize) {
        self.raw(prefix);
        let at = self.bytes.len();
        self.u32(0);
        self.fixups.push((at, label));
    }
    fn call(&mut self, label: usize) {
        self.relative(&[0xe8], label);
    }
    fn jump(&mut self, label: usize) {
        self.relative(&[0xe9], label);
    }
    fn condition(&mut self, cc: u8, label: usize) {
        self.relative(&[0x0f, cc], label);
    }
    fn zero(&mut self) {
        self.raw(&[0x48, 0x85, 0xc0]);
    }
    fn boolean(&mut self) {
        self.zero();
        self.raw(&[0x0f, 0x95, 0xc0, 0x0f, 0xb6, 0xc0]);
    }
    fn load(&mut self, slot: usize) {
        self.raw(&[0x48, 0x8b, 0x85]);
        self.u32((-(8 * (slot as i32 + 1))) as u32);
    }
    fn store(&mut self, slot: usize) {
        self.raw(&[0x48, 0x89, 0x85]);
        self.u32((-(8 * (slot as i32 + 1))) as u32);
    }
    fn expr(&mut self, expr: &Expr) {
        if self.fold {
            if let Some(n) = constant(expr) {
                self.imm(n);
                return;
            }
        }
        match &expr.kind {
            ExprKind::Number(n) => self.imm(*n),
            ExprKind::Slot(s) => self.load(*s),
            ExprKind::Function(index, args) => {
                for arg in args {
                    self.expr(arg);
                    self.raw(&[0x50]);
                }
                self.call(self.functions[*index]);
                if !args.is_empty() {
                    self.raw(&[0x48, 0x81, 0xc4]);
                    self.u32((args.len() * 8) as u32);
                }
            }
            ExprKind::Unary(op, x) => {
                self.expr(x);
                match op.as_str() {
                    "-" => self.raw(&[0x48, 0xf7, 0xd8]),
                    "~" => self.raw(&[0x48, 0xf7, 0xd0]),
                    "!" => {
                        self.zero();
                        self.raw(&[0x0f, 0x94, 0xc0, 0x0f, 0xb6, 0xc0]);
                    }
                    _ => {}
                }
            }
            ExprKind::Binary(op, a, b) if op == "&&" || op == "||" => {
                let end = self.label();
                self.expr(a);
                self.boolean();
                self.condition(if op == "&&" { 0x84 } else { 0x85 }, end);
                self.expr(b);
                self.boolean();
                self.mark(end);
            }
            ExprKind::Binary(op, a, b) => {
                self.expr(a);
                self.raw(&[0x50]);
                self.expr(b);
                self.raw(&[0x59]); // left RCX, right RAX
                match op.as_str() {
                    "+" => self.raw(&[0x48, 0x01, 0xc8]),
                    "-" => self.raw(&[0x48, 0x29, 0xc1, 0x48, 0x89, 0xc8]),
                    "*" => self.raw(&[0x48, 0x0f, 0xaf, 0xc1]),
                    "&" => self.raw(&[0x48, 0x21, 0xc8]),
                    "|" => self.raw(&[0x48, 0x09, 0xc8]),
                    "^" => self.raw(&[0x48, 0x31, 0xc8]),
                    "<<" | ">>" => {
                        self.raw(&[
                            0x48,
                            0x87,
                            0xc8,
                            0x48,
                            0xd3,
                            if op == "<<" { 0xe0 } else { 0xf8 },
                        ]);
                    }
                    "/" | "%" => {
                        self.raw(&[0x48, 0x87, 0xc8, 0x48, 0x85, 0xc9]);
                        self.condition(0x84, self.divide_error);
                        let normal = self.label();
                        let end = self.label();
                        self.raw(&[0x48, 0x83, 0xf9, 0xff]);
                        self.condition(0x85, normal); // divisor != -1
                        self.raw(&[0x48, 0xba]);
                        self.raw(&i64::MIN.to_le_bytes());
                        self.raw(&[0x48, 0x39, 0xd0]);
                        self.condition(0x85, normal);
                        if op == "%" {
                            self.raw(&[0x31, 0xc0]);
                        } // MIN/-1 wraps; MIN%-1=0
                        self.jump(end);
                        self.mark(normal);
                        self.raw(&[0x48, 0x99, 0x48, 0xf7, 0xf9]);
                        if op == "%" {
                            self.raw(&[0x48, 0x89, 0xd0]);
                        }
                        self.mark(end);
                    }
                    _ => {
                        self.raw(&[0x48, 0x39, 0xc1]);
                        let cc = match op.as_str() {
                            "==" => 0x94,
                            "!=" => 0x95,
                            "<" => 0x9c,
                            "<=" => 0x9e,
                            ">" => 0x9f,
                            ">=" => 0x9d,
                            _ => unreachable!(),
                        };
                        self.raw(&[0x0f, cc, 0xc0, 0x0f, 0xb6, 0xc0]);
                    }
                }
            }
            _ => unreachable!("unresolved expression"),
        }
    }
    fn block(&mut self, body: &[Stmt], loops: Option<(usize, usize)>) {
        for stmt in body {
            match stmt {
                Stmt::Let { slot, value, .. } | Stmt::Assign { slot, value, .. } => {
                    self.expr(value);
                    self.store(*slot);
                }
                Stmt::Expr(x) => self.expr(x),
                Stmt::Return(x) => {
                    self.expr(x);
                    self.raw(&[0xc9, 0xc3]);
                }
                Stmt::Print(x) => {
                    self.expr(x);
                    self.call(self.print_int);
                }
                Stmt::Put(x) => {
                    self.expr(x);
                    self.raw(&[0x50, 0x48, 0x89, 0xe0, 0xba, 1, 0, 0, 0]);
                    self.call(self.print_bytes);
                    self.raw(&[0x48, 0x83, 0xc4, 8]);
                }
                Stmt::Text(text) => {
                    let label = self.label();
                    let mut bytes = text.clone();
                    bytes.push(10);
                    self.data.push((label, bytes));
                    self.relative(&[0x48, 0x8d, 0x05], label); // lea rax,[rip+data]
                    self.raw(&[0x48, 0xba]);
                    self.raw(&((text.len() + 1) as u64).to_le_bytes());
                    self.call(self.print_bytes);
                }
                Stmt::If(c, a, b) => {
                    let no = self.label();
                    let end = self.label();
                    self.expr(c);
                    self.zero();
                    self.condition(0x84, no);
                    self.block(a, loops);
                    self.jump(end);
                    self.mark(no);
                    self.block(b, loops);
                    self.mark(end);
                }
                Stmt::While(c, body) => {
                    let start = self.label();
                    let end = self.label();
                    self.mark(start);
                    self.expr(c);
                    self.zero();
                    self.condition(0x84, end);
                    self.block(body, Some((start, end)));
                    self.jump(start);
                    self.mark(end);
                }
                Stmt::Block(b) => self.block(b, loops),
                Stmt::Break(_) => self.jump(loops.unwrap().1),
                Stmt::Continue(_) => self.jump(loops.unwrap().0),
            }
        }
    }
    fn exit(&mut self, code: u32) {
        if self.target == Target::Linux {
            self.raw(&[0xbf]);
            self.u32(code);
            self.raw(&[0xb8, 60, 0, 0, 0, 0x0f, 0x05, 0x0f, 0x0b]);
        } else {
            self.raw(&[0xb9]);
            self.u32(code);
            self.raw(&[0x48, 0x83, 0xe4, 0xf0, 0x48, 0x83, 0xec, 0x20]);
            self.relative(&[0xff, 0x15], self.iat[2]);
            self.raw(&[0x0f, 0x0b]);
        }
    }
    fn runtime(&mut self) {
        self.mark(self.divide_error);
        self.exit(70);
        self.mark(self.io_error);
        self.exit(74);
        self.mark(self.print_int);
        self.raw(&[0x55, 0x48, 0x89, 0xe5, 0x48, 0x83, 0xec, 0x40]);
        self.raw(&[0x49, 0x89, 0xc0, 0x48, 0x8d, 0x75, 0xff, 0xc6, 0x06, 10]); // R8 original;RSI newline
        let positive = self.label();
        self.zero();
        self.condition(0x89, positive);
        self.raw(&[0x48, 0xf7, 0xd8]);
        self.mark(positive);
        self.raw(&[0x41, 0xba, 10, 0, 0, 0]);
        let digits = self.label();
        self.mark(digits);
        self.raw(&[
            0x31, 0xd2, 0x49, 0xf7, 0xf2, 0x80, 0xc2, 0x30, 0x48, 0xff, 0xce, 0x88, 0x16,
        ]);
        self.zero();
        self.condition(0x85, digits);
        let unsigned = self.label();
        self.raw(&[0x4d, 0x85, 0xc0]);
        self.condition(0x89, unsigned);
        self.raw(&[0x48, 0xff, 0xce, 0xc6, 0x06, 0x2d]);
        self.mark(unsigned);
        self.raw(&[0x48, 0x89, 0xf0, 0x48, 0x89, 0xea, 0x48, 0x29, 0xf2]);
        self.call(self.print_bytes);
        self.raw(&[0xc9, 0xc3]);
        self.mark(self.print_bytes);
        if self.target == Target::Linux {
            self.raw(&[0x48, 0x89, 0xc6]); // RSI pointer, RDX remaining
            let start = self.label();
            let done = self.label();
            let written = self.label();
            self.mark(start);
            self.raw(&[0x48, 0x85, 0xd2]);
            self.condition(0x84, done);
            self.raw(&[0xb8, 1, 0, 0, 0, 0xbf, 1, 0, 0, 0, 0x0f, 0x05]);
            self.zero();
            self.condition(0x8f, written);
            self.raw(&[0x48, 0x83, 0xf8, 0xfc]);
            self.condition(0x84, start); // EINTR
            self.jump(self.io_error);
            self.mark(written);
            self.raw(&[0x48, 0x01, 0xc6, 0x48, 0x29, 0xc2]);
            self.jump(start);
            self.mark(done);
            self.raw(&[0xc3]);
        } else {
            // Every Win64 API call gets aligned RSP, 32-byte shadow space and its fifth argument.
            self.raw(&[
                0x55, 0x48, 0x89, 0xe5, 0x48, 0x83, 0xe4, 0xf0, 0x48, 0x83, 0xec, 0x50,
            ]);
            self.raw(&[
                0x48, 0x89, 0x44, 0x24, 0x28, 0x48, 0x89, 0x54, 0x24, 0x30, 0xb9, 0xf5, 0xff, 0xff,
                0xff,
            ]);
            self.relative(&[0xff, 0x15], self.iat[0]);
            self.raw(&[0x48, 0x89, 0x44, 0x24, 0x38]);
            let start = self.label();
            let done = self.label();
            self.mark(start);
            self.raw(&[0x48, 0x83, 0x7c, 0x24, 0x30, 0]);
            self.condition(0x84, done);
            self.raw(&[
                0x48, 0x8b, 0x4c, 0x24, 0x38, 0x48, 0x8b, 0x54, 0x24, 0x28, 0x44, 0x8b, 0x44, 0x24,
                0x30, 0x4c, 0x8d, 0x4c, 0x24, 0x40,
            ]);
            self.raw(&[0x48, 0xc7, 0x44, 0x24, 0x20, 0, 0, 0, 0]);
            self.relative(&[0xff, 0x15], self.iat[1]);
            self.zero();
            self.condition(0x84, self.io_error);
            self.raw(&[0x8b, 0x44, 0x24, 0x40]);
            self.zero();
            self.condition(0x84, self.io_error);
            self.raw(&[0x48, 0x01, 0x44, 0x24, 0x28, 0x48, 0x29, 0x44, 0x24, 0x30]);
            self.jump(start);
            self.mark(done);
            self.raw(&[0xc9, 0xc3]);
        }
    }
}

pub fn generate(program: &Program, target: Target, fold: bool) -> Result<Code> {
    let n = program.functions.len();
    let mut g = Generator {
        bytes: Vec::new(),
        labels: HashMap::new(),
        fixups: Vec::new(),
        next: n + 7,
        functions: (0..n).collect(),
        print_int: n,
        print_bytes: n + 1,
        divide_error: n + 2,
        io_error: n + 3,
        data: Vec::new(),
        iat: vec![n + 4, n + 5, n + 6],
        fold,
        target,
    };
    g.raw(&[0x31, 0xed]);
    g.call(g.functions[program.main]);
    if target == Target::Linux {
        g.raw(&[0x48, 0x89, 0xc7, 0xb8, 60, 0, 0, 0, 0x0f, 0x05, 0x0f, 0x0b]);
    } else {
        g.raw(&[
            0x48, 0x89, 0xc1, 0x48, 0x83, 0xe4, 0xf0, 0x48, 0x83, 0xec, 0x20,
        ]);
        g.relative(&[0xff, 0x15], g.iat[2]);
        g.raw(&[0x0f, 0x0b]);
    }
    let mut map = Vec::new();
    for (index, f) in program.functions.iter().enumerate() {
        g.mark(index);
        map.push((f.name.clone(), g.bytes.len()));
        g.raw(&[0x55, 0x48, 0x89, 0xe5, 0x48, 0x81, 0xec]);
        g.u32(((f.locals * 8 + 15) & !15) as u32);
        for slot in 0..f.params.len() {
            g.raw(&[0x48, 0x8b, 0x85]);
            g.u32((16 + 8 * (f.params.len() - 1 - slot)) as u32);
            g.store(slot);
        }
        g.block(&f.body, None);
        g.raw(&[0x31, 0xc0, 0xc9, 0xc3]);
    }
    g.runtime();
    let data = std::mem::take(&mut g.data);
    for (label, bytes) in data {
        g.mark(label);
        g.raw(&bytes);
    }
    if g.bytes.len() > 1024 * 1024 {
        return Err(error(0, "generated code exceeds 1 MiB"));
    }
    // PE import thunks live in .idata; relative locations are known after .text size is fixed.
    if target == Target::Windows {
        let idata_rva = (0x1000 + g.bytes.len() + 4095) & !4095;
        for (i, label) in g.iat.iter().enumerate() {
            g.labels.insert(*label, idata_rva - 0x1000 + 72 + 8 * i);
        }
    }
    for (at, label) in &g.fixups {
        let dest = *g
            .labels
            .get(label)
            .ok_or_else(|| error(0, "internal unresolved code label"))?;
        let displacement = i32::try_from(dest as i64 - (*at + 4) as i64)
            .map_err(|_| error(0, "relative address overflow"))?;
        g.bytes[*at..*at + 4].copy_from_slice(&displacement.to_le_bytes());
    }
    Ok(Code {
        bytes: g.bytes,
        functions: map,
    })
}
