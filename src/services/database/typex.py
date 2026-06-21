"""
Database service type definitions, protocols, and models.
"""
from datetime import date, datetime
from typing import Protocol, Optional, List
from pydantic import BaseModel


# ============================================================================
# Pydantic Models for Data Validation
# ============================================================================

class RecipientModel(BaseModel):
    """Model for a recipient (child)."""
    id: Optional[int] = None
    team_id: Optional[int] = None
    name_ar: str
    name_en: str
    date_of_birth: date
    created_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class EvaluatorModel(BaseModel):
    """Model for an evaluator (parent)."""
    id: Optional[int] = None
    team_id: Optional[int] = None
    name_ar: str
    name_en: str
    device_id: str
    created_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class ClassificationModel(BaseModel):
    """Model for a classification type."""
    id: Optional[int] = None
    team_id: Optional[int] = None
    name: str
    weight: int
    created_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class TeamModel(BaseModel):
    """Model for a team (family)."""
    id: Optional[int] = None
    name_ar: str
    name_en: str
    timezone: str = "UTC"  # IANA timezone (e.g., 'America/New_York', 'Asia/Dubai')
    recipients: List[RecipientModel] = []
    evaluators: List[EvaluatorModel] = []
    classifications: List[ClassificationModel] = []
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class EvaluationModel(BaseModel):
    """Model for an evaluation message."""
    id: Optional[int] = None
    team_id: int
    recipient_id: int
    evaluator_id: int
    message: str
    classification: Optional[str] = None
    weight: Optional[int] = None
    status: str = "queued"  # queued, processing, completed, failed
    worker_id: Optional[str] = None
    reception_timestamp: Optional[datetime] = None
    process_timestamp: Optional[datetime] = None
    error_message: Optional[str] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class StatsModel(BaseModel):
    """Model for system statistics."""
    total_teams: int
    total_recipients: int
    total_evaluators: int
    total_evaluations: int
    queued_evaluations: int
    processing_evaluations: int
    completed_evaluations: int
    failed_evaluations: int


# ============================================================================
# Database Service Protocol
# ============================================================================

class IDatabaseService(Protocol):
    """Protocol defining the database service interface."""

    async def connect(self) -> None:
        """Connect to the database."""
        ...

    async def disconnect(self) -> None:
        """Disconnect from the database."""
        ...

    # Team operations
    async def create_team(self, team: TeamModel) -> int:
        """Create a new team and return its ID."""
        ...

    async def get_team(self, team_id: int) -> Optional[TeamModel]:
        """Get a team by ID."""
        ...

    async def get_all_teams(self) -> List[TeamModel]:
        """Get all teams."""
        ...

    async def update_team(self, team_id: int, team: TeamModel) -> bool:
        """Update a team."""
        ...

    async def delete_team(self, team_id: int) -> bool:
        """Delete a team."""
        ...

    # Evaluator operations
    async def get_evaluator_by_device_id(self, device_id: str) -> Optional[EvaluatorModel]:
        """Get an evaluator by device ID."""
        ...

    async def get_evaluator(self, evaluator_id: int) -> Optional[EvaluatorModel]:
        """Get an evaluator by ID."""
        ...

    # Recipient operations
    async def get_recipient_by_name(self, team_id: int, name: str) -> Optional[RecipientModel]:
        """Get a recipient by name (English or Arabic) within a team."""
        ...

    async def get_recipient(self, recipient_id: int) -> Optional[RecipientModel]:
        """Get a recipient by ID."""
        ...

    # Classification operations
    async def get_classifications_for_team(self, team_id: int) -> List[ClassificationModel]:
        """Get all classifications for a team."""
        ...

    # Evaluation operations
    async def create_evaluation(self, evaluation: EvaluationModel) -> int:
        """Create a new evaluation and return its ID."""
        ...

    async def get_evaluation(self, evaluation_id: int) -> Optional[EvaluationModel]:
        """Get an evaluation by ID."""
        ...

    async def get_evaluations_for_recipient(
        self,
        team_id: int,
        recipient_id: int,
        start_date: date,
        end_date: date
    ) -> List[EvaluationModel]:
        """Get evaluations for a recipient within a date range."""
        ...

    async def get_queued_evaluations(self, worker_id: str, limit: int = 10) -> List[EvaluationModel]:
        """
        Get queued evaluations and mark them as processing with the given worker_id.
        This operation should be atomic to prevent multiple workers from processing the same message.
        """
        ...

    async def update_evaluation_status(
        self,
        evaluation_id: int,
        status: str,
        classification: Optional[str] = None,
        weight: Optional[int] = None,
        error_message: Optional[str] = None
    ) -> bool:
        """Update the status of an evaluation."""
        ...

    # Statistics
    async def get_stats(self) -> StatsModel:
        """Get system statistics."""
        ...
