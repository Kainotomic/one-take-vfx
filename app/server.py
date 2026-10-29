# /// script
# requires-python = ">=3.10"
# dependencies = ["fastapi>=0.115", "uvicorn>=0.30", "httpx>=0.27", "websockets>=13", "python-multipart>=0.0.9"]
# ///
"""One-take VFX web app: uploads a clip, fills a workflow with a preset, and relays progress from ComfyUI."""
import asyncio
import base64
import copy
import hmac
import json
import os
import random
import uuid
from pathlib import Path

import httpx
import websockets
from fastapi import FastAPI, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse, JSONResponse, Response, StreamingResponse
from fastapi.staticfiles import StaticFiles

ROOT = Path(__file__).resolve().parent.parent
COMFYUI_URL = os.environ.get("COMFYUI_URL", "http://127.0.0.1:8188").rstrip("/")
COMFYUI_AUTH = (os.environ["COMFYUI_USER"], os.environ["COMFYUI_PASSWORD"]) if os.environ.get("COMFYUI_USER") else None
WORKFLOW = json.loads((ROOT / "workflows" / "one_take_vfx_api.json").read_text())
PRESETS = {p["id"]: p for p in (json.loads(f.read_text()) for f in sorted((ROOT / "presets").glob("*.json")))}

app = FastAPI(title="One-take VFX")
client = httpx.AsyncClient(base_url=COMFYUI_URL, auth=COMFYUI_AUTH, timeout=httpx.Timeout(60, read=600))
APP_PASSWORD = os.environ.get("APP_PASSWORD")
ALLOWED_HOSTS = {h.strip().lower() for h in os.environ.get("ALLOWED_HOSTS", "localhost,127.0.0.1,[::1]").split(",")}
MAX_QUEUE = int(os.environ.get("MAX_QUEUE", "0"))
jobs: dict[str, dict] = {}
submit_lock = asyncio.Lock()


@app.middleware("http")
async def password_gate(request: Request, call_next):
    """Optional shared password (HTTP basic auth, any username) for when the app is reachable by other people."""
    if APP_PASSWORD:
        try:
            given = base64.b64decode(request.headers.get("authorization", "")[6:]).decode().partition(":")[2]
        except Exception:
            given = ""
        if not hmac.compare_digest(given.encode(), APP_PASSWORD.encode()):
            return Response(status_code=401, headers={"WWW-Authenticate": 'Basic realm="One-take VFX"'})
    return await call_next(request)


@app.middleware("http")
async def same_origin_only(request: Request, call_next):
    """Without a password, only answer to local host names (blocks DNS rebinding) and reject cross-site POSTs (CSRF)."""
    if not APP_PASSWORD and request.headers.get("host", "").rsplit(":", 1)[0].lower().strip() not in ALLOWED_HOSTS and request.headers.get("host", "").lower() not in ALLOWED_HOSTS:
        return JSONResponse({"detail": "host not allowed (set ALLOWED_HOSTS)"}, status_code=403)
    origin = request.headers.get("origin")
    if request.method == "POST" and origin and origin.split("://", 1)[-1] != request.headers.get("host"):
        return JSONResponse({"detail": "cross-origin request rejected"}, status_code=403)
    return await call_next(request)


def fit_size(width: int, height: int) -> tuple[int, int]:
    """Long side 768, short side rounded to a multiple of 64 (the control reference is half size, so both halves stay /32)."""
    long_side, short_side = 768, max(256, round(768 * min(width, height) / max(width, height) / 64) * 64)
    return (long_side, short_side) if width >= height else (short_side, long_side)


def build_prompt(preset: dict, video_name: str, seed: int, size: tuple[int, int]) -> dict:
    """Patch the parameterised workflow; node ids are the fixed keys written by scripts/build_workflow.py."""
    wf = copy.deepcopy(WORKFLOW)
    w, h = size
    frames, fps = preset["num_frames"], preset["fps"]
    wf["load_video"]["inputs"].update(video=video_name, frame_load_cap=frames, force_rate=fps)
    wf["fit"]["inputs"].update(width=w, height=h)
    wf["control_small"]["inputs"].update(width=w // 2, height=h // 2)
    wf["empty_latent"]["inputs"].update(width=w, height=h, length=frames)
    wf["audio_latent"]["inputs"].update(frames_number=frames, frame_rate=fps)
    wf["positive"]["inputs"]["text"] = preset["prompt"]
    wf["negative"]["inputs"]["text"] = preset["negative_prompt"]
    wf["conditioning"]["inputs"]["frame_rate"] = float(fps)
    wf["guide"]["inputs"]["strength"] = preset["control_strength"]
    wf["ic_lora"]["inputs"]["strength_model"] = preset["control_strength"]
    wf["noise"]["inputs"]["noise_seed"] = seed
    wf["save"]["inputs"].update(frame_rate=float(fps), filename_prefix=f"onetake/{preset['id']}")
    return wf


@app.get("/api/presets")
def presets():
    return [{"id": p["id"], "name": p["name"], "prompt": p["prompt"]} for p in PRESETS.values()]


@app.post("/api/jobs")
async def create_job(file: UploadFile = File(...), preset: str = Form(...), seed: int | None = Form(None), width: int = Form(768, gt=0, le=8192), height: int = Form(448, gt=0, le=8192)):
    if preset not in PRESETS:
        raise HTTPException(404, "unknown preset")
    data = await file.read()
    name = f"onetake_{uuid.uuid4().hex[:8]}_{Path(file.filename or 'clip.mp4').name}"
    client_id = uuid.uuid4().hex
    seed = random.randint(0, 2**32 - 1) if seed is None else seed
    async with submit_lock:  # the queue check and the submit must be atomic, or concurrent requests all pass the cap
        if MAX_QUEUE:
            q = (await client.get("/queue")).json()
            if len(q["queue_running"]) + len(q["queue_pending"]) >= MAX_QUEUE:
                raise HTTPException(429, "The GPU is busy, try again in a minute")
        up = await client.post("/upload/image", files={"image": (name, data, file.content_type or "video/mp4")}, data={"overwrite": "true"})
        up.raise_for_status()
        r = await client.post("/prompt", json={"prompt": build_prompt(PRESETS[preset], up.json()["name"], seed, fit_size(width, height)), "client_id": client_id})
        if r.status_code != 200:
            raise HTTPException(502, f"ComfyUI rejected the workflow: {r.text[:800]}")
        prompt_id = r.json()["prompt_id"]
    jobs[prompt_id] = {"client_id": client_id}
    return {"job_id": prompt_id}


def sse(obj: dict) -> str:
    return f"data: {json.dumps(obj)}\n\n"


async def output_of(prompt_id: str):
    h = (await client.get(f"/history/{prompt_id}")).json().get(prompt_id)
    if not h:
        return None
    status = h.get("status", {})
    if status.get("status_str") == "error":
        msgs = [m[1] for m in status.get("messages", []) if m[0] == "execution_error"]
        return {"state": "error", "error": (msgs[0].get("exception_message") if msgs else "execution failed")}
    for out in h.get("outputs", {}).values():
        for f in out.get("gifs", []) + out.get("videos", []):
            return {"state": "done", "filename": f["filename"], "subfolder": f.get("subfolder", ""), "type": f.get("type", "output")}
    return None


@app.get("/api/jobs/{job_id}/events")
async def events(job_id: str):
    job = jobs.get(job_id)
    if not job:
        raise HTTPException(404, "unknown job")
    ws_url = COMFYUI_URL.replace("http", "ws", 1) + f"/ws?clientId={job['client_id']}"
    headers = {}
    if COMFYUI_AUTH:
        import base64
        headers["Authorization"] = "Basic " + base64.b64encode(":".join(COMFYUI_AUTH).encode()).decode()

    async def gen():
        done = await output_of(job_id)
        if done:
            yield sse(done)
            return
        async with websockets.connect(ws_url, additional_headers=headers, max_size=None) as ws:
            yield sse({"state": "queued"})
            while True:
                try:
                    msg = await asyncio.wait_for(ws.recv(), timeout=20)
                except asyncio.TimeoutError:
                    done = await output_of(job_id)
                    if done:
                        yield sse(done)
                        return
                    continue
                if isinstance(msg, bytes):
                    continue
                m = json.loads(msg)
                d = m.get("data", {})
                if d.get("prompt_id") not in (None, job_id):
                    continue
                if m["type"] == "progress":
                    yield sse({"state": "running", "value": d["value"], "max": d["max"]})
                elif m["type"] == "executing" and d.get("node"):
                    yield sse({"state": "running", "node": d["node"]})
                elif m["type"] in ("executed", "execution_success", "execution_error"):
                    for _ in range(20):
                        done = await output_of(job_id)
                        if done:
                            yield sse(done)
                            return
                        await asyncio.sleep(0.5)
                    yield sse({"state": "error", "error": "no video output"})
                    return

    return StreamingResponse(gen(), media_type="text/event-stream")


@app.get("/api/jobs/{job_id}/video")
async def video(job_id: str, download: bool = False):
    done = await output_of(job_id)
    if not done or done["state"] != "done":
        raise HTTPException(404, "not finished")
    r = await client.get("/view", params={"filename": done["filename"], "subfolder": done["subfolder"], "type": done["type"]})
    headers = {"Content-Disposition": f'attachment; filename="{done["filename"]}"'} if download else {}
    return Response(r.content, media_type="video/mp4", headers=headers)


@app.get("/")
def index():
    return FileResponse(ROOT / "app" / "static" / "index.html")


app.mount("/static", StaticFiles(directory=ROOT / "app" / "static"), name="static")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host=os.environ.get("HOST", "127.0.0.1"), port=int(os.environ.get("PORT", "7860")))
