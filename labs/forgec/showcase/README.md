# ForgeC presentation files

Short videos showing actual ForgeC compilation and the native program's output.

| File | Use |
| --- | --- |
| [forgec-demo.mp4](forgec-demo.mp4) | Landscape video, 1280×720, 22 seconds |
| [forgec-vertical.mp4](forgec-vertical.mp4) | Vertical video, 720×1280, 22 seconds |
| [forgec-cover.png](forgec-cover.png) | Thumbnail |
| [forgec-preview.gif](forgec-preview.gif) | Short loop used in GitHub READMEs |
| [POST.md](POST.md) | Ready-to-edit title and captions |
| [forgec-captions.srt](forgec-captions.srt) | Optional subtitle file |
| [recording.json](recording.json) | Actual source, commands, captured output and binary identities |

The videos are rendered terminal replays, not live screen recordings. The
commands were executed locally using the compiler covered by the committed
native validation. The source excerpt and fractal output are real. Playback is
edited for readability and the build JSON is presented as readable fields;
the animation is not an execution-time measurement. The demo executes Linux
output. Windows PE output was also generated and validated separately; native
Windows correctness is covered by the compiler CI, not by this Linux video.

No voiceover, music or third-party footage is included. Share the video yourself
using [the prepared copy](POST.md). No social/community messages were sent.

## Recreate

The optional renderer needs Python 3.10+, Pillow, FFmpeg with libx264 and the
DejaVu Sans / Sans Mono font files. These are presentation dependencies; ForgeC
itself still has no third-party Rust crate dependencies.

```bash
python3 labs/forgec/showcase/make_showcase.py \
  --compiler labs/forgec/target/release/forgec \
  --output /tmp/forgec-presentation
```

The renderer checks the compiler hash against committed native evidence, runs
the real commands in a temporary workspace, validates output formats and
compares the captured fractal with the prior checked output when available.
The font path is explicit in the script. Outputs are freshly generated
presentation files; their visual timing does not inherit runtime measurements.
