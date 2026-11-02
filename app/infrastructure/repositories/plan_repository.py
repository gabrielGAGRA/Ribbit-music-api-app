"""SQLite implementation of the plan persistence port."""

lazy import sqlite3

from app.application.ports.repositories.plan_repository import PlanRepositoryPort
from app.domain.exceptions import EntityNotFoundError
from app.domain.models.plan import Plan


def _row_to_plan(row: sqlite3.Row) -> Plan:
    return Plan(
        plan_id=row["plan_id"],
        name=row["name"],
        initial_monthly_price=float(row["monthly_price"]),
        initial_max_profiles=int(row["max_profiles"]),
    )


class SQLitePlanRepository(PlanRepositoryPort):
    """SQLite adapter implementing PlanRepositoryPort."""

    def __init__(self, conn: sqlite3.Connection) -> None:
        self.conn = conn

    def find_by_id(self, plan_id: int) -> Plan | None:
        cursor = self.conn.execute(
            "SELECT * FROM plans WHERE plan_id = ?",
            (plan_id,),
        )
        row = cursor.fetchone()
        return _row_to_plan(row) if row else None

    def find_by_name(self, name: str) -> Plan | None:
        cursor = self.conn.execute(
            "SELECT * FROM plans WHERE lower(name) = ?",
            (name.lower().strip(),),
        )
        row = cursor.fetchone()
        return _row_to_plan(row) if row else None

    def list_all(self) -> list[Plan]:
        cursor = self.conn.execute("SELECT * FROM plans ORDER BY plan_id ASC")
        rows = cursor.fetchall()
        return [_row_to_plan(r) for r in rows]

    def save(self, plan: Plan) -> Plan:
        if plan.plan_id is not None:
            cursor = self.conn.execute(
                "SELECT plan_id FROM plans WHERE plan_id = ?",
                (plan.plan_id,),
            )
            if cursor.fetchone():
                self.conn.execute(
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
                self.conn.commit()
                return self.find_by_id(plan.plan_id) or plan
            raise EntityNotFoundError(entity_name="Plan", entity_id=plan.plan_id)

        cursor = self.conn.execute(
            """
            INSERT INTO plans (name, monthly_price, max_profiles)
            VALUES (?, ?, ?)
            """,
            (plan.name, plan.monthly_price, plan.max_profiles),
        )
        self.conn.commit()
        new_id = cursor.lastrowid
        if new_id is not None:
            return self.find_by_id(new_id) or plan
        return plan


__all__ = ["SQLitePlanRepository"]
