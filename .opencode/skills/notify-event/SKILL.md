---
name: notify-event
description: |
  タスク完了・ブロッカー検出・エラー発生時にデスクトップ通知またはSlack通知を送る。
  「通知して」「知らせて」「完了を報告して」といった依頼、または他のSkill内の
  完了処理ステップから呼び出される。
---

# Notify Event Skill

## いつ使うか
- Issue完了・エラー発生・重要な判断が必要になったタイミング
- 他のSkill（priority-scoring, execute-issue）の完了処理ステップから

## 手順

このSkillには専用スクリプトはない。プロジェクト共有の `tools/notify.py` を
以下のイベント種別に応じて呼び出すだけでよい。

```bash
# タスク完了時
python3 tools/notify.py --event task_done --issue <id> --title "<タイトル>"

# ブロッカー検出時
python3 tools/notify.py --event blocker --issue <id> --detail "<詳細>"

# スコアリング完了時
python3 tools/notify.py --event scored --top "<Top Issue概要>"

# 全体サマリー
python3 tools/notify.py --event daily_summary

# 任意メッセージ（エラー等）
python3 tools/notify.py --event custom --title "<タイトル>" --detail "<本文>"
```

## 制約
- 通知内容に機微情報（APIキー、パスワード等）を含めてはいけない。
- 通知は「提案」ではなく実行してよい（通知送信自体は破壊的操作ではないため
  `opencode.json` の permission でも `allow` に設定されている）。

## 関連ファイル
- 実体: `tools/notify.py`（プロジェクト共有スクリプト）
- 設定: `tools/notify-config.json`（Slack Webhook等。`.gitignore`対象）
