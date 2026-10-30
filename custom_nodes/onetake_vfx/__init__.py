"""OneTakeVFX nodes: Preset (loads presets/*.json) and Guide Motion (moves the control guide over time)."""
import json
from pathlib import Path

import torch

PRESET_DIR = Path(__file__).resolve().parent.parent.parent / "presets"


def _load():
    return {p["id"]: p for p in (json.loads(f.read_text()) for f in sorted(PRESET_DIR.glob("*.json")))}


class OneTakeVFXPreset:
    @classmethod
    def INPUT_TYPES(cls):
        return {"required": {"preset": (list(_load()), {"tooltip": "Effect preset from presets/*.json"})}}

    RETURN_TYPES = ("STRING", "STRING", "FLOAT", "FLOAT", "INT", "FLOAT", "FLOAT", "FLOAT", "FLOAT", "FLOAT", "FLOAT")
    RETURN_NAMES = ("prompt", "negative_prompt", "control_strength", "anchor_strength", "num_frames", "fps",
                    "guide_dy", "guide_dx", "guide_fade_below", "guide_region_x0", "guide_region_x1")
    FUNCTION = "load"
    CATEGORY = "OneTakeVFX"

    def load(self, preset):
        p = _load()[preset]
        m = p.get("guide_motion", {})
        x0, x1 = m.get("region", [0.0, 1.0])
        return (p["prompt"], p["negative_prompt"], float(p["control_strength"]), float(p.get("anchor_strength", 1.0)),
                int(p["num_frames"]), float(p["fps"]), float(m.get("dy", 0.0)), float(m.get("dx", 0.0)),
                float(m.get("fade_below", 0.0)), float(x0), float(x1))

    @classmethod
    def IS_CHANGED(cls, preset):
        return json.dumps(_load()[preset], sort_keys=True)


class OneTakeGuideMotion:
    """Moves the control guide (a frame batch) over the clip so the render is pulled along: dy and dx are fractions of
    the frame size reached at the last frame (negative dy moves up), eased in as t**ease_power. region limits the move to
    a horizontal band (x0..x1 as fractions of width), so background edges outside the subject stay put. fade_below
    blacks out that fraction of the frame height at the bottom after the move (e.g. to drop the legs' contact with the floor)."""

    @classmethod
    def INPUT_TYPES(cls):
        return {"required": {
            "image": ("IMAGE",),
            "dy": ("FLOAT", {"default": 0.0, "min": -1.0, "max": 1.0, "step": 0.01}),
            "dx": ("FLOAT", {"default": 0.0, "min": -1.0, "max": 1.0, "step": 0.01}),
            "ease_power": ("FLOAT", {"default": 2.0, "min": 0.5, "max": 5.0, "step": 0.1}),
            "fade_below": ("FLOAT", {"default": 0.0, "min": 0.0, "max": 1.0, "step": 0.01}),
            "region_x0": ("FLOAT", {"default": 0.0, "min": 0.0, "max": 1.0, "step": 0.01}),
            "region_x1": ("FLOAT", {"default": 1.0, "min": 0.0, "max": 1.0, "step": 0.01}),
        }}

    RETURN_TYPES = ("IMAGE",)
    FUNCTION = "move"
    CATEGORY = "OneTakeVFX"

    def move(self, image, dy, dx, ease_power, fade_below, region_x0, region_x1):
        if dy == 0 and dx == 0 and fade_below == 0:
            return (image,)
        frames, height, width = image.shape[0], image.shape[1], image.shape[2]
        x0, x1 = int(round(region_x0 * width)), max(int(round(region_x1 * width)), int(round(region_x0 * width)) + 1)
        out = image.clone()
        for t in range(frames):
            k = (t / max(frames - 1, 1)) ** ease_power
            sy, sx = int(round(dy * height * k)), int(round(dx * width * k))
            band = torch.zeros_like(image[t, :, x0:x1])
            src = image[t, :, x0:x1]
            ys, ye = max(0, sy), min(height, height + sy)  # destination rows
            if ye > ys:
                band[ys:ye] = src[ys - sy:ye - sy]
            if sx:
                band = torch.roll(band, shifts=sx, dims=1)
                if sx > 0:
                    band[:, :sx] = 0
                else:
                    band[:, sx:] = 0
            out[t, :, x0:x1] = band
            if fade_below > 0:
                out[t, int(height * (1 - fade_below)):, :] = 0
        return (out,)


NODE_CLASS_MAPPINGS = {"OneTakeVFXPreset": OneTakeVFXPreset, "OneTakeGuideMotion": OneTakeGuideMotion}
NODE_DISPLAY_NAME_MAPPINGS = {"OneTakeVFXPreset": "OneTakeVFX Preset", "OneTakeGuideMotion": "OneTakeVFX Guide Motion"}
