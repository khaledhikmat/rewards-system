"""
Batch processor for the Rewards System.
This module handles:
- Dequeuing messages from the database
- Processing messages using the message handler
- Updating message status

This script is designed to run as a cron job.
"""
import os
import logging
import asyncio
from datetime import datetime
from dotenv import load_dotenv

from .services.database.database_svc import DatabaseService
from .handlers.message.message_handler import MessageHandler

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(
    level=os.getenv("LOG_LEVEL", "INFO"),
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# Get environment variables
DATABASE_URL = os.getenv("DATABASE_URL")
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")
WORKER_ID = os.getenv("WORKER_ID", "worker-1")
BATCH_SIZE = int(os.getenv("BATCH_SIZE", "10"))

# Validate required environment variables
if not DATABASE_URL:
    raise RuntimeError("Missing required environment variable: DATABASE_URL")
if not ANTHROPIC_API_KEY:
    raise RuntimeError("Missing required environment variable: ANTHROPIC_API_KEY")


async def process_batch():
    """
    Main batch processing function.
    Dequeues messages and processes them.
    """
    db_service = None
    message_handler = None

    try:
        logger.info(f"Starting batch processor with worker ID: {WORKER_ID}")
        logger.info(f"Batch size: {BATCH_SIZE}")

        # Initialize database service
        logger.info("Connecting to database...")
        db_service = DatabaseService(DATABASE_URL)
        await db_service.connect()

        # Initialize message handler
        logger.info("Initializing message handler...")
        message_handler = MessageHandler(db_service, ANTHROPIC_API_KEY)

        # Get queued evaluations
        logger.info("Fetching queued evaluations...")
        evaluations = await db_service.get_queued_evaluations(WORKER_ID, BATCH_SIZE)

        if not evaluations:
            logger.info("No queued evaluations found")
            return

        logger.info(f"Processing {len(evaluations)} evaluations...")

        # Process each evaluation
        processed_count = 0
        failed_count = 0

        for evaluation in evaluations:
            try:
                logger.info(f"Processing evaluation {evaluation.id}...")
                success = await message_handler.process(evaluation.id)

                if success:
                    processed_count += 1
                    logger.info(f"Successfully processed evaluation {evaluation.id}")
                else:
                    failed_count += 1
                    logger.error(f"Failed to process evaluation {evaluation.id}")

            except Exception as e:
                failed_count += 1
                logger.error(f"Error processing evaluation {evaluation.id}: {e}")

        # Log summary
        logger.info(
            f"Batch processing complete. "
            f"Processed: {processed_count}, Failed: {failed_count}, "
            f"Total: {len(evaluations)}"
        )

    except Exception as e:
        logger.error(f"Error in batch processing: {e}")
        raise

    finally:
        # Cleanup
        if db_service:
            logger.info("Disconnecting from database...")
            await db_service.disconnect()

        logger.info("Batch processor finished")


def main():
    """Main entry point."""
    start_time = datetime.now()
    logger.info(f"Batch processor started at {start_time}")

    try:
        # Run the batch processing
        asyncio.run(process_batch())

    except Exception as e:
        logger.error(f"Fatal error in batch processor: {e}")
        raise

    finally:
        end_time = datetime.now()
        duration = (end_time - start_time).total_seconds()
        logger.info(f"Batch processor completed in {duration:.2f} seconds")


if __name__ == "__main__":
    main()
