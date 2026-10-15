use std::collections::HashMap;

#[derive(Debug, Clone)]
pub struct Error {
    pub at: usize,
    pub message: String,
}
pub type Result<T> = std::result::Result<T, Error>;
pub fn error(at: usize, message: impl Into<String>) -> Error {
    Error {
        at,
        message: message.into(),
    }
}

#[derive(Debug, Clone, PartialEq)]
enum Kind {
    Word(String),
    Number(u64),
    Text(Vec<u8>),
    Sym(String),
    Eof,
}
#[derive(Debug, Clone)]
struct Token {
    kind: Kind,
    at: usize,
}

fn lex(source: &str) -> Result<Vec<Token>> {
    let b = source.as_bytes();
    let mut i = 0;
    let mut tokens = Vec::new();
    while i < b.len() {
        if b[i].is_ascii_whitespace() {
            i += 1;
            continue;
        }
        if b[i..].starts_with(b"//") {
            while i < b.len() && b[i] != b'\n' {
                i += 1;
            }
            continue;
        }
        if b[i..].starts_with(b"/*") {
            let start = i;
            i += 2;
            while i < b.len() && !b[i..].starts_with(b"*/") {
                i += 1;
            }
            if i == b.len() {
                return Err(error(start, "unterminated block comment"));
            }
            i += 2;
            continue;
        }
        let at = i;
        let kind = if b[i].is_ascii_alphabetic() || b[i] == b'_' {
            i += 1;
            while i < b.len() && (b[i].is_ascii_alphanumeric() || b[i] == b'_') {
                i += 1;
            }
            Kind::Word(source[at..i].into())
        } else if b[i].is_ascii_digit() {
            let hex = b[i..].starts_with(b"0x");
            if hex {
                i += 2;
            }
            let digits = i;
            while i < b.len()
                && if hex {
                    b[i].is_ascii_hexdigit()
                } else {
                    b[i].is_ascii_digit()
                }
            {
                i += 1;
            }
            if digits == i {
                return Err(error(at, "expected digits after 0x"));
            }
            let value = u64::from_str_radix(&source[digits..i], if hex { 16 } else { 10 })
                .map_err(|_| error(at, "integer literal exceeds 64 bits"))?;
            Kind::Number(value)
        } else if b[i] == b'"' {
            i += 1;
            let mut bytes = Vec::new();
            while i < b.len() && b[i] != b'"' {
                if b[i] == b'\n' || b[i] == b'\r' {
                    return Err(error(at, "newline in string; use \\n"));
                }
                if b[i] == b'\\' {
                    i += 1;
                    if i == b.len() {
                        return Err(error(at, "unterminated string"));
                    }
                    bytes.push(match b[i] {
                        b'n' => 10,
                        b't' => 9,
                        b'r' => 13,
                        b'0' => 0,
                        b'"' => b'"',
                        b'\\' => b'\\',
                        _ => return Err(error(i, "unknown string escape")),
                    });
                } else {
                    bytes.push(b[i]);
                }
                i += 1;
            }
            if i == b.len() {
                return Err(error(at, "unterminated string"));
            }
            i += 1;
            Kind::Text(bytes)
        } else {
            let mut two = None;
            for op in ["==", "!=", "<=", ">=", "&&", "||", "<<", ">>"] {
                if b[i..].starts_with(op.as_bytes()) {
                    two = Some(op);
                    break;
                }
            }
            if let Some(op) = two {
                i += 2;
                Kind::Sym(op.into())
            } else if b"(){};,+-*/%~!<>=&|^".contains(&b[i]) {
                i += 1;
                Kind::Sym((b[at] as char).to_string())
            } else {
                return Err(error(at, "unexpected character"));
            }
        };
        tokens.push(Token { kind, at });
        if tokens.len() > 16000 {
            return Err(error(at, "source exceeds 16000 tokens"));
        }
    }
    tokens.push(Token {
        kind: Kind::Eof,
        at: source.len(),
    });
    Ok(tokens)
}

#[derive(Debug, Clone)]
pub struct Expr {
    pub at: usize,
    pub kind: ExprKind,
    depth: usize,
}
#[derive(Debug, Clone)]
pub enum ExprKind {
    Number(i64),
    Var(String),
    Slot(usize),
    Call(String, Vec<Expr>),
    Function(usize, Vec<Expr>),
    Unary(String, Box<Expr>),
    Binary(String, Box<Expr>, Box<Expr>),
}
#[derive(Debug, Clone)]
pub enum Stmt {
    Let {
        at: usize,
        name: String,
        slot: usize,
        value: Expr,
    },
    Assign {
        at: usize,
        name: String,
        slot: usize,
        value: Expr,
    },
    Expr(Expr),
    Print(Expr),
    Put(Expr),
    Text(Vec<u8>),
    Return(Expr),
    If(Expr, Vec<Stmt>, Vec<Stmt>),
    While(Expr, Vec<Stmt>),
    Block(Vec<Stmt>),
    Break(usize),
    Continue(usize),
}
#[derive(Debug, Clone)]
pub struct Function {
    pub name: String,
    pub at: usize,
    pub params: Vec<String>,
    pub body: Vec<Stmt>,
    pub locals: usize,
}
pub struct Program {
    pub functions: Vec<Function>,
    pub main: usize,
}

struct Parser {
    tokens: Vec<Token>,
    pos: usize,
}
impl Parser {
    fn token(&self) -> &Token {
        &self.tokens[self.pos]
    }
    fn is(&self, s: &str) -> bool {
        matches!(&self.token().kind,Kind::Word(w)|Kind::Sym(w) if w==s)
    }
    fn eat(&mut self, s: &str) -> bool {
        if self.is(s) {
            self.pos += 1;
            true
        } else {
            false
        }
    }
    fn need(&mut self, s: &str) -> Result<()> {
        if self.eat(s) {
            Ok(())
        } else {
            Err(error(self.token().at, format!("expected '{s}'")))
        }
    }
    fn name(&mut self) -> Result<(String, usize)> {
        let t = self.token().clone();
        if let Kind::Word(w) = t.kind {
            if [
                "int", "if", "else", "while", "return", "break", "continue", "print", "put",
            ]
            .contains(&w.as_str())
            {
                return Err(error(t.at, "reserved word used as a name"));
            }
            self.pos += 1;
            Ok((w, t.at))
        } else {
            Err(error(t.at, "expected a name"))
        }
    }
    fn expression(&mut self, min: u8, nesting: usize) -> Result<Expr> {
        if nesting > 64 {
            return Err(error(self.token().at, "expression nesting exceeds 64"));
        }
        let at = self.token().at;
        let mut left = if self.is("-") || self.is("+") || self.is("!") || self.is("~") {
            let op = if let Kind::Sym(s) = self.token().kind.clone() {
                s
            } else {
                unreachable!()
            };
            self.pos += 1;
            let x = self.expression(11, nesting + 1)?;
            let depth = x.depth + 1;
            Expr {
                at,
                kind: ExprKind::Unary(op, Box::new(x)),
                depth,
            }
        } else if self.eat("(") {
            let x = self.expression(0, nesting + 1)?;
            self.need(")")?;
            x
        } else if let Kind::Number(n) = self.token().kind {
            self.pos += 1;
            Expr {
                at,
                kind: ExprKind::Number(n as i64),
                depth: 1,
            }
        } else {
            let (name, _) = self.name()?;
            if self.eat("(") {
                let mut args = Vec::new();
                if !self.eat(")") {
                    loop {
                        if args.len() == 8 {
                            return Err(error(at, "at most eight call arguments"));
                        }
                        args.push(self.expression(0, nesting + 1)?);
                        if self.eat(")") {
                            break;
                        }
                        self.need(",")?;
                    }
                }
                let depth = 1 + args.iter().map(|a| a.depth).max().unwrap_or(0);
                Expr {
                    at,
                    kind: ExprKind::Call(name, args),
                    depth,
                }
            } else {
                Expr {
                    at,
                    kind: ExprKind::Var(name),
                    depth: 1,
                }
            }
        };
        loop {
            let op = match &self.token().kind {
                Kind::Sym(s) => s.clone(),
                _ => break,
            };
            let binding = match op.as_str() {
                "||" => 1,
                "&&" => 2,
                "|" => 3,
                "^" => 4,
                "&" => 5,
                "==" | "!=" => 6,
                "<" | "<=" | ">" | ">=" => 7,
                "<<" | ">>" => 8,
                "+" | "-" => 9,
                "*" | "/" | "%" => 10,
                _ => break,
            };
            if binding < min {
                break;
            }
            self.pos += 1;
            let right = self.expression(binding + 1, nesting + 1)?;
            let depth = 1 + left.depth.max(right.depth);
            if depth > 64 {
                return Err(error(
                    at,
                    "expression tree exceeds depth 64; use intermediate variables",
                ));
            }
            left = Expr {
                at,
                kind: ExprKind::Binary(op, Box::new(left), Box::new(right)),
                depth,
            };
        }
        if left.depth > 64 {
            return Err(error(at, "expression tree exceeds depth 64"));
        }
        Ok(left)
    }
    fn block(&mut self, depth: usize) -> Result<Vec<Stmt>> {
        if depth > 32 {
            return Err(error(self.token().at, "block nesting exceeds 32"));
        }
        self.need("{")?;
        let mut body = Vec::new();
        while !self.eat("}") {
            if self.token().kind == Kind::Eof {
                return Err(error(self.token().at, "expected '}' before end of file"));
            }
            body.push(self.statement(depth)?);
        }
        Ok(body)
    }
    fn statement(&mut self, depth: usize) -> Result<Stmt> {
        let at = self.token().at;
        if self.eat("int") {
            let (name, at) = self.name()?;
            self.need("=")?;
            let value = self.expression(0, 0)?;
            self.need(";")?;
            return Ok(Stmt::Let {
                at,
                name,
                slot: 0,
                value,
            });
        }
        if self.eat("return") {
            let value = self.expression(0, 0)?;
            self.need(";")?;
            return Ok(Stmt::Return(value));
        }
        if self.eat("put") {
            self.need("(")?;
            let value = self.expression(0, 0)?;
            self.need(")")?;
            self.need(";")?;
            return Ok(Stmt::Put(value));
        }
        if self.eat("print") {
            self.need("(")?;
            let stmt = if let Kind::Text(s) = self.token().kind.clone() {
                self.pos += 1;
                Stmt::Text(s)
            } else {
                Stmt::Print(self.expression(0, 0)?)
            };
            self.need(")")?;
            self.need(";")?;
            return Ok(stmt);
        }
        if self.eat("if") {
            self.need("(")?;
            let cond = self.expression(0, 0)?;
            self.need(")")?;
            let yes = self.block(depth + 1)?;
            let no = if self.eat("else") {
                if self.is("if") {
                    if depth >= 32 {
                        return Err(error(at, "if nesting exceeds 32"));
                    }
                    vec![self.statement(depth + 1)?]
                } else {
                    self.block(depth + 1)?
                }
            } else {
                Vec::new()
            };
            return Ok(Stmt::If(cond, yes, no));
        }
        if self.eat("while") {
            self.need("(")?;
            let cond = self.expression(0, 0)?;
            self.need(")")?;
            return Ok(Stmt::While(cond, self.block(depth + 1)?));
        }
        if self.eat("break") {
            self.need(";")?;
            return Ok(Stmt::Break(at));
        }
        if self.eat("continue") {
            self.need(";")?;
            return Ok(Stmt::Continue(at));
        }
        if self.is("{") {
            return Ok(Stmt::Block(self.block(depth + 1)?));
        }
        if matches!(&self.token().kind, Kind::Word(_))
            && matches!(&self.tokens[self.pos+1].kind,Kind::Sym(s) if s=="=")
        {
            let (name, at) = self.name()?;
            self.need("=")?;
            let value = self.expression(0, 0)?;
            self.need(";")?;
            return Ok(Stmt::Assign {
                at,
                name,
                slot: 0,
                value,
            });
        }
        let value = self.expression(0, 0)?;
        self.need(";")?;
        Ok(Stmt::Expr(value))
    }
}

fn resolve_expr(
    expr: &mut Expr,
    scopes: &[HashMap<String, usize>],
    functions: &HashMap<String, (usize, usize)>,
) -> Result<()> {
    match &mut expr.kind {
        ExprKind::Var(name) => {
            let slot = scopes
                .iter()
                .rev()
                .find_map(|s| s.get(name))
                .copied()
                .ok_or_else(|| error(expr.at, format!("unknown variable '{name}'")))?;
            expr.kind = ExprKind::Slot(slot);
        }
        ExprKind::Call(name, args) => {
            let &(index, count) = functions
                .get(name)
                .ok_or_else(|| error(expr.at, format!("unknown function '{name}'")))?;
            if args.len() != count {
                return Err(error(
                    expr.at,
                    format!(
                        "'{name}' expects {count} arguments, received {}",
                        args.len()
                    ),
                ));
            }
            for arg in args.iter_mut() {
                resolve_expr(arg, scopes, functions)?;
            }
            expr.kind = ExprKind::Function(index, std::mem::take(args));
        }
        ExprKind::Unary(_, x) => resolve_expr(x, scopes, functions)?,
        ExprKind::Binary(_, a, b) => {
            resolve_expr(a, scopes, functions)?;
            resolve_expr(b, scopes, functions)?;
        }
        _ => {}
    }
    Ok(())
}
fn resolve_block(
    body: &mut [Stmt],
    scopes: &mut Vec<HashMap<String, usize>>,
    functions: &HashMap<String, (usize, usize)>,
    locals: &mut usize,
    loops: usize,
) -> Result<()> {
    for stmt in body {
        match stmt {
            Stmt::Let {
                at,
                name,
                slot,
                value,
            } => {
                resolve_expr(value, scopes, functions)?;
                let scope = scopes.last_mut().unwrap();
                if scope.contains_key(name) {
                    return Err(error(
                        *at,
                        format!("duplicate variable '{name}' in this scope"),
                    ));
                }
                if *locals == 256 {
                    return Err(error(
                        *at,
                        "at most 256 parameters and local variables per function",
                    ));
                }
                *slot = *locals;
                *locals += 1;
                scope.insert(name.clone(), *slot);
            }
            Stmt::Assign {
                at,
                name,
                slot,
                value,
            } => {
                *slot = scopes
                    .iter()
                    .rev()
                    .find_map(|s| s.get(name))
                    .copied()
                    .ok_or_else(|| error(*at, format!("unknown variable '{name}'")))?;
                resolve_expr(value, scopes, functions)?;
            }
            Stmt::Expr(x) | Stmt::Print(x) | Stmt::Put(x) | Stmt::Return(x) => {
                resolve_expr(x, scopes, functions)?
            }
            Stmt::If(c, a, b) => {
                resolve_expr(c, scopes, functions)?;
                for block in [a, b] {
                    scopes.push(HashMap::new());
                    resolve_block(block, scopes, functions, locals, loops)?;
                    scopes.pop();
                }
            }
            Stmt::While(c, b) => {
                resolve_expr(c, scopes, functions)?;
                scopes.push(HashMap::new());
                resolve_block(b, scopes, functions, locals, loops + 1)?;
                scopes.pop();
            }
            Stmt::Block(b) => {
                scopes.push(HashMap::new());
                resolve_block(b, scopes, functions, locals, loops)?;
                scopes.pop();
            }
            Stmt::Break(at) | Stmt::Continue(at) if loops == 0 => {
                return Err(error(
                    *at,
                    "break/continue requires an enclosing while loop",
                ))
            }
            _ => {}
        }
    }
    Ok(())
}

pub fn parse(source: &str) -> Result<Program> {
    if source.len() > 65536 {
        return Err(error(0, "source exceeds 64 KiB"));
    }
    let mut parser = Parser {
        tokens: lex(source)?,
        pos: 0,
    };
    let mut functions = Vec::new();
    while parser.token().kind != Kind::Eof {
        if functions.len() == 128 {
            return Err(error(parser.token().at, "at most 128 functions"));
        }
        parser.need("int")?;
        let (name, at) = parser.name()?;
        parser.need("(")?;
        let mut params = Vec::new();
        if !parser.eat(")") {
            loop {
                if params.len() == 8 {
                    return Err(error(at, "at most eight parameters"));
                }
                parser.need("int")?;
                let (param, pat) = parser.name()?;
                if params.contains(&param) {
                    return Err(error(pat, "duplicate parameter"));
                }
                params.push(param);
                if parser.eat(")") {
                    break;
                }
                parser.need(",")?;
            }
        }
        let body = parser.block(0)?;
        functions.push(Function {
            name,
            at,
            params,
            body,
            locals: 0,
        });
    }
    let mut signatures = HashMap::new();
    for (index, f) in functions.iter().enumerate() {
        if signatures
            .insert(f.name.clone(), (index, f.params.len()))
            .is_some()
        {
            return Err(error(f.at, format!("duplicate function '{}'", f.name)));
        }
    }
    let &(main, count) = signatures
        .get("main")
        .ok_or_else(|| error(0, "program needs int main()"))?;
    if count != 0 {
        return Err(error(functions[main].at, "main must not take parameters"));
    }
    for f in &mut functions {
        let scope = f
            .params
            .iter()
            .enumerate()
            .map(|(i, p)| (p.clone(), i))
            .collect();
        f.locals = f.params.len();
        resolve_block(&mut f.body, &mut vec![scope], &signatures, &mut f.locals, 0)?;
    }
    Ok(Program { functions, main })
}

pub fn constant(expr: &Expr) -> Option<i64> {
    match &expr.kind {
        ExprKind::Number(n) => Some(*n),
        ExprKind::Unary(op, x) => {
            let n = constant(x)?;
            Some(match op.as_str() {
                "-" => n.wrapping_neg(),
                "+" => n,
                "!" => (n == 0) as i64,
                "~" => !n,
                _ => return None,
            })
        }
        ExprKind::Binary(op, a, b) => {
            let x = constant(a)?;
            if op == "&&" && x == 0 {
                return Some(0);
            }
            if op == "||" && x != 0 {
                return Some(1);
            }
            let y = constant(b)?;
            Some(match op.as_str() {
                "+" => x.wrapping_add(y),
                "-" => x.wrapping_sub(y),
                "*" => x.wrapping_mul(y),
                "/" if y != 0 => x.wrapping_div(y),
                "%" if y != 0 => x.wrapping_rem(y),
                "<<" => x.wrapping_shl((y as u32) & 63),
                ">>" => x.wrapping_shr((y as u32) & 63),
                "&" => x & y,
                "|" => x | y,
                "^" => x ^ y,
                "==" => (x == y) as i64,
                "!=" => (x != y) as i64,
                "<" => (x < y) as i64,
                "<=" => (x <= y) as i64,
                ">" => (x > y) as i64,
                ">=" => (x >= y) as i64,
                "&&" => (x != 0 && y != 0) as i64,
                "||" => (x != 0 || y != 0) as i64,
                _ => return None,
            })
        }
        _ => None,
    }
}
