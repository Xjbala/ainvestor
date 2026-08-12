# -*- coding: utf-8 -*-
"""历史分析会话删除契约测试。"""

import asyncio
import os
import sys
import unittest
from datetime import datetime

from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.persistence.orm_models import (
    AgentOutput,
    AgentPhase,
    AnalysisSession,
    RatingReport,
    SessionStatus,
)
from backend.persistence.db import Base


class TestAnalysisSessionDeletion(unittest.TestCase):
    def test_relationships_cascade_outputs_and_report(self):
        engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(
            engine,
            tables=[
                AnalysisSession.__table__,
                AgentOutput.__table__,
                RatingReport.__table__,
            ],
        )
        try:
            with Session(engine) as session:
                analysis = AnalysisSession(
                    id="session-delete",
                    tickers='["603137"]',
                    date="2026-08-11",
                    status=SessionStatus.COMPLETED,
                    completed_at=datetime.now(),
                )
                analysis.outputs.append(
                    AgentOutput(
                        agent_id="fundamentals_analyst",
                        agent_type="analyst",
                        phase=AgentPhase.ANALYSIS,
                        content="done",
                    )
                )
                analysis.report = RatingReport(
                    report_content="# report",
                    recommendations=None,
                )
                session.add(analysis)
                session.commit()

                session.delete(analysis)
                session.commit()

                self.assertIsNone(
                    session.scalar(
                        select(AnalysisSession).where(AnalysisSession.id == "session-delete")
                    )
                )
                self.assertEqual(0, session.query(AgentOutput).count())
                self.assertEqual(0, session.query(RatingReport).count())
        finally:
            engine.dispose()
    def test_cancelled_session_can_be_deleted_with_related_records(self):
        engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(
            engine,
            tables=[
                AnalysisSession.__table__,
                AgentOutput.__table__,
                RatingReport.__table__,
            ],
        )
        try:
            with Session(engine) as session:
                analysis = AnalysisSession(
                    id="session-cancelled",
                    tickers='["603137"]',
                    date="2026-08-11",
                    status=SessionStatus.CANCELLED,
                    completed_at=datetime.now(),
                )
                analysis.outputs.append(
                    AgentOutput(
                        agent_id="fundamentals_analyst",
                        agent_type="analyst",
                        phase=AgentPhase.ANALYSIS,
                        content="partial output",
                    )
                )
                session.add(analysis)
                session.commit()

                session.delete(analysis)
                session.commit()

                self.assertIsNone(
                    session.scalar(
                        select(AnalysisSession).where(AnalysisSession.id == "session-cancelled")
                    )
                )
                self.assertEqual(0, session.query(AgentOutput).count())
        finally:
            engine.dispose()


if __name__ == "__main__":
    unittest.main()
