"""
Message handler implementation with Claude API integration for classification.
"""
import logging
from typing import Optional
from anthropic import Anthropic

from ...services.database.typex import IDatabaseService, EvaluationModel, ClassificationModel

logger = logging.getLogger(__name__)


class MessageHandler:
    """
    Message handler implementation.
    Implements the IMessageHandler protocol.
    """

    def __init__(self, db_service: IDatabaseService, anthropic_api_key: str):
        """
        Initialize the message handler.

        Args:
            db_service: Database service instance
            anthropic_api_key: Anthropic API key for Claude
        """
        self.db_service = db_service
        self.client = Anthropic(api_key=anthropic_api_key)

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
        try:
            evaluation = EvaluationModel(
                team_id=team_id,
                evaluator_id=evaluator_id,
                recipient_id=recipient_id,
                message=message,
                status="queued"
            )

            evaluation_id = await self.db_service.create_evaluation(evaluation)
            logger.info(f"Message enqueued with evaluation ID: {evaluation_id}")
            return evaluation_id

        except Exception as e:
            logger.error(f"Failed to enqueue message: {e}")
            raise

    async def process(self, evaluation_id: int) -> bool:
        """
        Process a single evaluation message.
        Classifies the message using Claude API and updates the database.

        Args:
            evaluation_id: The ID of the evaluation to process

        Returns:
            True if successful, False otherwise
        """
        try:
            # Get the evaluation
            evaluation = await self.db_service.get_evaluation(evaluation_id)
            if not evaluation:
                logger.error(f"Evaluation {evaluation_id} not found")
                return False

            # Get classifications for the team
            classifications = await self.db_service.get_classifications_for_team(
                evaluation.team_id
            )

            if not classifications:
                logger.error(f"No classifications found for team {evaluation.team_id}")
                await self.db_service.update_evaluation_status(
                    evaluation_id,
                    status="failed",
                    error_message="No classifications configured for this team"
                )
                return False

            # Classify the message using Claude API
            classification, weight = await self._classify_message(
                evaluation.message,
                classifications
            )

            if classification:
                # Update evaluation with classification result
                await self.db_service.update_evaluation_status(
                    evaluation_id,
                    status="completed",
                    classification=classification,
                    weight=weight
                )
                logger.info(
                    f"Evaluation {evaluation_id} classified as '{classification}' "
                    f"with weight {weight}"
                )
                return True
            else:
                # Classification failed
                await self.db_service.update_evaluation_status(
                    evaluation_id,
                    status="failed",
                    error_message="Failed to classify message"
                )
                logger.error(f"Failed to classify evaluation {evaluation_id}")
                return False

        except Exception as e:
            logger.error(f"Error processing evaluation {evaluation_id}: {e}")
            try:
                await self.db_service.update_evaluation_status(
                    evaluation_id,
                    status="failed",
                    error_message=str(e)
                )
            except:
                pass
            return False

    async def _classify_message(
        self,
        message: str,
        classifications: list[ClassificationModel]
    ) -> tuple[Optional[str], Optional[int]]:
        """
        Classify a message using Claude API.

        Args:
            message: The message to classify
            classifications: Available classifications for the team

        Returns:
            Tuple of (classification_name, weight) or (None, None) if failed
        """
        try:
            # Build classification options for the prompt
            classification_options = ", ".join([
                f"'{c.name}' (weight: {c.weight})"
                for c in classifications
            ])

            # Build the prompt for Claude
            prompt = f"""You are analyzing an evaluation message about a child's behavior. The message can be in either English or Arabic.

Your task is to classify the sentiment and tone of this message into one of these categories:
{classification_options}

The message to classify is:
"{message}"

Please respond with ONLY the classification name from the list above (e.g., "good", "bad", "superb", etc.), without any additional text or explanation. Choose the classification that best matches the sentiment expressed in the message."""

            # Call Claude API
            response = self.client.messages.create(
                model="claude-sonnet-4-6",
                max_tokens=4096,
                temperature=0,
                messages=[
                    {
                        "role": "user",
                        "content": prompt
                    }
                ]
            )

            # Extract the classification from response
            if response.content and len(response.content) > 0:
                classification_name = response.content[0].text.strip().lower()

                # Find the matching classification and get its weight
                for classification in classifications:
                    if classification.name.lower() == classification_name:
                        return classification.name, classification.weight

                # If exact match not found, log the response and try partial matching
                logger.warning(
                    f"Exact classification match not found. "
                    f"Claude returned: '{classification_name}'"
                )

                # Try partial matching (in case Claude added extra words)
                for classification in classifications:
                    if classification.name.lower() in classification_name:
                        logger.info(
                            f"Using partial match: '{classification.name}' "
                            f"from '{classification_name}'"
                        )
                        return classification.name, classification.weight

                logger.error(
                    f"Could not match classification '{classification_name}' "
                    f"to any available option"
                )
                return None, None

            logger.error("Empty response from Claude API")
            return None, None

        except Exception as e:
            logger.error(f"Error calling Claude API: {e}")
            return None, None
