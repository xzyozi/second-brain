# 運用詳細設計書（定常運用・ランブック・トラブルシューティング）
**Second Brain OS 日次サイクル・監査トレーサビリティ・障害対応ランブック**

| 項目 | 内容 |
| :--- | :--- |
| 文書番号 | SBOS-OP-001 |
| 版数     | Rev.3.3 |
| 改訂日   | 2026年7月28日（D1〜D5 バグ修正）|
| 作成日 | 2026年7月27日 |
| 対象読者 | 運用エンジニア / プロジェクトリード / DevOpsエンジニア |
| 関連文書 | SBOS-BD-002（基本設計書）、SBOS-ENV-001（環境構築仕様書）、SBOS-PM-005（矛盾点一覧） |

---

## 1. 日次・定常運用サイクル仕様

本システムの強みは、夜間や朝のバッチ処理による自動優先度計算と、人間の対話承認を組み合わせたハイブリッド運用にある。以下に標準的な日次運用サイクルを規定する。

### 1.1 朝の自動評価バッチ（cron / systemd タイマー連携）
毎朝 07:00 JST に、母艦から全衛星のタスクを自動スキャンしてスコアリングおよびブロッカー検出を行うバッチジョブを実行する。

#### crontab 設定例
```bash
# m h  dom mon dow   command
# [D2修正] notify.py に --event daily_summary 引数を追加
0 7 * * * cd ~/second-brain && /home/user/.local/bin/uv run python tools/score-issues.py && /home/user/.local/bin/uv run python tools/check-blockers.py && /home/user/.local/bin/uv run python tools/notify.py --event daily_summary > ~/second-brain/tools/.cache/daily_batch.log 2>&1
```

#### スコアリング計算数式と判定根拠 (`score-issues.py`)
全 Issue に対し、以下の4軸数式を適用して 0〜100点 のスコアを算出する。
$$\text{Total} = (P \times 3.0) + (F \times 2.0) + (E \times 1.5) + (D \times 2.0)$$
$$\text{Score} = \frac{\text{Total}}{42.5} \times 100$$
- **優先度 ($P$, 1〜5):** `critical`/`urgent`=5, `high`=4, `medium`=3, `low`=2, `none`=1
- **鮮度 ($F$, 0〜5):** 最終更新または追加日 (`added:`) から 7日以内=5, 30日以内=3, 90日以内=1, 超=0
- **工数軽さ ($E$, 1〜5):** サブタスク粒度および推定工数：1h=5, 4h=4, 8h=3, 16h=2, それ以上=1
- **依存解決度 ($D$, 0〜5):** `blockedby` ブロッカー数：0個=5, 1個=3, 2個=1, 3個以上=0（先行タスク未完了なら自動的に順位低下）

---

### 1.2 対話的な計画承認と Issue 実行 (`/orchestrate` と `/work`)

1. **実行計画の呼び出し:**
   ターミナルで OpenCode を起動し、`/orchestrate` を実行する。システムはバッチが計算したキャッシュ（`priority-cache.json`）を読み込み、実行可能な上位3件を人間に提示する。
   ```text
   【本日の実行計画 (推奨上位3件)】
   1位: [EC-012]「決済例外処理ロールバックハンドラの統合」（スコア: 94.2）
        → 理由: 優先度highであり、先行するAPI仕様書[EC-010]が完了して依存が解消されたため。
   2位: [FX-005]「LightGBMバックテスト指標推移表の追加」（スコア: 88.0）
        → 理由: 直近で追加されたタスクであり、単独モジュールで実装が完了するため。
   3位: [EC-015]「ユーザープロファイルアイコンのS3アップロード」（スコア: 81.5）

   承認したら /work EC-012 から開始します。よろしいですか？ (y/N)
   ```

2. **自律ループの起動 (`/work <ID>`):**
   ユーザーが `y` または `/work EC-012` を入力すると、Orchestrator が立ち上がり、以下のフェーズを自動的に進行する。
   - ① 要件収集 ＆ 制約検証
   - ② Executor による実装指示書生成
   - ③ Coder によるコード生成 ＆ AST マージ
   - ④ Ruff / pytest による自動検証（失敗時は自動自己修復）
   - ⑤ Reviewer Agent による差分監査（指示書とdiffの突き合わせ）
   - ⑥ すべて通過後、`execution_history.json` に実行結果を記録し、`tasks.md` のステータスを `[x]` に更新して完了。（注: `orchestrator.py` は git 操作を行わない。コミットは運用者が手動で実施すること。）

---

## 2. ブロッカー監視と B7 エスカレーション解消手順

### 2.1 ブロッカー B1〜B7 の一覧と自動ルーティング
| 分類コード | ブロッカー名 | 状態および対応方針 |
| :--- | :--- | :--- |
| **B1** | 仕様不明確 (`仕様未確定`, `TBD`) | 自動実行から除外し、Sisyphus が質問リストを生成してユーザーに提示。 |
| **B2** | 依存未完了 (`blockedby:#ID`) | 先行 Issue `#ID` を検出。先行 Issue の優先順位を自動で繰り上げる。 |
| **B3** | 技術調査未完 (`[ ] 技術調査`) | 実装ではなくスパイク調査タスクとして Orchestrator に引き渡す。 |
| **B4 / B5** | レビュー待ち / 外部依存待ち | LLMでは解決不能。スキップして日次レポートの通知対象にリストアップ。 |
| **B6** | リソース・予算不足 | 管理者への通知のみ。 |
| **B7** | **レビュー上限到達** | ⭐NEW：**人間エンジニアによる介在・指示書／コードの直接修正が必須。** |

---

### 2.2 B7 ブロッカー（レビュー上限到達）発生時の開発者介在手順
タスクの `round` が `max_round`（デフォルト3）に達し、`REVIEW_REJECTED` で停止した（B7ブロッカー化した）場合、以下の手順で問題を解決し、自律ループへ復帰させる。

#### Step 1: レビュー履歴と差分ログの確認
```bash
# 1. 該当 Issue のレビュー監査ログを表示
# [D3修正] chr(39)式を廃止。辞書アクセスを変数に事前代入しf-string内のクォートネストを完全に回避
python -c '
import json
with open("tools/.cache/execution_history.json", "r") as f:
    data = json.load(f)
logs = [e for e in data["executions"] if "EC-012" in e.get("issue_id", "")]
if not logs:
    print("該当 Issue の履歴が見つかりません")
else:
    latest = logs[-1]
    for r in latest.get("review", {}).get("rounds", []):
        rn = r.get("round", "?")
        rv = r.get("verdict", "?")
        rc = r.get("comment", "")
        print("--- Round " + str(rn) + " (" + rv + ") ---")
        print(rc)
'
```
**確認のポイント:** レビュアーの指摘が「実装上のバグ・例外処理漏れ」なのか、そもそも「Executor が作成した指示書（仕様）の矛盾・無理筋な要求」なのかを見極める。

#### Step 2: 衛星プロジェクトの直接修正（シングルリポジトリ開発モード）
母艦の存在を意識せず、該当の衛星プロジェクトを直接エディタで開き、人間が介入してコードまたは仕様書を調整する。
```bash
# 衛星リポジトリを VSCode 等で直接開く
code ~/second-brain/projects/ec-site

# ターミナルでテストを直接実行して問題箇所を特定・手動修正
cd ~/second-brain/projects/ec-site
uv run pytest
```

#### Step 3: メタデータのリセットと再実行
問題が手動解消したら、`tasks.md` を編集してラウンド数をリセットし、再度オーケストレーターへ投入する。
```markdown
# 修正前 (B7でブロック中)
- [/] [EC-012] 決済バグ修正  <!-- priority:high round:3 max_round:3 -->

# [C5修正] round:0 にリセットする（1巡目からやり直し）
- [/] [EC-012] 決済バグ修正  <!-- priority:high round:0 max_round:3 -->
```
```bash
# 母艦からオーケストレーターを再トリガー
cd ~/second-brain
python tools/orchestrator.py execute --issue-id EC-012
```


---

## 3. 監査ログ管理と品質トレーサビリティ

### 3.1 監査ログ (`execution_history.json`) の集計と品質分析
`tools/.cache/execution_history.json` は **単一JSONオブジェクト形式**（`{"executions": [...]}` ）として記録される。プロジェクト全体の品質統計を可視化するための貴重なデータソースとなる。

```bash
# 過去のテスト通過率とレビュー差し戻し平均回数を集計するワンライナー
# [C3修正] json.load() で単一JSONとして読み込む
# [C6修正] "total_rounds" フィールドは存在しないため len(rounds) で算出する
python -c '
import json
with open("tools/.cache/execution_history.json") as f:
    data = json.load(f)
records = data.get("executions", [])
total = len(records)
success_cnt = sum(1 for r in records if r.get("success"))
round_counts = [len(r["review"]["rounds"]) for r in records if "review" in r and "rounds" in r["review"]]
avg_rounds = sum(round_counts) / len(round_counts) if round_counts else 0
print("=== 品質監査サマリー ===")
print(f"総実行数: {total}件 | 最終成功率: {success_cnt/total*100:.1f}%" if total else "実行履歴なし")
print(f"平均レビューラウンド数: {avg_rounds:.2f}回")
'
```

### 3.2 障害記録とナレッジベース化 (`record-failure.py`)
システムが予期せぬエラーでクラッシュした場合や、独自のビジネスロジックにより特定のモデルで失敗した場合は、そのノウハウを母艦のナレッジとして記録する。

```bash
# 障害記録スクリプトの実行例
python tools/record-failure.py   --agent "coder"   --issue "EC-018"   --error "OpenAI互換APIでの特殊トークンパース例外"   --action "prompt_builder.pyにてコードブロック終了タグの正規表現補正を追加"
```

---

## 4. トラブルシューティング・ランブック（障害対応フロー）

運用中に発生しうる主要な障害ケースと、対応すべき具体的アプローチを規定する。

### ケース1: LLM 応答パース失敗 (`Agent response parse failed`)
- **症状:** `agent_client.py` で `ERROR: Agent response parse failed` が出力され、最大3回リトライ後も失敗する。
- **根本原因:**
  1. Ollama のコンテキスト窓（`num_ctx`）が枯渇し、モデルが出力を途中で打ち切っている。
  2. モデルが JSON フォーマットの要求を無視し、前後に解説文や挨拶を混入させている。
- **対処・解消手順:**

  **Linux / macOS:**
  ```bash
  # 1. 中間キャッシュの削除
  # [D4修正] context_*.json は実在しないファイル名。実在するキャッシュを削除する
  rm -f tools/.cache/priority-cache.json tools/.cache/blocked.json

  # 2. agent_client.py 内のパース正規表現の緩和確認
  # または対象 Issue のタスク記述を分割して短くする
  ```

  **Windows (PowerShell):**
  ```powershell
  Remove-Item tools\.cache\priority-cache.json, tools\.cache\blocked.json -ErrorAction SilentlyContinue
  ```

### ケース2: テスト継続失敗 (`TestFailureError` / 上限到達)
- **症状:** Coder が2回修正を試みてもテストが通らず、`State.FAILED` に遷移する。
- **根本原因:**
  1. 既存のテストコード側が古く、新しい要件と矛盾している。
  2. データベースや外部モジュールのモック設定が不足している。
- **対処・解消手順:**
  - `orchestrator.py` のログから直近の pytest 失敗ログを確認する。
  - テストコードの修正が必要な場合は、人間が `projects/<name>/tests/` を編集する（LLM にテストコードの無断書き換えを許さないため、これは意図された正しいエスカレーションである）。

### ケース3: OpenCode CLI サブプロセスのタイムアウト
- **症状:** `AgentCallError: Agent executor がタイムアウトしました (timeout=300)` が発生。
- **根本原因:**
  1. ローカルマシンで他の重いプロセス（動画エンコードや別のLLM推論）が走り、GPU リソースが枯渇している。
  2. Ollama が swap に落ちており、推論速度が著しく低下している。
- **対処・解消手順:**
  ```bash
  # 1. Ollama の実行プロセスと VRAM 使用状況の確認
  nvidia-smi  # または htop / asitop

  # 2. agent_client.py のデフォルトタイムアウトを延長
  # [C8修正] コンストラクタ引数名は default_timeout ではなく timeout
  # AgentClient(timeout=600) へ一時調整するか、軽量モデル(7B)へフォールバック
  ```

### ケース4: AST マージの衝突および構文エラー検知 (`SyntaxError during merge`)
- **症状:** `_merge_python_code` 実行時に `SyntaxError` がスローされ、ファイルが更新されない。
- **根本原因:**
  - Coder が出力した Python コードが、不完全なインデントや未閉じの文字列リテラルを含んでいる。
- **対処・解消手順:**
  - `orchestrator.py` は自動的に書き込み前のオリジナルスナップショット（`existing_content`）へロールバックし、リポジトリの破壊を防ぐように設計されている。
  - エラーログを確認し、モデルの温度パラメータ（temperature）を下げて再実行するか、またはプロンプト指示書の曖昧な記述を明確化する。

### ケース5: レビュー差し戻し上限到達（B7ブロッカー）⭐NEW
- **症状:** `REVIEW_REJECTED` が `max_round`（デフォルト3）回繰り返し、Issue が `State.FAILED` に遷移する。翌朝のバッチで `blocked.json` に `B7` として記録される。
- **根本原因:**
  1. Coder への修正依頼だけでは解決しない根本的な要件定義の矛盾・曖昧さが存在する。
  2. Reviewer モデルの応答品質が不安定で、正当な実装に対しても `changes_requested` を返し続けている。
- **対処・解消手順:**
  ```bash
  # 1. 対象 Issue の全レビュー履歴を確認
  python -c "
  import json
  data = json.load(open('tools/.cache/execution_history.json'))
  for e in data['executions']:
      if e['issue_id'] == 'EC-012':
          print(json.dumps(e.get('review', {}), ensure_ascii=False, indent=2))
  "
  ```
  - 指摘内容が**実装上のバグ・例外処理漏れ**なら → 衛星プロジェクトを直接エディタで開き手動修正後、`round` をリセットして再実行する。
  - 指摘内容が**実装指示書（仕様）自体の矛盾・無理筋な要求**なら → `tasks.md` のIssue説明文を人間が直接修正してから、`round` をリセットして再実行する。
  ```markdown
  # 修正後（round を手動リセット）
  - [/] [EC-012] 決済バグ修正  <!-- priority:high round:0 max_round:3 -->
  ```
  > **設計上の注意：** `round` のリセットは意図的に自動化しない。B7 は「人間の判断を挟むための安全弁」であり、機械的なリセット自動化は本設計の目的（判断ミスによるリポジトリ破壊防止）に反する。

## 5. 定常自動化スクリプト群の完全ソースコードリファレンス

運用担当者が障害調査および数式チューニングを即座に行えるよう、日次サイクルの核となる計算スクリプトの実装ソースコードを本書に明記する。

### 5.1 横断スコアリングスクリプト (`tools/score-issues.py`)
```python
#!/usr/bin/env python3
"""全衛星および母艦の tasks.md をスキャンし、4軸スコアを計算するスクリプト"""
import os
import glob
import json
import re
from datetime import datetime, timedelta
from typing import List, Dict, Any

def parse_all_issues(root_dir: str) -> List[Dict[str, Any]]:
    issues = []
    # 台帳の読み込み
    reg_path = os.path.join(root_dir, "projects", ".project-registry.json")
    if not os.path.exists(reg_path):
        return []
        
    with open(reg_path, "r", encoding="utf-8") as f:
        registry = json.load(f)
        
    for p_key, rel_path in registry.items():
        target_dir = os.path.join(root_dir, rel_path)
        tasks_file = os.path.join(target_dir, "tasks.md")
        if not os.path.exists(tasks_file):
            continue
            
        with open(tasks_file, "r", encoding="utf-8") as f:
            for line in f:
                match = re.search(r"-\s*\[([ x/])\]\s*\[([A-Z0-9]+-\d+)\]\s*(.*?)\s*<!--\s*(.*?)\s*-->", line)
                if match and match.group(1) != "x": # 未完了タスクのみ
                    status_char, idx, title, meta = match.groups()
                    meta_dict = dict(re.findall(r"([a-z_]+):([^\s]+)", meta))
                    issues.append({
                        "id": idx,
                        "project_key": p_key,
                        "title": title.strip(),
                        "status": status_char,
                        "priority": meta_dict.get("priority", "medium"),
                        "added": meta_dict.get("added", "2026-01-01"),
                        "blockedby": meta_dict.get("blockedby", None)
                    })
    return issues

def calculate_score(issue: Dict[str, Any]) -> float:
    # 1. 優先度スコア (P: 1〜5, 重み 3.0)
    p_map = {"critical": 5, "urgent": 5, "high": 4, "medium": 3, "low": 2, "none": 1}
    p_val = p_map.get(issue["priority"], 3)
    
    # 2. 鮮度スコア (F: 0〜5, 重み 2.0)
    try:
        added_dt = datetime.strptime(issue["added"], "%Y-%m-%d")
        days = (datetime.now() - added_dt).days
        f_val = 5 if days <= 7 else (3 if days <= 30 else (1 if days <= 90 else 0))
    except ValueError:
        f_val = 2
        
    # 3. 工数軽さスコア (E: 1〜5, 重み 1.5)
    # [2.2修正] estimate:Xh メタデータから動的にパース。
    # 取得できない場合のデフォルト値は 3.0（旧固定値との後方互換性維持）。
    # estimate → E マッピング: 1h=5, 4h=4, 8h=3, 16h=2, それ以上=1
    _estimate_map = {"1h": 5, "2h": 5, "4h": 4, "8h": 3, "16h": 2}
    _raw_estimate = str(issue.get("estimate", "")).strip().lower()
    if _raw_estimate in _estimate_map:
        e_val = float(_estimate_map[_raw_estimate])
    elif _raw_estimate:
        # 数値のみ抽出 (例: "3h", "6h") してバケット分類
        import re as _re
        _m = _re.match(r"^(\d+)h?$", _raw_estimate)
        if _m:
            _hours = int(_m.group(1))
            e_val = 5.0 if _hours <= 2 else (4.0 if _hours <= 4 else (3.0 if _hours <= 8 else (2.0 if _hours <= 16 else 1.0)))
        else:
            e_val = 3.0  # 不明な形式はフォールバック
    else:
        e_val = 3.0  # estimate 未指定はフォールバック
    
    # 4. 依存解決度スコア (D: 0〜5, 重み 2.0)
    # [C11修正] ブロッカー数に応じた段階評価（§1.1の定義表と一致させる）
    blockedby = issue.get("blockedby")
    if not blockedby:
        d_val = 5.0
    else:
        # blockedby は "#ID1,#ID2" 形式を想定
        blocker_count = len(str(blockedby).split(","))
        d_val = 3.0 if blocker_count == 1 else (1.0 if blocker_count == 2 else 0.0)
    
    total = (p_val * 3.0) + (f_val * 2.0) + (e_val * 1.5) + (d_val * 2.0)
    return round((total / 42.5) * 100, 1)

def main():
    root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    issues = parse_all_issues(root)
    
    scored = []
    for issue in issues:
        issue["score"] = calculate_score(issue)
        scored.append(issue)
        
    scored.sort(key=lambda x: x["score"], reverse=True)
    
    out_dir = os.path.join(root, "tools", ".cache")
    os.makedirs(out_dir, exist_ok=True)
    out_path = os.path.join(out_dir, "priority-cache.json")
    
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump({"updated_at": datetime.now().isoformat(), "issues": scored[:20]}, f, indent=2, ensure_ascii=False)
    print(f"Successfully generated priority cache for {len(scored)} issues.")

if __name__ == "__main__":
    main()
```

---

## 6. 中長期メンテナンス・モデル定期更新ランブック

オープンウェイトのローカルLLMは日々進化しており、月に数回の頻度で新しいモデル（例: Qwen シリーズの新バージョン、Gemma の改版等）がリリースされる。モデルの入れ替えによる退化（リグレッション）を防ぐための標準更新手順を規定する。

### 6.1 新モデルベンチマーク評価プロセス
本番運用中の `opencode.json` のモデル切り替えを行う前に、必ず以下のテスト衛星における回帰テストを実施すること。

| 検証フェーズ | 実行内容・コマンド | 合否判定基準（許容ライン） |
| :--- | :--- | :--- |
| **1. 構文追従性テスト** | `opencode run --agent coder -m ollama/<new-model> ...` にてダミー指示書を投入 | 出力にマークダウンの文脈や挨拶が混入せず、100%の確率でクリーンなコードブロックのみを返すこと。 |
| **2. リファクタリングマージテスト** | クラス内メソッド1件変更指示を出し、`_merge_python_code` を走行 | 既存の無関係なメソッドやプロパティが欠落・破壊されないこと。 |
| **3. 監査厳密性テスト (Reviewer)** | 意図的に例外処理を削ったバグ込みのコードと仕様書を提示 | `changes_requested` を正しく返し、バグの所在行番号を指摘できること。 |

### 6.2 ロールバック（切り戻し）手順
新モデル投入後に `Agent response parse failed` やループ上限到達の頻度が急増した場合、以下のコマンドで即座に旧安定バージョンへロールバックする。

```bash
# 1. opencode.json のモデル指定を安定版 (例: qwen2.5-coder:7b-16k) へ戻す
# [C9修正] 正しいパスは ~/second-brain/opencode.json
git checkout ~/second-brain/opencode.json

# 2. Ollama サーバー上の不安定な新モデルのタグを削除
ollama rm <unstable-new-model-tag>

# 3. 失敗したタスクのキャッシュリセット
# [D4修正] context_*.json は実在しないファイル名。実在するキャッシュを削除する
rm -f tools/.cache/priority-cache.json tools/.cache/blocked.json
```

---

## 7. リポジトリバックアップおよび災害復旧 (DR) ガイド

### 7.1 母艦および衛星 Git リポジトリのバックアップポリシー
本システムはクラウドデータベースを使用せず、すべてファイルシステム上に状態を保存するため、Git リポジトリ自体が完全なバックアップとなる。

```bash
#!/bin/bash
# バックアップスクリプト (~/second-brain/tools/backup-second-brain.sh)
set -e
BACKUP_DIR="/mnt/backup/second-brain-$(date +%Y%m%d_%H%M%S)"
mkdir -p "$BACKUP_DIR"

# [C10修正] print は Python 構文。bash では echo を使用する
echo "=== Starting Backup of Second Brain OS ==="
# 1. 母艦のコミット済みツリーのアーカイブ
tar --exclude="tools/.cache" --exclude=".venv" -czf "$BACKUP_DIR/second-brain-root.tar.gz" -C ~/ second-brain

# 2. 各衛星プロジェクトの個別アーカイブ
for proj in ~/second-brain/projects/*/; do
    # [C10修正] "; in" は bash 構文エラー。正しくは "; then"
    if [ -d "$proj/.git" ]; then
        proj_name=$(basename "$proj")
        tar --exclude=".venv" --exclude="node_modules" --exclude="__pycache__" -czf "$BACKUP_DIR/proj-${proj_name}.tar.gz" -C ~/second-brain/projects "$proj_name"
    fi
done
echo "=== Backup Completed Successfully: $BACKUP_DIR ==="
```