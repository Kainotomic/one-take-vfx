#!/usr/bin/env bash
# Download three free-license sample clips (Mixkit Video License: https://mixkit.co/license/#videoFree)
# and trim/crop them to 768x448, 24 fps, 4 s. Output: assets/clips/<id>_clip.mp4
set -euo pipefail
cd "$(dirname "$0")/.."
mkdir -p assets/clips
for id in 407 26925 36624; do
  curl -fsSL -o "/tmp/mixkit_$id.mp4" "https://assets.mixkit.co/videos/$id/$id-720.mp4"
  ffmpeg -v error -y -ss 1 -i "/tmp/mixkit_$id.mp4" -t 4.1 -r 24 -vf "scale=-2:448,crop=768:448" -an \
    -c:v libx264 -crf 14 -pix_fmt yuv420p "assets/clips/${id}_clip.mp4"
done
