"""
test_update_roadmap.py  ―  update-roadmap.py のユニットテスト

対象:
  - update_issue()  : テキスト内の指定 Issue の status/updated を書き換え
"""

import datetime
import pytest


# ── update_issue ───────────────────────────────────────────────────

SAMPLE_ROADMAP = """\
## [#1] ユーザー認証APIの実装
- priority-high
- estimate: 4h
- status: open
- updated: 2026-06-20

## [#2] デプロイスクリプト整備
- priority-medium
- status: open
"""


class TestUpdateIssue:
    def test_status_changed_to_done(self, update_roadmap_mod):
        new_text, changed = update_roadmap_mod.update_issue(SAMPLE_ROADMAP, "1", "done", None)
        assert changed is True
        assert "status: done" in new_text

    def test_unknown_id_returns_unchanged(self, update_roadmap_mod):
        new_text, changed = update_roadmap_mod.update_issue(SAMPLE_ROADMAP, "999", "done", None)
        assert changed is False
        assert new_text == SAMPLE_ROADMAP

    def test_updated_date_set_to_today(self, update_roadmap_mod):
        today = datetime.date.today().isoformat()
        new_text, changed = update_roadmap_mod.update_issue(SAMPLE_ROADMAP, "1", "done", None)
        assert changed is True
        assert f"updated: {today}" in new_text

    def test_note_appended_when_provided(self, update_roadmap_mod):
        new_text, changed = update_roadmap_mod.update_issue(SAMPLE_ROADMAP, "1", "blocked", "B1: 仕様未確定")
        assert changed is True
        assert "note: B1: 仕様未確定" in new_text

    def test_no_note_when_none(self, update_roadmap_mod):
        new_text, changed = update_roadmap_mod.update_issue(SAMPLE_ROADMAP, "1", "done", None)
        assert changed is True
        assert "note:" not in new_text

    def test_other_issues_not_affected(self, update_roadmap_mod):
        new_text, _ = update_roadmap_mod.update_issue(SAMPLE_ROADMAP, "1", "done", None)
        # #2 のブロックを探して status が open のままであることを確認
        # #2 は status: open を持つ行が含まれているはず（#1 の変更には影響されない）
        # #2 は元々 status: open を持っているが、新テキストでも変わらないはず
        issue2_start = new_text.find("## [#2]")
        assert issue2_start != -1
        issue2_block = new_text[issue2_start:]
        assert "status: open" in issue2_block

    def test_status_changed_to_in_progress(self, update_roadmap_mod):
        new_text, changed = update_roadmap_mod.update_issue(SAMPLE_ROADMAP, "2", "in-progress", None)
        assert changed is True
        assert "status: in-progress" in new_text

    def test_issue_without_updated_field_gets_one(self, update_roadmap_mod):
        # #2 には updated: 行がないため、新規追加されるはず
        today = datetime.date.today().isoformat()
        new_text, changed = update_roadmap_mod.update_issue(SAMPLE_ROADMAP, "2", "done", None)
        assert changed is True
        assert f"updated: {today}" in new_text
