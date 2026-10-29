# /// script
# requires-python = ">=3.10"
# dependencies = ["playwright>=1.45"]
# ///
"""Convert ComfyUI API-format workflows to UI (graph) format by loading them in the real ComfyUI frontend and serializing.
Needs a running ComfyUI (default http://127.0.0.1:8188) and `playwright install chromium`.
Usage: uv run scripts/api_to_ui.py API.json UI.json [COMFYUI_URL]"""
import json
import sys

from playwright.sync_api import sync_playwright

api_path, ui_path = sys.argv[1], sys.argv[2]
base = sys.argv[3] if len(sys.argv) > 3 else "http://127.0.0.1:8188"
api = json.load(open(api_path))

with sync_playwright() as p:
    browser = p.chromium.launch()
    page = browser.new_page(viewport={"width": 1920, "height": 1080})
    page.goto(base)
    page.wait_for_function("window.app && window.app.graph", timeout=60000)
    page.wait_for_timeout(3000)
    page.evaluate("(a) => window.app.loadApiJson(a, 'one_take_vfx')", api)
    page.wait_for_timeout(2000)
    ui = page.evaluate("() => JSON.parse(JSON.stringify(window.app.graph.serialize()))")
    browser.close()

for node in ui["nodes"]:
    node["title"] = node.get("title") or node["type"]

# Left-to-right layout: column = longest path from a source node, rows stacked by node height.
by_id = {node["id"]: node for node in ui["nodes"]}
ups = {node["id"]: [] for node in ui["nodes"]}
for _, origin, _, target, _, _ in ui["links"]:
    ups[target].append(origin)
depth = {}


def col_of(i):
    if i not in depth:
        depth[i] = 1 + max((col_of(u) for u in ups[i]), default=-1)
    return depth[i]


col_y = {}
for node in sorted(ui["nodes"], key=lambda nd: (col_of(nd["id"]), nd["id"])):
    col = col_of(node["id"])
    node["pos"] = [40 + col * 400, col_y.get(col, 40)]
    col_y[col] = col_y.get(col, 40) + node["size"][1] + 40
json.dump(ui, open(ui_path, "w"), indent=2)
print("wrote", ui_path, len(ui["nodes"]), "nodes", len(ui["links"]), "links")
