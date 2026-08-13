"""
test_score_issues.py  ―  score-issues.py のユニットテスト

対象:
  - parse_effort_hours()  : estimate 文字列 → 時間換算
  - effort_score()        : 時間 → スコア（1-5）
  - freshness_score()     : updated 日付 → 鮮度スコア
  - dependency_score()    : blockedby 件数 → 依存スコア
  - parse_issues()        : roadmap.md テキスト → Issue リスト
  - parse_tasks_file()    : tasks.md テキスト → Issue リスト（衛星プロジェクト）
"""

import datetime
import pytest


# ── parse_effort_hours ─────────────────────────────────────────────

class TestParseEffortHours:
    def test_hours(self, score_issues_mod):
        assert score_issues_mod.parse_effort_hours("estimate: 4h") == 4.0

    def test_minutes(self, score_issues_mod):
        assert score_issues_mod.parse_effort_hours("estimate: 30m") == pytest.approx(0.5)

    def test_days(self, score_issues_mod):
        assert score_issues_mod.parse_effort_hours("estimate: 1d") == 8.0

    def test_no_estimate_defaults_to_8h(self, score_issues_mod):
        assert score_issues_mod.parse_effort_hours("no estimate here") == 8.0

    def test_decimal(self, score_issues_mod):
        assert score_issues_mod.parse_effort_hours("estimate: 1.5h") == 1.5


# ── effort_score ───────────────────────────────────────────────────

class TestEffortScore:
    def test_1h_is_5(self, score_issues_mod):
        assert score_issues_mod.effort_score(1.0) == 5

    def test_4h_is_4(self, score_issues_mod):
        assert score_issues_mod.effort_score(4.0) == 4

    def test_8h_is_3(self, score_issues_mod):
        assert score_issues_mod.effort_score(8.0) == 3

    def test_16h_is_2(self, score_issues_mod):
        assert score_issues_mod.effort_score(16.0) == 2

    def test_over_16h_is_1(self, score_issues_mod):
        assert score_issues_mod.effort_score(24.0) == 1


# ── freshness_score ────────────────────────────────────────────────

class TestFreshnessScore:
    def test_today_is_5(self, score_issues_mod):
        today = datetime.date.today().isoformat()
        text = f"updated: {today}"
        assert score_issues_mod.freshness_score(text) == 5

    def test_no_date_is_1(self, score_issues_mod):
        assert score_issues_mod.freshness_score("no date here") == 1

    def test_old_date_over_90days_is_0(self, score_issues_mod):
        old = (datetime.date.today() - datetime.timedelta(days=100)).isoformat()
        assert score_issues_mod.freshness_score(f"updated: {old}") == 0

    def test_within_30days_is_3(self, score_issues_mod):
        recent = (datetime.date.today() - datetime.timedelta(days=20)).isoformat()
        assert score_issues_mod.freshness_score(f"updated: {recent}") == 3


# ── dependency_score ───────────────────────────────────────────────

class TestDependencyScore:
    def test_no_blockers_is_5(self, score_issues_mod):
        assert score_issues_mod.dependency_score("no blockers") == 5

    def test_one_blocker_is_3(self, score_issues_mod):
        assert score_issues_mod.dependency_score("blockedby: #1") == 3

    def test_two_blockers_is_1(self, score_issues_mod):
        text = "blockedby: #1\nblockedby: #2"
        assert score_issues_mod.dependency_score(text) == 1

    def test_three_or_more_blockers_is_0(self, score_issues_mod):
        text = "blockedby: #1\nblockedby: #2\nblockedby: #3"
        assert score_issues_mod.dependency_score(text) == 0


# ── parse_issues ───────────────────────────────────────────────────

class TestParseIssues:
    def test_returns_list(self, score_issues_mod, sample_roadmap_text):
        issues = score_issues_mod.parse_issues(sample_roadmap_text)
        assert isinstance(issues, list)

    def test_skips_done_issues(self, score_issues_mod, sample_roadmap_text):
        issues = score_issues_mod.parse_issues(sample_roadmap_text)
        ids = [i["id"] for i in issues]
        assert "3" not in ids

    def test_parses_numeric_id(self, score_issues_mod, sample_roadmap_text):
        issues = score_issues_mod.parse_issues(sample_roadmap_text)
        ids = [i["id"] for i in issues]
        assert "1" in ids

    def test_parses_prefix_id(self, score_issues_mod, sample_roadmap_text):
        issues = score_issues_mod.parse_issues(sample_roadmap_text)
        ids = [i["id"] for i in issues]
        assert "TST-001" in ids

    def test_sorted_by_score_descending(self, score_issues_mod, sample_roadmap_text):
        issues = score_issues_mod.parse_issues(sample_roadmap_text)
        scores = [i["score"] for i in issues]
        assert scores == sorted(scores, reverse=True)

    def test_has_required_keys(self, score_issues_mod, sample_roadmap_text):
        issues = score_issues_mod.parse_issues(sample_roadmap_text)
        assert len(issues) > 0
        for issue in issues:
            assert "id" in issue
            assert "title" in issue
            assert "score" in issue
            assert "axes" in issue

    def test_score_between_0_and_100(self, score_issues_mod, sample_roadmap_text):
        issues = score_issues_mod.parse_issues(sample_roadmap_text)
        for issue in issues:
            assert 0 <= issue["score"] <= 100


# ── parse_tasks_file ───────────────────────────────────────────────

class TestParseTasksFile:
    def test_skips_completed_tasks(self, score_issues_mod, sample_tasks_text):
        issues = score_issues_mod.parse_tasks_file(sample_tasks_text, "EC", "test-proj")
        ids = [i["id"] for i in issues]
        # [x] 完了済みはスキップされるべき
        titles = [i["title"] for i in issues]
        assert "完了済みタスク" not in titles

    def test_includes_in_progress(self, score_issues_mod, sample_tasks_text):
        issues = score_issues_mod.parse_tasks_file(sample_tasks_text, "EC", "test-proj")
        titles = [i["title"] for i in issues]
        assert "進行中のタスク" in titles

    def test_prefix_id_extracted(self, score_issues_mod, sample_tasks_text):
        issues = score_issues_mod.parse_tasks_file(sample_tasks_text, "EC", "test-proj")
        ids = [i["id"] for i in issues]
        assert "EC-001" in ids

    def test_project_field_set(self, score_issues_mod, sample_tasks_text):
        issues = score_issues_mod.parse_tasks_file(sample_tasks_text, "EC", "test-proj")
        for issue in issues:
            assert issue.get("project") == "test-proj"

    def test_dependency_reduces_score(self, score_issues_mod):
        # 依存関係がないタスクと、あるタスクを用意してスコアを比較する
        tasks_text = """# Tasks
- [ ] [EC-001] タスクA  <!-- priority:medium -->
- [ ] [EC-002] タスクB  <!-- priority:medium blockedby:#EC-001 -->
"""
        issues = score_issues_mod.parse_tasks_file(tasks_text, "EC", "test-proj")
        
        issue_a = next(i for i in issues if i["id"] == "EC-001")
        issue_b = next(i for i in issues if i["id"] == "EC-002")
        
        # 依存解決度（D）のスコアが タスクA(5) > タスクB(3) であることを確認
        assert issue_a["axes"]["D"] == 5
        assert issue_b["axes"]["D"] == 3
        # 最終スコアも タスクA > タスクB であることを確認
        assert issue_a["score"] > issue_b["score"]

