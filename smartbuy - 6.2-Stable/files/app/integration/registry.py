from __future__ import annotations

import json
import re
from dataclasses import asdict
from typing import Iterable

from app import database
from app.integration.contracts import (
    ConnectorCapability,
    ConnectorDescriptor,
    EnterpriseConnector,
)
from app.integration.connectors import connector_registry


_SEMVER = re.compile(
    r"^(?P<major>0|[1-9]\d*)\."
    r"(?P<minor>0|[1-9]\d*)\."
    r"(?P<patch>0|[1-9]\d*)"
    r"(?:-(?P<pre>[0-9A-Za-z.-]+))?$"
)


def validate_version(version: str) -> None:
    if not _SEMVER.fullmatch(version):
        raise ValueError(
            "Versão de conector inválida. Use SemVer, por exemplo 1.0.0."
        )


def _capabilities_for(connector_type: str) -> frozenset[ConnectorCapability]:
    common = {
        ConnectorCapability.TEST_CONNECTION,
        ConnectorCapability.PREVIEW,
        ConnectorCapability.FULL_SYNC,
        ConnectorCapability.READ_ONLY,
    }
    if connector_type in {"CSV", "EXCEL"}:
        return frozenset(common | {ConnectorCapability.CURSOR})
    return frozenset(
        common
        | {
            ConnectorCapability.INCREMENTAL_SYNC,
            ConnectorCapability.CURSOR,
        }
    )


def descriptors() -> list[ConnectorDescriptor]:
    result = []
    with database.connect() as conn:
        rows = conn.execute(
            """
            SELECT connector_type, version, display_name,
                   capabilities_json
            FROM integration_connector_registry
            WHERE active=1
            ORDER BY connector_type, version
            """
        ).fetchall()

    for row in rows:
        raw = json.loads(row["capabilities_json"] or "{}")
        capabilities = {
            ConnectorCapability(key)
            for key, enabled in raw.items()
            if enabled and key in ConnectorCapability._value2member_map_
        }
        if not capabilities:
            capabilities = set(_capabilities_for(row["connector_type"]))

        result.append(
            ConnectorDescriptor(
                connector_type=row["connector_type"],
                version=row["version"],
                display_name=row["display_name"],
                capabilities=frozenset(capabilities),
            )
        )
    return result


def get_connector(
    connector_type: str,
    version: str | None = None,
) -> EnterpriseConnector:
    connector_key = connector_type.strip().upper()
    connector = connector_registry.get(connector_key)
    if connector is None:
        raise KeyError(f"Conector não registrado: {connector_key}")

    installed_version = str(getattr(connector, "version", "1.0.0"))
    validate_version(installed_version)

    if version is not None and version != installed_version:
        raise KeyError(
            f"Versão {version} não está carregada para {connector_key}. "
            f"Versão disponível: {installed_version}."
        )
    return connector


def register_runtime_connectors() -> None:
    with database.connect() as conn:
        for connector_type, connector in connector_registry.items():
            version = str(getattr(connector, "version", "1.0.0"))
            validate_version(version)
            capabilities = {
                capability.value: True
                for capability in _capabilities_for(connector_type)
            }
            conn.execute(
                """
                INSERT INTO integration_connector_registry(
                    connector_type, version, display_name,
                    capabilities_json, active
                ) VALUES(?, ?, ?, ?, 1)
                ON CONFLICT(connector_type, version) DO UPDATE SET
                    capabilities_json=excluded.capabilities_json,
                    active=1
                """,
                (
                    connector_type,
                    version,
                    connector_type.title(),
                    json.dumps(capabilities, ensure_ascii=False),
                ),
            )
        conn.commit()
