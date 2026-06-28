"""
Telegram handler implementation with webhook support.
"""
import logging
from datetime import datetime, date, time, timedelta
from typing import Optional
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes
import pytz

from ...services.database.typex import IDatabaseService
from ..message.typex import IMessageHandler

logger = logging.getLogger(__name__)


class TelegramHandler:
    """
    Telegram handler implementation.
    Implements the ITelegramHandler protocol.
    """

    def __init__(
        self,
        bot_token: str,
        db_service: IDatabaseService,
        message_handler: IMessageHandler
    ):
        """
        Initialize the Telegram handler.

        Args:
            bot_token: Telegram bot token
            db_service: Database service instance
            message_handler: Message handler instance
        """
        self.bot_token = bot_token
        self.db_service = db_service
        self.message_handler = message_handler
        self.application: Optional[Application] = None

    async def initialize(self) -> None:
        """Initialize the Telegram bot application."""
        try:
            # Build the application
            self.application = Application.builder().token(self.bot_token).build()

            # Register command handlers
            self.application.add_handler(CommandHandler("eval", self._handle_eval))
            self.application.add_handler(CommandHandler("report", self._handle_report))
            self.application.add_handler(CommandHandler("help", self._handle_help))

            # Initialize the application
            await self.application.initialize()
            logger.info("Telegram bot initialized successfully")

        except Exception as e:
            logger.error(f"Failed to initialize Telegram bot: {e}")
            raise

    async def handle_webhook(self, update_data: dict) -> None:
        """
        Handle incoming webhook updates from Telegram.

        Args:
            update_data: The webhook update data from Telegram
        """
        try:
            if not self.application:
                logger.error("Telegram application not initialized")
                return

            # Convert the update data to an Update object
            update = Update.de_json(update_data, self.application.bot)

            # Process the update
            await self.application.process_update(update)

        except Exception as e:
            logger.error(f"Error handling webhook update: {e}")

    async def set_webhook(self, webhook_url: str) -> bool:
        """
        Set the webhook URL for the Telegram bot.

        Args:
            webhook_url: The URL where Telegram should send updates

        Returns:
            True if successful, False otherwise
        """
        try:
            if not self.application:
                logger.error("Telegram application not initialized")
                return False

            # Validate webhook URL is not empty
            if not webhook_url or not webhook_url.strip():
                logger.error("Webhook URL is empty or not set. Check TELEGRAM_WEBHOOK_URL environment variable.")
                return False

            # Validate it's a proper HTTPS URL
            if not webhook_url.startswith("https://"):
                logger.error(f"Webhook URL must start with https://. Got: {webhook_url}")
                return False

            await self.application.bot.set_webhook(url=webhook_url)
            logger.info(f"Webhook set to: {webhook_url}")
            return True
        except Exception as e:
            logger.error(f"Failed to set webhook: {e}")
            return False

    async def delete_webhook(self) -> bool:
        """
        Delete the webhook for the Telegram bot.

        Returns:
            True if successful, False otherwise
        """
        try:
            if not self.application:
                logger.error("Telegram application not initialized")
                return False
            await self.application.bot.delete_webhook()
            logger.info("Webhook deleted")
            return True
        except Exception as e:
            logger.error(f"Failed to delete webhook: {e}")
            return False

    # ========================================================================
    # Command Handlers
    # ========================================================================

    async def _handle_eval(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """
        Handle the /eval command.
        Format: /eval <recipient_name> <message>
        """
        try:
            # Get the device ID (user ID in Telegram)
            device_id = str(update.effective_user.id)

            # Validate the evaluator
            evaluator = await self.db_service.get_evaluator_by_device_id(device_id)
            if not evaluator:
                await update.message.reply_text(
                    "❌ You are not authorized to use this bot. "
                    "Please contact your administrator."
                )
                return

            # Parse the command arguments
            if not context.args or len(context.args) < 2:
                await update.message.reply_text(
                    "❌ Invalid command format.\n"
                    "Usage: /eval <recipient_name> <message>\n"
                    "Example: /eval Child1 Did homework without being asked"
                )
                return

            recipient_name = context.args[0]
            message_text = " ".join(context.args[1:])

            # Find the recipient
            recipient = await self.db_service.get_recipient_by_name(
                evaluator.team_id,
                recipient_name
            )

            if not recipient:
                await update.message.reply_text(
                    f"❌ Recipient '{recipient_name}' not found in your team."
                )
                return

            # Enqueue the evaluation
            evaluation_id = await self.message_handler.enqueue(
                team_id=evaluator.team_id,
                evaluator_id=evaluator.id,
                recipient_id=recipient.id,
                message=message_text
            )

            await update.message.reply_text(
                f"✅ Evaluation for {recipient.name_en} has been queued.\n"
                f"Evaluation ID: {evaluation_id}"
            )

            logger.info(
                f"Evaluation queued by {evaluator.name_en} "
                f"for {recipient.name_en}: {message_text}"
            )

        except Exception as e:
            logger.error(f"Error handling /eval command: {e}")
            await update.message.reply_text(
                "❌ An error occurred while processing your evaluation. "
                "Please try again later."
            )

    async def _handle_report(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """
        Handle the /report command.
        Format: /report <recipient_name> <YYYY-MM-DD|today|yesterday>
        """
        try:
            # Get the device ID (user ID in Telegram)
            device_id = str(update.effective_user.id)

            # Validate the evaluator
            evaluator = await self.db_service.get_evaluator_by_device_id(device_id)
            if not evaluator:
                await update.message.reply_text(
                    "❌ You are not authorized to use this bot. "
                    "Please contact your administrator."
                )
                return

            # Parse the command arguments
            if not context.args or len(context.args) != 2:
                await update.message.reply_text(
                    "❌ Invalid command format.\n"
                    "Usage: /report <recipient_name> <YYYY-MM-DD|today|yesterday>\n"
                    "Examples:\n"
                    "  /report Child1 2026-06-20\n"
                    "  /report Child1 today\n"
                    "  /report Child1 yesterday"
                )
                return

            recipient_name = context.args[0]
            date_str = context.args[1].lower()

            # Get the team to access its timezone (needed for today/yesterday)
            team = await self.db_service.get_team(evaluator.team_id)
            if not team:
                await update.message.reply_text(
                    "❌ Team not found."
                )
                return

            # Get team timezone
            try:
                team_tz = pytz.timezone(team.timezone)
            except pytz.exceptions.UnknownTimeZoneError:
                logger.error(f"Unknown timezone: {team.timezone}")
                team_tz = pytz.UTC

            # Parse the date - support "today", "yesterday", or YYYY-MM-DD
            if date_str == "today":
                # Get today's date in team's timezone
                report_date = datetime.now(team_tz).date()
                display_date = f"today ({report_date.strftime('%Y-%m-%d')})"
            elif date_str == "yesterday":
                # Get yesterday's date in team's timezone
                report_date = (datetime.now(team_tz) - timedelta(days=1)).date()
                display_date = f"yesterday ({report_date.strftime('%Y-%m-%d')})"
            else:
                # Try to parse as YYYY-MM-DD
                try:
                    report_date = datetime.strptime(date_str, "%Y-%m-%d").date()
                    display_date = date_str
                except ValueError:
                    await update.message.reply_text(
                        "❌ Invalid date format. Please use:\n"
                        "  - YYYY-MM-DD (e.g., 2026-06-20)\n"
                        "  - today\n"
                        "  - yesterday"
                    )
                    return

            # Find the recipient
            recipient = await self.db_service.get_recipient_by_name(
                evaluator.team_id,
                recipient_name
            )

            if not recipient:
                await update.message.reply_text(
                    f"❌ Recipient '{recipient_name}' not found in your team."
                )
                return

            # Create start and end of day in team's timezone
            # Start: 2026-06-20 00:00:00 in team timezone
            # End: 2026-06-20 23:59:59 in team timezone
            start_of_day = team_tz.localize(datetime.combine(report_date, time.min))
            end_of_day = team_tz.localize(datetime.combine(report_date, time.max))

            # Convert to UTC for database query (since DB stores in UTC)
            start_date_utc = start_of_day.astimezone(pytz.UTC).date()
            end_date_utc = end_of_day.astimezone(pytz.UTC).date()

            # Get evaluations for the specified date range (in UTC)
            evaluations = await self.db_service.get_evaluations_for_recipient(
                team_id=evaluator.team_id,
                recipient_id=recipient.id,
                start_date=start_date_utc,
                end_date=end_date_utc
            )

            if not evaluations:
                await update.message.reply_text(
                    f"📊 No evaluations found for {recipient.name_en} on {display_date}"
                )
                return

            # Calculate the total score
            total_score = 0
            completed_count = 0
            report_lines = [
                f"📊 *Report for {recipient.name_en}*",
                f"📅 Date: {display_date}",
                f"",
                f"*Evaluations:*"
            ]

            for eval in evaluations:
                if eval.status == "completed" and eval.weight is not None:
                    total_score += eval.weight
                    completed_count += 1

                    # Get evaluator info
                    eval_evaluator = await self.db_service.get_evaluator(eval.evaluator_id)
                    evaluator_name = eval_evaluator.name_en if eval_evaluator else "Unknown"

                    # Format the evaluation line
                    emoji = "✅" if eval.weight >= 0 else "❌"
                    report_lines.append(
                        f"{emoji} [{eval.classification}] {eval.message} "
                        f"(by {evaluator_name}, weight: {eval.weight})"
                    )

            report_lines.extend([
                f"",
                f"*Summary:*",
                f"Total Evaluations: {len(evaluations)}",
                f"Completed: {completed_count}",
                f"*Final Score: {total_score}*"
            ])

            # Send the report
            report_text = "\n".join(report_lines)
            await update.message.reply_text(
                report_text,
                parse_mode="Markdown"
            )

            logger.info(
                f"Report generated by {evaluator.name_en} "
                f"for {recipient.name_en} on {display_date}"
            )

        except Exception as e:
            logger.error(f"Error handling /report command: {e}")
            await update.message.reply_text(
                "❌ An error occurred while generating the report. "
                "Please try again later."
            )

    async def _handle_help(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """
        Handle the /help command.
        Shows available commands.
        """
        help_text = """
🤖 *Reward Tracker Bot - Available Commands*

📝 */eval <recipient_name> <message>*
   Post an evaluation about a recipient
   Example: `/eval Child1 Did homework without being asked`

📊 */report <recipient_name> <date>*
   Get all evaluations for a recipient on a specific date with final score

   Date can be:
   • `today` - Today's evaluations
   • `yesterday` - Yesterday's evaluations
   • `YYYY-MM-DD` - Specific date

   Examples:
   `/report Child1 today`
   `/report Child1 yesterday`
   `/report Child1 2026-06-20`

❓ */help*
   Show this list of commands

---
For support, contact your team administrator.
        """

        await update.message.reply_text(help_text, parse_mode="Markdown")
        logger.info(f"Help command executed by user {update.effective_user.id}")
