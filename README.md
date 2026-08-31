# DataPipe — Async Data Ingestion Pipeline

An asynchronous ETL pipeline built with **Python, HTTPX, Pydantic, asyncio, and SQLite**.

DataPipe extracts data from multiple public APIs concurrently, validates incoming records with Pydantic, transforms them into a clean structure, and loads them into SQLite. Failed records are preserved separately, while retry and exponential backoff improve resilience against temporary API failures.

The project focuses on applying **production-oriented data engineering patterns** rather than simply fetching API data.

---

## 🚀 Project Overview

DataPipe ingests data from two public APIs:

* Users API
* Posts API

The pipeline follows:

```text
                 ┌──────────────┐
                 │  Public APIs │
                 └──────┬───────┘
                        │
                  Async Extraction
                        │
                 ┌──────┴───────┐
                 │              │
              Users           Posts
                 │              │
                 └──────┬───────┘
                        │
                 Pydantic Validation
                        │
              ┌─────────┴─────────┐
              │                   │
            Valid               Invalid
              │                   │
          Transform        Failed Records
              │                   │
              └─────────┬─────────┘
                        │
                   SQLite Load
```

### ETL Flow

```text
Extract → Validate → Transform → Load
```

with additional reliability mechanisms:

```text
Retry + Exponential Backoff
Failed-Record Handling
Idempotent Loading
Configuration Management
```

---

# 🏗️ Architecture

The project separates responsibilities across several modules:

```text
datapipe/
│
├── main.py
├── config.py
├── models.py
├── storage.py
├── .env
├── .gitignore
├── requirements.txt
└── datapipe.db
```

### `main.py`

Responsible for orchestrating the complete pipeline:

* API extraction
* Concurrent execution
* Validation
* Transformation
* Loading
* Failed-record handling

### `models.py`

Contains Pydantic schemas used to validate incoming API data.

### `config.py`

Manages application configuration using Pydantic Settings and `.env`.

### `storage.py`

Handles SQLite database creation and data insertion/upsert operations.

### `.env`

Stores environment-specific configuration such as API URLs.

It is intentionally excluded from version control.

---

# ⚡ Why Async?

The pipeline is **I/O-bound**, not CPU-bound.

The application spends most of its time waiting for:

* Network connections
* API responses
* Response data

Instead of waiting for one API request to finish before starting another, asynchronous execution allows multiple requests to make progress concurrently.

For example:

```python
users_task = fetch(client, settings.users_url)
posts_task = fetch(client, settings.posts_url)

users_data, posts_data = await asyncio.gather(
    users_task,
    posts_task
)
```

Conceptually:

```text
Sequential

Users API ────────────────>
                          ↓
Posts API ────────────────>

Total ≈ Users time + Posts time
```

With async:

```text
Users API ────────────────>
Posts API ────────────────>

Total ≈ longest operation
```

This makes async particularly useful for applications that make many network requests.

---

# 🔄 Retry + Exponential Backoff

Network requests can fail temporarily because of:

* Timeouts
* Temporary server problems
* Network instability
* Rate limiting
* Transient HTTP failures

DataPipe retries timeout failures up to three times.

The waiting period increases exponentially:

```text
Attempt 1 → failure
       ↓
    wait 1 sec

Attempt 2 → failure
       ↓
    wait 2 sec

Attempt 3 → failure
       ↓
    give up
```

The implementation uses:

```python
wait_time = 2 ** attempt
```

This avoids immediately hammering an API when a temporary failure occurs.

---

# 🛡️ Pydantic Validation

External APIs cannot always be assumed to return perfectly structured data.

DataPipe validates incoming records before loading them into the database.

For example:

```python
validated_user = User(**user)
```

If validation succeeds:

```text
API record
    ↓
Pydantic
    ↓
Valid
    ↓
Transform
    ↓
Database
```

If validation fails:

```text
API record
    ↓
Pydantic
    ↓
ValidationError
    ↓
Failed Records
```

This prevents malformed records from silently entering the database.

---

# 🚨 Failed-Record Handling

A failed record should not necessarily cause the entire pipeline to fail.

Instead of discarding invalid data, DataPipe stores it in a dedicated table:

```text
failed_records
```

Each failed record contains information such as:

```text
source
record
error
```

Example:

```text
source: users

record:
{
    "id": "INVALID",
    "name": "Example User"
}

error:
validation error...
```

This provides an audit trail and makes failed records available for debugging or future reprocessing.

The principle is:

> **Don't lose bad data just because it cannot currently be processed.**

---

# 🔁 Idempotent Loading

A production ingestion pipeline may run repeatedly.

If the same API data is processed multiple times, a simple `INSERT` could create duplicates.

DataPipe addresses this using primary keys and SQLite UPSERT logic.

For example:

```sql
id INTEGER PRIMARY KEY
```

combined with:

```sql
ON CONFLICT(id) DO UPDATE SET
    name = excluded.name,
    email = excluded.email
```

The behavior becomes:

```text
First run
    ↓
Record doesn't exist
    ↓
INSERT


Second run
    ↓
Record already exists
    ↓
UPDATE
```

Therefore, running the pipeline multiple times does not continuously create duplicate records.

This makes the loading process **idempotent**.

> An idempotent pipeline can be safely re-run without producing unintended duplicate records.

---

# 🔐 Configuration & Secrets Management

API configuration is separated from application code.

Instead of hardcoding configuration:

```python
users_url = "https://..."
```

DataPipe uses:

```text
.env
 ↓
Pydantic Settings
 ↓
Application
```

Example `.env`:

```env
USERS_URL=https://jsonplaceholder.typicode.com/users
POSTS_URL=https://jsonplaceholder.typicode.com/posts
```

The `.env` file is excluded from Git:

```gitignore
.env
```

This pattern allows different environments to provide different configuration without changing application code.

It also provides a safe place for future secrets such as API keys and database credentials.

---

# 🗄️ Database

SQLite is used as the destination database for this project.

The pipeline creates:

```text
users
posts
failed_records
```

The `users` and `posts` tables use primary keys to support idempotent loading.

The `failed_records` table provides a separate path for records that fail validation.

---

# 🧪 Example Run

Running:

```bash
python main.py
```

produces output similar to:

```text
Valid users: 10
Failed users: 0
Valid posts: 100
Failed posts: 0
Data loaded successfully!
```

After repeated executions, the database remains consistent rather than continuously accumulating duplicate users and posts.

---

# ⚙️ Installation

Clone the repository:

```bash
git clone <your-repository-url>
cd <repository-name>
```

Create a virtual environment:

```bash
python -m venv day11-venv
```

Activate it on Windows:

```powershell
day11-venv\Scripts\activate
```

Install dependencies:

```bash
pip install -r requirements.txt
```

Create a `.env` file:

```env
USERS_URL=https://jsonplaceholder.typicode.com/users
POSTS_URL=https://jsonplaceholder.typicode.com/posts
```

Run the pipeline:

```bash
python main.py
```

---

# 📦 Dependencies

The project uses:

* **HTTPX** — synchronous and asynchronous HTTP requests
* **Pydantic** — data validation
* **Pydantic Settings** — configuration management
* **asyncio** — asynchronous task execution
* **SQLite** — lightweight relational data storage

---

# 🧠 Engineering Concepts Demonstrated

This project was built to explore practical concepts used in production data pipelines:

* Asynchronous programming
* I/O-bound concurrency
* `asyncio.gather()`
* HTTP clients
* API ingestion
* ETL architecture
* Data validation
* Pydantic models
* Configuration management
* Environment variables
* Retry strategies
* Exponential backoff
* Error handling
* Failed-record management
* SQLite
* Primary keys
* UPSERT
* Idempotent data ingestion
