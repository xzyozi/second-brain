# =============================================================================
# register-task.ps1  ―  Windows タスクスケジューラへの daily-loop 登録
# 管理者 PowerShell で実行すること
# =============================================================================

param(
    [string]$Time = "07:00",
    [string]$TaskName = "SecondBrain-DailyLoop"
)

$ScriptPath = Join-Path $PSScriptRoot "daily-loop.ps1"

if (-not (Test-Path $ScriptPath)) {
    Write-Error "daily-loop.ps1 が見つかりません: $ScriptPath"
    exit 1
}

$action = New-ScheduledTaskAction `
    -Execute "powershell.exe" `
    -Argument "-NonInteractive -ExecutionPolicy Bypass -File `"$ScriptPath`" -Mode auto"

$trigger = New-ScheduledTaskTrigger -Daily -At $Time

$settings = New-ScheduledTaskSettingsSet `
    -ExecutionTimeLimit (New-TimeSpan -Hours 1) `
    -StartWhenAvailable `
    -WakeToRun $false

# 既存タスクがあれば削除
if (Get-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue) {
    Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false
    Write-Host "既存タスクを削除しました: $TaskName"
}

Register-ScheduledTask `
    -TaskName $TaskName `
    -Action $action `
    -Trigger $trigger `
    -Settings $settings `
    -Description "Second Brain 毎日の優先度スコアリングと通知" `
    -RunLevel Limited

Write-Host "✅ タスクスケジューラに登録しました: $TaskName  実行時刻: $Time"
Write-Host "   確認: Get-ScheduledTask -TaskName '$TaskName'"
Write-Host "   手動実行: Start-ScheduledTask -TaskName '$TaskName'"
