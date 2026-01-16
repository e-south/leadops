from crm.adapters.airtable.mirror import FieldExpectation, _field_payload


def test_field_payload_adds_datetime_options() -> None:
    spec = FieldExpectation(
        name="Created At",
        field_type="dateTime",
        options=None,
        required=True,
        source="mirror",
        domain_field=None,
    )
    payload = _field_payload(spec)
    options = payload.get("options") or {}
    assert options.get("dateFormat", {}).get("name") == "iso"
    assert options.get("timeFormat", {}).get("name") == "24hour"
    assert options.get("timeZone") == "utc"


def test_field_payload_adds_date_options() -> None:
    spec = FieldExpectation(
        name="Due Date",
        field_type="date",
        options=None,
        required=False,
        source="domain",
        domain_field="next_action_due",
    )
    payload = _field_payload(spec)
    options = payload.get("options") or {}
    assert options.get("dateFormat", {}).get("name") == "iso"


def test_field_payload_adds_number_options() -> None:
    spec = FieldExpectation(
        name="MirrorVersion",
        field_type="number",
        options=None,
        required=True,
        source="mirror",
        domain_field=None,
    )
    payload = _field_payload(spec)
    options = payload.get("options") or {}
    assert options.get("precision") == 0
