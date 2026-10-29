#!/usr/bin/env bash
# Install ComfyUI + the one custom node pack the workflow needs, at the commits this project was built and tested on.
# Usage: scripts/install_comfyui.sh /path/to/install-dir      (needs git and uv)
set -euo pipefail
DEST="${1:?install dir}"
REPO="$(cd "$(dirname "$0")/.." && pwd)"
COMFY_SHA=fd7639f477050e5c25b68fc38a9c2a6b6d988211
VHS_SHA=4d907bee61e92c2e65af3bd6383a4e4d356126d1
mkdir -p "$DEST" && cd "$DEST"
[ -d ComfyUI ] || git clone https://github.com/comfyanonymous/ComfyUI.git
git -C ComfyUI checkout "$COMFY_SHA"
uv venv --python 3.12 venv
. venv/bin/activate
uv pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu128
uv pip install -r ComfyUI/requirements.txt
cd ComfyUI/custom_nodes
[ -d ComfyUI-VideoHelperSuite ] || git clone https://github.com/Kosinkadink/ComfyUI-VideoHelperSuite.git
git -C ComfyUI-VideoHelperSuite checkout "$VHS_SHA"
uv pip install -r ComfyUI-VideoHelperSuite/requirements.txt
ln -sfn "$REPO/custom_nodes/onetake_vfx" onetake_vfx
echo "Installed. Start with: $DEST/venv/bin/python $DEST/ComfyUI/main.py --listen 127.0.0.1 --port 8188 --lowvram"
