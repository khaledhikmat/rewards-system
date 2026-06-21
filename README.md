# Reward Tracker System

A comprehensive family reward tracking system with Telegram bot integration, REST API, and admin dashboard. Parents can evaluate their children's behavior through Telegram, and the system automatically classifies and scores the evaluations using AI.

## Features

- **Telegram Bot Interface**: Parents can submit evaluations and request reports via Telegram commands
- **AI-Powered Classification**: Uses Claude AI to automatically classify evaluations (good, bad, awesome, etc.) in both English and Arabic
- **REST API**: Full CRUD operations for team management
- **Admin Dashboard**: Real-time HTMX-based dashboard with statistics and team overview
- **Multi-Language Support**: Handles both Arabic and English names and evaluation messages
- **Batch Processing**: Efficient queued message processing with worker locking
- **PostgreSQL Database**: Robust data persistence with connection pooling

## Architecture

The system consists of two main components:

### 1. Rewards System Processor (`main.py`)
- Handles HTTP API requests
- Processes Telegram webhook updates
- Serves the admin dashboard
- Runs continuously as a web service

### 2. Rewards System Batch Processor (`batch.py`)
- Dequeues and processes evaluation messages
- Runs periodically via cron job
- Uses worker ID for distributed processing

## Technology Stack

- **Backend**: Python 3.11+ with FastAPI
- **Database**: PostgreSQL
- **AI**: Anthropic Claude API
- **Bot**: python-telegram-bot library (webhooks)
- **Frontend**: HTMX with Jinja2 templates
- **Deployment**: Docker + Railway

## Project Structure

```
reward-tracker/
├── docs/
│   └── schema.sql              # PostgreSQL database schema
├── src/
│   ├── services/
│   │   └── database/
│   │       ├── typex.py        # Database protocols and models
│   │       └── database-svc.py # Database service implementation
│   ├── handlers/
│   │   ├── message-handler/
│   │   │   ├── typex.py        # Message handler protocol
│   │   │   └── message-handler.py
│   │   ├── telegram-handler/
│   │   │   ├── typex.py        # Telegram handler protocol
│   │   │   └── telegram-handler.py
│   │   └── http-handler/
│   │       ├── typex.py        # HTTP handler protocol
│   │       └── http-handler.py
│   ├── main.py                 # Main application entry point
│   └── batch.py                # Batch processor entry point
├── templates/
│   └── dashboard.html          # Admin dashboard template
├── requirements.txt
├── Dockerfile
├── .env.example
├── .gitignore
├── .dockerignore
└── README.md
```

## Setup

### Prerequisites

- Python 3.11+
- PostgreSQL database
- Telegram Bot Token (from @BotFather)
- Anthropic API Key (for Claude)
- ngrok or similar (for local testing with webhooks)

### Local Development Setup

1. **Clone the repository**
   ```bash
   git clone <repository-url>
   cd reward-tracker
   ```

2. **Create virtual environment**
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

3. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```

4. **Set up PostgreSQL database**
   ```bash
   # Create database
   createdb reward_tracker

   # Run schema
   psql reward_tracker < docs/schema.sql
   ```

5. **Configure environment variables**
   ```bash
   cp .env.example .env
   # Edit .env with your actual values
   ```

6. **Run the application**
   ```bash
   # Start the main processor (from project root)
   python -m src.main

   # In another terminal, run batch processor (optional for testing)
   python -m src.batch
   ```

### Testing with ngrok

For local development with Telegram webhooks:

```bash
# In a separate terminal
ngrok http 8000

# Copy the HTTPS URL and update TELEGRAM_WEBHOOK_URL in .env
# Example: https://abc123.ngrok.io/webhook/telegram
```

## Environment Variables

All required environment variables are documented in `.env.example`:

```env
DATABASE_URL=postgresql://username:password@localhost:5432/reward_tracker
API_KEY=your-secret-api-key-here
ADMIN_USERNAME=admin
ADMIN_PASSWORD=your-secure-password-here
TELEGRAM_BOT_TOKEN=your-telegram-bot-token-here
TELEGRAM_WEBHOOK_URL=https://your-domain.com/webhook/telegram
ANTHROPIC_API_KEY=your-anthropic-api-key-here
APP_HOST=0.0.0.0
APP_PORT=8000
WORKER_ID=worker-1
BATCH_SIZE=10
LOG_LEVEL=INFO
```

## Deployment to Railway

### Main Application Deployment

1. **Create a new Railway project**
2. **Add PostgreSQL database** from Railway marketplace
3. **Connect GitHub repository**
4. **Set environment variables** in Railway dashboard
5. **Deploy**

Railway will automatically:
- Detect the Dockerfile
- Build the container
- Run `python src/main.py`
- Provide a public URL

### Batch Processor Deployment

1. **Create a second service** in the same Railway project
2. **Use the same GitHub repository**
3. **Override start command**: `python src/batch.py`
4. **Set up cron job** in Railway settings:
   ```
   Schedule: */5 * * * *  (every 5 minutes)
   ```

## API Endpoints

All API endpoints require authentication via `X-API-Key` header.

### Teams

- `GET /api/teams` - List all teams
- `GET /api/teams/{team_id}` - Get specific team
- `POST /api/teams` - Create new team
- `PUT /api/teams/{team_id}` - Update team
- `DELETE /api/teams/{team_id}` - Delete team

### Statistics

- `GET /api/stats` - Get system statistics

### Example: Create a Team

```bash
curl -X POST https://your-domain.com/api/teams \
  -H "Content-Type: application/json" \
  -H "X-API-Key: your-api-key" \
  -d '{
    "name_ar": "عائلة جونز",
    "name_en": "Jones Family",
    "recipients": [
      {
        "name_ar": "أحمد",
        "name_en": "Ahmed",
        "date_of_birth": "2020-01-15"
      }
    ],
    "evaluators": [
      {
        "name_ar": "محمد",
        "name_en": "Mohammed",
        "device_id": "123456789"
      }
    ],
    "classifications": [
      {"name": "horrible", "weight": -3},
      {"name": "very bad", "weight": -2},
      {"name": "bad", "weight": -1},
      {"name": "ok", "weight": 0},
      {"name": "good", "weight": 1},
      {"name": "very good", "weight": 2},
      {"name": "awesome", "weight": 3}
    ]
  }'
```

## Telegram Bot Commands

### `/eval <recipient_name> <message>`
Submit an evaluation for a recipient.

Example:
```
/eval Ahmed Did homework without being asked
```

### `/report <recipient_name> <YYYY-MM-DD>`
Get evaluation report for a specific date.

Example:
```
/report Ahmed 2026-06-20
```

### `/help`
Display available commands.

## Admin Dashboard

Access the dashboard at `https://your-domain.com/`

- **Authentication**: Basic Auth (username/password from .env)
- **Features**:
  - Real-time statistics
  - Auto-refresh every 30 seconds
  - Team overview with recipients, evaluators, and classifications

## Database Schema

The system uses the following main tables:

- `teams` - Family teams
- `recipients` - Children in teams
- `evaluators` - Parents with device IDs
- `classifications` - Classification types with weights
- `evaluations` - Evaluation messages with status tracking

See `docs/schema.sql` for complete schema.

## How It Works

1. **Parent sends evaluation via Telegram**:
   ```
   /eval Child1 cleaned room without being asked
   ```

2. **System validates and enqueues**:
   - Verifies parent's device ID
   - Validates recipient exists
   - Creates evaluation with status="queued"

3. **Batch processor runs (every 5 min)**:
   - Fetches max 10 queued evaluations
   - Locks them with worker ID
   - Processes each one

4. **Message processing**:
   - Sends message to Claude API
   - Claude classifies as "good", "bad", etc.
   - Updates evaluation with classification and weight
   - Sets status to "completed" or "failed"

5. **Parent requests report**:
   ```
   /report Child1 2026-06-20
   ```
   - System retrieves all evaluations for that day
   - Calculates total score
   - Returns formatted report

## Known Limitations

The system has some intentional design limitations that make it simpler and better suited for family use:

### One Team Per Evaluator

**Each Telegram account (device_id) can only belong to ONE team.**

- An evaluator cannot be part of multiple teams using the same Telegram account
- This is enforced by a UNIQUE constraint on the `device_id` column in the database
- **Workaround**: Use different Telegram accounts for each team, or deploy separate bot instances

**Why this design?**
- Simpler user experience (no team selection needed)
- Prevents confusion about which team is being evaluated
- Matches the typical use case: one family per parent

### Timezone Handling

- Each team has a single timezone setting
- All team members are assumed to be in the same timezone
- Reports are generated based on the team's configured timezone
- If family members are in different timezones, use the primary location's timezone

### Other Limitations

- Batch processing delay (not real-time)
- Single shared API key (no per-admin auth)
- Session expires after 24 hours

**See [docs/LIMITATIONS.md](docs/LIMITATIONS.md) for detailed information about limitations, design rationale, and workarounds.**

## Development

### Adding New Features

The system uses Protocol-based design for easy testing and extensibility:

```python
# Example: Swap database implementation
from services.database.typex import IDatabaseService

class FakeDatabaseService:
    """Implements IDatabaseService for testing"""
    # ... implementation
```

### Running Tests

```bash
# Install test dependencies
pip install pytest pytest-asyncio

# Run tests (when test files are added)
pytest
```

## Troubleshooting

### Webhook not receiving updates

1. Check `TELEGRAM_WEBHOOK_URL` is correct and accessible
2. Verify webhook is set: check Railway logs for "Webhook set to..."
3. Test webhook manually:
   ```bash
   curl https://your-domain.com/webhook/telegram
   ```

### Messages not processing

1. Check batch processor logs
2. Verify `ANTHROPIC_API_KEY` is valid
3. Check database for queued messages:
   ```sql
   SELECT * FROM evaluations WHERE status = 'queued';
   ```

### Database connection issues

1. Verify `DATABASE_URL` format
2. Check PostgreSQL is running and accessible
3. Ensure database schema is applied

## License

MIT License

## Support

For issues and questions, please open an issue on GitHub or contact the administrator.

---

Built with Python, FastAPI, PostgreSQL, and Claude AI
