#!/bin/zsh
set -euo pipefail
cd /Users/rivierehome/.openclaw/workspace/daily-update-site
python3 generate_daily_site.py >/tmp/daily_update_gen.log 2>&1
git add index.html
if ! git diff --cached --quiet; then
  git commit -m "Daily update refresh $(date '+%Y-%m-%d %H:%M %Z')" >/tmp/daily_update_git.log 2>&1 || true
  git push origin main >/tmp/daily_update_push.log 2>&1 || true
fi
