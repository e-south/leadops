from crm.services.pull import decide_pull_action


def test_conflict_when_local_and_remote_changed() -> None:
    local_row = {"updated_at": "2026-01-02T00:00:00+00:00"}
    mirror_state = {"mirror_updated_at": "2026-01-01T00:00:00+00:00"}
    decision = decide_pull_action(
        local_row=local_row,
        mirror_state=mirror_state,
        changed_fields=["stage"],
        remote_modified_at="2026-01-03T00:00:00+00:00",
    )
    assert decision.action == "conflict"


def test_apply_when_only_remote_changed() -> None:
    local_row = {"updated_at": "2026-01-01T00:00:00+00:00"}
    mirror_state = {"mirror_updated_at": "2026-01-02T00:00:00+00:00"}
    decision = decide_pull_action(
        local_row=local_row,
        mirror_state=mirror_state,
        changed_fields=["stage"],
        remote_modified_at="2026-01-03T00:00:00+00:00",
    )
    assert decision.action == "apply"


def test_skip_when_only_local_changed() -> None:
    local_row = {"updated_at": "2026-01-03T00:00:00+00:00"}
    mirror_state = {"mirror_updated_at": "2026-01-02T00:00:00+00:00"}
    decision = decide_pull_action(
        local_row=local_row,
        mirror_state=mirror_state,
        changed_fields=["stage"],
        remote_modified_at="2026-01-02T00:00:00+00:00",
    )
    assert decision.action == "skip"
