"""
conftest.py  ―  pytest 共通フィクスチャ定義

ハイフン付きファイル名（score-issues.py など）は
importlib.util 経由で動的ロードし、モジュールオブジェクトとして各テストへ提供する。
"""

import importlib.util
import sys
from pathlib import Path
import pytest

ROOT = Path(__file__).parent.parent  # second-brain/ ルート


def _load(script_name: str):
    """tools/{script_name} を importlib 経由でロードしてモジュールを返す"""
    path = ROOT / "tools" / script_name
    spec = importlib.util.spec_from_file_location(script_name.replace("-", "_").replace(".py", ""), path)
    mod = importlib.util.module_from_spec(spec)
    # 既にキャッシュされていれば再利用
    mod_key = spec.name
    if mod_key not in sys.modules:
        spec.loader.exec_module(mod)
        sys.modules[mod_key] = mod
    return sys.modules[mod_key]


@pytest.fixture(scope="session")
def score_issues_mod():
    return _load("score-issues.py")


@pytest.fixture(scope="session")
def check_blockers_mod():
    return _load("check-blockers.py")


@pytest.fixture(scope="session")
def update_roadmap_mod():
    return _load("update-roadmap.py")


@pytest.fixture(scope="session")
def add_task_mod():
    return _load("add-task.py")


@pytest.fixture(scope="session")
def record_failure_mod():
    return _load("record-failure.py")



# ── サンプルデータ ──────────────────────────────────────────────────

@pytest.fixture
def sample_roadmap_text():
    """テスト用の最小限 roadmap.md テキスト"""
    return """\
## [#1] ユーザー認証APIの実装
- priority-high
- estimate: 4h
- updated: 2026-06-25
- status: open

## [#2] デプロイスクリプト整備
- priority-medium
- estimate: 2h
- updated: 2026-06-10
- status: open
- blockedby: #1

## [#3] 完了済みタスク
- priority-low
- status: done

## [TST-001] プレフィックスIDタスク
- priority-high
- estimate: 1h
- updated: 2026-06-26
- status: open
- 仕様未確定
"""


@pytest.fixture
def sample_tasks_text():
    """テスト用の最小限 tasks.md テキスト"""
    return """\
- [ ] [EC-001] 依存タスクA <!-- priority:high estimate:4h added:2026-06-27 -->
- [ ] タスクB <!-- priority:medium estimate:2h added:2026-06-20 blockedby:#1 -->
- [x] 完了済みタスク <!-- priority:low -->
- [/] 進行中のタスク <!-- priority:high estimate:1h added:2026-06-27 -->
"""


def pytest_addoption(parser):
    parser.addoption(
        "--run-llm", action="store_true", default=False, help="LLMの呼び出しを伴うインテグレーションテストを実行する"
    )


def pytest_collection_modifyitems(config, items):
    if config.getoption("--run-llm"):
        return
    skip_llm = pytest.mark.skip(reason="--run-llm オプションが指定されていないためスキップします")
    for item in items:
        if "llm" in item.keywords:
            item.add_marker(skip_llm)

