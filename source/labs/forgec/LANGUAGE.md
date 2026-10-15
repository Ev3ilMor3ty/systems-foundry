# ForgeC 0.1 language contract

## Program structure

A source file contains one or more function definitions. Every function returns
`int` and each parameter has type `int`. The entry function is `int main()` with
no parameters. Functions may be called before they are defined; duplicate
function names are errors. A function falling through its closing brace returns
zero. `return expression;` returns immediately.

```c
int add(int a, int b) { return a + b; }
int main() { print(add(20, 22)); return 0; }
```

Names use ASCII letters, digits and underscores, starting with a letter or
underscore. Keywords are `int`, `if`, `else`, `while`, `return`, `break`,
`continue`, `print`, `put`. Source is UTF-8; `//` line comments and non-nested `/* */`
block comments are accepted.

## Values and expressions

`int` is a signed two's-complement 64-bit value. Decimal and lowercase-prefix
`0x` hexadecimal literals accept the full unsigned 64-bit bit-pattern range;
values with bit 63 set are interpreted as negative. Thus `0xffffffffffffffff`
and `-1` have the same integer value. A literal wider than 64 bits is an error.

Arithmetic wraps modulo 2^64. This applies to negation, addition, subtraction
and multiplication. Division truncates toward zero; remainder satisfies
`a = (a / b) * b + (a % b)` before wrapping. `INT64_MIN / -1` wraps to
`INT64_MIN` and its remainder is zero. Division or remainder by zero terminates
the generated process with status **70**, including when the operands are
literals. Constant folding preserves that runtime failure behavior.

Right shift is arithmetic (sign-preserving). Shift counts use their low six
bits, including negative counts. Comparisons are signed. Boolean false is zero;
any other value is true. Comparisons, `!`, `&&` and `||` produce zero or one.

Precedence, highest to lowest:

| Operators | Behavior |
| --- | --- |
| `(...)`, calls | Grouping, function calls |
| unary `+ - ! ~` | Plus, wrapping negation, logical not, bitwise not |
| `* / %` | Multiplicative |
| `+ -` | Additive |
| `<< >>` | Shifts |
| `< <= > >=` | Signed comparisons |
| `== !=` | Equality |
| `&` | Bitwise AND |
| `^` | Bitwise XOR |
| `\|` | Bitwise OR |
| `&&` | Logical AND, short circuit |
| `\|\|` | Logical OR, short circuit |

Binary operators associate left to right. Operands and function arguments are
evaluated left to right. The right operand of `&&` runs only when the left is
true; the right operand of `||` runs only when the left is false. This applies to
function calls with visible `print` effects as well as arithmetic faults.

## Variables and statements

```c
int main() {
    int total = 0;
    int n = 0;
    while (n < 10) {
        n = n + 1;
        if (n == 4) { continue; }
        if (n == 8) { break; }
        total = total + n;
    }
    print(total);
    return 0;
}
```

Every declaration needs an initializer. Assignment is a statement,
`name = expression;`; it is not an expression. `++`, `+=`, `for`, `do`, switch,
ternary expressions and comma expressions are unsupported. Conditions use
parentheses; `if`, `else` and `while` bodies require braces. `else if` is allowed.
`break` and `continue` affect the nearest enclosing while loop and are rejected
outside a loop. Function-call expressions can be standalone statements.

Blocks introduce lexical scopes. Names can be shadowed in a nested block but
cannot be declared twice in one scope. A declaration's initializer is resolved
in the existing outer environment before its new binding is introduced:
`int x=5; { int x=x+1; print(x); }` prints 6. A self-initializer with no outer
binding is rejected. Function parameters share the function body's outer scope.

## Output and exit

`print` is a statement with one integer expression or one string literal.
Strings are not values and cannot be assigned, passed to functions or joined.
String escapes are `\n`, `\t`, `\r`, `\0`, `\"` and `\\`; an unescaped newline
inside a string is rejected. Output is UTF-8 bytes and `print` always appends a
newline. Integer output is signed decimal, including `INT64_MIN`.

`put(expression);` writes the low eight bits of its integer value as one byte,
with no extra newline. This supports character-by-character terminal output;
the supplied Mandelbrot example uses it to draw a fixed-point ASCII fractal.

The main return value becomes the process exit status: Linux retains its low
eight bits; Windows retains its low 32 bits. Normal output writes retry partial
writes; Linux also retries interrupted writes. Detected I/O failures exit with
status 74. OS signals, stack exhaustion or termination remain native-process
behavior.

## Bounded compilation and target scope

- Source: 64 KiB, at most 16,000 tokens.
- Functions: 128 per file; parameters/call arguments: eight per function/call.
- Locals plus parameters: 256 slots per function, counting nested declarations.
- Expression syntax/tree nesting: 64; block/conditional nesting: 32.
- Emitted instruction/literal payload: 1 MiB.

These are compilation bounds. Generated loops and recursion have no fuel limit.
The runtime provides no pointers, allocation, file/network API, foreign
function calls, exceptions, global variables, types beyond integers, includes,
macros, object files, linking, debugger metadata or operating-system facilities.
Each source file becomes one standalone x86-64 executable.
