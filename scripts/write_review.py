#!/usr/bin/env python3
"""Generate AI tool review articles via claude CLI."""
from __future__ import annotations
import json
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
LOG = ROOT / "logs" / "writer.log"
LOG.parent.mkdir(exist_ok=True)

CONFIG = json.loads((ROOT / "config.json").read_text())
OUT_DIR = ROOT / "site" / "src" / "content" / "blog"
OUT_DIR.mkdir(parents=True, exist_ok=True)

sys.path.insert(0, str(ROOT / "scripts"))
from prompts import SYSTEM_RULES, SINGLE_REVIEW, VS_COMPARISON, CATEGORY_ROUNDUP, BUYING_GUIDE


def log(msg: str) -> None:
    line = f"[{datetime.now().isoformat(timespec='seconds')}] {msg}"
    print(line)
    with LOG.open("a") as f:
        f.write(line + "\n")


def call_claude(prompt: str, retries: int = 2) -> str:
    cli = CONFIG.get("claude_cli", "claude")
    for attempt in range(retries + 1):
        try:
            r = subprocess.run(
                [cli, "-p", prompt, "--output-format", "text"],
                capture_output=True, text=True, timeout=600,
            )
            if r.returncode == 0 and r.stdout.strip():
                return r.stdout.strip()
            log(f"claude attempt {attempt+1} rc={r.returncode} err={r.stderr[:200]}")
        except subprocess.TimeoutExpired:
            log(f"claude attempt {attempt+1} timed out")
        except Exception as e:
            log(f"claude attempt {attempt+1} error: {e}")
    return ""


def slugify(text: str) -> str:
    text = re.sub(r"[^\w\s-]", "", text, flags=re.UNICODE)
    text = re.sub(r"\s+", "-", text.strip())
    return text.lower()[:60]


def parse_frontmatter(md: str) -> tuple[dict, str]:
    if not md.startswith("---"):
        return {}, md
    m = re.match(r"^---\s*\n(.*?)\n---\s*\n(.*)$", md, re.DOTALL)
    if not m:
        return {}, md
    body = m.group(2)
    fm: dict = {}
    for line in m.group(1).splitlines():
        if ":" not in line:
            continue
        k, v = line.split(":", 1)
        fm[k.strip()] = v.strip().strip('"').strip("'")
    return fm, body


def looks_valid(md: str) -> tuple[bool, str]:
    if not md.startswith("---"):
        return False, "no frontmatter"
    fm, body = parse_frontmatter(md)
    if not fm.get("title"):
        return False, "no title"
    char_count = len(body.replace(" ", "").replace("\n", ""))
    if char_count < CONFIG.get("min_words", 2000):
        return False, f"too short ({char_count} chars)"
    for bad in CONFIG.get("publish_filter", {}).get("ban_words", []):
        if bad in body:
            return False, f"contains banned word: {bad}"
    return True, "ok"


def build_prompt(topic: dict) -> str:
    today = datetime.now().strftime("%Y-%m-%d")
    t = topic["type"]
    if t == "single_review":
        tool = topic["tool"]
        block = SINGLE_REVIEW.format(
            name=tool["name"], vendor=tool["vendor"], category=tool["category"],
            price_jpy=tool["price_jpy"], url=tool["url"], tagline=tool["tagline"],
            best_for=tool["best_for"],
        )
    elif t == "vs_comparison":
        a, b = topic["tools"][0], topic["tools"][1]
        block = VS_COMPARISON.format(
            category=topic["category"],
            a_name=a["name"], a_vendor=a["vendor"], a_price=a["price_jpy"], a_tagline=a["tagline"],
            b_name=b["name"], b_vendor=b["vendor"], b_price=b["price_jpy"], b_tagline=b["tagline"],
        )
    elif t == "category_roundup":
        n = min(7, len(topic["tools"]))
        tools_list = ", ".join(f"{x['name']}({x['vendor']})" for x in topic["tools"][:n])
        block = CATEGORY_ROUNDUP.format(category=topic["category"], n=n, tools_list=tools_list)
    elif t == "buying_guide":
        tools_list = ", ".join(f"{x['name']}" for x in topic["tools"])
        block = BUYING_GUIDE.format(category=topic["category"], tools_list=tools_list)
    else:
        block = f"# 不明なタイプ: {t}"
    closing = f"""

## 今回の記事
- 公開日: {today}
- カテゴリ: {topic.get('category', '')}

上記の構成と共通ルールに従ってMarkdown(frontmatter+本文)のみ出力してください。
"""
    return SYSTEM_RULES + "\n\n" + block + closing


def write_article(topic: dict) -> Path | None:
    log(f"writing: [{topic['type']}] {topic.get('title_hint', '')}")
    prompt = build_prompt(topic)
    raw = call_claude(prompt)
    if not raw:
        log("claude returned empty")
        return None
    raw = re.sub(r"^```(?:markdown|md)?\s*\n", "", raw)
    raw = re.sub(r"\n```\s*$", "", raw)
    ok, why = looks_valid(raw)
    if not ok:
        log(f"rejected: {why}")
        (DATA / f"reject_{slugify(topic['key'])}.md").write_text(raw)
        return None
    fm, _ = parse_frontmatter(raw)
    slug = slugify(fm.get("title") or topic["key"]) or datetime.now().strftime("%Y%m%d-%H%M%S")
    base = slug
    n = 0
    while (OUT_DIR / f"{slug}.md").exists():
        n += 1
        slug = f"{base}-{n}"
    out_path = OUT_DIR / f"{slug}.md"
    out_path.write_text(raw)
    log(f"wrote: {out_path.relative_to(ROOT)}")
    return out_path


def main() -> int:
    today_path = DATA / "today_topics.json"
    if not today_path.exists():
        log("no today_topics.json — run pick_topic first")
        return 1
    today = json.loads(today_path.read_text())
    items = today.get("items", [])
    if not items:
        log("no topics picked")
        return 0
    written: list[str] = []
    for it in items:
        p = write_article(it)
        if p:
            written.append(str(p.relative_to(ROOT)))
    (DATA / "last_written.json").write_text(json.dumps({
        "written_at": datetime.now(timezone.utc).isoformat(),
        "count": len(written),
        "files": written,
    }, ensure_ascii=False, indent=2))
    log(f"wrote {len(written)}/{len(items)} articles")
    return 0 if written else 2


if __name__ == "__main__":
    raise SystemExit(main())
