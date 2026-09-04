from __future__ import annotations

import concurrent.futures as cf
import hashlib
import json
import random
import threading
import time
from datetime import datetime, timezone
from pathlib import Path

import requests

OUT = Path(__file__).resolve().parent.parent / "sake_suggest"
MANIFEST = OUT / "api_manifest.jsonl"
LOG = OUT / "api_collection.log"
LOCK = threading.Lock()
BASE = "https://sake-suggest.com/api/sakes?mode=and&sort=relevance&page={}"
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) sake-saijo-db/0.1"


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


def log(msg: str) -> None:
    line = f"[{now()}] {msg}"
    print(line, flush=True)
    with LOCK, LOG.open("a", encoding="utf-8") as f:
        f.write(line + "\n")


def fetch_page(page: int) -> tuple[int, int, int]:
    path = OUT / f"sake_suggest_ui_api_page_{page:03d}.json"
    if path.exists() and path.stat().st_size > 20:
        try:
            obj = json.loads(path.read_text(encoding="utf-8"))
            if obj.get("ok") is True and obj.get("page") == page:
                return page, len(obj.get("sakes", [])), path.stat().st_size
        except Exception:
            pass
    url = BASE.format(page)
    last = None
    for attempt in range(4):
        try:
            r = requests.get(url, headers={"User-Agent": UA}, timeout=(10, 45))
            data = r.content
            if r.status_code == 200:
                obj = r.json()
                if obj.get("ok") is not True or obj.get("page") != page:
                    raise RuntimeError(f"unexpected payload page={page}")
                path.write_bytes(data)
                item = {"source": "sake_suggest", "url": url, "file": path.name,
                        "status": r.status_code, "page": page,
                        "items": len(obj.get("sakes", [])), "bytes": len(data),
                        "sha256": hashlib.sha256(data).hexdigest(), "collected_at": now()}
                with LOCK, MANIFEST.open("a", encoding="utf-8") as f:
                    f.write(json.dumps(item, ensure_ascii=False) + "\n")
                return page, item["items"], item["bytes"]
            last = RuntimeError(f"HTTP {r.status_code}")
        except Exception as e:
            last = e
        time.sleep((2 ** attempt) + random.random())
    raise last or RuntimeError(f"failed page {page}")


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    first = requests.get(BASE.format(1), headers={"User-Agent": UA}, timeout=(10, 45)).json()
    total_pages = int(first["totalPages"])
    expected_total = int(first["total"])
    results = []
    failures = []
    with cf.ThreadPoolExecutor(max_workers=4) as ex:
        futures = {ex.submit(fetch_page, p): p for p in range(1, total_pages + 1)}
        for n, fut in enumerate(cf.as_completed(futures), 1):
            p = futures[fut]
            try:
                results.append(fut.result())
            except Exception as e:
                failures.append({"page": p, "error": repr(e)})
            if n % 25 == 0 or n == total_pages:
                log(f"{n}/{total_pages} pages checked; failures={len(failures)}")
    total_items = sum(x[1] for x in results)
    summary = {"source": "sake_suggest", "total_pages": total_pages,
               "expected_total": expected_total, "items_across_pages": total_items,
               "failures": failures, "generated_at": now()}
    (OUT / "api_summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    log(f"finished pages={len(results)}/{total_pages} items={total_items} expected={expected_total}")


if __name__ == "__main__":
    main()
