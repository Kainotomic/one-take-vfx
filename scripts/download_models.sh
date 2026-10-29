#!/usr/bin/env bash
# Download the LTX 2.5 files used by the workflow into a ComfyUI models directory.
# Usage: HF_TOKEN=... scripts/download_models.sh /path/to/ComfyUI/models
# The Lightricks/LTX-2.5 repo is gated: accept the license at https://huggingface.co/Lightricks/LTX-2.5 first.
set -euo pipefail
M="${1:?path to ComfyUI/models}"
: "${HF_TOKEN:?set HF_TOKEN to a Hugging Face read token}"
get() {
  mkdir -p "$M/$2"
  curl -fL -C - -H "Authorization: Bearer $HF_TOKEN" -o "$M/$2/$(basename "$1")" \
    "https://huggingface.co/Lightricks/LTX-2.5/resolve/main/$1"
}
get diffusion_models/ltx-2.5-22b-distilled-transformer-comfy-int8-convrot.safetensors diffusion_models  # 21.5 GB
get text_encoders/gemma4-12b-with-proj-ltx-2.5-comfy-int8-convrot.safetensors text_encoders              # 15.4 GB
get vae/ltx-2.5-video-vae-bf16.safetensors vae                                                           # 1.5 GB
get vae/ltx-2.5-audio-vae-bf16.safetensors vae                                                           # 0.4 GB
# IC-LoRA (control): public repo, no token needed. Trained for LTX-2.3; Lightricks states most LTX-2.3 IC-LoRAs run on 2.5.
mkdir -p "$M/loras"
curl -fL -C - -o "$M/loras/ltx-2.3-22b-ic-lora-union-control-ref0.5.safetensors" \
  "https://huggingface.co/Lightricks/LTX-2.3-22b-IC-LoRA-Union-Control/resolve/main/ltx-2.3-22b-ic-lora-union-control-ref0.5.safetensors"  # 0.65 GB
echo "done"
