# /// script
# requires-python = ">=3.10"
# dependencies = ["httpx>=0.27"]
# ///
"""Render a clip with a preset through the One-take VFX server and save the MP4. Usage: render.py CLIP PRESET OUT [--seed N]"""
import argparse
import json
import os
import subprocess
import sys

import httpx

ap = argparse.ArgumentParser()
ap.add_argument("clip")
ap.add_argument("preset")
ap.add_argument("out")
ap.add_argument("--seed", type=int)
a = ap.parse_args()
base = os.environ.get("APP_URL", "http://127.0.0.1:7860")
data = {"preset": a.preset}
probe = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries", "stream=width,height", "-of", "csv=p=0", a.clip], capture_output=True, text=True)
if probe.returncode == 0 and "," in probe.stdout:
    data["width"], data["height"] = probe.stdout.strip().split(",")[:2]
if a.seed is not None:
    data["seed"] = str(a.seed)
with httpx.Client(base_url=base, timeout=httpx.Timeout(30, read=900)) as c:
    with open(a.clip, "rb") as f:
        r = c.post("/api/jobs", files={"file": (os.path.basename(a.clip), f, "video/mp4")}, data=data)
    r.raise_for_status()
    job = r.json()["job_id"]
    with c.stream("GET", f"/api/jobs/{job}/events") as s:
        for line in s.iter_lines():
            if line.startswith("data:"):
                m = json.loads(line[5:])
                if m["state"] == "error":
                    sys.exit(f"render failed: {m['error']}")
                if m["state"] == "done":
                    break
    open(a.out, "wb").write(c.get(f"/api/jobs/{job}/video").content)
print("saved", a.out)
