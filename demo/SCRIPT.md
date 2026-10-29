# Demo video script (target 90 s)

`demo/one-take-vfx-demo.mp4` has an AI narration (a text-to-speech voice, used only for the video; the app and pipeline use open weights only). `demo/one-take-vfx-demo-nov.mp4` is the silent cut with on-screen captions. The text below is the outline of the narration (wording differs slightly); read it live over the silent cut if you prefer your own voice. Times are cues, not limits.

**0:00 Title (5 s).** "One-take VFX: upload a phone clip, pick an effect. Open weights, running in ComfyUI."

**0:05 The problem (10 s).** "Apps like Higgsfield turn a phone clip into a movie effect in one tap. They are closed. I rebuilt the idea with open weights: LTX 2.5 and ComfyUI, on one GPU."

**0:15 The effects (40 s).** Before/after for each preset; one line each, about 5 s:
- "Disintegrate."
- "Levitate."
- "Set on fire."
- "Portal."
- "Time freeze."
- "And slow-mo debris, rain stop and hologram."
Say once: "Same clip, same motion, same room. Only the effect is new."

**0:55 How it's built (25 s).** Show the ComfyUI graph. "The input clip goes through Canny edges into LTX's IC-LoRA, so the person's motion is kept. The first frame is locked in, so the person and the room stay recognisable. The preset adds the effect prompt, LTX 2.5 distilled renders it in eight steps. The same graph runs behind a small web app and from a dropdown inside ComfyUI, using a custom OneTakeVFX Preset node."

**1:20 Open and runnable (10 s).** "Presets are plain JSON: add one file, get a new effect. Code is MIT, models are LTX open weights. Runs on a single RTX 3090 at about 70 seconds per clip. Repo link below."
