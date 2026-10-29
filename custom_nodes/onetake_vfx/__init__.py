"""OneTakeVFX Preset: load an effect preset (prompt, negative prompt, control strength, frames, fps) from presets/*.json."""
import json
from pathlib import Path

PRESET_DIR = Path(__file__).resolve().parent.parent.parent / "presets"


def _load():
    return {p["id"]: p for p in (json.loads(f.read_text()) for f in sorted(PRESET_DIR.glob("*.json")))}


class OneTakeVFXPreset:
    @classmethod
    def INPUT_TYPES(cls):
        return {"required": {"preset": (list(_load()), {"tooltip": "Effect preset from presets/*.json"})}}

    RETURN_TYPES = ("STRING", "STRING", "FLOAT", "INT", "FLOAT")
    RETURN_NAMES = ("prompt", "negative_prompt", "control_strength", "num_frames", "fps")
    FUNCTION = "load"
    CATEGORY = "OneTakeVFX"

    def load(self, preset):
        p = _load()[preset]
        return (p["prompt"], p["negative_prompt"], float(p["control_strength"]), int(p["num_frames"]), float(p["fps"]))

    @classmethod
    def IS_CHANGED(cls, preset):
        return json.dumps(_load()[preset], sort_keys=True)


NODE_CLASS_MAPPINGS = {"OneTakeVFXPreset": OneTakeVFXPreset}
NODE_DISPLAY_NAME_MAPPINGS = {"OneTakeVFXPreset": "OneTakeVFX Preset"}
