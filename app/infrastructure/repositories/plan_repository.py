"""SQLite implementation of the plan persistence port."""

from typing import Any
lazy import sqlite3

from app.application.ports.repositories.plan_repository import PlanRepositoryPort
from app.domain.exceptions import EntityNotFoundError
from app.domain.models.plan import Plan
from app.infrastructure.repositories.connection import transaction


def _row_to_plan(row: sqlite3.Row) -> Plan:
    return Plan(
        plan_id=row["plan_id"],
        name=row["name"],
        initial_monthly_price=float(row["monthly_price"]),
        initial_max_profiles=int(row["max_profiles"]),
    )


class SQLitePlanRepository(PlanRepositoryPort):
    """SQLite adapter implementing PlanRepositoryPort."""

    def __init__(
        self, conn: sqlite3.Connection, sync_service: Any | None = None
    ) -> None:
        self.conn = conn
        self._sync = sync_service

    def find_by_id(self, plan_id: int) -> Plan | None:
        if self._sync is not None:
            self._sync.pull_deltas()
        cursor = self.conn.execute(
            "SELECT * FROM plans WHERE plan_id = ?",
            (plan_id,),
        )
        row = cursor.fetchone()
        return _row_to_plan(row) if row else None

    def find_by_name(self, name: str) -> Plan | None:
        if self._sync is not None:
            self._sync.pull_deltas()
        cursor = self.conn.execute(
            "SELECT * FROM plans WHERE lower(name) = ?",
            (name.lower().strip(),),
        )
        row = cursor.fetchone()
        return _row_to_plan(row) if row else None

    def list_all(self) -> list[Plan]:
        if self._sync is not None:
            self._sync.pull_deltas()
        cursor = self.conn.execute("SELECT * FROM plans ORDER BY plan_id ASC")
        rows = cursor.fetchall()
        return [_row_to_plan(r) for r in rows]

    def save(self, plan: Plan) -> Plan:
        if self._sync is not None:
            self._sync.pull_deltas()
        target_id: int | None = plan.plan_id
        with transaction(self.conn) as cursor:
            if plan.plan_id is not None:
                row = cursor.execute(
                    "SELECT plan_id FROM plans WHERE plan_id = ?",
                    (plan.plan_id,),
                ).fetchone()
                if not row:
                    raise EntityNotFoundError(
                        entity_name="Plan", entity_id=plan.plan_id
                    )
                cursor.execute(
                    """
                    UPDATE plans
                    SET name = ?,
                        monthly_price = ?,
                        max_profiles = ?
                    WHERE plan_id = ?
                    """,
                    (
                        plan.name,
                        plan.monthly_price,
                        plan.max_profiles,
                        plan.plan_id,
                    ),
                )
                if self._sync is not None:
                    self._sync.push_plan_by_id(plan.plan_id)
            else:
                cursor.execute(
                    """
                    INSERT INTO plans (name, monthly_price, max_profiles)
                    VALUES (?, ?, ?)
                    """,
                    (plan.name, plan.monthly_price, plan.max_profiles),
                )
                target_id = cursor.lastrowid
                if target_id is not None and self._sync is not None:
                    self._sync.push_plan_by_id(target_id)
        if target_id is not None:
            return self.find_by_id(target_id) or plan
        return plan


__all__ = ["SQLitePlanRepository"]
