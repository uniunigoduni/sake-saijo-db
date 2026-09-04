from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from playwright.sync_api import sync_playwright

HERE = Path(__file__).resolve().parent
EDGE = r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"
MANIFEST = HERE / "sake_suggest_browser_manifest.jsonl"
INJECTION = HERE / "potential_prompt_injection.jsonl"
PATTERNS = [
    "ignore previous instructions", "ignore all previous instructions",
    "system prompt", "developer message", "prompt injection",
    "以前の指示を無視", "上の指示を無視", "システムプロンプト",
]


def now() -> str:
    return datetime.now(timezone.utc).isoformat()

def append_manifest(item: dict) -> None:
    item.setdefault("collected_at", now())
    with MANIFEST.open("a", encoding="utf-8") as f:
        f.write(json.dumps(item, ensure_ascii=False) + "\n")


def scan(source_url: str, filename: str, data: bytes) -> None:
    text = data.decode("utf-8", errors="ignore").lower()
    hits = [p for p in PATTERNS if p.lower() in text]
    if not hits:
        return
    with INJECTION.open("a", encoding="utf-8") as f:
        f.write(json.dumps({
            "source": "sake_suggest", "url": source_url,
            "file": filename, "patterns": hits, "detected_at": now(),
        }, ensure_ascii=False) + "\n")


def save_bytes(filename: str, url: str, data: bytes, kind: str, page_num: int) -> None:
    path = HERE / filename
    path.write_bytes(data)
    append_manifest({
        "source": "sake_suggest", "url": url, "file": filename,
        "kind": kind, "page": page_num, "bytes": len(data),
        "sha256": hashlib.sha256(data).hexdigest(),
    })
    scan(url, filename, data)

def save_rendered(page, page_num: int) -> None:
    data = page.content().encode("utf-8")
    save_bytes(
        f"sake_suggest_ui_page_{page_num:03d}.html",
        page.url, data, "rendered_html", page_num,
    )


def save_api(response, page_num: int) -> None:
    data = response.body()
    save_bytes(
        f"sake_suggest_ui_api_page_{page_num:03d}.json",
        response.url, data, "browser_api_response", page_num,
    )


def wait_page(page, page_num: int, total_pages: int) -> None:
    page.get_by_text(f"{page_num} / {total_pages}", exact=True).wait_for(timeout=30000)


def click_and_capture(page, button_text: str, target_page: int, total_pages: int, responses):
    before = len(responses)
    page.get_by_role("button", name=button_text, exact=True).click()
    wait_page(page, target_page, total_pages)
    page.wait_for_timeout(800)
    candidates = [r for r in responses[before:] if f"page={target_page}" in r.url]
    if not candidates:
        page.wait_for_timeout(2500)
        candidates = [r for r in responses[before:] if f"page={target_page}" in r.url]
    if not candidates:
        raise RuntimeError(f"API response not captured for page {target_page}")
    save_api(candidates[-1], target_page)
    save_rendered(page, target_page)
    return candidates[-1]


def main() -> None:
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True, executable_path=EDGE)
        context = browser.new_context(locale="ja-JP")
        page = context.new_page()
        api_responses = []
        page.on("response", lambda r: api_responses.append(r) if "/api/sakes?" in r.url else None)
        def route_handler(route):
            req = route.request
            u = req.url
            if ("/sake/" in u and "_rsc=" in u) or "google-analytics.com" in u or "googlesyndication.com" in u or req.resource_type in {"image", "font", "media"}:
                route.abort()
            else:
                route.continue_()
        page.route("**/*", route_handler)
        page.goto("https://sake-suggest.com/", wait_until="domcontentloaded", timeout=60000)
        page.get_by_role("button", name="次へ", exact=True).wait_for(timeout=30000)
        text = page.locator("main").inner_text()
        marker = next(line for line in text.splitlines() if " / " in line and line.split(" / ")[0].isdigit())
        total_pages = int(marker.split(" / ")[1])
        save_rendered(page, 1)
        print(f"total_pages={total_pages}", flush=True)

        click_and_capture(page, "次へ", 2, total_pages, api_responses)
        click_and_capture(page, "前へ", 1, total_pages, api_responses)
        click_and_capture(page, "次へ", 2, total_pages, api_responses)

        for target in range(3, total_pages + 1):
            api_path = HERE / f"sake_suggest_ui_api_page_{target:03d}.json"
            html_path = HERE / f"sake_suggest_ui_page_{target:03d}.html"
            if api_path.exists() and html_path.exists():
                click_and_capture(page, "次へ", target, total_pages, api_responses)
            else:
                click_and_capture(page, "次へ", target, total_pages, api_responses)
            if target % 10 == 0 or target == total_pages:
                print(f"page {target}/{total_pages}", flush=True)
        browser.close()


if __name__ == "__main__":
    main()
