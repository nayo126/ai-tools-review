#!/usr/bin/env python3
"""Replace <!-- AFFILIATE_SLOT:keyword --> markers with affiliate cards.
Auto-activates when ~/MONETIZATION_IDS.json has real IDs."""
from __future__ import annotations
import json
import re
import urllib.parse
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
LOG = ROOT / "logs" / "affiliate.log"
LOG.parent.mkdir(exist_ok=True)
BLOG_DIR = ROOT / "site" / "src" / "content" / "blog"
MIDS_PATH = Path.home() / "MONETIZATION_IDS.json"


def log(msg: str) -> None:
    line = f"[{datetime.now().isoformat(timespec='seconds')}] {msg}"
    print(line)
    with LOG.open("a") as f:
        f.write(line + "\n")


def load_ids() -> dict:
    if not MIDS_PATH.exists():
        return {}
    try:
        return json.loads(MIDS_PATH.read_text())
    except Exception as e:
        log(f"load MIDS: {e}")
        return {}


IDS = load_ids()


def _resolve_rakuten_id(platform: str = "ai-tools-review") -> str:
    r = (IDS.get("rakuten_affiliate") or {})
    ids_map = r.get("ids") or {}
    routing = r.get("routing") or {}
    if platform in routing and routing[platform] in ids_map:
        v = ids_map[routing[platform]]
        if v and v != "TODO":
            return v
    v = ids_map.get("main")
    if v and v != "TODO":
        return v
    v = r.get("affiliate_id")
    return v if v and v != "TODO" else ""


RAKUTEN_ID = _resolve_rakuten_id("ai-tools-review")
RAKUTEN_OK = bool(RAKUTEN_ID)
NINJA_TAG = (IDS.get("ninja_admax") or {}).get("ad_tag_html")
NINJA_OK = bool(NINJA_TAG) and NINJA_TAG != "TODO"


def rakuten_link(keyword: str) -> str:
    q = urllib.parse.quote(keyword)
    search = f"https://search.rakuten.co.jp/search/mall/{q}/"
    if RAKUTEN_OK:
        return (
            f"https://hb.afl.rakuten.co.jp/hgc/{RAKUTEN_ID}/?pc="
            + urllib.parse.quote(search, safe="")
            + "&link_type=text&ut=eyJwYWdlIjoiYWZmaWxpYXRlIn0%3D"
        )
    return search


def amazon_link(keyword: str) -> str:
    return f"https://www.amazon.co.jp/s?k={urllib.parse.quote(keyword)}"


def render_card(keyword: str) -> str:
    bits = [
        '\n<aside class="affiliate-card">',
        f'<div class="label">{keyword} に関連する書籍・教材</div>',
        f'<p>「{keyword}」を実践的に学ぶための参考リソース。</p>',
        f'<p><a href="{rakuten_link(keyword)}" target="_blank" rel="sponsored noopener">▶ 楽天市場で「{keyword}」関連を見る</a></p>',
        f'<p><a href="{amazon_link(keyword)}" target="_blank" rel="sponsored noopener">▶ Amazonで「{keyword}」関連を見る</a></p>',
    ]
    if NINJA_OK:
        bits.append(NINJA_TAG)
    bits.append("</aside>\n")
    return "\n".join(bits)


def process_file(path: Path) -> bool:
    text = path.read_text()
    found = list(re.finditer(r"<!--\s*AFFILIATE_SLOT:(.+?)\s*-->", text))
    if not found:
        # auto-insert a default slot near end if review article and no slot present
        return False
    new = text
    for m in reversed(found):
        kw = m.group(1).strip()
        new = new[: m.start()] + render_card(kw) + new[m.end():]
    path.write_text(new)
    log(f"injected {len(found)} slot(s) -> {path.name}")
    return True


def main() -> int:
    log(f"=== affiliate insert (rakuten={RAKUTEN_OK} ninja={NINJA_OK}) ===")
    if not BLOG_DIR.exists():
        log("blog dir missing"); return 1
    last = DATA / "last_written.json"
    files: list[Path] = []
    if last.exists():
        ld = json.loads(last.read_text())
        for rel in ld.get("files", []):
            p = ROOT / rel
            if p.exists():
                files.append(p)
    else:
        files = list(BLOG_DIR.glob("*.md"))
    touched = 0
    for f in files:
        if process_file(f):
            touched += 1
    log(f"done: {touched}/{len(files)} modified")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
