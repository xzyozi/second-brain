#!/usr/bin/env bash
# =============================================================================
# install-hooks.sh  ―  git hooks のインストール
# git commit で tasks.md の [x] 完了行を検出して自動通知する
#
# 使い方: bash bin/install-hooks.sh
# =============================================================================

set -euo pipefail
ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
HOOK_DIR="$ROOT_DIR/.git/hooks"

if [[ ! -d "$ROOT_DIR/.git" ]]; then
  echo "ERROR: $ROOT_DIR は git リポジトリではありません。先に git init を実行してください。"
  exit 1
fi

mkdir -p "$HOOK_DIR"

# ── post-commit hook を生成 ──────────────────────────────────────
cat > "$HOOK_DIR/post-commit" << 'HOOK_EOF'
#!/usr/bin/env bash
# Second Brain post-commit hook
# tasks.md で新たに [x] になった行を検出して通知する

ROOT_DIR="$(git rev-parse --show-toplevel)"
cd "$ROOT_DIR"

# 直前のコミットとの差分から [x] に変わった行を取得
DONE_TASKS=$(git diff HEAD~1 HEAD -- "**/tasks.md" 2>/dev/null \
  | grep '^+' \
  | grep '\[x\]' \
  | sed 's/^+- \[x\] //' \
  | sed 's/<!--.*-->//' \
  | tr -s ' ' \
  | head -3)

if [[ -n "$DONE_TASKS" ]]; then
  while IFS= read -r task; do
    [[ -z "$task" ]] && continue
    echo "[post-commit] タスク完了を検出: $task"
    python3 tools/notify.py \
      --event task_done \
      --issue "?" \
      --title "$task" 2>/dev/null || true
  done <<< "$DONE_TASKS"
fi
HOOK_EOF

chmod +x "$HOOK_DIR/post-commit"
echo "✅ post-commit hook をインストールしました: $HOOK_DIR/post-commit"
echo "   tasks.md の [ ] を [x] にして git commit すると自動通知が届きます。"
