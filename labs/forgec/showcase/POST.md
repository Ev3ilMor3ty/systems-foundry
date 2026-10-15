# ForgeC showcase copy

## Suggested title

My C-like language compiles directly to native Linux and Windows executables

## Short caption

My latest project is ForgeC: a small C-like language with a compiler written in
Rust. It emits native x86-64 Linux ELF and Windows PE executables directly.

The video shows a Mandelbrot program compiled and run on Linux. The terminal
replays actual captured output with pacing edited for readability.

Code, examples and build instructions:
https://github.com/Ev3ilMor3ty/systems-foundry/tree/main/labs/forgec

I’d appreciate feedback on the language design and generated code.

## Longer technical post

I’m working on ForgeC, a small C-like language with an original frontend and
x86-64 backend written in Rust. The compiler writes Linux ELF64 and Windows
PE32+ executables itself, without invoking an external assembler or linker
when compiling a `.fc` file.

It currently supports signed 64-bit integers, initialized locals, lexical
scopes, functions and recursion, if/else, while/break/continue, short-circuit
logic and terminal output. The video shows a fixed-point Mandelbrot example
compiled and executed on Linux; it replays real command output with edited
pacing.

Both native Linux and Windows CI execute generated programs against independent
expectations, with constant folding on and off. It is an early prototype: one
integer type, no pointers/arrays/modules, and no C or HolyC compatibility or
self-hosting claim. HolyC inspired the hands-on language-building direction.

Source and instructions:
https://github.com/Ev3ilMor3ty/systems-foundry/tree/main/labs/forgec

Feedback on ABI decisions, frontend errors and useful next language features
would be welcome.

## Video choice

- `forgec-demo.mp4`: 1280×720, 16:9, 22 seconds; useful for Discord and posts
  with a landscape player.
- `forgec-vertical.mp4`: 720×1280, 9:16, 22 seconds; useful for vertical feeds.
- `forgec-cover.png`: a thumbnail or preview image.

The videos are silent with built-in scene captions. There is no licensed music
or third-party footage. `forgec-captions.srt` is optional caption text if your
posting platform accepts subtitle files. Choose one video per post and keep the
source link in the caption. You can pin `systems-foundry` on your GitHub profile;
ForgeC is featured at the top of that repository.
