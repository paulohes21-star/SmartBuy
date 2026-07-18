from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any, Protocol, runtime_checkable

from app.integration.models import ConnectionTestResult, ReadResult


class ConnectorCapability(StrEnum):
    TEST_CONNECTION = "test_connection"
    PREVIEW = "preview"
    INCREMENTAL_SYNC = "incremental_sync"
    FULL_SYNC = "full_sync"
    CURSOR = "cursor"
    READ_ONLY = "read_only"


@dataclass(frozen=True)
class ConnectorDescriptor:
    connector_type: str
    version: str
    display_name: str
    capabilities: frozenset[ConnectorCapability]
    configuration_schema: dict[str, Any] = field(default_factory=dict)

    def supports(self, capability: ConnectorCapability) -> bool:
        return capability in self.capabilities


@dataclass(frozen=True)
class HealthSnapshot:
    connector_type: str
    connector_version: str
    status: str
    message: str
    latency_ms: int | None
    checked_at: str
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class ConnectorReadRequest:
    config: dict[str, Any]
    secrets: dict[str, str]
    cursor: str | None = None
    limit: int = 10000


@runtime_checkable
class EnterpriseConnector(Protocol):
    connector_type: str
    version: str

    def test_connection(
        self,
        config: dict[str, Any],
        secrets: dict[str, str],
    ) -> ConnectionTestResult:
        ...

    def read(
        self,
        config: dict[str, Any],
        secrets: dict[str, str],
        cursor: str | None = None,
        limit: int = 10000,
    ) -> ReadResult:
        ...
