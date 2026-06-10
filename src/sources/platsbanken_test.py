from sources.platsbanken import _detect_work_type, _parse_hit, _text


def _hit(**kwargs) -> dict[str, object]:
    """A realistic Platsbanken hit, overridable per test."""
    defaults: dict[str, object] = {
        "id": "hit-1",
        "headline": "Data Engineer",
        "employer": {"name": "Acme AB"},
        "workplace_address": {
            "municipality": "Stockholm",
            "region": "Stockholms län",
        },
        "description": {"text": "We are hiring a data engineer."},
        "working_hours_type": {"label": "Heltid"},
        "webpage_url": "https://example.com/jobs/1",
        "publication_date": "2026-01-01T00:00:00",
    }
    return {**defaults, **kwargs}


# --- _text ---


def test_text_reads_top_level_string():
    assert _text({"id": "abc"}, "id") == "abc"


def test_text_walks_nested_path():
    assert _text({"a": {"b": "deep"}}, "a", "b") == "deep"


def test_text_returns_empty_for_missing_key():
    assert _text({"a": {}}, "a", "b") == ""


def test_text_returns_empty_for_none_value():
    # The original crash: a present key whose value is None.
    assert _text({"a": {"b": None}}, "a", "b") == ""


def test_text_returns_empty_for_none_intermediate():
    assert _text({"a": None}, "a", "b") == ""


def test_text_returns_empty_for_non_dict_node():
    assert _text({"a": "string"}, "a", "b") == ""


def test_text_returns_empty_for_non_string_leaf():
    assert _text({"a": 42}, "a") == ""


# --- _detect_work_type ---


def test_detect_remote_from_distansarbete_label():
    assert _detect_work_type("Distansarbete", "") == "remote"


def test_detect_remote_label_is_case_insensitive():
    assert _detect_work_type("DISTANSARBETE", "") == "remote"


def test_detect_hybrid_from_description():
    assert _detect_work_type("Heltid", "Hybrid role in Malmö") == "hybrid"


def test_detect_on_site_when_description_present():
    assert _detect_work_type("Heltid", "On-site only.") == "on-site"


def test_detect_unknown_when_nothing_matches():
    assert _detect_work_type("", "") == "unknown"


# --- _parse_hit ---


def test_parse_hit_maps_all_fields():
    job = _parse_hit(_hit())

    assert job.id == "hit-1"
    assert job.title == "Data Engineer"
    assert job.company == "Acme AB"
    assert job.location == "Stockholm"
    assert job.work_type == "on-site"
    assert job.description == "We are hiring a data engineer."
    assert job.url == "https://example.com/jobs/1"
    assert job.posted_date == "2026-01-01T00:00:00"
    assert job.source == "platsbanken"


def test_parse_hit_survives_none_values():
    # Regression: Platsbanken returns these keys with None values.
    job = _parse_hit(
        _hit(
            description={"text": None},
            working_hours_type={"label": None},
        )
    )

    assert job.description == ""
    assert job.work_type == "unknown"


def test_parse_hit_generates_id_when_missing():
    job = _parse_hit(_hit(id=None))

    assert job.id


def test_parse_hit_falls_back_to_region_for_location():
    job = _parse_hit(_hit(workplace_address={"region": "Skåne län"}))

    assert job.location == "Skåne län"


def test_parse_hit_posted_date_is_none_when_missing():
    job = _parse_hit(_hit(publication_date=None))

    assert job.posted_date is None
