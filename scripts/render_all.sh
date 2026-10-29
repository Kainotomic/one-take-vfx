#!/usr/bin/env bash
# Render every preset on every clip in assets/clips -> demo/outputs/<clip>__<preset>.mp4
set -u
cd "$(dirname "$0")/.."
for clip in assets/clips/*_clip.mp4; do
  c=$(basename "$clip" _clip.mp4)
  for p in presets/*.json; do
    id=$(basename "$p" .json)
    out="demo/outputs/${c}__${id}.mp4"
    [ -s "$out" ] || uv run scripts/render.py "$clip" "$id" "$out" --seed 7 || echo "FAILED $c $id"
  done
done
echo RENDER_ALL_DONE
