from __future__ import annotations

import concurrent.futures as cf
import hashlib
import json
import os
import random
import re
import threading
import time
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse
import xml.etree.ElementTree as ET

import requests

HERE = Path(__file__).resolve().parent
MANIFEST = HERE / "manifest.jsonl"
LOG = HERE / "collection.log"
USER_AGENT = "sake-saijo-db/0.1 archival-collector"
LOCK = threading.Lock()

def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def log(message: str) -> None:
    line = f"[{now_iso()}] {message}"
    print(line, flush=True)
    with LOCK:
        with LOG.open("a", encoding="utf-8") as f:
            f.write(line + "\n")


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def record(**item) -> None:
    item.setdefault("collected_at", now_iso())
    with LOCK:
        with MANIFEST.open("a", encoding="utf-8") as f:
            f.write(json.dumps(item, ensure_ascii=False) + "\n")


def session() -> requests.Session:
    s = requests.Session()
    s.headers.update({"User-Agent": USER_AGENT, "Accept-Encoding": "gzip, deflate"})
    return s

def fetch_bytes(url: str, retries: int = 5, timeout: tuple[int, int] = (15, 90)):
    last = None
    for attempt in range(retries):
        try:
            r = session().get(url, timeout=timeout, allow_redirects=True)
            if r.status_code == 429 or 500 <= r.status_code < 600:
                wait = min(30, 2 ** attempt + random.random())
                log(f"retry {r.status_code} {url} in {wait:.1f}s")
                time.sleep(wait)
                last = RuntimeError(f"HTTP {r.status_code}")
                continue
            return r
        except Exception as e:
            last = e
            if attempt + 1 < retries:
                time.sleep(min(30, 2 ** attempt + random.random()))
    raise last or RuntimeError("fetch failed")


def save_response(source: str, url: str, filename: str) -> Path | None:
    path = HERE / filename
    if path.exists() and path.stat().st_size > 0:
        return path
    try:
        r = fetch_bytes(url)
        data = r.content
        path.write_bytes(data)
        record(source=source, url=url, final_url=r.url, file=filename,
               status=r.status_code, bytes=len(data), sha256=sha256_bytes(data),
               content_type=r.headers.get("content-type"))
        if r.status_code >= 400:
            log(f"HTTP {r.status_code}: {url}")
        return path
    except Exception as e:
        record(source=source, url=url, file=filename, status="error", error=repr(e))
        log(f"ERROR {source} {url}: {e}")
        return None

def flatten_name(prefix: str, member: str) -> str:
    clean = member.replace("\\", "/").strip("/")
    clean = re.sub(r"[^0-9A-Za-z._\-一-龠ぁ-んァ-ン]+", "__", clean)
    return f"{prefix}_repo__{clean}"


def collect_repo(source: str, repo: str, branch: str = "master") -> None:
    owner, name = repo.split("/", 1)
    url = f"https://codeload.github.com/{owner}/{name}/zip/refs/heads/{branch}"
    zip_name = f"{source}_repo_{branch}.zip"
    zpath = save_response(source, url, zip_name)
    if not zpath or not zpath.exists():
        return
    with zipfile.ZipFile(zpath) as zf:
        for info in zf.infolist():
            if info.is_dir():
                continue
            rel = info.filename.split("/", 1)[-1]
            out_name = flatten_name(source, rel)
            out = HERE / out_name
            if out.exists():
                continue
            data = zf.read(info)
            out.write_bytes(data)
            record(source=source, url=url, file=out_name, archive=zip_name,
                   archive_member=info.filename, status="extracted", bytes=len(data),
                   sha256=sha256_bytes(data))
    log(f"repo collected: {source}")


def collect_sake_dataset() -> None:
    collect_repo("sake_dataset", "yoichi1484/sake_dataset")
    sheet_id = "1O46CJxzCWOEK2akm5HRWcs1kK6k-aDStZ_yauIqxyvs"
    save_response("sake_dataset", f"https://docs.google.com/spreadsheets/d/{sheet_id}/export?format=xlsx",
                  "sake_dataset_google_sheet.xlsx")

def collect_sakeopendata() -> None:
    collect_repo("sakeopendata", "Code-for-SAKE/SAKEOpenData")


def collect_sakenowa() -> None:
    base = "https://muro.sakenowa.com/sakenowa-data/api"
    endpoints = [
        "areas", "brands", "breweries", "rankings",
        "flavor-charts", "flavor-tags", "brand-flavor-tags",
    ]
    save_response("sakenowa", "https://muro.sakenowa.com/sakenowa-data/", "sakenowa_api_docs.html")
    for ep in endpoints:
        save_response("sakenowa", f"{base}/{ep}", f"sakenowa_{ep.replace('-', '_')}.json")
    log("API collected: sakenowa")


def parse_sitemap(data: bytes) -> list[str]:
    root = ET.fromstring(data)
    return [e.text.strip() for e in root.iter() if e.tag.endswith("loc") and e.text]


def page_filename(source: str, index: int, url: str) -> str:
    digest = hashlib.sha1(url.encode("utf-8")).hexdigest()[:10]
    suffix = ".html"
    return f"{source}_page_{index:05d}_{digest}{suffix}"

INJECTION_PATTERNS = [
    "ignore previous instructions", "ignore all previous instructions",
    "system prompt", "developer message", "prompt injection",
    "以前の指示を無視", "上の指示を無視", "システムプロンプト",
]


def scan_injection(source: str, url: str, filename: str, data: bytes) -> None:
    try:
        text = data.decode("utf-8", errors="ignore").lower()
    except Exception:
        return
    hits = [p for p in INJECTION_PATTERNS if p.lower() in text]
    if not hits:
        return
    item = {"source": source, "url": url, "file": filename, "patterns": hits,
            "detected_at": now_iso()}
    with LOCK:
        with (HERE / "potential_prompt_injection.jsonl").open("a", encoding="utf-8") as f:
            f.write(json.dumps(item, ensure_ascii=False) + "\n")
    log(f"POTENTIAL PROMPT INJECTION {source} {url}: {hits}")


def fetch_site_page(source: str, index: int, url: str) -> tuple[bool, str]:
    filename = page_filename(source, index, url)
    path = HERE / filename
    if path.exists() and path.stat().st_size > 0:
        return True, "cached"
    try:
        time.sleep(random.uniform(0.03, 0.12))
        r = fetch_bytes(url)
        data = r.content
        path.write_bytes(data)
        record(source=source, url=url, final_url=r.url, file=filename,
               status=r.status_code, bytes=len(data), sha256=sha256_bytes(data),
               content_type=r.headers.get("content-type"), sitemap_index=index)
        scan_injection(source, url, filename, data)
        return r.status_code < 400, str(r.status_code)
    except Exception as e:
        record(source=source, url=url, file=filename, status="error", error=repr(e), sitemap_index=index)
        return False, repr(e)

def collect_sitemap_site(source: str, base: str, sitemap_url: str, workers: int = 6) -> None:
    save_response(source, base.rstrip("/") + "/robots.txt", f"{source}_robots.txt")
    sitemap_name = f"{source}_sitemap.xml"
    spath = save_response(source, sitemap_url, sitemap_name)
    if not spath or not spath.exists():
        return
    urls = parse_sitemap(spath.read_bytes())
    (HERE / f"{source}_urls.txt").write_text("\n".join(urls) + "\n", encoding="utf-8")
    record(source=source, url=sitemap_url, file=f"{source}_urls.txt", status="derived_url_list",
           bytes=(HERE / f"{source}_urls.txt").stat().st_size, url_count=len(urls))
    log(f"{source}: sitemap contains {len(urls)} URLs")
    ok = 0
    failed = []
    with cf.ThreadPoolExecutor(max_workers=workers) as ex:
        futures = {ex.submit(fetch_site_page, source, i, u): (i, u) for i, u in enumerate(urls, 1)}
        for n, fut in enumerate(cf.as_completed(futures), 1):
            i, u = futures[fut]
            try:
                success, detail = fut.result()
            except Exception as e:
                success, detail = False, repr(e)
            ok += int(success)
            if not success:
                failed.append({"index": i, "url": u, "error": detail})
            if n % 250 == 0 or n == len(urls):
                log(f"{source}: {n}/{len(urls)} complete; ok={ok} failed={len(failed)}")
    (HERE / f"{source}_failures.json").write_text(
        json.dumps(failed, ensure_ascii=False, indent=2), encoding="utf-8")
    log(f"{source}: finished ok={ok} failed={len(failed)}")

def write_summary() -> None:
    stats: dict[str, dict[str, int]] = {}
    if MANIFEST.exists():
        for line in MANIFEST.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            try:
                row = json.loads(line)
            except json.JSONDecodeError:
                continue
            src = row.get("source", "unknown")
            s = stats.setdefault(src, {"records": 0, "bytes": 0, "errors": 0})
            s["records"] += 1
            s["bytes"] += int(row.get("bytes") or 0)
            if row.get("status") == "error" or (isinstance(row.get("status"), int) and row["status"] >= 400):
                s["errors"] += 1
    files = [p for p in HERE.iterdir() if p.is_file()]
    summary = {
        "generated_at": now_iso(),
        "folder": str(HERE),
        "file_count": len(files),
        "total_file_bytes": sum(p.stat().st_size for p in files),
        "sources": stats,
    }
    (HERE / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    log("summary written")


def main() -> None:
    log("collection started")
    collect_sake_dataset()
    collect_sakeopendata()
    collect_sakenowa()
    collect_sitemap_site("sake_suggest", "https://sake-suggest.com", "https://sake-suggest.com/sitemap.xml")
    collect_sitemap_site("jsake", "https://jsake.jp", "https://jsake.jp/sitemap.xml")
    write_summary()
    log("collection finished")


if __name__ == "__main__":
    main()
