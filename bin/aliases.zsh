# =============================================================================
# aliases.zsh  ―  oh-my-opencode 統合版 CLIエイリアス（WSL2 / macOS / Linux）
#
# 使い方:
#   source ~/second-brain/bin/aliases.zsh
#   または ~/.zshrc / ~/.bashrc に以下を追加：
#   [ -f ~/second-brain/bin/aliases.zsh ] && source ~/second-brain/bin/aliases.zsh
# =============================================================================

SECOND_BRAIN_DIR="${SECOND_BRAIN_DIR:-$HOME/second-brain}"

# ── 基本エイリアス ────────────────────────────────────────────────
alias oc='opencode'
alias octl='cd "$SECOND_BRAIN_DIR" && opencode'      # TUI を second-brain から起動

# ── エージェント別 CLI ─────────────────────────────────────────────
# oh-my-opencode の aliases.zsh 準拠
alias ocs='cd "$SECOND_BRAIN_DIR" && opencode run --agent sisyphus'      # 統括オーケストレーター
alias ocp='cd "$SECOND_BRAIN_DIR" && opencode run --agent pm'            # 壁打ちPM
alias oco='cd "$SECOND_BRAIN_DIR" && opencode run --agent orchestrator'  # 優先度計画
alias ocx='cd "$SECOND_BRAIN_DIR" && opencode run --agent executor'      # Issue実行
alias ocb='cd "$SECOND_BRAIN_DIR" && opencode run --agent coder'         # 実装・コード

# ── ショートカット ────────────────────────────────────────────────
alias sb-plan='cd "$SECOND_BRAIN_DIR" && opencode run --agent orchestrator "/orchestrate"'
alias sb-status='cd "$SECOND_BRAIN_DIR" && opencode run --agent sisyphus "/status"'
alias sb-score='cd "$SECOND_BRAIN_DIR" && python3 tools/score-issues.py'
alias sb-check='cd "$SECOND_BRAIN_DIR" && python3 tools/check-blockers.py'

# ── 使い方表示 ────────────────────────────────────────────────────
alias sb-help='cat << "HELP"
Second Brain CLI エイリアス（oh-my-opencode 統合版）

  octl              TUI を second-brain ルートから起動
  ocs "<指示>"      Sisyphus（全体統括）に投げる
  ocp "<指示>"      PM エージェントに直接投げる
  oco "<指示>"      Orchestrator に直接投げる
  ocx "<指示>"      Executor に直接投げる
  ocb "<指示>"      Coder に直接投げる

  sb-plan           /orchestrate を実行（今日の優先度計画）
  sb-status         /status を実行（全体俯瞰）
  sb-score          score-issues.py を実行
  sb-check          check-blockers.py を実行

TUI 内スラッシュコマンド:
  /new-proj <name>  新規プロジェクト発足
  /orchestrate      今日の実行計画を提示
  /work <id>        指定 Issue を実行
  /ask "<依頼>"     Sisyphus 経由で振り分け
  /status           全体状態を俯瞰
HELP'
