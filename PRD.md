I would like to create a bot to respond to commands arriving from channels (i.e. Telegram). 

The system is mainly going to be used as reward tracker for children within a family. But it can be extended to other avenues.

## Entities

The following are the main entities:

- **Recipient**: a person who receives evaluations i.e. Child. We need to know name (in Arabic and English) and date of birth.
- **Evaluator**: a person who evaluates recipients (and eventually rewards them) i.e. Parent. We need to know name (in Arabic and English) and Device ID (so we can accept evaluations from their devices). **Note**: Each device ID can only belong to ONE team. The same person cannot be an evaluator in multiple teams using the same Telegram account.
- **classifications**: a collection of classifications that each evaluator message would be subjected to. Each classification has a weight:

|  CLASSIFICATION | WEIGHT |
| -------- | -------- |
|  `horrible`  | -3      |
|  `very bad`  | -2      |
|  `bad`  | -1      |
|  `neutral`  | 0      |
|  `ok`  | +1      |
|  `good`  | +2      |
|  `superb`  | +3      |
    
- **Team**: a family, for example:
    - Name: Team Name. Must support both Arabic and English.
    - Recipients: a list of recipients (i.e., children) within the team.
    - Evaluators: a list of evaluators (i.e., parents) with the team.
    - Classifications: a list of applicable classifications. 

- **Evaluation**:
    - Team: the team.
    - Recipient: the recipient who is evaluated.
    - Evaluator: the evaluator who sent the message.
    - ReceptionTimestamp: when the evaluation message was received and enqueued. 
    - Message: the actual evaluation message. 
    - Classification: the actual classification i.e. `good`.
    - Weight: the classification weight.
    - Status: Queued, Processed, Failed, etc.
    - Worker ID: the dequeuer worker ID that processed the message. This is needed because it is possible to have multiple batch dequeuer processors. 
    - ProcessTimestamp: when the evaluation message was processed. 

## Commands

For the first phase, we want to support the following commands from channels:

|  COMMAND| DESC |
| -------- | -------- |
|  `/eval <recipient_name> <message>`  | Posts an evaluation about a recipient      |
|  `/report <recipient_name> <YYYY-MM-DD>`  | Returns all evaluations for that day with a final score    |
|  `/help`  | Shows this list of commands     |

and the following API Endpoints (authenticated usinh an API Key stored as ENV variable):

|  COMMAND| AUTH | DESC |
| -------- | -------- | -------- |
|  `GET /api/teams`  | API KEY | List all available teams      |
|  `POST /api/teams`  | API KEY | Create a new team      |
|  `PUT /api/teams`  | API KEY | Update an existing team      |
|  `GET /api/stats`  | API KEY | Required to build a dashboard that displays: number of queued messages, number of processed messages, etc      |

**Proposed Team Payload**:

```json
{
    "name_ar": "جونز عائلة",
    "name_en": "Jones Family",
    "recipients": [
        {
            "name_ar": "...",
            "name_en": "Child1",
            "dob": "2022-09-19" 
        },
        {
            "name_ar": "...",
            "name_en": "Child2",
            "dob": "2024-11-23" 
        }
    ],
    "evaluators": [
        {
            "name_ar": "...",
            "name_en": "Parent1",
            "device_id": "738473847387434" 
        },
        {
            "name_ar": "...",
            "name_en": "Parent2",
            "device_id": "7384676747387434" 
        }
    ],
    "classifications": [
        {
            "name": "horrible",
            "weight": -3 
        },
        {
            "name": "very bad",
            "weight": -2 
        },
        {
            "name": "bad",
            "weight": -1 
        },
        {
            "name": "ok",
            "weight": 0 
        },
        {
            "name": "good",
            "weight": 1 
        },
        {
            "name": "very good",
            "weight": 2 
        },
        {
            "name": "awesome",
            "weight": 3 
        }
    ]
}
```

## Personas

- Admins - these users are able to use the API Endpoints because they know the API Key. They are responsible for the app backend. Initially they use curl-like or Postman to process team operations. But they can also log in to a dashboard portal using credentails stored as ENV variables to display the dashboard.
- Evaluators - these users use the Telegram channels by poting commands to the bot. 
- Recipients are not able to interact with the app.

## Data Flow

- Admins create teams via a JSON payload to indicate recipients, evaluators and classifications.
- Evaluators (i.e. parents) that belong to teams post evaluation messages against certain recipients (children) using Channels (Telegram). The messages reflect certain behavior: good, bad, awesome, etc.  
- Channel (Telegram) processor periodically polls the channel to see if there are any pending messages.
- The channel processor does not accept a message unless it comes from a device that is defined in a team. 
- The channel processors enqueues the received message to a queue (database table), sets the status to `queued` and the `enqueueTimestamp`.
- A periodic batch processor checks for enqueued messages. Dequeues max of 10 messages and processes them by calling a message processor. In order to make sure to lock these messages so they cannot be processed by another batch processor, messages need to be stamped with `workerId` to identify the batch process that dequeued the messages.  
- The message processor operates on the message by classifying the message text for the team;sclassification i.e. ok, good, bad, etc. 
- Once completed, the message processor sets the message status to either `completed` or `failed` and sets the `processTimestamp`.  
- In addition to posting evaluations, evaluators can request reports about recipients as indicated above.
- Admins can access API Endpoints to manage teams and access the dashboard to see stats.

## Backend

Python-based backend with multiple handlers:
- Channel Handler
- HTTP Handler
- Message Handler

I imagine two main modules: one to run the Rewards System Processor and another to run the Rewards System Batch.

## Front End

Simple HTMX-based Dashboard portal that displays stats. This dashboard is accessed by admins only using credentials stored in ENV vars. Evaluators do not have access and they don't need it.

## Deployment

Planning to deploy to Raliway:

- Postgres database
- Rewards System Processor: contains channel handler to receive/validate messages and queues them to a database. It also includes an HTTP handler to expose API Endpoints. This can be deployed using Docker in Github Repository.
- Rewards System Batch Processor: contains dequeuer handler to dequeue messages and process them via a message handler. This can be deployed using Docker in the same Github Repository. But it will be triggered by a Cron job.

*So please assume `Postgres` when you design the database layer.*

## Source Code 

Here is how I imagine the code layout:
- `docs` folder contains all .md files
- `src` folder contains 
    - services
        - database
            - `database-svc.py`
            - `typex.py` - defines Protocols and Models
    - handlers
        - http-handler
            - `http-handler.py` - implementations
            - `typex.py` - defines Protocols and Models
        - telegram-handler
            - `telegram-handler.py`
            - `typex.py` - defines Protocols and Models
        - message-handler.py
            - `message-handler.py`
            - `typex.py` - defines Protocols and Models
    - `main.py`
    - `batch.py`
- `templates` folder contains HTML templates for HTMX
- `.env`
- `.env.example`
- `Dockerfile`
- `README.md`

I prefer that services and handlers be designed with a contract (i.e. Python `Protocol`) so that they can be swapped with fake or real handlers (and services) for testing purposes. Example of Message handler contract and impl:

```python
class IMessageHandler(Protocol): 
    async def enqueue(self, team: str, evaluator: str, recipient: str, message: str) -> bool:
        """Enqueue message (usually called from a telegram handler)."""
        pass

    async def process(self, message_id: str) -> bool:
        """Process message (usually called from a batch processor)."""
        pass

class MessageHandler():
    """
    An implementation of IMessageHandler
    """
```
