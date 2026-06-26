#!/usr/bin/env bash
# =============================================================================
# daily-loop.sh  ―  Layer 3 フル自動化ループ（oh-my-opencode 統合版）
#
# crontab への登録例（毎朝 07:00）:
#   0 7 * * * cd ~/second-brain && bash bin/daily-loop.sh --auto >> /tmp/sb.log 2>&1
#
# 動作モード:
#   --auto      Step1〜2 をスクリプト実行 + デイリー通知（推奨・安定）
#   --full      Step1〜2 + opencode run --agent orchestrator で Step3 も自動実行
#   --dry-run   スコアリングのみ。変更・通知なし
# =============================================================================

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
TS="[$(date '+%Y-%m-%d %H:%M:%S')]"
MODE="${1:---auto}"

echo "$TS daily-loop 開始  mode=$MODE"
cd "$ROOT_DIR"

# ── Step 1: スコアリング ────────────────────────────────────────
echo "$TS Step 1: score-issues.py"
if ! python3 tools/score-issues.py; then
  echo "$TS ERROR: スコアリング失敗"
  python3 tools/notify.py --event custom \
    --title "⛔ Second Brain エラー" \
    --detail "daily-loop: score-issues.py が失敗しました" 2>/dev/null || true
  exit 1
fi

# ── Step 2: ブロッカー判定 ──────────────────────────────────────
echo "$TS Step 2: check-blockers.py"
python3 tools/check-blockers.py

# Top Issue を取得
TOP_ISSUE=$(python3 - <<'PY'
import json
from pathlib import Path
p = Path("tools/.cache/priority-cache.json")
if p.exists():
    d = json.loads(p.read_text())
    issues = d.get("issues", [])
    if issues:
        i = issues[0]
        print(f"#{i['id']} {i['title'][:28]} (score={i['score']})")
        exit()
print("（Issueなし）")
PY
)

# ── dry-run はここで終了 ────────────────────────────────────────
[[ "$MODE" == "--dry-run" ]] && {
  echo "$TS DRY-RUN 完了。Top: $TOP_ISSUE"
  exit 0
}

# ── --auto モード：通知のみ ─────────────────────────────────────
if [[ "$MODE" == "--auto" ]]; then
  echo "$TS Step 3a: デイリーサマリー通知"
  python3 tools/notify.py --event daily_summary   2>/dev/null || true
  python3 tools/notify.py --event scored --top "$TOP_ISSUE" 2>/dev/null || true
  echo "$TS 完了。ターミナルで sb-plan または /orchestrate を実行してください。"
  exit 0
fi

# ── --full モード：opencode run --agent orchestrator で Step 3 自動化 ────
if [[ "$MODE" == "--full" ]]; then
  echo "$TS Step 3b: opencode run --agent orchestrator（Layer 3 フル自動化）"

  if ! command -v opencode &>/dev/null; then
    echo "$TS ERROR: opencode コマンドが見つかりません"
    exit 1
  fi

  # スコアと状態をプロンプトに直接埋め込む（コンテキスト短縮のため）
  SCORE_JSON=$(cat tools/.cache/priority-cache.json)
  BLOCK_JSON=$(cat tools/.cache/blocked.json)

  PLAN=$(opencode run --agent orchestrator \
    "以下のJSONを読んで【本日の実行計画】を出力してください。\n\nスコア:\n${SCORE_JSON}\n\nブロッカー:\n${BLOCK_JSON}" \
    2>/dev/null || echo "ERROR: opencode run 失敗")

  echo "$TS 実行計画:"
  echo "$PLAN"

  # 計画をファイルに保存
  echo "$PLAN" > tools/.cache/today-plan.md

  # 通知（計画の最初の3行を本文に）
  PLAN_PREVIEW=$(echo "$PLAN" | head -5 | tr '\n' ' ')
  python3 tools/notify.py --event custom \
    --title "📋 本日の実行計画が完成しました" \
    --detail "$PLAN_PREVIEW" 2>/dev/null || true

  echo "$TS --full 完了。今日の計画: tools/.cache/today-plan.md"
  exit 0
fi

echo "$TS ERROR: 不明なモード: $MODE（--auto / --full / --dry-run）"
exit 1
