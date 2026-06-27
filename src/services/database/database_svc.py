"""
Database service implementation using PostgreSQL.
"""
import os
import logging
from datetime import date, datetime
from typing import Optional, List
from contextlib import asynccontextmanager
import psycopg2
from psycopg2 import pool
from psycopg2.extras import RealDictCursor

from .typex import (
    TeamModel,
    RecipientModel,
    EvaluatorModel,
    ClassificationModel,
    EvaluationModel,
    StatsModel,
)

logger = logging.getLogger(__name__)


class DatabaseService:
    """
    PostgreSQL database service implementation.
    Implements the IDatabaseService protocol.
    """

    def __init__(self, database_url: str, min_conn: int = 2, max_conn: int = 10):
        """
        Initialize the database service.

        Args:
            database_url: PostgreSQL connection URL
            min_conn: Minimum number of connections in the pool
            max_conn: Maximum number of connections in the pool
        """
        self.database_url = database_url
        self.min_conn = min_conn
        self.max_conn = max_conn
        self.connection_pool: Optional[pool.ThreadedConnectionPool] = None

    async def connect(self) -> None:
        """Create a connection pool to the database."""
        try:
            self.connection_pool = psycopg2.pool.ThreadedConnectionPool(
                self.min_conn,
                self.max_conn,
                self.database_url
            )
            logger.info("Database connection pool created successfully")
        except Exception as e:
            logger.error(f"Failed to create connection pool: {e}")
            raise

    async def disconnect(self) -> None:
        """Close all connections in the pool."""
        if self.connection_pool:
            self.connection_pool.closeall()
            logger.info("Database connection pool closed")

    @asynccontextmanager
    async def _get_connection(self):
        """Context manager for getting a connection from the pool."""
        if not self.connection_pool:
            raise RuntimeError("Database connection pool not initialized")

        conn = self.connection_pool.getconn()
        try:
            yield conn
        finally:
            self.connection_pool.putconn(conn)

    # ========================================================================
    # Team Operations
    # ========================================================================

    async def create_team(self, team: TeamModel) -> int:
        """Create a new team with all related entities."""
        async with self._get_connection() as conn:
            cursor = conn.cursor()
            try:
                # Insert team
                cursor.execute(
                    """
                    INSERT INTO teams (name_ar, name_en, timezone)
                    VALUES (%s, %s, %s)
                    RETURNING id
                    """,
                    (team.name_ar, team.name_en, team.timezone)
                )
                team_id = cursor.fetchone()[0]

                # Insert recipients
                for recipient in team.recipients:
                    cursor.execute(
                        """
                        INSERT INTO recipients (team_id, name_ar, name_en, date_of_birth)
                        VALUES (%s, %s, %s, %s)
                        """,
                        (team_id, recipient.name_ar, recipient.name_en, recipient.date_of_birth)
                    )

                # Insert evaluators
                for evaluator in team.evaluators:
                    cursor.execute(
                        """
                        INSERT INTO evaluators (team_id, name_ar, name_en, device_id)
                        VALUES (%s, %s, %s, %s)
                        """,
                        (team_id, evaluator.name_ar, evaluator.name_en, evaluator.device_id)
                    )

                # Insert classifications
                for classification in team.classifications:
                    cursor.execute(
                        """
                        INSERT INTO classifications (team_id, name, weight)
                        VALUES (%s, %s, %s)
                        """,
                        (team_id, classification.name, classification.weight)
                    )

                conn.commit()
                logger.info(f"Team created successfully with ID: {team_id}")
                return team_id

            except Exception as e:
                conn.rollback()
                logger.error(f"Failed to create team: {e}")
                raise
            finally:
                cursor.close()

    async def get_team(self, team_id: int) -> Optional[TeamModel]:
        """Get a team by ID with all related entities."""
        async with self._get_connection() as conn:
            cursor = conn.cursor(cursor_factory=RealDictCursor)
            try:
                # Get team
                cursor.execute(
                    "SELECT * FROM teams WHERE id = %s",
                    (team_id,)
                )
                team_row = cursor.fetchone()
                if not team_row:
                    return None

                # Get recipients
                cursor.execute(
                    "SELECT * FROM recipients WHERE team_id = %s",
                    (team_id,)
                )
                recipients = [RecipientModel(**row) for row in cursor.fetchall()]

                # Get evaluators
                cursor.execute(
                    "SELECT * FROM evaluators WHERE team_id = %s",
                    (team_id,)
                )
                evaluators = [EvaluatorModel(**row) for row in cursor.fetchall()]

                # Get classifications
                cursor.execute(
                    "SELECT * FROM classifications WHERE team_id = %s",
                    (team_id,)
                )
                classifications = [ClassificationModel(**row) for row in cursor.fetchall()]

                # Build team model
                team = TeamModel(
                    **team_row,
                    recipients=recipients,
                    evaluators=evaluators,
                    classifications=classifications
                )
                return team

            except Exception as e:
                logger.error(f"Failed to get team {team_id}: {e}")
                raise
            finally:
                cursor.close()

    async def get_all_teams(self) -> List[TeamModel]:
        """Get all teams with their related entities."""
        async with self._get_connection() as conn:
            cursor = conn.cursor(cursor_factory=RealDictCursor)
            try:
                cursor.execute("SELECT id FROM teams ORDER BY created_at DESC")
                team_ids = [row['id'] for row in cursor.fetchall()]

                teams = []
                for team_id in team_ids:
                    team = await self.get_team(team_id)
                    if team:
                        teams.append(team)

                return teams

            except Exception as e:
                logger.error(f"Failed to get all teams: {e}")
                raise
            finally:
                cursor.close()

    async def update_team(self, team_id: int, team: TeamModel) -> bool:
        """
        Update a team and intelligently merge its related entities.
        This preserves existing records (and their evaluations) when possible.
        """
        async with self._get_connection() as conn:
            cursor = conn.cursor(cursor_factory=RealDictCursor)
            try:
                # Update team
                cursor.execute(
                    """
                    UPDATE teams
                    SET name_ar = %s, name_en = %s, timezone = %s
                    WHERE id = %s
                    """,
                    (team.name_ar, team.name_en, team.timezone, team_id)
                )

                # ============================================================
                # Recipients: Match by name_en (preserve IDs to keep evaluations)
                # ============================================================

                # Get existing recipients
                cursor.execute(
                    "SELECT * FROM recipients WHERE team_id = %s",
                    (team_id,)
                )
                existing_recipients = {row['name_en']: row for row in cursor.fetchall()}

                # Track which ones to keep
                new_recipient_names = {r.name_en for r in team.recipients}

                # Update or insert recipients
                for recipient in team.recipients:
                    if recipient.name_en in existing_recipients:
                        # Update existing recipient
                        cursor.execute(
                            """
                            UPDATE recipients
                            SET name_ar = %s, date_of_birth = %s
                            WHERE id = %s
                            """,
                            (recipient.name_ar, recipient.date_of_birth,
                             existing_recipients[recipient.name_en]['id'])
                        )
                    else:
                        # Insert new recipient
                        cursor.execute(
                            """
                            INSERT INTO recipients (team_id, name_ar, name_en, date_of_birth)
                            VALUES (%s, %s, %s, %s)
                            """,
                            (team_id, recipient.name_ar, recipient.name_en, recipient.date_of_birth)
                        )

                # Delete recipients that are no longer in the team
                for name_en, existing in existing_recipients.items():
                    if name_en not in new_recipient_names:
                        cursor.execute(
                            "DELETE FROM recipients WHERE id = %s",
                            (existing['id'],)
                        )

                # ============================================================
                # Evaluators: Match by device_id (preserve IDs to keep evaluations)
                # ============================================================

                # Get existing evaluators
                cursor.execute(
                    "SELECT * FROM evaluators WHERE team_id = %s",
                    (team_id,)
                )
                existing_evaluators = {row['device_id']: row for row in cursor.fetchall()}

                # Track which ones to keep
                new_device_ids = {e.device_id for e in team.evaluators}

                # Update or insert evaluators
                for evaluator in team.evaluators:
                    if evaluator.device_id in existing_evaluators:
                        # Update existing evaluator
                        cursor.execute(
                            """
                            UPDATE evaluators
                            SET name_ar = %s, name_en = %s
                            WHERE id = %s
                            """,
                            (evaluator.name_ar, evaluator.name_en,
                             existing_evaluators[evaluator.device_id]['id'])
                        )
                    else:
                        # Insert new evaluator
                        cursor.execute(
                            """
                            INSERT INTO evaluators (team_id, name_ar, name_en, device_id)
                            VALUES (%s, %s, %s, %s)
                            """,
                            (team_id, evaluator.name_ar, evaluator.name_en, evaluator.device_id)
                        )

                # Delete evaluators that are no longer in the team
                for device_id, existing in existing_evaluators.items():
                    if device_id not in new_device_ids:
                        cursor.execute(
                            "DELETE FROM evaluators WHERE id = %s",
                            (existing['id'],)
                        )

                # ============================================================
                # Classifications: Match by name (these don't link to evaluations)
                # ============================================================

                # Get existing classifications
                cursor.execute(
                    "SELECT * FROM classifications WHERE team_id = %s",
                    (team_id,)
                )
                existing_classifications = {row['name']: row for row in cursor.fetchall()}

                # Track which ones to keep
                new_classification_names = {c.name for c in team.classifications}

                # Update or insert classifications
                for classification in team.classifications:
                    if classification.name in existing_classifications:
                        # Update existing classification (weight might change)
                        cursor.execute(
                            """
                            UPDATE classifications
                            SET weight = %s
                            WHERE id = %s
                            """,
                            (classification.weight,
                             existing_classifications[classification.name]['id'])
                        )
                    else:
                        # Insert new classification
                        cursor.execute(
                            """
                            INSERT INTO classifications (team_id, name, weight)
                            VALUES (%s, %s, %s)
                            """,
                            (team_id, classification.name, classification.weight)
                        )

                # Delete classifications that are no longer in the team
                for name, existing in existing_classifications.items():
                    if name not in new_classification_names:
                        cursor.execute(
                            "DELETE FROM classifications WHERE id = %s",
                            (existing['id'],)
                        )

                conn.commit()
                logger.info(f"Team {team_id} updated successfully (preserving evaluations)")
                return True

            except Exception as e:
                conn.rollback()
                logger.error(f"Failed to update team {team_id}: {e}")
                raise
            finally:
                cursor.close()

    async def delete_team(self, team_id: int) -> bool:
        """Delete a team (cascade deletes related entities)."""
        async with self._get_connection() as conn:
            cursor = conn.cursor()
            try:
                cursor.execute("DELETE FROM teams WHERE id = %s", (team_id,))
                conn.commit()
                logger.info(f"Team {team_id} deleted successfully")
                return True
            except Exception as e:
                conn.rollback()
                logger.error(f"Failed to delete team {team_id}: {e}")
                raise
            finally:
                cursor.close()

    # ========================================================================
    # Evaluator Operations
    # ========================================================================

    async def get_evaluator_by_device_id(self, device_id: str) -> Optional[EvaluatorModel]:
        """Get an evaluator by device ID."""
        async with self._get_connection() as conn:
            cursor = conn.cursor(cursor_factory=RealDictCursor)
            try:
                cursor.execute(
                    "SELECT * FROM evaluators WHERE device_id = %s",
                    (device_id,)
                )
                row = cursor.fetchone()
                return EvaluatorModel(**row) if row else None
            except Exception as e:
                logger.error(f"Failed to get evaluator by device_id {device_id}: {e}")
                raise
            finally:
                cursor.close()

    async def get_evaluator(self, evaluator_id: int) -> Optional[EvaluatorModel]:
        """Get an evaluator by ID."""
        async with self._get_connection() as conn:
            cursor = conn.cursor(cursor_factory=RealDictCursor)
            try:
                cursor.execute(
                    "SELECT * FROM evaluators WHERE id = %s",
                    (evaluator_id,)
                )
                row = cursor.fetchone()
                return EvaluatorModel(**row) if row else None
            except Exception as e:
                logger.error(f"Failed to get evaluator {evaluator_id}: {e}")
                raise
            finally:
                cursor.close()

    # ========================================================================
    # Recipient Operations
    # ========================================================================

    async def get_recipient_by_name(self, team_id: int, name: str) -> Optional[RecipientModel]:
        """Get a recipient by name (English or Arabic) within a team."""
        async with self._get_connection() as conn:
            cursor = conn.cursor(cursor_factory=RealDictCursor)
            try:
                cursor.execute(
                    """
                    SELECT * FROM recipients
                    WHERE team_id = %s AND (name_en = %s OR name_ar = %s)
                    """,
                    (team_id, name, name)
                )
                row = cursor.fetchone()
                return RecipientModel(**row) if row else None
            except Exception as e:
                logger.error(f"Failed to get recipient by name {name}: {e}")
                raise
            finally:
                cursor.close()

    async def get_recipient(self, recipient_id: int) -> Optional[RecipientModel]:
        """Get a recipient by ID."""
        async with self._get_connection() as conn:
            cursor = conn.cursor(cursor_factory=RealDictCursor)
            try:
                cursor.execute(
                    "SELECT * FROM recipients WHERE id = %s",
                    (recipient_id,)
                )
                row = cursor.fetchone()
                return RecipientModel(**row) if row else None
            except Exception as e:
                logger.error(f"Failed to get recipient {recipient_id}: {e}")
                raise
            finally:
                cursor.close()

    # ========================================================================
    # Classification Operations
    # ========================================================================

    async def get_classifications_for_team(self, team_id: int) -> List[ClassificationModel]:
        """Get all classifications for a team."""
        async with self._get_connection() as conn:
            cursor = conn.cursor(cursor_factory=RealDictCursor)
            try:
                cursor.execute(
                    "SELECT * FROM classifications WHERE team_id = %s ORDER BY weight DESC",
                    (team_id,)
                )
                return [ClassificationModel(**row) for row in cursor.fetchall()]
            except Exception as e:
                logger.error(f"Failed to get classifications for team {team_id}: {e}")
                raise
            finally:
                cursor.close()

    # ========================================================================
    # Evaluation Operations
    # ========================================================================

    async def create_evaluation(self, evaluation: EvaluationModel) -> int:
        """Create a new evaluation."""
        async with self._get_connection() as conn:
            cursor = conn.cursor()
            try:
                cursor.execute(
                    """
                    INSERT INTO evaluations (
                        team_id, recipient_id, evaluator_id, message, status
                    )
                    VALUES (%s, %s, %s, %s, %s)
                    RETURNING id
                    """,
                    (
                        evaluation.team_id,
                        evaluation.recipient_id,
                        evaluation.evaluator_id,
                        evaluation.message,
                        evaluation.status
                    )
                )
                evaluation_id = cursor.fetchone()[0]
                conn.commit()
                logger.info(f"Evaluation created with ID: {evaluation_id}")
                return evaluation_id
            except Exception as e:
                conn.rollback()
                logger.error(f"Failed to create evaluation: {e}")
                raise
            finally:
                cursor.close()

    async def get_evaluation(self, evaluation_id: int) -> Optional[EvaluationModel]:
        """Get an evaluation by ID."""
        async with self._get_connection() as conn:
            cursor = conn.cursor(cursor_factory=RealDictCursor)
            try:
                cursor.execute(
                    "SELECT * FROM evaluations WHERE id = %s",
                    (evaluation_id,)
                )
                row = cursor.fetchone()
                return EvaluationModel(**row) if row else None
            except Exception as e:
                logger.error(f"Failed to get evaluation {evaluation_id}: {e}")
                raise
            finally:
                cursor.close()

    async def get_evaluations_for_recipient(
        self,
        team_id: int,
        recipient_id: int,
        start_date: date,
        end_date: date
    ) -> List[EvaluationModel]:
        """Get evaluations for a recipient within a date range."""
        async with self._get_connection() as conn:
            cursor = conn.cursor(cursor_factory=RealDictCursor)
            try:
                cursor.execute(
                    """
                    SELECT * FROM evaluations
                    WHERE team_id = %s
                    AND recipient_id = %s
                    AND DATE(reception_timestamp) BETWEEN %s AND %s
                    ORDER BY reception_timestamp ASC
                    """,
                    (team_id, recipient_id, start_date, end_date)
                )
                return [EvaluationModel(**row) for row in cursor.fetchall()]
            except Exception as e:
                logger.error(f"Failed to get evaluations for recipient {recipient_id}: {e}")
                raise
            finally:
                cursor.close()

    async def get_queued_evaluations(self, worker_id: str, limit: int = 10) -> List[EvaluationModel]:
        """
        Get queued evaluations and atomically mark them as processing.
        Uses SELECT FOR UPDATE to lock rows and prevent race conditions.
        """
        async with self._get_connection() as conn:
            cursor = conn.cursor(cursor_factory=RealDictCursor)
            try:
                # Lock and update queued messages atomically
                cursor.execute(
                    """
                    UPDATE evaluations
                    SET status = 'processing', worker_id = %s
                    WHERE id IN (
                        SELECT id FROM evaluations
                        WHERE status = 'queued'
                        ORDER BY reception_timestamp ASC
                        LIMIT %s
                        FOR UPDATE SKIP LOCKED
                    )
                    RETURNING *
                    """,
                    (worker_id, limit)
                )
                evaluations = [EvaluationModel(**row) for row in cursor.fetchall()]
                conn.commit()
                logger.info(f"Worker {worker_id} acquired {len(evaluations)} evaluations")
                return evaluations
            except Exception as e:
                conn.rollback()
                logger.error(f"Failed to get queued evaluations: {e}")
                raise
            finally:
                cursor.close()

    async def update_evaluation_status(
        self,
        evaluation_id: int,
        status: str,
        classification: Optional[str] = None,
        weight: Optional[int] = None,
        error_message: Optional[str] = None
    ) -> bool:
        """Update the status and classification of an evaluation."""
        async with self._get_connection() as conn:
            cursor = conn.cursor()
            try:
                cursor.execute(
                    """
                    UPDATE evaluations
                    SET status = %s,
                        classification = %s,
                        weight = %s,
                        error_message = %s,
                        process_timestamp = CURRENT_TIMESTAMP
                    WHERE id = %s
                    """,
                    (status, classification, weight, error_message, evaluation_id)
                )
                conn.commit()
                logger.info(f"Evaluation {evaluation_id} status updated to {status}")
                return True
            except Exception as e:
                conn.rollback()
                logger.error(f"Failed to update evaluation {evaluation_id}: {e}")
                raise
            finally:
                cursor.close()

    # ========================================================================
    # Statistics
    # ========================================================================

    async def get_stats(self) -> StatsModel:
        """Get system statistics."""
        async with self._get_connection() as conn:
            cursor = conn.cursor()
            try:
                cursor.execute("SELECT COUNT(*) FROM teams")
                total_teams = cursor.fetchone()[0]

                cursor.execute("SELECT COUNT(*) FROM recipients")
                total_recipients = cursor.fetchone()[0]

                cursor.execute("SELECT COUNT(*) FROM evaluators")
                total_evaluators = cursor.fetchone()[0]

                cursor.execute("SELECT COUNT(*) FROM evaluations")
                total_evaluations = cursor.fetchone()[0]

                cursor.execute("SELECT COUNT(*) FROM evaluations WHERE status = 'queued'")
                queued_evaluations = cursor.fetchone()[0]

                cursor.execute("SELECT COUNT(*) FROM evaluations WHERE status = 'processing'")
                processing_evaluations = cursor.fetchone()[0]

                cursor.execute("SELECT COUNT(*) FROM evaluations WHERE status = 'completed'")
                completed_evaluations = cursor.fetchone()[0]

                cursor.execute("SELECT COUNT(*) FROM evaluations WHERE status = 'failed'")
                failed_evaluations = cursor.fetchone()[0]

                return StatsModel(
                    total_teams=total_teams,
                    total_recipients=total_recipients,
                    total_evaluators=total_evaluators,
                    total_evaluations=total_evaluations,
                    queued_evaluations=queued_evaluations,
                    processing_evaluations=processing_evaluations,
                    completed_evaluations=completed_evaluations,
                    failed_evaluations=failed_evaluations
                )
            except Exception as e:
                logger.error(f"Failed to get stats: {e}")
                raise
            finally:
                cursor.close()
