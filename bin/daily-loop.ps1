# =============================================================================
# daily-loop.ps1  ―  Layer 3 フル自動化ループ（Windows / oh-my-opencode 統合版）
# =============================================================================

param(
    [string]$Mode = "auto",
    [string]$WslDistro = "Ubuntu"
)

$ErrorActionPreference = "Stop"
$RootDir   = Split-Path -Parent $PSScriptRoot
$WslPath   = ($RootDir -replace "^([A-Za-z]):\\", '/mnt/$1/') -replace "\\", "/"
$WslPath   = $WslPath.Substring(0,6).ToLower() + $WslPath.Substring(6)
$LogFile   = "$env:TEMP\second-brain-daily.log"
$TS        = Get-Date -Format "yyyy-MM-dd HH:mm:ss"

function Write-Log($msg) {
    $line = "[$TS] $msg"
    Write-Host $line
    Add-Content -Path $LogFile -Value $line -Encoding UTF8
}

function Show-Toast($title, $body) {
    Add-Type -AssemblyName System.Windows.Forms
    $n = New-Object System.Windows.Forms.NotifyIcon
    $n.Icon    = [System.Drawing.SystemIcons]::Information
    $n.Visible = $true
    $n.ShowBalloonTip(7000, $title, $body, [System.Windows.Forms.ToolTipIcon]::Info)
    Start-Sleep 4
    $n.Dispose()
}

Write-Log "daily-loop.ps1 開始  mode=$Mode  wsl_path=$WslPath"

# Step 1: スコアリング
Write-Log "Step 1: score-issues.py"
$out = wsl -d $WslDistro -e bash -c "cd '$WslPath' && python3 tools/score-issues.py 2>&1"
Write-Log $out
if ($LASTEXITCODE -ne 0) {
    Show-Toast "⛔ Second Brain エラー" "score-issues.py が失敗しました"
    exit 1
}

# Step 2: ブロッカー判定
Write-Log "Step 2: check-blockers.py"
wsl -d $WslDistro -e bash -c "cd '$WslPath' && python3 tools/check-blockers.py 2>&1" | Write-Log

if ($Mode -eq "dry-run") { Write-Log "DRY-RUN 完了"; exit 0 }

# Top Issue 取得
$TopIssue = wsl -d $WslDistro -e bash -c @"
cd '$WslPath' && python3 - <<'PY'
import json
from pathlib import Path
p = Path('tools/.cache/priority-cache.json')
if p.exists():
    d = json.loads(p.read_text())
    issues = d.get('issues', [])
    if issues:
        i = issues[0]
        print(f"#{i['id']} [{i.get('project', 'core')}] {i['title'][:28]} (score={i['score']})")
        exit()
print('（Issueなし）')
PY
"@

# --auto: 通知のみ
if ($Mode -eq "auto") {
    Write-Log "Step 3a: Windows Toast 通知"
    Show-Toast "🧠 Second Brain デイリーサマリー" "本日の第1位: $TopIssue`nターミナルで sb-plan を実行してください。"
    Write-Log "完了"
    exit 0
}

# --full: opencode run --agent orchestrator で自動計画生成
if ($Mode -eq "full") {
    Write-Log "Step 3b: opencode run --agent orchestrator（フル自動化）"
    $PlanOutput = wsl -d $WslDistro -e bash -c @"
cd '$WslPath'
SCORE=\$(cat tools/.cache/priority-cache.json)
BLOCK=\$(cat tools/.cache/blocked.json)
opencode run --agent orchestrator "以下のJSONを読んで【本日の実行計画】を出力してください。スコア: \${SCORE} ブロッカー: \${BLOCK}" 2>/dev/null
"@
    Write-Log "実行計画: $PlanOutput"
    $PlanOutput | Out-File "$RootDir\tools\.cache\today-plan.md" -Encoding UTF8
    $Preview = ($PlanOutput -split "`n" | Select-Object -First 4) -join " "
    Show-Toast "📋 本日の実行計画が完成しました" $Preview
    Write-Log "--full 完了"
    exit 0
}

Write-Log "ERROR: 不明なモード: $Mode（auto / full / dry-run）"
exit 1
