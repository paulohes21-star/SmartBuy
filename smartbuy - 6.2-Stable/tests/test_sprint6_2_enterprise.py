import json

from app.integration_core import (
    CONNECTOR_CONFIG_TEMPLATES,
    ENTITY_MAPPING_TEMPLATES,
)
from app.integration.mapper import validate_mapping


def test_all_supported_entities_have_enterprise_templates():
    expected = {
        "PRODUCT",
        "INVENTORY",
        "CONSUMPTION",
        "PURCHASE",
        "SUPPLIER",
        "OPEN_ORDER",
    }
    assert expected.issubset(ENTITY_MAPPING_TEMPLATES)


def test_enterprise_mapping_templates_are_valid():
    for entity, mapping in ENTITY_MAPPING_TEMPLATES.items():
        assert validate_mapping(entity, mapping) == []


def test_connector_templates_are_json_serializable():
    serialized = json.dumps(
        CONNECTOR_CONFIG_TEMPLATES,
        ensure_ascii=False,
    )
    assert "SQLSERVER" in serialized
    assert "CSV" in serialized
    assert "REST" in serialized


def test_enterprise_json_editor_assets_exist():
    from app import database

    root = database.BASE
    assert (root / "app" / "static" / "sprint6_enterprise.js").exists()
    assert (root / "app" / "static" / "sprint6.css").exists()
