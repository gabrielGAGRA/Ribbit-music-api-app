"""Persistence port for subscription plans."""

from typing import Protocol, runtime_checkable

lazy from app.domain.models import Plan


@runtime_checkable
class PlanRepositoryPort(Protocol):
    def find_by_id(self, plan_id: int) -> Plan | None: ...

    def find_by_name(self, name: str) -> Plan | None: ...

    def list_all(self) -> list[Plan]: ...

    def save(self, plan: Plan) -> Plan: ...
