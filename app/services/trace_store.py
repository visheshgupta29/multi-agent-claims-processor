"""Trace storage — SQLite-based persistence for claim traces."""

from __future__ import annotations

import json
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Optional

from app.models.claim import ClaimDecision, ClaimTrace
from app.config import settings


class TraceStore:
    """SQLite-backed store for claim decisions and traces."""

    def __init__(self, db_path: str = None):
        self.db_path = db_path or settings.database_path
        Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _init_db(self):
        """Create tables if they don't exist."""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS claims (
                    claim_id TEXT PRIMARY KEY,
                    member_id TEXT NOT NULL,
                    claim_category TEXT NOT NULL,
                    claimed_amount REAL NOT NULL,
                    decision TEXT,
                    approved_amount REAL,
                    confidence_score REAL,
                    explanation TEXT,
                    error_message TEXT,
                    trace_json TEXT,
                    full_decision_json TEXT,
                    created_at TEXT NOT NULL
                )
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_claims_member
                ON claims(member_id)
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_claims_created
                ON claims(created_at)
            """)

    def save_decision(self, decision: ClaimDecision, request_data: dict = None):
        """Save a claim decision and its trace."""
        trace_json = decision.trace.model_dump_json() if decision.trace else None
        full_json = decision.model_dump_json()

        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                INSERT OR REPLACE INTO claims
                (claim_id, member_id, claim_category, claimed_amount, decision,
                 approved_amount, confidence_score, explanation, error_message,
                 trace_json, full_decision_json, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                decision.claim_id,
                decision.trace.member_id if decision.trace else "",
                decision.trace.claim_category if decision.trace else "",
                request_data.get("claimed_amount", 0) if request_data else 0,
                decision.decision.value if decision.decision else None,
                decision.approved_amount,
                decision.confidence_score,
                decision.explanation,
                decision.error_message,
                trace_json,
                full_json,
                datetime.utcnow().isoformat(),
            ))

    def get_decision(self, claim_id: str) -> Optional[dict]:
        """Retrieve a stored decision by claim ID."""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            row = conn.execute(
                "SELECT * FROM claims WHERE claim_id = ?", (claim_id,)
            ).fetchone()

            if row is None:
                return None

            result = dict(row)
            if result.get("full_decision_json"):
                result["decision_obj"] = json.loads(result["full_decision_json"])
            if result.get("trace_json"):
                result["trace_obj"] = json.loads(result["trace_json"])
            return result

    def get_trace(self, claim_id: str) -> Optional[dict]:
        """Retrieve just the trace for a claim."""
        with sqlite3.connect(self.db_path) as conn:
            row = conn.execute(
                "SELECT trace_json FROM claims WHERE claim_id = ?", (claim_id,)
            ).fetchone()

            if row and row[0]:
                return json.loads(row[0])
            return None

    def list_claims(self, member_id: str = None, limit: int = 50) -> list[dict]:
        """List recent claims, optionally filtered by member."""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            if member_id:
                rows = conn.execute(
                    "SELECT claim_id, member_id, claim_category, claimed_amount, decision, "
                    "approved_amount, confidence_score, created_at FROM claims "
                    "WHERE member_id = ? ORDER BY created_at DESC LIMIT ?",
                    (member_id, limit)
                ).fetchall()
            else:
                rows = conn.execute(
                    "SELECT claim_id, member_id, claim_category, claimed_amount, decision, "
                    "approved_amount, confidence_score, created_at FROM claims "
                    "ORDER BY created_at DESC LIMIT ?",
                    (limit,)
                ).fetchall()
            return [dict(r) for r in rows]


# Singleton
trace_store = TraceStore()
