#!/usr/bin/env python3
"""
notify.py  ―  拡張1: 通知連携プラグイン
タスク完了・ブロッカー検出・スコアリング完了などのイベントを
デスクトップ通知（macOS/Linux）または Slack に送信する。

設定ファイル: tools/.cache/notify-config.json
  {
    "slack_webhook": "https://hooks.slack.com/services/...",  // 省略可
    "slack_channel": "#second-brain",
    "desktop":       true    // macOS: osascript, Linux: notify-send
  }

使い方:
  python3 tools/notify.py --event task_done --issue 12 --title "認証API実装"
  python3 tools/notify.py --event blocker    --issue 15 --detail "B1: 仕様未確定"
  python3 tools/notify.py --event scored     --top "#5 スコア89.4"
  python3 tools/notify.py --event daily_summary
"""

import json
import argparse
import subprocess
import sys
import datetime
import urllib.request
import urllib.error
from pathlib import Path
import os
import logging

# loggerの設定
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger("notify")

CONFIG_PATH  = Path("tools/.cache/notify-config.json")
CACHE_SCORED = Path("tools/.cache/priority-cache.json")
CACHE_BLOCK  = Path("tools/.cache/blocked.json")


# ── 設定読み込み ─────────────────────────────────────────────────
def load_config() -> dict:
    if CONFIG_PATH.exists():
        return json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    # デフォルト（デスクトップ通知のみ）
    return {"desktop": True, "slack_webhook": None}


# ── メッセージ組み立て ─────────────────────────────────────────────
def build_message(event: str, args) -> tuple[str, str]:
    """(title, body) を返す"""
    now = datetime.datetime.now().strftime("%H:%M")

    if event == "task_done":
        title = "✅ タスク完了"
        body  = f"#{args.issue} 「{args.title}」 が完了しました。 ({now})"

    elif event == "blocker":
        title = "⚠️ ブロッカー検出"
        body  = f"#{args.issue} がブロックされました: {args.detail}"

    elif event == "scored":
        title = "📊 優先度スコアリング完了"
        top   = args.top or "（詳細は priority-cache.json 参照）"
        body  = f"本日の第1位: {top}"

    elif event == "daily_summary":
        title = "🧠 Second Brain デイリーサマリー"
        body  = _build_daily_summary()

    elif event == "custom":
        title = args.title or "Second Brain"
        body  = args.detail or ""

    else:
        title = "Second Brain"
        body  = f"イベント: {event}"

    return title, body


def _build_daily_summary() -> str:
    lines = []
    if CACHE_SCORED.exists():
        data   = json.loads(CACHE_SCORED.read_text())
        issues = data.get("issues", [])
        top3   = issues[:3]
        lines.append(f"実行可能 {data.get('total', 0)} 件 / 上位3件:")
        for i in top3:
            lines.append(f"  #{i['id']} {i['title'][:30]} (score={i['score']})")
    if CACHE_BLOCK.exists():
        data = json.loads(CACHE_BLOCK.read_text())
        bc   = data.get("summary", {}).get("blocked_count", 0)
        if bc:
            lines.append(f"ブロック中: {bc} 件")
    return "\n".join(lines) if lines else "スコアデータなし。先に score-issues.py を実行してください。"


# ── デスクトップ通知 ──────────────────────────────────────────────
def is_wsl() -> bool:
    """WSL環境（WSL1またはWSL2）かどうかを判定する"""
    if os.path.exists("/proc/sys/fs/binfmt_misc/WSLInterop"):
        return True
    try:
        with open("/proc/version", "r", encoding="utf-8") as f:
            content = f.read().lower()
            if "microsoft" in content or "wsl" in content:
                return True
    except Exception:
        pass
    return False


# ── デスクトップ通知 ──────────────────────────────────────────────
def notify_desktop(title: str, body: str) -> bool:
    import platform
    plat = platform.system()

    try:
        if plat == "Darwin":
            # macOS
            script = (
                f'display notification "{body}" '
                f'with title "{title}" '
                f'sound name "Glass"'
            )
            subprocess.run(["osascript", "-e", script], check=True, capture_output=True)
            return True

        elif plat == "Linux":
            if is_wsl():
                return notify_desktop_wsl_to_windows(title, body)
            subprocess.run(
                ["notify-send", "--urgency=normal", "--icon=dialog-information", title, body],
                check=True, capture_output=True
            )
            return True

        elif plat == "Windows":
            # Windows Toast（powershell）
            ps = (
                f"[Windows.UI.Notifications.ToastNotificationManager, Windows.UI.Notifications, "
                f"ContentType = WindowsRuntime] > $null; "
                f"$t = [Windows.UI.Notifications.ToastTemplateType]::ToastText02; "
                f"$x = [Windows.UI.Notifications.ToastNotificationManager]::GetTemplateContent($t); "
                f"$x.GetElementsByTagName('text')[0].AppendChild($x.CreateTextNode('{title}')); "
                f"$x.GetElementsByTagName('text')[1].AppendChild($x.CreateTextNode('{body}')); "
                f"[Windows.UI.Notifications.ToastNotificationManager]::CreateToastNotifier('SecondBrain')"
                f".Show([Windows.UI.Notifications.ToastNotification]::new($x))"
            )
            subprocess.run(["powershell", "-Command", ps], check=True, capture_output=True)
            return True

    except (subprocess.CalledProcessError, FileNotFoundError) as e:
        logger.error(f"desktop 通知失敗: {e}")
    return False


# ── Slack 通知 ────────────────────────────────────────────────────
def notify_slack(title: str, body: str, webhook: str, channel: str | None) -> bool:
    payload: dict = {
        "text": f"*{title}*\n{body}",
        "username": "Second Brain",
        "icon_emoji": ":brain:",
    }
    if channel:
        payload["channel"] = channel

    data = json.dumps(payload).encode("utf-8")
    req  = urllib.request.Request(
        webhook,
        data=data,
        headers={"Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(req, timeout=5) as resp:
            return resp.status == 200
    except urllib.error.URLError as e:
        logger.error(f"Slack 送信失敗: {e}")
        return False


# ── エントリポイント ──────────────────────────────────────────────
def main():
    parser = argparse.ArgumentParser(description="通知連携プラグイン（拡張1）")
    parser.add_argument("--event",   required=True,
                        choices=["task_done", "blocker", "scored", "daily_summary", "custom"])
    parser.add_argument("--issue",   default=None)
    parser.add_argument("--title",   default=None)
    parser.add_argument("--detail",  default=None)
    parser.add_argument("--top",     default=None)
    args = parser.parse_args()

    config  = load_config()
    title, body = build_message(args.event, args)

    logger.info(f"{title}: {body[:80]}")

    results = []

    # デスクトップ通知
    if config.get("desktop", True):
        ok = notify_desktop(title, body)
        results.append(("desktop", ok))

    # Slack 通知
    webhook = config.get("slack_webhook")
    if webhook:
        channel = config.get("slack_channel")
        ok = notify_slack(title, body, webhook, channel)
        results.append(("slack", ok))

    for dest, ok in results:
        status = "✓" if ok else "✗"
        logger.info(f"  [{status}] {dest}")

    # どれか1つでも成功すれば exit 0
    if not results or any(ok for _, ok in results):
        sys.exit(0)
    else:
        sys.exit(1)


if __name__ == "__main__":
    main()


# ── WSL2 → Windows トースト通知（追記）────────────────────────
def notify_desktop_wsl_to_windows(title: str, body: str) -> bool:
    """WSL2内からPowerShellを経由してWindowsトースト通知を発火させる"""
    import shutil
    ps_candidates = [
        shutil.which("powershell.exe"),
        "/mnt/c/Windows/System32/WindowsPowerShell/v1.0/powershell.exe",
    ]
    ps_path = next((p for p in ps_candidates if p), None)
    if not ps_path:
        logger.error("powershell.exe が見つかりません（WSL2環境ではないかもしれません）")
        return False

    # BalloonTip方式（全Windowsバージョン対応）
    ps_script = (
        "Add-Type -AssemblyName System.Windows.Forms; "
        "$n = New-Object System.Windows.Forms.NotifyIcon; "
        "$n.Icon = [System.Drawing.SystemIcons]::Information; "
        "$n.Visible = $true; "
        f"$n.ShowBalloonTip(5000, '{title}', '{body}', [System.Windows.Forms.ToolTipIcon]::Info); "
        "Start-Sleep 3; $n.Dispose()"
    )
    try:
        subprocess.run(
            [ps_path, "-NonInteractive", "-Command", ps_script],
            check=True, capture_output=True, timeout=10
        )
        return True
    except Exception as e:
        logger.error(f"WSL2→Windows通知失敗: {e}")
        return False
