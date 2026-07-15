"""
test_check_blockers.py  ―  check-blockers.py のユニットテスト

対象:
  - detect_blockers()  : 1つの Issue ブロックに対してブロッカールールを適用
  - parse_and_check()  : roadmap.md 全体を解析してブロッカーリストと実行可能IDを返す
"""

import pytest


# ── detect_blockers ────────────────────────────────────────────────

class TestDetectBlockers:
    def test_no_blockers_returns_empty(self, check_blockers_mod):
        result = check_blockers_mod.detect_blockers("1", "通常タスク", "## [#1] 通常タスク\n- priority-high\n")
        assert result == []

    def test_b1_spec_unclear(self, check_blockers_mod):
        block = "## [#1] 仕様確認タスク\n- priority-high\n- 仕様未確定\n"
        result = check_blockers_mod.detect_blockers("1", "仕様確認タスク", block)
        types = [r["type"] for r in result]
        assert "B1" in types

    def test_b2_blocked_by(self, check_blockers_mod):
        block = "## [#2] 依存タスク\n- priority-high\n- blockedby: #1\n"
        result = check_blockers_mod.detect_blockers("2", "依存タスク", block)
        types = [r["type"] for r in result]
        assert "B2" in types

    def test_b4_review_pending(self, check_blockers_mod):
        block = "## [#3] レビュー待ちタスク\n- priority-medium\n- レビュー待ち\n"
        result = check_blockers_mod.detect_blockers("3", "レビュー待ちタスク", block)
        types = [r["type"] for r in result]
        assert "B4" in types

    def test_result_has_required_keys(self, check_blockers_mod):
        block = "## [#1] ブロックタスク\n- 仕様未確定\n"
        result = check_blockers_mod.detect_blockers("1", "ブロックタスク", block)
        assert len(result) > 0
        for item in result:
            assert "id" in item
            assert "title" in item
            assert "type" in item
            assert "label" in item
            assert "action" in item

    def test_prefix_id_supported(self, check_blockers_mod):
        block = "## [TST-001] プレフィックスIDタスク\n- 仕様未確定\n"
        result = check_blockers_mod.detect_blockers("TST-001", "プレフィックスIDタスク", block)
        assert any(r["id"] == "TST-001" for r in result)


# ── parse_and_check ────────────────────────────────────────────────

class TestParseAndCheck:
    def test_returns_two_values(self, check_blockers_mod, sample_roadmap_text):
        blocked, actionable = check_blockers_mod.parse_and_check(sample_roadmap_text)
        assert isinstance(blocked, list)
        assert isinstance(actionable, list)

    def test_done_issues_excluded_from_actionable(self, check_blockers_mod, sample_roadmap_text):
        _, actionable = check_blockers_mod.parse_and_check(sample_roadmap_text)
        # #3 は done なので実行可能リストに含まれないはず
        assert "3" not in actionable

    def test_blocked_issue_not_in_actionable(self, check_blockers_mod, sample_roadmap_text):
        blocked, actionable = check_blockers_mod.parse_and_check(sample_roadmap_text)
        blocked_ids = {b["id"] for b in blocked}
        for bid in blocked_ids:
            assert bid not in actionable

    def test_detects_b2_in_sample(self, check_blockers_mod, sample_roadmap_text):
        blocked, _ = check_blockers_mod.parse_and_check(sample_roadmap_text)
        types = [b["type"] for b in blocked]
        # #2 は blockedby: #1 なので B2 が検出されるはず
        assert "B2" in types

    def test_detects_b1_in_sample(self, check_blockers_mod, sample_roadmap_text):
        blocked, _ = check_blockers_mod.parse_and_check(sample_roadmap_text)
        types = [b["type"] for b in blocked]
        # TST-001 は 仕様未確定 なので B1 が検出されるはず
        assert "B1" in types

    def test_empty_roadmap_returns_empty(self, check_blockers_mod):
        blocked, actionable = check_blockers_mod.parse_and_check("")
        assert blocked == []
        assert actionable == []


# ── parse_tasks_file ────────────────────────────────────────────────

class TestParseTasksFile:
    def test_parse_tasks_file_blockedby(self, check_blockers_mod):
        tasks_text = """# Tasks
- [ ] [TFG-001] タスク1  <!-- priority:medium -->
- [ ] [TFG-002] タスク2  <!-- priority:medium blockedby:#TFG-001 -->
"""
        blocked, actionable = check_blockers_mod.parse_tasks_file(tasks_text, "TFG", "test_file_grep")
        
        # B2ブロッカーが検出されることを検証
        assert len(blocked) == 1
        assert blocked[0]["id"] == "TFG-002"
        assert blocked[0]["type"] == "B2"
        assert blocked[0]["detail"] == "blockedby: #TFG-001"
        
        # TFG-001はactionable、TFG-002はblockedなのでactionableに含まれないことを検証
        assert "TFG-001" in actionable
        assert "TFG-002" not in actionable

