# /// script
# requires-python = ">=3.10"
# dependencies = []
# ///
"""Assemble demo/one-take-vfx-demo.mp4 and docs/preview.gif from demo/outputs with ffmpeg: title card,
before/after splits for every preset, ComfyUI graph slides, outro. Silent, with on-screen captions (see demo/SCRIPT.md)."""
import subprocess
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
FONT = "/System/Library/Fonts/Supplemental/Arial Bold.ttf"
W, H, FPS = 1280, 720, 24
# (preset id, clip id, caption)
SHOTS = [
    ("disintegrate", "26925", "Disintegrate"),
    ("levitate", "407", "Levitate"),
    ("set-on-fire", "407", "Set on fire"),
    ("portal", "26925", "Portal"),
    ("time-freeze", "26925", "Time freeze"),
    ("slow-mo-debris", "407", "Slow-mo debris"),
    ("rain-stop", "36624", "Rain stop"),
    ("hologram", "26925", "Hologram"),
]


def ff(*args):
    subprocess.run(["ffmpeg", "-v", "error", "-y", *args], check=True)


def text(s, size, y, color="white", x="(w-text_w)/2"):
    s = s.replace(":", r"\:").replace("'", "").replace("%", r"\\%")
    return f"drawtext=fontfile={FONT}:text='{s}':fontsize={size}:fontcolor={color}:x={x}:y={y}"


common = ["-r", str(FPS), "-c:v", "libx264", "-pix_fmt", "yuv420p", "-crf", "17"]


def card(path, dur, lines):
    vf = ",".join(text(s, size, y, color) for s, size, y, color in lines)
    ff("-f", "lavfi", "-i", f"color=c=0x0b0b0e:s={W}x{H}:d={dur}", "-vf", vf, *common, str(path))


def split(path, clip, out, caption, dur=4.05, label=None, src=None, res=None, ss=0.0):
    src = src or ROOT / "assets/clips" / f"{clip}_clip.mp4"
    res = res or ROOT / "demo/outputs" / f"{clip}__{out}.mp4"
    fc = (f"[0:v]scale=620:-2,setsar=1[a];[1:v]scale=620:-2,setsar=1[b];[a][b]hstack,pad={W}:{H}:(ow-iw)/2:(oh-ih)/2+20:0x0b0b0e,"
          + ",".join([text("BEFORE", 28, 150, "0x8b8b9a", "330"), text("AFTER", 28, 150, "0xff6a3d", "950"), text(caption, 54, 60)] + ([text(label, 22, "h-50", "0x8b8b9a")] if label else [])))
    ff("-ss", f"{ss:.3f}", "-i", str(src), "-ss", f"{ss:.3f}", "-i", str(res), "-filter_complex", fc, "-t", f"{dur:.3f}", *common, str(path))


def slide(path, image, dur, caption):
    vf = f"scale={W}:{H}:force_original_aspect_ratio=decrease,pad={W}:{H}:(ow-iw)/2:(oh-ih)/2,{text(caption, 40, 'h-90')}"
    ff("-loop", "1", "-i", str(image), "-t", str(dur), "-vf", vf, *common, str(path))


def main():
    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        parts = []
        card(tmp / "title.mp4", 6, [("One-take VFX", 96, "230", "white"), ("Upload a phone clip. Pick an effect.", 40, "380", "0xff6a3d"),
                                   ("LTX 2.5 + ComfyUI. 100% open weights.", 32, "450", "0x8b8b9a")])
        parts.append(tmp / "title.mp4")
        for i, (preset, clip, caption) in enumerate(SHOTS):
            if not (ROOT / "demo/outputs" / f"{clip}__{preset}.mp4").exists():
                continue
            split(tmp / f"s{i}.mp4", clip, preset, caption)
            parts.append(tmp / f"s{i}.mp4")
        card(tmp / "how.mp4", 8, [("How it's built", 64, "150", "white"), ("Canny edges of your clip drive the motion (LTX IC-LoRA)", 32, "290", "white"),
                                  ("The first frame keeps the person and the room", 32, "350", "white"),
                                  ("The preset prompt adds the effect. LTX 2.5 renders it in 8 steps", 32, "410", "white")])
        parts.append(tmp / "how.mp4")
        for name, image, cap in [("g1", "docs/graph-left.png", "The ComfyUI workflow: inputs, control and first-frame anchor"),
                                 ("g2", "docs/graph-right.png", "LTX 2.5 sampler, guider and decode")]:
            slide(tmp / f"{name}.mp4", ROOT / image, 9, cap)
            parts.append(tmp / f"{name}.mp4")
        card(tmp / "outro.mp4", 6, [("Open source. MIT. Runs on one GPU.", 48, "250", "white"), ("Presets are JSON: add one file, get a new effect", 32, "340", "0x8b8b9a"),
                                    ("github.com/Kainotomic/one-take-vfx", 36, "430", "0xff6a3d")])
        parts.append(tmp / "outro.mp4")
        lst = tmp / "list.txt"
        lst.write_text("".join(f"file '{p}'\n" for p in parts))
        out = ROOT / "demo/one-take-vfx-demo-nov.mp4"
        ff("-f", "concat", "-safe", "0", "-i", str(lst), "-c", "copy", str(out))
        print("wrote", out)
        # Social clip (about 12 s): the three strongest effects back to back
        social = [tmp / f"s{i}.mp4" for i, (p, c, _) in enumerate(SHOTS) if p in ("set-on-fire", "portal", "disintegrate") and (tmp / f"s{i}.mp4").exists()]
        if social:
            sl = tmp / "slist.txt"
            sl.write_text("".join(f"file '{p}'\n" for p in social))
            ff("-f", "concat", "-safe", "0", "-i", str(sl), "-c", "copy", str(ROOT / "demo/social-clip.mp4"))
            print("wrote demo/social-clip.mp4")
        # README preview: three presets, before/after, small
        previews = [tmp / f"s{i}.mp4" for i, (p, c, _) in enumerate(SHOTS) if p in ("disintegrate", "set-on-fire") and (tmp / f"s{i}.mp4").exists()]
        if previews:
            pl = tmp / "plist.txt"
            pl.write_text("".join(f"file '{p}'\n" for p in previews))
            ff("-f", "concat", "-safe", "0", "-i", str(pl), "-vf", "fps=10,scale=560:-1:flags=lanczos,split[a][b];[a]palettegen[p];[b][p]paletteuse", str(ROOT / "docs/preview.gif"))
            print("wrote docs/preview.gif")


if __name__ == "__main__":
    main()
