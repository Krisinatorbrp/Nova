"""Talking to Ollama (the program that runs AI models on your PC) and picking a model for your GPU."""
import json
import os
import shutil
import subprocess
import threading
import time

import httpx

# Vision + tool-calling models, smallest to largest.
MODELS = [
    {"tag": "qwen3-vl:2b", "size_gb": 1.9, "min_vram": 0, "label": "Qwen3-VL 2B · tiny, for weak PCs"},
    {"tag": "qwen3-vl:4b", "size_gb": 3.3, "min_vram": 4, "label": "Qwen3-VL 4B · light"},
    {"tag": "qwen3-vl:8b", "size_gb": 6.1, "min_vram": 7, "label": "Qwen3-VL 8B · balanced"},
    {"tag": "qwen3-vl:30b", "size_gb": 20, "min_vram": 20, "label": "Qwen3-VL 30B · smartest, needs a big GPU"},
]


def host(cfg) -> str:
    return cfg.get("ollama_host", "http://127.0.0.1:11434").rstrip("/")


def status(cfg) -> dict:
    out = {"running": False, "installed": bool(shutil.which("ollama")) or _default_install_exists(),
           "models": [], "version": None}
    try:
        r = httpx.get(host(cfg) + "/api/tags", timeout=2)
        out["running"] = r.status_code == 200
        out["models"] = sorted(m["name"] for m in r.json().get("models", []))
        v = httpx.get(host(cfg) + "/api/version", timeout=2).json()
        out["version"] = v.get("version")
    except Exception:
        pass
    gpu = gpu_info()
    out["gpu"] = gpu
    out["recommended"] = recommend(gpu.get("vram_gb"))
    out["catalog"] = MODELS
    return out


def _default_install_exists() -> bool:
    p = os.path.join(os.environ.get("LOCALAPPDATA", ""), "Programs", "Ollama", "ollama.exe")
    return os.path.exists(p)


def try_start(cfg):
    """Start the Ollama background server if it's installed but not running."""
    exe = shutil.which("ollama")
    if not exe:
        p = os.path.join(os.environ.get("LOCALAPPDATA", ""), "Programs", "Ollama", "ollama.exe")
        exe = p if os.path.exists(p) else None
    if not exe:
        return False
    try:
        subprocess.Popen([exe, "serve"], creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
                         stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        return True
    except Exception:
        return False


_gpu_cache = None


def gpu_info() -> dict:
    global _gpu_cache
    if _gpu_cache is not None:
        return _gpu_cache
    info = {"name": None, "vram_gb": None}
    try:  # NVIDIA
        out = subprocess.run(["nvidia-smi", "--query-gpu=name,memory.total", "--format=csv,noheader,nounits"],
                             capture_output=True, text=True, timeout=5,
                             creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0)).stdout.strip()
        if out:
            name, mem = out.splitlines()[0].rsplit(",", 1)
            info = {"name": name.strip(), "vram_gb": round(int(mem) / 1024, 1)}
    except Exception:
        pass
    if not info["name"] and os.name == "nt":
        try:  # AMD / Intel: registry has the real VRAM size (WMI caps at 4 GB)
            ps = ("Get-ItemProperty 'HKLM:\\SYSTEM\\ControlSet001\\Control\\Class\\{4d36e968-e325-11ce-bfc1-08002be10318}\\0*' "
                  "-ErrorAction SilentlyContinue | Where-Object { $_.'HardwareInformation.qwMemorySize' } | "
                  "Select-Object -First 1 DriverDesc, 'HardwareInformation.qwMemorySize' | ConvertTo-Json")
            out = subprocess.run(["powershell", "-NoProfile", "-Command", ps], capture_output=True, text=True,
                                 timeout=8, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0)).stdout
            j = json.loads(out)
            info = {"name": j.get("DriverDesc"), "vram_gb": round(int(j["HardwareInformation.qwMemorySize"]) / 2**30, 1)}
        except Exception:
            pass
    _gpu_cache = info
    return info


def recommend(vram_gb) -> str:
    if vram_gb is None:
        return "qwen3-vl:4b"
    pick = MODELS[0]["tag"]
    for m in MODELS:
        if vram_gb >= m["min_vram"]:
            pick = m["tag"]
    return pick


class Puller:
    """Downloads a model in the background and reports progress through emit()."""

    def __init__(self, cfg, emit):
        self.cfg, self.emit = cfg, emit
        self.active = None

    def start(self, tag: str) -> bool:
        if self.active:
            return False
        self.active = tag
        threading.Thread(target=self._run, args=(tag,), daemon=True).start()
        return True

    def _run(self, tag):
        try:
            with httpx.stream("POST", host(self.cfg) + "/api/pull", json={"model": tag, "stream": True},
                              timeout=httpx.Timeout(30, read=600)) as r:
                last, parts = 0, {}
                for line in r.iter_lines():
                    if not line:
                        continue
                    ev = json.loads(line)
                    if ev.get("error"):
                        raise RuntimeError(ev["error"])
                    # a model comes in several parts: show the progress of all of them together
                    if ev.get("digest") and ev.get("total"):
                        parts[ev["digest"]] = (ev.get("completed") or 0, ev["total"])
                    total = sum(t for _, t in parts.values())
                    done = sum(c for c, _ in parts.values())
                    pct = round(done * 100 / total, 1) if total and done else None
                    if pct is None or abs(pct - last) >= 0.5 or ev.get("status") == "success":
                        last = pct or last
                        self.emit({"type": "pull", "model": tag, "status": ev.get("status", ""), "pct": pct})
            self.emit({"type": "pull", "model": tag, "status": "success", "pct": 100, "done": True})
        except Exception as e:
            self.emit({"type": "pull", "model": tag, "status": f"Download failed: {e}", "error": True, "done": True})
        finally:
            self.active = None


_warm = {"model": None, "t": 0.0}


def warm_up(cfg, min_gap=0.0):
    """Load the model into the graphics card now, so the first question isn't slow.
    min_gap: skip if we already did this for the same model within that many seconds."""
    model = cfg.get("local_model")
    if not model:
        return
    now = time.time()
    if min_gap and _warm["model"] == model and now - _warm["t"] < min_gap:
        return
    _warm.update(model=model, t=now)

    def run():
        try:
            httpx.post(host(cfg) + "/api/generate",
                       json={"model": model, "prompt": "", "keep_alive": "30m",
                             "options": {"num_ctx": int(cfg.get("local_ctx", 8192))}},
                       timeout=httpx.Timeout(10, read=300))
        except Exception:
            pass
    threading.Thread(target=run, daemon=True).start()
