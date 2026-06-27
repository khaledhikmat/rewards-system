# Quick Setup Guide

## Initial Setup Steps

### 1. Install Dependencies

```bash
python3 -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

### 2. Set Up PostgreSQL

#### Option A: Using Local PostgreSQL

**Install PostgreSQL (macOS):**
```bash
# Using Homebrew
brew install postgresql@15
brew services start postgresql@15

# Or download Postgres.app from https://postgresapp.com/
```

**Create database and apply schema:**
```bash
# Method 1: Using createdb utility
createdb reward_tracker
psql reward_tracker < docs/schema.sql

# Method 2: Using psql directly
psql postgres -c "CREATE DATABASE reward_tracker;"
psql reward_tracker < docs/schema.sql
```

#### Option B: Using Cloud Database (Railway, etc.)

**The database is already created for you! Just apply the schema:**

```bash
# Install psql client only (if you don't need full PostgreSQL server)
brew install libpq
echo 'export PATH="/opt/homebrew/opt/libpq/bin:$PATH"' >> ~/.zshrc
source ~/.zshrc

# Set your connection string from Railway/cloud provider
export DATABASE_URL="postgresql://user:password@host:port/database"

# Apply schema using the connection string
psql "$DATABASE_URL" -f docs/schema.sql

# Or connect interactively and run commands
psql "$DATABASE_URL"
# Inside psql:
\i docs/schema.sql
\q
```

**Pro Tip:** Using `DATABASE_URL` is the recommended approach as it matches exactly what your application will use.

#### Essential psql Commands

**Meta Commands:**
```bash
\l              # List all databases
\c dbname       # Connect to database
\dt             # List tables
\d evaluations  # Describe evaluations table
\d+ evaluations # Describe with sizes and indexes
\du             # List users/roles
\q              # Quit psql
```

**Query Formatting:**
```bash
\x              # Toggle expanded display (vertical format)
\x auto         # Auto expand for wide results
\pset pager off # Disable pager for long output
\timing         # Show query execution time
```

**File Operations:**
```bash
\i script.sql        # Execute SQL from file
\o output.txt        # Send results to file
\o                   # Stop output to file
```

### 3. Configure Environment

```bash
cp .env.example .env
# Edit .env with your actual credentials
```

### 4. Get Required API Keys

1. **Telegram Bot Token**:
   - Message @BotFather on Telegram
   - Create new bot: `/newbot`
   - Copy the token to `.env` (looks like: `123456789:ABCdef...`)

2. **Anthropic API Key**:
   - Sign up at https://console.anthropic.com
   - Create API key
   - Copy to `.env`

3. **Generate API Key** for admin endpoints:
   ```bash
   python -c "import secrets; print(secrets.token_urlsafe(32))"
   ```
   Add to `.env` as `API_KEY`

### 5. Test Locally

```bash
# Terminal 1: ngrok
brew install ngrok/ngrok/ngrok

# Sign up and authenticate (optional but recommended)

# Sign up for free at https://ngrok.com
# Get your authtoken from the dashboard

# Add your authtoken
ngrok config add-authtoken YOUR_AUTH_TOKEN

# Note: The free tier allows you to create tunnels without authentication, but with an authtoken you get:
# - Longer session times
# - More simultaneous tunnels
# - Custom subdomains (paid plans)

# Usage for your project

# Start ngrok tunnel to your local app
ngrok http 8000

# You'll get output like:
# Forwarding  https://abc123.ngrok-free.app -> http://localhost:8000

# Then copy the HTTPS URL (e.g., https://abc123.ngrok-free.app) and use it in your .env:
TELEGRAM_WEBHOOK_URL=https://abc123.ngrok-free.app/webhook/telegram

# Terminal 2: Update .env with ngrok URL, then start app
python3 -m src.main

# Terminal 3: Test batch processor
python3 -m src.batch
```

**Note:** We use `python3 -m src.main` instead of `cd src && python3 main.py` because:
- `-m` treats `src` as a proper Python package
- More consistent with Docker deployment
- Ensures imports work correctly
- Recommended "Pythonic" approach

### 6. Create Your First Team

```bash
curl -X POST http://localhost:8000/api/teams \
  -H "Content-Type: application/json" \
  -H "X-API-Key: YOUR_API_KEY" \
  -d '{
    "name_ar": "عائلة جونز",
    "name_en": "Jones Family",
    "timezone": "America/New_York",
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
        "device_id": "YOUR_TELEGRAM_USER_ID"
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

**Notes**:
- To get your Telegram User ID, message your bot and check the logs, or use a bot like @userinfobot
- **Device ID Limitation**: Each device_id (Telegram account) can only belong to ONE team. If you try to add the same person to multiple teams, you'll get a database error. Use different Telegram accounts if someone needs to manage multiple teams.
- **Timezone**: Set this to your family's local timezone (IANA format). Common examples:
  - `America/New_York` - US Eastern Time
  - `America/Chicago` - US Central Time
  - `America/Los_Angeles` - US Pacific Time
  - `Europe/London` - UK Time
  - `Asia/Dubai` - UAE Time
  - `Asia/Riyadh` - Saudi Arabia Time
  - See full list: https://en.wikipedia.org/wiki/List_of_tz_database_time_zones
- Reports will use this timezone when filtering by date

### 7. Test Telegram Bot

Send to your bot:
```
/help
/eval Ahmed cleaned his room
/report Ahmed 2026-06-20
```

### 8. Access Dashboard

Visit `http://localhost:8000` and login with credentials from `.env`

## Deployment to Railway

1. Push code to GitHub
2. Create Railway project
3. Add PostgreSQL from marketplace
4. Deploy main app (auto-detects Dockerfile)
5. Add cron service for batch processor:
   - Same repo
   - Command: `python -m src.batch`
   - Schedule: `*/5 * * * *`
6. Set all environment variables
7. Update `TELEGRAM_WEBHOOK_URL` to Railway URL

Make sure the Telegram bot's webhook is registerd properly:

```bash
curl https://api.telegram.org/<telegram-token>/getWebhookInfo
```

If not, register Telegram bot's webhook manually:

```bash
curl -X POST "https://api.telegram.org/<telegram-token>/setWebhook?url=https://<railwat-base-url>/webhook/telegram"
```

## Webhook Persistence

**Important:** Telegram webhooks are persistent and survive service restarts.

- ✅ The webhook is set once during startup
- ✅ It persists even when Railway restarts your service
- ✅ You don't need to manually set it after each deployment

**When to manually manage webhooks:**

If you need to delete the webhook (e.g., switching to polling mode):
```bash
# Delete webhook
curl -X POST "https://api.telegram.org/bot<YOUR_BOT_TOKEN>/deleteWebhook"

# Or set to empty
curl -X POST "https://api.telegram.org/bot<YOUR_BOT_TOKEN>/setWebhook?url="
```

To verify webhook status anytime:
```bash
curl "https://api.telegram.org/bot<YOUR_BOT_TOKEN>/getWebhookInfo"
```

## Troubleshooting

### "No module named 'services'"
- Make sure you're running from the project root directory (not inside `src/`)
- Use `python -m src.main` instead of `python main.py`
- Verify all `__init__.py` files exist in package directories

### Telegram webhook not working
- Verify HTTPS URL is accessible
- Check Railway logs for "Webhook set to..."
- Telegram requires HTTPS (not HTTP)

### Database connection failed
- Check `DATABASE_URL` format: `postgresql://user:pass@host:port/dbname`
- Ensure PostgreSQL is running
- Verify schema is applied

## Python Execution Methods Explained

There are three common ways to run Python code in this project:

### 1. `python -m src.main` ✅ Recommended
```bash
# From project root
python -m src.main
```
- **Treats `src` as a Python package** (uses `__init__.py` files)
- Working directory: project root
- Imports work correctly: `from services.database...`
- **Most "Pythonic"** and consistent with packaging standards
- **Same as Dockerfile uses**

### 2. `cd src && python main.py` ⚠️ Works but not ideal
```bash
cd src
python main.py
```
- **Direct script execution**
- Working directory: `src/`
- Imports work because current dir is `src/`
- Requires changing directories
- Less portable

### 3. `python src/main.py` ⚠️ Avoid
```bash
# From project root
python src/main.py
```
- **Script execution with path**
- Working directory: project root
- Python adds `src/` to sys.path automatically
- Works but can cause confusion
- Not recommended for packages

**Recommendation:** Always use `python -m src.main` for consistency with deployment and proper package handling.

## Next Steps

- Monitor the dashboard for system stats
- Set up Railway cron for automatic batch processing
- Configure monitoring and alerting
- Add more teams via API
