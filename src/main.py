"""
Main entry point for the Rewards System Processor.
This module handles:
- HTTP API endpoints for team management
- Telegram webhook processing
- Admin dashboard serving
"""
import os
import logging
import asyncio
from contextlib import asynccontextmanager
from dotenv import load_dotenv
import uvicorn
from fastapi import FastAPI

from .services.database.database_svc import DatabaseService
from .handlers.message.message_handler import MessageHandler
from .handlers.telegram.telegram_handler import TelegramHandler
from .handlers.http.http_handler import HttpHandler

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
API_KEY = os.getenv("API_KEY")
ADMIN_USERNAME = os.getenv("ADMIN_USERNAME")
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD")
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_WEBHOOK_URL = os.getenv("TELEGRAM_WEBHOOK_URL")
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")
APP_HOST = os.getenv("APP_HOST", "0.0.0.0")
APP_PORT = int(os.getenv("APP_PORT", "8000"))

# Validate required environment variables
required_vars = {
    "DATABASE_URL": DATABASE_URL,
    "API_KEY": API_KEY,
    "ADMIN_USERNAME": ADMIN_USERNAME,
    "ADMIN_PASSWORD": ADMIN_PASSWORD,
    "TELEGRAM_BOT_TOKEN": TELEGRAM_BOT_TOKEN,
    "TELEGRAM_WEBHOOK_URL": TELEGRAM_WEBHOOK_URL,
    "ANTHROPIC_API_KEY": ANTHROPIC_API_KEY,
}

missing_vars = [name for name, value in required_vars.items() if not value]
if missing_vars:
    raise RuntimeError(
        f"Missing required environment variables: {', '.join(missing_vars)}"
    )

# Global service instances
db_service = None
message_handler = None
telegram_handler = None
http_handler = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifespan context manager for startup and shutdown events."""
    global db_service, message_handler, telegram_handler, http_handler

    logger.info("Starting Rewards System Processor...")

    # Initialize database service
    logger.info("Initializing database service...")
    db_service = DatabaseService(DATABASE_URL)
    await db_service.connect()

    # Initialize message handler
    logger.info("Initializing message handler...")
    message_handler = MessageHandler(db_service, ANTHROPIC_API_KEY)

    # Initialize Telegram handler
    logger.info("Initializing Telegram handler...")
    telegram_handler = TelegramHandler(
        TELEGRAM_BOT_TOKEN,
        db_service,
        message_handler
    )
    await telegram_handler.initialize()

    # Set Telegram webhook
    logger.info(f"Setting Telegram webhook to: {TELEGRAM_WEBHOOK_URL}")
    webhook_set = await telegram_handler.set_webhook(TELEGRAM_WEBHOOK_URL)
    if not webhook_set:
        logger.warning("Failed to set Telegram webhook")

    # Update http_handler with initialized services
    if http_handler:
        http_handler.db_service = db_service
        http_handler.telegram_handler = telegram_handler

    logger.info("Rewards System Processor started successfully")

    yield

    # Cleanup on shutdown
    logger.info("Shutting down Rewards System Processor...")

    # Note: We don't delete the Telegram webhook on shutdown.
    # Webhooks should persist across service restarts.
    # Only delete manually if you need to switch to polling mode.

    # Disconnect from database
    if db_service:
        await db_service.disconnect()

    logger.info("Rewards System Processor shut down successfully")


def create_app() -> FastAPI:
    """Create and configure the FastAPI application."""
    global http_handler

    # Initialize HTTP handler with lifespan
    http_handler = HttpHandler(
        db_service=None,  # Will be set during lifespan
        telegram_handler=None,  # Will be set during lifespan
        api_key=API_KEY,
        admin_username=ADMIN_USERNAME,
        admin_password=ADMIN_PASSWORD,
        templates_dir="templates",
        lifespan=lifespan
    )

    # Get the FastAPI app with routes and lifespan configured
    return http_handler.get_app()


# Create the application
app = create_app()


def main():
    """Main entry point."""
    logger.info(f"Starting server on {APP_HOST}:{APP_PORT}")

    # Run the application
    # Note: Pass app object directly (not module string) when using python -m
    uvicorn.run(
        app,
        host=APP_HOST,
        port=APP_PORT,
        log_level=os.getenv("LOG_LEVEL", "info").lower()
    )


if __name__ == "__main__":
    main()
