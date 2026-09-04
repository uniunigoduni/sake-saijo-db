from __future__ import annotations

import concurrent.futures as cf
import hashlib
import json
import random
import threading
import time
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from pathlib import Path

import requests

OUT = Path(__file__).resolve().parent.parent / "jsake"
MANIFEST = OUT / "manifest.jsonl"
LOG = OUT / "collection.log"
LOCK = threading.Lock()
BASE = "https://jsake.jp"
SITEMAP = BASE + "/sitemap.xml"
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) sake-saijo-db/0.1"
PATTERNS = ["ignore previous instructions", "ignore all previous instructions",
            "system prompt", "developer message", "prompt injection",
            "以前の指示を無視", "上の指示を無視", "システムプロンプト"]


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


def log(msg: str) -> None:
    line = f"[{now()}] {msg}"
    print(line, flush=True)
    with LOCK, LOG.open("a", encoding="utf-8") as f:
        f.write(line + "\n")


def record(item: dict) -> None:
    item.setdefault("collected_at", now())
    with LOCK, MANIFEST.open("a", encoding="utf-8") as f:
        f.write(json.dumps(item, ensure_ascii=False) + "\n")


def get(url: str) -> requests.Response:
    last = None
    for attempt in range(4):
        try:
            r = requests.get(url, headers={"User-Agent": UA}, timeout=(10, 60))
            if r.status_code == 429 or 500 <= r.status_code < 600:
                last = RuntimeError(f"HTTP {r.status_code}")
                if attempt < 3:
                    time.sleep((2 ** attempt) + random.random())
                    continue
            return r
        except Exception as e:
            last = e
            if attempt < 3:
                time.sleep((2 ** attempt) + random.random())
    raise last or RuntimeError("request failed")


def save_static(url: str, filename: str) -> bytes:
    path = OUT / filename
    if path.exists() and path.stat().st_size > 0:
        return path.read_bytes()
    r = get(url)
    data = r.content
    path.write_bytes(data)
    record({"source": "jsake", "url": url, "file": filename,
            "status": r.status_code, "bytes": len(data),
            "sha256": hashlib.sha256(data).hexdigest(),
            "content_type": r.headers.get("content-type")})
    return data


def page_name(index: int, url: str) -> str:
    digest = hashlib.sha1(url.encode("utf-8")).hexdigest()[:10]
    return f"page_{index:05d}_{digest}.html"


def scan(url: str, filename: str, data: bytes) -> None:
    text = data.decode("utf-8", errors="ignore").lower()
    hits = [p for p in PATTERNS if p.lower() in text]
    if hits:
        with LOCK, (OUT / "potential_prompt_injection.jsonl").open("a", encoding="utf-8") as f:
            f.write(json.dumps({"source": "jsake", "url": url,
                                "file": filename, "patterns": hits,
                                "detected_at": now()}, ensure_ascii=False) + "\n")


def fetch_page(index: int, url: str) -> tuple[bool, int]:
    filename = page_name(index, url)
    path = OUT / filename
    if path.exists() and path.stat().st_size > 0:
        return True, path.stat().st_size
    time.sleep(random.uniform(0.02, 0.10))
    r = get(url)
    data = r.content
    path.write_bytes(data)
    record({"source": "jsake", "url": url, "file": filename,
            "status": r.status_code, "sitemap_index": index,
            "bytes": len(data), "sha256": hashlib.sha256(data).hexdigest(),
            "content_type": r.headers.get("content-type")})
    scan(url, filename, data)
    return r.status_code < 400, len(data)


def sitemap_urls(data: bytes) -> list[str]:
    root = ET.fromstring(data)
    return [e.text.strip() for e in root.iter()
            if e.tag.endswith("loc") and e.text]


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    save_static(BASE + "/robots.txt", "robots.txt")
    data = save_static(SITEMAP, "sitemap.xml")
    urls = sitemap_urls(data)
    (OUT / "urls.txt").write_text("\n".join(urls) + "\n", encoding="utf-8")
    log(f"sitemap URLs={len(urls)}")
    ok = 0
    failures = []
    with cf.ThreadPoolExecutor(max_workers=6) as ex:
        futures = {ex.submit(fetch_page, i, u): (i, u)
                   for i, u in enumerate(urls, 1)}
        for n, fut in enumerate(cf.as_completed(futures), 1):
            i, u = futures[fut]
            try:
                success, _ = fut.result()
                ok += int(success)
                if not success:
                    failures.append({"index": i, "url": u, "error": "HTTP error"})
            except Exception as e:
                failures.append({"index": i, "url": u, "error": repr(e)})
            if n % 250 == 0 or n == len(urls):
                log(f"{n}/{len(urls)} complete; ok={ok} failed={len(failures)}")
    (OUT / "failures.json").write_text(
        json.dumps(failures, ensure_ascii=False, indent=2), encoding="utf-8")
    summary = {"source": "jsake", "url_count": len(urls), "ok": ok,
               "failed": len(failures), "generated_at": now()}
    (OUT / "summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    log(f"finished ok={ok} failed={len(failures)}")


if __name__ == "__main__":
    main()
