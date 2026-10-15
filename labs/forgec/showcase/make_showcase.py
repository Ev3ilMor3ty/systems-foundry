#!/usr/bin/env python3
"""Record real ForgeC commands and render a silent, edited terminal showcase."""
import argparse
from functools import lru_cache
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import tempfile
import textwrap
import time

from PIL import Image, ImageDraw, ImageFilter, ImageFont, ImageOps

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]
BACKDROP = HERE / "background-charcoal-amber.png"
LINE = "#3a332c"
WHITE = "#faf4ec"
MUTED = "#b6ada2"
ACCENT = "#ffc28c"
HIGHLIGHT = "#e8cdb0"
FPS = 24
DURATION = 22
FONT_ROOT = Path("/usr/share/fonts/truetype/dejavu")


@lru_cache(maxsize=64)
def font(size, style="normal"):
    name = {
        "normal": "DejaVuSans.ttf",
        "bold": "DejaVuSans-Bold.ttf",
        "mono": "DejaVuSansMono.ttf",
    }[style]
    return ImageFont.truetype(str(FONT_ROOT / name), size)


def record(compiler):
    source = (HERE.parent / "examples/mandelbrot.fc").read_text()
    validated = json.loads((HERE.parent / "evidence/linux-native.json").read_text())
    compiler_hash = hashlib.sha256(compiler.read_bytes()).hexdigest()
    if compiler_hash != validated["compiler_sha256"]:
        raise RuntimeError(
            "use the compiler binary covered by the committed native evidence"
        )
    evidence = {
        "compiler_sha256": hashlib.sha256(compiler.read_bytes()).hexdigest(),
        "source": source,
        "source_sha256": hashlib.sha256(source.encode()).hexdigest(),
        "commands": [],
        "presentation": "Rendered replay of actual command output. Pacing is edited; no execution-speed claim. JSON result is reformatted for readability.",
    }
    with tempfile.TemporaryDirectory(prefix="forgec showcase ") as tmp:
        root = Path(tmp)
        shutil.copyfile(compiler, root / "forgec")
        (root / "forgec").chmod(0o755)
        (root / "mandelbrot.fc").write_text(source)
        for args in [
            ["./forgec", "check", "mandelbrot.fc"],
            [
                "./forgec",
                "build",
                "mandelbrot.fc",
                "-o",
                "fractal",
                "--target",
                "linux",
            ],
            ["./fractal"],
            [
                "./forgec",
                "build",
                "mandelbrot.fc",
                "-o",
                "fractal.exe",
                "--target",
                "windows",
            ],
        ]:
            started = time.monotonic()
            result = subprocess.run(args, cwd=root, capture_output=True, timeout=15)
            if result.returncode:
                raise RuntimeError(result.stderr.decode())
            evidence["commands"].append(
                {
                    "argv": args,
                    "exit_status": result.returncode,
                    "stdout": result.stdout.decode(),
                    "stderr": result.stderr.decode(),
                    "elapsed_seconds": round(time.monotonic() - started, 6),
                }
            )
        if not (root / "fractal").read_bytes().startswith(b"\x7fELF\x02\x01"):
            raise RuntimeError("expected ELF64 output")
        if not (root / "fractal.exe").read_bytes().startswith(b"MZ"):
            raise RuntimeError("expected PE output")
        output = evidence["commands"][2]["stdout"]
        expected = (
            (REPO.parent / "forge-mandelbrot.txt").read_text()
            if (REPO.parent / "forge-mandelbrot.txt").exists()
            else None
        )
        if expected is not None and output != expected:
            raise RuntimeError("output differs from the previously checked fractal")
        rows = output.splitlines()
        if len(rows) != 24 or any(len(row) != 80 for row in rows):
            raise RuntimeError("unexpected fractal dimensions")
        evidence["fractal_sha256"] = hashlib.sha256(output.encode()).hexdigest()
        evidence["executables"] = {
            name: {
                "bytes": (root / name).stat().st_size,
                "sha256": hashlib.sha256((root / name).read_bytes()).hexdigest(),
            }
            for name in ["fractal", "fractal.exe"]
        }
    return evidence


def text(draw, xy, value, size=22, fill=WHITE, style="normal"):
    draw.text(xy, value, font=font(size, style), fill=fill, spacing=8)


def wrap(draw, value, width, size, style="normal"):
    """Pixel wrapping preserves all source characters, using visual editor wraps."""
    result = []
    for original in value.splitlines():
        line = original
        while draw.textlength(line, font=font(size, style)) > width:
            n = len(line)
            while n > 1 and draw.textlength(line[:n], font=font(size, style)) > width:
                n -= 1
            split = line.rfind(" ", 1, n)
            if split > n // 2:
                n = split
            result.append(line[:n])
            line = "    " + line[n:].lstrip()
        result.append(line)
    return result


@lru_cache(maxsize=4)
def background_plate(w, h):
    with Image.open(BACKDROP) as image:
        return ImageOps.fit(
            image.convert("RGB"),
            (w, h),
            method=Image.Resampling.LANCZOS,
            centering=(0.85 if h > w else 0.5, 0.5),
        )


def base(w, h):
    return background_plate(w, h).copy()


@lru_cache(maxsize=4)
def terminal_overlay(w, h, x1, top, x2, bottom):
    shadow = Image.new("RGBA", (w, h))
    ImageDraw.Draw(shadow).rounded_rectangle(
        (x1 + 3, top + 12, x2 + 3, bottom + 12), radius=18, fill=(0, 0, 0, 180)
    )
    shadow = shadow.filter(ImageFilter.GaussianBlur(16))
    card = Image.new("RGBA", (w, h))
    ImageDraw.Draw(card).rounded_rectangle(
        (x1, top, x2, bottom),
        radius=18,
        fill=(15, 15, 17, 232),
        outline=(93, 79, 66, 170),
        width=1,
    )
    return Image.alpha_composite(shadow, card)


def render(t, w, h, evidence):
    portrait = h > w
    image = base(w, h)
    d = ImageDraw.Draw(image)
    margin = 42 if portrait else 64
    text(d, (margin, 34), "FORGEC", 24, ACCENT, "bold")
    text(d, (w - margin - 159, 40), "NATIVE x86-64", 16, MUTED, "mono")
    d.line((margin, 84, w - margin, 84), fill=LINE, width=1)
    # This footer distinguishes rendered playback from a live screen recording.
    footer = "Actual compiler output · edited playback"
    text(d, (margin, h - 48), footer, 15 if portrait else 16, MUTED)
    d.rounded_rectangle((margin, h - 16, w - margin, h - 12), radius=2, fill=LINE)
    d.rounded_rectangle(
        (margin, h - 16, margin + (w - 2 * margin) * min(t / DURATION, 1), h - 12),
        radius=2,
        fill=ACCENT,
    )
    rows = evidence["commands"][2]["stdout"].splitlines()
    if t < 3 or t >= 18:
        outro = t >= 18
        if portrait:
            title_y = 154
            text(
                d,
                (margin, title_y),
                "Try the compiler." if outro else "My language.\nNative code.",
                49 if outro else 59,
                WHITE,
                "bold",
            )
            subtitle_y = 252 if outro else 345
            text(
                d,
                (margin, subtitle_y),
                (
                    "Code, examples and build guides."
                    if outro
                    else "A small C-like compiler,\nwritten in Rust."
                ),
                24,
                MUTED,
            )
            fy = 470
            fs = 13
            dy = 14
        else:
            text(
                d,
                (margin, 164),
                "Try the compiler." if outro else "My language.\nNative code.",
                62,
                WHITE,
                "bold",
            )
            text(
                d,
                (margin, 340 if outro else 365),
                (
                    "Code, examples and build guides."
                    if outro
                    else "A small C-like compiler, written in Rust."
                ),
                23,
                MUTED,
            )
            fy = 205
            fs = 11
            dy = 11
        fw = d.textlength("#" * 80, font=font(fs, "mono"))
        fx = (w - fw) / 2 if portrait else w - margin - fw
        for n, row in enumerate(rows):
            text(d, (fx, fy + n * dy), row, fs, ACCENT, "mono")
        if portrait:
            text(d, (margin, 970), "Linux ELF  /  Windows PE", 23, HIGHLIGHT, "mono")
            text(
                d,
                (margin, 1040),
                "github.com/Ev3ilMor3ty\nsystems-foundry → labs/forgec",
                22,
                WHITE,
                "mono",
            )
        else:
            text(d, (margin, 478), "Linux ELF  /  Windows PE", 22, HIGHLIGHT, "mono")
            text(
                d,
                (margin, 552),
                "github.com/Ev3ilMor3ty/systems-foundry",
                25,
                WHITE,
                "mono",
            )
            text(d, (margin, 594), "Open labs/forgec · MIT · first release", 18, MUTED)
        return image

    top = 285 if portrait else 230
    bottom = h - (170 if portrait else 86)
    x1, x2 = margin, w - margin
    overlay = terminal_overlay(w, h, x1, top, x2, bottom)
    image.paste(overlay, (0, 0), overlay)
    for n, color in enumerate(["#746b63", "#a69889", "#d6b797"]):
        d.ellipse((x1 + 22 + n * 23, top + 19, x1 + 32 + n * 23, top + 29), fill=color)
    d.line((x1, top + 49, x2, top + 49), fill=LINE)
    title_size = 39 if portrait else 46
    if t < 7:
        text(d, (margin, 128), "Start with source.", title_size, WHITE, "bold")
        text(d, (margin, 194), "A fixed-point Mandelbrot program.", 23, MUTED)
        text(d, (x1 + 107, top + 13), "mandelbrot.fc · excerpt", 16, MUTED, "mono")
        excerpt = textwrap.dedent("\n".join(evidence["source"].splitlines()[10:23]))
        size = 17 if portrait else 20
        lines = wrap(d, excerpt, x2 - x1 - 58, size, "mono")
        line_height = 27 if portrait else 23
        for n, line in enumerate(lines):
            color = ACCENT if "while" in line or "if" in line else WHITE
            text(d, (x1 + 27, top + 66 + n * line_height), line, size, color, "mono")
    elif t < 11.5:
        text(d, (margin, 128), "Compile it.", title_size, WHITE, "bold")
        text(d, (margin, 194), "Source → native machine code.", 23, MUTED)
        text(d, (x1 + 107, top + 13), "terminal · recorded result", 16, MUTED, "mono")
        command = "$ " + " ".join(evidence["commands"][1]["argv"])
        shown = command[: int(len(command) * min(max((t - 7.15) / 1.1, 0), 1))]
        size = 20 if portrait else 23
        yy = top + 74
        for line in wrap(
            d, shown + ("▌" if t < 8.5 else ""), x2 - x1 - 54, size, "mono"
        ):
            text(d, (x1 + 27, yy), line, size, ACCENT, "mono")
            yy += 34
        if t >= 8.7:
            result = json.loads(evidence["commands"][1]["stdout"])
            fields = [
                "BUILD COMPLETE",
                f"target     {result['target']}",
                f"size       {result['bytes']:,} bytes",
                f"functions  {result['functions']}",
                "constant folding enabled",
            ]
            for n, line in enumerate(fields):
                text(
                    d,
                    (x1 + 27, yy + 34 + n * 35),
                    line,
                    20 if portrait else 23,
                    HIGHLIGHT if n == 0 else WHITE,
                    "mono",
                )
            if portrait:
                text(
                    d,
                    (x1 + 27, bottom - 190),
                    "ONE COMPILER / TWO TARGETS",
                    18,
                    MUTED,
                    "mono",
                )
                text(
                    d,
                    (x1 + 27, bottom - 142),
                    "Linux ELF64\nWindows PE32+",
                    25,
                    HIGHLIGHT,
                    "mono",
                )
    else:
        text(d, (margin, 128), "Run native code.", title_size, WHITE, "bold")
        text(d, (margin, 194), "The executable draws this fractal.", 23, MUTED)
        text(d, (x1 + 107, top + 13), "terminal · ./fractal", 16, MUTED, "mono")
        size = 12 if portrait else 15
        line_height = 14
        fw = d.textlength("#" * 80, font=font(size, "mono"))
        fx = (w - fw) / 2
        fy = top + (150 if portrait else 61)
        visible = min(24, max(0, int((t - 11.8) * 15)))
        for n, row in enumerate(rows[:visible]):
            text(d, (fx, fy + n * line_height), row, size, ACCENT, "mono")
        if portrait:
            text(
                d,
                (x1 + 27, bottom - 90),
                "80 × 24 cells\n64-bit integer arithmetic",
                20,
                MUTED,
                "mono",
            )
    return image


def video(output, w, h, evidence):
    command = [
        "ffmpeg",
        "-hide_banner",
        "-loglevel",
        "error",
        "-y",
        "-f",
        "rawvideo",
        "-pixel_format",
        "rgb24",
        "-video_size",
        f"{w}x{h}",
        "-framerate",
        str(FPS),
        "-i",
        "-",
        "-an",
        "-c:v",
        "libx264",
        "-preset",
        "veryfast",
        "-crf",
        "20",
        "-threads",
        "2",
        "-pix_fmt",
        "yuv420p",
        "-movflags",
        "+faststart",
        str(output),
    ]
    process = subprocess.Popen(command, stdin=subprocess.PIPE)
    try:
        for frame in range(DURATION * FPS):
            process.stdin.write(render(frame / FPS, w, h, evidence).tobytes())
        process.stdin.close()
        if process.wait() != 0:
            raise RuntimeError("video encode failed")
    finally:
        if process.poll() is None:
            process.kill()
            process.wait()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    inputs = parser.add_mutually_exclusive_group(required=True)
    inputs.add_argument("--compiler", type=Path)
    inputs.add_argument(
        "--recording", type=Path, help="reuse the original verified command recording"
    )
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    evidence = (
        json.loads(args.recording.read_text())
        if args.recording
        else record(args.compiler.resolve())
    )
    rows = evidence["commands"][2]["stdout"].splitlines()
    if len(rows) != 24 or any(len(row) != 80 for row in rows):
        raise RuntimeError("recording has unexpected fractal dimensions")
    (args.output / "recording.json").write_text(json.dumps(evidence, indent=2) + "\n")
    for name, w, h in [
        ("forgec-demo.mp4", 1280, 720),
        ("forgec-vertical.mp4", 720, 1280),
    ]:
        video(args.output / name, w, h, evidence)
    render(1, 1280, 720, evidence).save(args.output / "forgec-cover.png")
    for t in [4, 9, 15]:
        render(t, 1280, 720, evidence).save(args.output / f"review-{t}.png")
        render(t, 720, 1280, evidence).save(args.output / f"review-vertical-{t}.png")
    # A short, clearly edited loop for GitHub Markdown's image support.
    subprocess.run(
        [
            "ffmpeg",
            "-hide_banner",
            "-loglevel",
            "error",
            "-y",
            "-ss",
            "7",
            "-i",
            str(args.output / "forgec-demo.mp4"),
            "-t",
            "10.5",
            "-filter_complex",
            "fps=6,scale=768:-1:flags=lanczos,split[a][b];[a]palettegen=max_colors=96[p];[b][p]paletteuse=dither=bayer:bayer_scale=4",
            "-loop",
            "0",
            str(args.output / "forgec-preview.gif"),
        ],
        check=True,
    )
    print(
        json.dumps(
            {
                "ok": True,
                "seconds_each": DURATION,
                "fps": FPS,
                "compiler_sha256": evidence["compiler_sha256"],
                "native_output_verified": True,
            }
        )
    )


if __name__ == "__main__":
    main()
