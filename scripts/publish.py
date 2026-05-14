#!/usr/bin/env python3
"""Build Astro site and commit+push."""
from __future__ import annotations
import json
import subprocess
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
LOG = ROOT / "logs" / "publish.log"
LOG.parent.mkdir(exist_ok=True)
CONFIG = json.loads((ROOT / "config.json").read_text())
SITE = ROOT / "site"


def log(msg: str) -> None:
    line = f"[{datetime.now().isoformat(timespec='seconds')}] {msg}"
    print(line)
    with LOG.open("a") as f:
        f.write(line + "\n")


def run(cmd: list[str], cwd: Path) -> tuple[int, str, str]:
    p = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, timeout=900)
    return p.returncode, p.stdout, p.stderr


def is_git_repo() -> bool:
    rc, _, _ = run(["git", "rev-parse", "--git-dir"], ROOT)
    return rc == 0


def ensure_git_setup() -> None:
    if not is_git_repo():
        log("initializing git repo")
        run(["git", "init", "-b", CONFIG["git"]["branch"]], ROOT)
    cfg = CONFIG["git"]
    run(["git", "config", "user.name", cfg["user_name"]], ROOT)
    run(["git", "config", "user.email", cfg["user_email"]], ROOT)


def commit_and_push() -> bool:
    ensure_git_setup()
    run(["git", "add",
         "site/src/content/blog", "site/src/pages", "site/src/layouts",
         "site/astro.config.mjs", "site/src/content.config.ts",
         "data/last_written.json", "data/used_topics.json",
         "data/today_topics.json", "data/tools_db.json"], ROOT)
    rc, out, _ = run(["git", "status", "--porcelain"], ROOT)
    if not out.strip():
        log("nothing to commit")
        return False
    today = datetime.now().strftime("%Y-%m-%d")
    last = DATA / "last_written.json"
    msg = f"chore(review): auto-post {today}"
    if last.exists():
        ld = json.loads(last.read_text())
        msg += f" ({ld.get('count', 0)} articles)"
    rc, out, err = run(["git", "commit", "-m", msg], ROOT)
    if rc != 0:
        log(f"commit failed: {err}")
        return False
    log(f"committed: {msg}")
    rc, remotes, _ = run(["git", "remote"], ROOT)
    if CONFIG["git"]["remote"] in remotes:
        rc, _, err = run(["git", "push", CONFIG["git"]["remote"], CONFIG["git"]["branch"]], ROOT)
        if rc != 0:
            log(f"push failed: {err}")
            return False
        log("pushed to remote")
    else:
        log("no remote configured; skipping push")
    return True


def build_site() -> bool:
    rc, out, err = run(["npm", "run", "build"], SITE)
    tail = "\n".join((out + err).splitlines()[-10:])
    log(f"build rc={rc}\n{tail}")
    return rc == 0


def main() -> int:
    if not SITE.exists():
        log("no site dir")
        return 1
    if not build_site():
        log("build failed; aborting publish")
        return 2
    commit_and_push()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
