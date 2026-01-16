from crm.adapters.airtable.pull import PullChange, PullSummary
from crm.services.pull_service import format_pull_report


def test_pull_report_format() -> None:
    summary = PullSummary(scanned=2, skipped=0, applied=1, conflicts=0, created=0, ignored=1)
    changes = [
        PullChange(
            table="organizations",
            external_id="org-123",
            action="apply",
            changed_fields=["name", "notes"],
        )
    ]
    lines = format_pull_report(summary, changes)
    assert lines[0].startswith("summary ")
    assert "applied=1" in lines[0]
    assert lines[1] == "organizations org-123 apply fields=name,notes"
