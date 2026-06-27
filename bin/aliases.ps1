# =============================================================================
# aliases.ps1  ―  oh-my-opencode 統合版 CLIエイリアス（Windows PowerShell版）
#
# 使い方（$PROFILE に追記）:
#   . "$HOME\second-brain\bin\aliases.ps1"
# =============================================================================

$env:SECOND_BRAIN_DIR = "$HOME\second-brain"

function octl  { Set-Location $env:SECOND_BRAIN_DIR; opencode @args }

# エージェント別（WSL2経由）
function ocs   { wsl -e bash -c "cd ~/second-brain && opencode run --agent sisyphus '$args'" }
function ocp   { wsl -e bash -c "cd ~/second-brain && opencode run --agent pm '$args'" }
function oco   { wsl -e bash -c "cd ~/second-brain && opencode run --agent orchestrator '$args'" }
function ocx   { wsl -e bash -c "cd ~/second-brain && opencode run --agent executor '$args'" }
function ocb   { wsl -e bash -c "cd ~/second-brain && opencode run --agent coder '$args'" }

# ショートカット
function sb-plan   { wsl -e bash -c 'cd ~/second-brain && opencode run --agent orchestrator "/orchestrate"' }
function sb-status { wsl -e bash -c 'cd ~/second-brain && opencode run --agent sisyphus "/status"' }
function sb-score  { wsl -e bash -c 'cd ~/second-brain && uv run python tools/score-issues.py' }
function sb-check  { wsl -e bash -c 'cd ~/second-brain && uv run python tools/check-blockers.py' }

function sb-help {
    Write-Host @"
Second Brain CLI エイリアス (PowerShell / oh-my-opencode 統合版)

  octl              TUI を second-brain ルートから起動
  ocs "<指示>"      Sisyphus（全体統括）に投げる
  ocp "<指示>"      PM エージェントに直接投げる
  oco "<指示>"      Orchestrator に直接投げる
  ocx "<指示>"      Executor に直接投げる
  ocb "<指示>"      Coder に直接投げる

  sb-plan           今日の優先度計画を実行
  sb-status         全体状態を俯瞰
  sb-score          score-issues.py を実行
  sb-check          check-blockers.py を実行
"@
}
