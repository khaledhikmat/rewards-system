# Known Limitations

This document describes the current limitations and design constraints of the Reward Tracker system.

## One Team Per Evaluator (Device ID)

### The Limitation

**Each Telegram account (device_id) can only belong to ONE team.**

This is enforced by a UNIQUE constraint on the `device_id` column in the `evaluators` table:

```sql
CREATE TABLE evaluators (
    id SERIAL PRIMARY KEY,
    team_id INTEGER NOT NULL REFERENCES teams(id),
    name_ar VARCHAR(255) NOT NULL,
    name_en VARCHAR(255) NOT NULL,
    device_id VARCHAR(255) NOT NULL,
    UNIQUE(device_id)  -- ⚠️ One device per team
);
```

### What This Means

- ❌ The same Telegram account cannot be an evaluator in multiple teams
- ❌ If you try to add a device_id that already exists, you'll get a database constraint violation error
- ❌ A divorced parent cannot manage two separate family teams using one account
- ❌ A grandparent cannot help with multiple families using the same Telegram account

### Why This Design?

This limitation is **intentional** and provides several benefits:

1. **Simpler User Experience**: No need to select which team you're evaluating when sending commands
2. **No Ambiguity**: Every message is automatically associated with the correct team
3. **Clearer Mental Model**: One account = one family keeps things simple
4. **Matches Common Use Case**: Most parents manage one household
5. **Prevents Confusion**: Users don't accidentally evaluate the wrong team's children

### Workarounds

If someone needs to manage multiple teams, they can:

**Option 1: Use Multiple Telegram Accounts**
- Create a second Telegram account with a different phone number
- Each account can be in a different team
- Most flexible solution

**Option 2: Separate Bot Instances**
- Deploy a separate bot instance for each family
- Each bot has its own database and team configuration
- Complete isolation between families

**Option 3: Change the Design (Advanced)**
If you absolutely need multi-team support, you would need to:
1. Remove the UNIQUE constraint on `device_id`
2. Implement team selection logic in the Telegram handler
3. Modify commands to either:
   - Ask "Which team?" before processing each command
   - Add team identifier to commands: `/eval Team1 Child1 message`
4. Update the UI to handle multiple teams per user

## Single Timezone Per Team

### The Limitation

**Each team has one timezone setting that applies to all team members.**

This is stored in the `teams` table:

```sql
CREATE TABLE teams (
    id SERIAL PRIMARY KEY,
    name_ar VARCHAR(255) NOT NULL,
    name_en VARCHAR(255) NOT NULL,
    timezone VARCHAR(50) NOT NULL DEFAULT 'UTC',
    ...
);
```

### What This Means

- All family members are assumed to be in the same timezone
- Reports are generated based on the team's configured timezone
- If family members are in different physical locations (different timezones), the system uses the team's single timezone setting

### When This Works Well

- Family members all live in the same house/city ✅
- Family members are in different locations but want a unified schedule ✅
- Short-term timezone differences (travel, etc.) ✅

### When This Doesn't Work

- Parents are permanently in different timezones (e.g., divorced, living in different countries)
- Mixed timezone households where day boundaries matter

### Workaround

- Set the timezone to the **primary location** where most evaluations happen
- Family members in other timezones should mentally adjust when requesting reports
- For split families, consider creating separate teams

## Database Timestamp Storage

### How Timestamps Work

- All timestamps are stored in UTC in the database
- The `reception_timestamp` records when an evaluation was received
- The `process_timestamp` records when it was processed
- These are ALWAYS in UTC

### Timezone Conversion Happens At

1. **Report Generation**: When filtering by date, the system converts the requested date (in team's timezone) to UTC ranges
2. **Display**: Future features might convert timestamps for display in team's timezone

### Example

Team timezone: `America/New_York` (EST/EDT, UTC-5/UTC-4)

User requests: `/report Child1 2026-06-20`

System interprets this as:
- Start: June 20, 2026 00:00:00 EST → converts to UTC
- End: June 20, 2026 23:59:59 EST → converts to UTC
- Queries database for evaluations in this UTC range

This ensures the report shows all evaluations that occurred on "June 20" in New York time, even though they're stored in UTC.

## API Key Authentication

### The Limitation

The REST API uses a **single shared API key** for all admin operations.

### What This Means

- No per-admin authentication or authorization
- All admins share the same API key
- No audit trail of who made which changes
- API key is stored in environment variables

### When This Works Well

- Small family deployment with trusted administrators ✅
- Personal use ✅
- Simple deployment scenarios ✅

### For Production/Enterprise Use

You would need to implement:
- Per-user authentication (JWT tokens, OAuth, etc.)
- Role-based access control (RBAC)
- Audit logging of API changes
- User management system

## Session-Based Dashboard Authentication

### The Limitation

- Admin dashboard uses signed cookies for sessions
- Sessions expire after 24 hours
- No "remember me" functionality
- Session secret is regenerated on each app restart

### Implications

- Users must log in again after 24 hours
- Restarting the app invalidates all sessions
- No persistent "stay logged in" option

### For Production Use

Consider implementing:
- Configurable session duration
- Persistent session storage (Redis, database)
- Refresh token mechanism
- "Remember me" functionality

## Batch Processing

### The Limitation

- Batch processor runs as a separate process (cron job)
- Processes max 10 messages at a time (configurable)
- No real-time processing
- Relies on periodic execution

### What This Means

- There's a delay between evaluation submission and classification
- The delay depends on cron frequency (e.g., every 5 minutes)
- Not suitable for applications requiring instant feedback

### For Real-Time Processing

You would need to:
- Implement async task queue (Celery, RQ, etc.)
- Process messages immediately upon receipt
- Add WebSocket support for live updates

## Scalability Considerations

### Current Architecture

- Single PostgreSQL database
- Connection pooling (configurable)
- Stateless HTTP handlers
- File-based templates

### Scalability Limits

- **Database**: Single PostgreSQL instance can handle thousands of teams
- **Connection Pool**: Default 10 connections may need tuning for high load
- **Batch Processing**: Single worker may become bottleneck
- **Templates**: File I/O on each request (no caching)

### For Large-Scale Deployment

Consider:
- Database replication for read scaling
- Multiple batch processor workers
- Template caching
- CDN for static assets
- Load balancer for multiple app instances

## Summary

Most of these limitations are **intentional design choices** that make the system:
- Simpler to use
- Easier to deploy
- Better suited for family/small group use cases

For enterprise or large-scale deployments, many of these would need to be revisited and enhanced.
