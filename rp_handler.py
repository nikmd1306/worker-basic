import json
import os
import subprocess
import time
import uuid

import requests
import runpod

COMFY_PORT = int(os.getenv("COMFY_PORT", "8188"))
COMFY_URL = f"http://127.0.0.1:{COMFY_PORT}"

# --- стартуем ComfyUI один раз (cold start) ---
if "COMFY_STARTED" not in os.environ:
    # headless сервер ComfyUI
    proc = subprocess.Popen(
        [
            "python",
            "-u",
            "ComfyUI/main.py",
            "--listen",
            "0.0.0.0",
            "--port",
            str(COMFY_PORT),
            "--disable-auto-launch",
            "--dont-print-server",
        ],
        cwd="/workspace",
        env=os.environ.copy(),
    )
    # ждём, пока API поднимется
    for _ in range(180):
        try:
            r = requests.get(f"{COMFY_URL}/system_stats", timeout=2)
            if r.status_code == 200:
                break
        except Exception:
            if proc.poll() is not None:
                raise RuntimeError("ComfyUI exited early")
            time.sleep(1)
    else:
        raise RuntimeError("ComfyUI failed to start in time")
    os.environ["COMFY_STARTED"] = "1"


def _queue_prompt(workflow: dict, client_id: str):
    r = requests.post(
        f"{COMFY_URL}/prompt",
        json={"prompt": workflow, "client_id": client_id},
        timeout=60,
    )
    r.raise_for_status()
    return r.json()["prompt_id"]


def _get_images(prompt_id: str):
    # ждём завершения и забираем пути к файлам из /history
    while True:
        h = requests.get(f"{COMFY_URL}/history/{prompt_id}", timeout=60).json()
        if prompt_id in h and h[prompt_id].get("outputs"):
            return h[prompt_id]["outputs"]
        time.sleep(0.5)


def handler(job):
    inp = job["input"]
    # подставляем prompt/seed/размеры в готовый workflow
    wf = json.load(open("/workspace/workflows/Qwen_danrisi.json"))
    # пример: заменим текстовые поля, если такие есть в узлах
    for node in wf.values():
        if (
            isinstance(node, dict)
            and node.get("class_type", "").lower().find("prompt") >= 0
        ):
            if "inputs" in node and "text" in node["inputs"]:
                node["inputs"]["text"] = inp.get("prompt", "a girl, high quality")
    # укажем путь к LoRA, если требуется нодой
    # (в Qwen-узлах это обычно поле типа lora_path / lora_name)
    for node in wf.values():
        if isinstance(node, dict) and "lora" in json.dumps(node).lower():
            if "inputs" in node:
                node["inputs"]["lora_name"] = "adorablegirls.safetensors"

    client_id = str(uuid.uuid4())
    prompt_id = _queue_prompt(wf, client_id)
    outputs = _get_images(prompt_id)

    # соберём абсолютные пути и вернём base64/пути
    # (см. лимит полезной нагрузки)
    images = []
    for _, data in outputs.items():
        for img in data.get("images", []):
            images.append(
                {
                    "filename": img.get("filename"),
                    "subfolder": img.get("subfolder"),
                    "type": img.get("type"),
                }
            )
    # можно добавить refresh_worker для чистого состояния
    return {"images": images}


runpod.serverless.start({"handler": handler})
