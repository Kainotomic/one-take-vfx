"""Generate the ComfyUI API-format workflows in workflows/ with fixed, human-readable node ids.

Pipeline: canny edges of the input clip drive the motion through LTX's IC-LoRA (union control), the clip's first
frame anchors the person and scene, and the preset prompt adds the effect. LTX 2.5 distilled does the generation.
"""
import json
from pathlib import Path

UNET = "ltx-2.5-22b-distilled-transformer-comfy-int8-convrot.safetensors"
TEXT_ENCODER = "gemma4-12b-with-proj-ltx-2.5-comfy-int8-convrot.safetensors"
VIDEO_VAE = "ltx-2.5-video-vae-bf16.safetensors"
AUDIO_VAE = "ltx-2.5-audio-vae-bf16.safetensors"
IC_LORA = "ltx-2.3-22b-ic-lora-union-control-ref0.5.safetensors"
SIGMAS = "1.0, 0.99375, 0.9875, 0.98125, 0.975, 0.909375, 0.725, 0.421875, 0.0"
W, H = 768, 448


def n(class_type, **inputs):
    return {"class_type": class_type, "inputs": inputs}


wf = {
    "unet": n("UNETLoader", unet_name=UNET, weight_dtype="default"),
    "ic_lora": n("LTXICLoRALoaderModelOnly", model=["unet", 0], lora_name=IC_LORA, strength_model=0.6),
    "clip": n("CLIPLoader", clip_name=TEXT_ENCODER, type="ltxv", device="default"),
    "vae": n("VAELoader", vae_name=VIDEO_VAE),
    "audio_vae": n("VAELoader", vae_name=AUDIO_VAE),
    "load_video": n("VHS_LoadVideo", video="input.mp4", force_rate=24, custom_width=0, custom_height=0,
                    frame_load_cap=97, skip_first_frames=0, select_every_nth=1, format="AnimateDiff"),
    "fit": n("ImageScale", image=["load_video", 0], upscale_method="bilinear", width=W, height=H, crop="center"),
    "preprocess": n("LTXVPreprocess", image=["fit", 0], img_compression=18),
    "canny": n("Canny", image=["fit", 0], low_threshold=0.1, high_threshold=0.3),
    "guide_motion": n("OneTakeGuideMotion", image=["canny", 0], dy=0.0, dx=0.0, ease_power=2.0, fade_below=0.0, region_x0=0.0, region_x1=1.0),
    "control_small": n("ImageScale", image=["guide_motion", 0], upscale_method="bilinear", width=W // 2, height=H // 2, crop="disabled"),
    "positive": n("CLIPTextEncode", clip=["clip", 0], text=""),
    "negative": n("CLIPTextEncode", clip=["clip", 0], text=""),
    "conditioning": n("LTXVConditioning", positive=["positive", 0], negative=["negative", 0], frame_rate=24.0),
    "empty_latent": n("EmptyLTXVLatentVideo", width=W, height=H, length=97, batch_size=1),
    "first_frame": n("ImageFromBatch", image=["preprocess", 0], batch_index=0, length=1),
    "anchor": n("LTXVImgToVideoInplace", vae=["vae", 0], image=["first_frame", 0], latent=["empty_latent", 0], strength=1.0, bypass=False),
    "guide": n("LTXAddVideoICLoRAGuide", positive=["conditioning", 0], negative=["conditioning", 1], vae=["vae", 0], latent=["anchor", 0],
               image=["control_small", 0], frame_idx=0, strength=0.6, latent_downscale_factor=["ic_lora", 1], crop="center",
               use_tiled_encode=False, tile_size=256, tile_overlap=64),
    "audio_latent": n("LTXVEmptyLatentAudio", frames_number=97, frame_rate=24, batch_size=1, audio_vae=["audio_vae", 0]),
    "av_latent": n("LTXVConcatAVLatent", video_latent=["guide", 2], audio_latent=["audio_latent", 0]),
    "guider": n("LTXVDualCFGGuider", model=["ic_lora", 0], positive=["guide", 0], negative=["guide", 1], video_cfg=1.0, audio_cfg=1.0),
    "sampler_select": n("KSamplerSelect", sampler_name="euler_ancestral"),
    "sigmas": n("ManualSigmas", sigmas=SIGMAS),
    "noise": n("RandomNoise", noise_seed=0),
    "sample": n("SamplerCustomAdvanced", noise=["noise", 0], guider=["guider", 0], sampler=["sampler_select", 0],
                sigmas=["sigmas", 0], latent_image=["av_latent", 0]),
    "split": n("LTXVSeparateAVLatent", av_latent=["sample", 0]),
    "crop_guides": n("LTXVCropGuides", positive=["guide", 0], negative=["guide", 1], latent=["split", 0]),
    "decode": n("VAEDecodeTiled", samples=["crop_guides", 2], vae=["vae", 0], tile_size=512, overlap=64, temporal_size=64, temporal_overlap=16),
    "save": n("VHS_VideoCombine", images=["decode", 0], frame_rate=24.0, loop_count=0, filename_prefix="onetake/out",
              format="video/h264-mp4", pingpong=False, save_output=True),
}

for key, spec in wf.items():
    spec["_meta"] = {"title": key.replace("_", " ").title()}

wf_dir = Path(__file__).resolve().parent.parent / "workflows"
(wf_dir / "one_take_vfx_api.json").write_text(json.dumps(wf, indent=2) + "\n")

# Variant driven by the OneTakeVFX Preset custom node: pick an effect from a dropdown inside ComfyUI.
node = json.loads(json.dumps(wf))
node["preset"] = {**n("OneTakeVFXPreset", preset="set-on-fire"), "_meta": {"title": "Preset"}}
node["positive"]["inputs"]["text"] = ["preset", 0]
node["negative"]["inputs"]["text"] = ["preset", 1]
node["guide"]["inputs"]["strength"] = ["preset", 2]
node["ic_lora"]["inputs"]["strength_model"] = ["preset", 2]
node["anchor"]["inputs"]["strength"] = ["preset", 3]
node["load_video"]["inputs"]["frame_load_cap"] = ["preset", 4]
node["load_video"]["inputs"]["force_rate"] = ["preset", 5]
node["empty_latent"]["inputs"]["length"] = ["preset", 4]
node["audio_latent"]["inputs"]["frames_number"] = ["preset", 4]
node["audio_latent"]["inputs"]["frame_rate"] = ["preset", 5]
node["conditioning"]["inputs"]["frame_rate"] = ["preset", 5]
node["save"]["inputs"]["frame_rate"] = ["preset", 5]
node["guide_motion"]["inputs"].update(dy=["preset", 6], dx=["preset", 7], fade_below=["preset", 8], region_x0=["preset", 9], region_x1=["preset", 10])
(wf_dir / "one_take_vfx_preset_node_api.json").write_text(json.dumps(node, indent=2) + "\n")
print("wrote workflows")
