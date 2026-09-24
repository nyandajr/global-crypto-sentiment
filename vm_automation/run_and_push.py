"""VM-side automation entry point -- run from the VM's own crontab every 3
minutes (~480 runs/day), not GitHub Actions -- same reasoning as every
other tracker in this portfolio (schedule triggers deliver a fraction of
their configured cadence for sub-hourly jobs), doubly true at this
cadence.
"""

import os
import subprocess
import sys
from pathlib import Path

from dotenv import load_dotenv

REPO_DIR = Path(__file__).resolve().parent.parent
SRC_DIR = REPO_DIR / "src"
DATA_FILES = ["data/sentiment_history.csv", "data/state.json", "docs/data.json"]

sys.path.insert(0, str(SRC_DIR))
load_dotenv(REPO_DIR / ".env")  # populates GITHUB_TOKEN for pushing on the VM


def run(*args, check=True):
    return subprocess.run(list(args), cwd=str(REPO_DIR), check=check)


def sync_with_remote():
    # --hard, not --soft, and BEFORE the pipeline runs -- reset --soft only
    # moves HEAD, leaving stale index entries for any file this script
    # doesn't explicitly `git add`, which then get silently recommitted on
    # the next force-push. Learned this the hard way on hormuz-strait-monitor.
    run("git", "fetch", "origin", "main")
    run("git", "reset", "--hard", "origin/main")


def build_commit_message(row):
    if row is None:
        return None
    direction = "bullish" if row["sentiment_index"] > 0 else "bearish" if row["sentiment_index"] < 0 else "neutral"
    return (
        f"data: crypto sentiment {direction} {row['sentiment_index']} "
        f"| BTC ${row['btc_price']:,} ({row['btc_change_24h']:+}%) "
        f"| top: {row['top_gainer']} {row['top_gainer_pct']:+}%"
    )


def git_commit_and_push(row):
    # freddynyanda@proton.me is Fred's real, verified GitHub email -- same
    # standardization as every other tracker in this portfolio.
    run("git", "config", "user.name", "nyandajr")
    run("git", "config", "user.email", "freddynyanda@proton.me")
    run("git", "add", *DATA_FILES, check=False)

    diff = run("git", "diff", "--cached", "--quiet", check=False)
    if diff.returncode == 0:
        print("[run_and_push] no changes to commit")
        return

    message = build_commit_message(row)
    if message is None:
        print("[run_and_push] pipeline produced no row, skipping commit")
        return
    run("git", "commit", "-m", message)

    # On the VM this pushes via an authenticated URL built from the .env
    # token at push time (not stored in git config) since the VM's
    # remotes use HTTPS+PAT, not a local SSH key. Locally, origin is
    # already an SSH remote, so GITHUB_TOKEN is unset and this falls back
    # to the stored remote's own credentials.
    token = os.environ.get("GITHUB_TOKEN")
    if token:
        push_url = f"https://{token}@github.com/nyandajr/global-crypto-sentiment.git"
        run("git", "push", "--force", push_url, "HEAD:main")
    else:
        run("git", "push", "--force", "origin", "HEAD:main")


def main():
    sync_with_remote()

    import pipeline
    row = pipeline.run()

    git_commit_and_push(row)
    print("[run_and_push] done")


if __name__ == "__main__":
    main()
