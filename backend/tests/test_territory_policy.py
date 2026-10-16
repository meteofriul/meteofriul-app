from app.services.territory_policy import (
    COMMUNITY_REGION_NOT_ENABLED_CODE,
    community_region_not_enabled_detail,
    community_write_enabled,
    source_eligibility,
)


def test_fvg_enables_osmer_and_community_writes() -> None:
    sources = source_eligibility(region_id="IT-36")

    assert sources["osmer"].status == "enabled"
    assert sources["webcams"].status == "enabled"
    assert sources["radar"].status == "enabled"
    assert community_write_enabled(region_id="IT-36") is True


def test_national_region_keeps_national_sources_and_community_without_osmer() -> None:
    sources = source_eligibility(region_id="IT-21")

    assert sources["forecast"].status == "enabled"
    assert sources["forecast"].provider == "icon-2i"
    assert sources["icon2i"].status == "enabled"
    assert sources["radar"].status == "enabled"
    assert sources["national_alerts"].status == "planned"
    assert sources["osmer"].status == "unsupported"
    assert community_write_enabled(region_id="IT-21") is True


def test_unknown_region_fails_closed_for_regional_capabilities() -> None:
    sources = source_eligibility(region_id=None)
    assert all(source.status == "unsupported" for source in sources.values())
    assert community_write_enabled(region_id=None) is False

    detail = community_region_not_enabled_detail()
    assert detail["code"] == COMMUNITY_REGION_NOT_ENABLED_CODE
    assert detail["read_scope"] == "IT"
    assert detail["write_scope"] == "IT"
    assert len(detail["enabled_regions"]) == 20
    assert "IT-21" in detail["enabled_regions"]
    assert "IT-36" in detail["enabled_regions"]


def test_foreign_region_fails_closed_for_all_italian_sources() -> None:
    sources = source_eligibility(region_id="SI-044")

    assert all(source.status == "unsupported" for source in sources.values())
    assert community_write_enabled(region_id="SI-044") is False


def test_unknown_it_prefixed_region_is_not_treated_as_italian() -> None:
    sources = source_eligibility(region_id="IT-99")

    assert all(source.status == "unsupported" for source in sources.values())
    assert community_write_enabled(region_id="IT-99") is False
