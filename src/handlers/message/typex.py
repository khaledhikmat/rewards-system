"""
Message handler type definitions and protocols.
"""
from typing import Protocol


class IMessageHandler(Protocol):
    """Protocol defining the message handler interface."""

    async def enqueue(
        self,
        team_id: int,
        evaluator_id: int,
        recipient_id: int,
        message: str
    ) -> int:
        """
        Enqueue a message for processing.

        Args:
            team_id: The team ID
            evaluator_id: The evaluator ID
            recipient_id: The recipient ID
            message: The evaluation message text

        Returns:
            The evaluation ID
        """
        ...

    async def process(self, evaluation_id: int) -> bool:
        """
        Process a single evaluation message.
        Classifies the message using Claude API and updates the database.

        Args:
            evaluation_id: The ID of the evaluation to process

        Returns:
            True if successful, False otherwise
        """
        ...
