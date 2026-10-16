"""Ordinary collection bridge for the deterministic B05 regressions.

The structural diagnostic module also contains still-open audit groups and is
therefore opt-in as a whole.  These wrappers keep only the corrected B05 cases
in the regular backend suite without copying or weakening their assertions.
"""

from tests import social_geo_structural_audit_diagnostic as b05_diagnostics


def test_b05_repository_late_confirmation_does_not_recreate_report():
    b05_diagnostics.test_confirmation_materialization_never_recreates_a_deleted_report()


def test_b05_repository_late_hidden_flag_does_not_recreate_report():
    b05_diagnostics.test_hidden_group_flag_never_recreates_report_deleted_after_snapshot()


def test_b05_repository_duplicate_undo_preserves_newer_cooldown():
    b05_diagnostics.test_duplicate_undo_does_not_delete_the_cooldown_owned_by_a_newer_report()


def test_b05_service_late_confirmation_does_not_recreate_report():
    b05_diagnostics.test_service_confirmation_never_recreates_report_removed_after_group_read()


def test_b05_service_late_hidden_flag_does_not_recreate_report():
    b05_diagnostics.test_service_flag_never_recreates_report_removed_after_group_read()


def test_b05_service_duplicate_undo_preserves_newer_cooldown():
    b05_diagnostics.test_service_duplicate_undo_never_deletes_newer_report_cooldown()


def test_b05_service_confirmation_preserves_complete_report_and_mirrors():
    b05_diagnostics.test_service_strict_confirmation_preserves_a_complete_active_report()


def test_b05_service_visible_flag_preserves_complete_report_and_mirrors():
    b05_diagnostics.test_service_strict_flag_preserves_a_complete_active_visible_report()


def test_b05_service_hidden_flag_preserves_complete_report_and_mirrors():
    b05_diagnostics.test_service_strict_flag_preserves_a_complete_active_hidden_report()


def test_b05_service_single_undo_allows_replacement_report():
    b05_diagnostics.test_service_strict_single_undo_allows_a_legitimate_replacement_report()
