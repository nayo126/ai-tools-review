#!/usr/bin/env python3
"""Pick N AI tool review topics for today, avoiding past ones."""
from __future__ import annotations
import json
import random
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
LOG = ROOT / "logs" / "topic.log"
LOG.parent.mkdir(exist_ok=True)

CONFIG = json.loads((ROOT / "config.json").read_text())
DB = json.loads((DATA / "tools_db.json").read_text())
HIST_PATH = DATA / "used_topics.json"


def log(msg: str) -> None:
    line = f"[{datetime.now().isoformat(timespec='seconds')}] {msg}"
    print(line)
    with LOG.open("a") as f:
        f.write(line + "\n")


def load_history() -> set[str]:
    if HIST_PATH.exists():
        try:
            return set(json.loads(HIST_PATH.read_text()))
        except Exception:
            return set()
    return set()


def save_history(used: set[str]) -> None:
    HIST_PATH.write_text(json.dumps(sorted(used), ensure_ascii=False, indent=2))


def build_pool() -> list[dict]:
    tools = DB["tools"]
    pool: list[dict] = []
    # Single review per tool
    for t in tools:
        pool.append({
            "type": "single_review",
            "category": t["category"],
            "key": f"single::{t['name']}",
            "title_hint": f"{t['name']}徹底レビュー 料金・機能・使い方・評判",
            "tool": t,
        })
    # Vs comparisons within same category
    by_cat: dict[str, list[dict]] = {}
    for t in tools:
        by_cat.setdefault(t["category"], []).append(t)
    for cat, lst in by_cat.items():
        for i in range(len(lst)):
            for j in range(i + 1, len(lst)):
                a, b = lst[i]["name"], lst[j]["name"]
                pool.append({
                    "type": "vs_comparison",
                    "category": cat,
                    "key": f"vs::{a}::{b}",
                    "title_hint": f"{a} vs {b} 徹底比較 どっちが高校生におすすめ?",
                    "tools": [lst[i], lst[j]],
                })
    # Category roundups
    for cat, lst in by_cat.items():
        if len(lst) >= 3:
            pool.append({
                "type": "category_roundup",
                "category": cat,
                "key": f"roundup::{cat}",
                "title_hint": f"【2026最新】{cat}おすすめ{min(7, len(lst))}選 用途別の選び方",
                "tools": lst,
            })
    # Buying guide
    for cat in by_cat.keys():
        pool.append({
            "type": "buying_guide",
            "category": cat,
            "key": f"guide::{cat}",
            "title_hint": f"{cat}の選び方完全ガイド 失敗しない7つの基準",
            "tools": by_cat[cat],
        })
    return pool


def pick(n: int) -> list[dict]:
    used = load_history()
    pool = build_pool()
    fresh = [p for p in pool if p["key"] not in used]
    if not fresh:
        log("topic pool exhausted; resetting history")
        used = set()
        fresh = pool
    random.shuffle(fresh)
    # spread types so we don't generate 5 reviews back-to-back
    chosen: list[dict] = []
    types_taken: set[str] = set()
    for p in fresh:
        if p["type"] in types_taken and len(chosen) < n:
            continue
        chosen.append(p)
        types_taken.add(p["type"])
        if len(chosen) >= n:
            break
    if len(chosen) < n:
        for p in fresh:
            if p not in chosen:
                chosen.append(p)
                if len(chosen) >= n:
                    break
    for c in chosen:
        used.add(c["key"])
    save_history(used)
    return chosen[:n]


def main() -> int:
    n = CONFIG.get("articles_per_run", 2)
    if len(sys.argv) > 1:
        try:
            n = int(sys.argv[1])
        except ValueError:
            pass
    chosen = pick(n)
    out = {
        "picked_at": datetime.now(timezone.utc).isoformat(),
        "count": len(chosen),
        "items": chosen,
    }
    (DATA / "today_topics.json").write_text(json.dumps(out, ensure_ascii=False, indent=2))
    log(f"picked {len(chosen)} topics -> data/today_topics.json")
    for c in chosen:
        log(f"  [{c['type']}] {c['title_hint']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
