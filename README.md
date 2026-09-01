# Containerizing an Async Data Pipeline with PostgreSQL & MongoDB

Built a production-style asynchronous data ingestion pipeline that fetches data from multiple public APIs, validates records with Pydantic, handles transient failures with retry and exponential backoff, and captures invalid records for later investigation.

For Day 13, I containerized the entire stack using Docker Compose and added both PostgreSQL and MongoDB as storage layers. PostgreSQL stores the validated and transformed relational data, while MongoDB preserves the raw API documents.

## Architecture

flowchart LR
    A[Public APIs] --> B[DataPipe Container]
    B --> C[Async Extraction]
    C --> D[Pydantic Validation]

    D -->|Valid| E[Transformation]
    D -->|Invalid| F[Failed Records]

    E --> G[(PostgreSQL)]
    E --> H[(MongoDB)]

    G --> I[(Persistent Volume)]
    H --> J[(Persistent Volume)]

    F --> G
    
### Data Flow

```text
External APIs
     │
     ▼
┌───────────────────┐
│     DataPipe      │
│    Container      │
└─────────┬─────────┘
          │
          ▼
   Async Extraction
          │
          ▼
   Pydantic Validation
       │       │
   Valid       Invalid
      │           │
      ▼           ▼
 Transform    Failed Records
      │
   ┌──┴───────────┐
   │              │
   ▼              ▼
PostgreSQL      MongoDB
   │              │
   ▼              ▼
Volume          Volume
```
---

## Architecture Decisions

### Why Async?

The pipeline retrieves data from multiple APIs, making it primarily I/O-bound.

Instead of waiting for the users API to complete before requesting the posts API, the pipeline uses `asyncio.gather()` to fetch both concurrently.

```python
users_task = fetch(client, settings.users_url)
posts_task = fetch(client, settings.posts_url)

users_data, posts_data = await asyncio.gather(
    users_task,
    posts_task
)
```

This allows independent network requests to make progress concurrently and reduces unnecessary waiting.

Async was chosen because the bottleneck is network I/O rather than CPU computation.

---

### Why Pydantic Validation?

External API data cannot be assumed to always match the application's expected schema.

Pydantic models provide a clear validation boundary between extraction and loading.

```text
API Response
     │
     ▼
Pydantic Validation
     │
 ┌───┴────┐
 │        │
Valid    Invalid
 │        │
 ▼        ▼
Load    Failed Records
```

Invalid records are not allowed to silently enter the main database tables.

Instead, validation errors are captured together with the original record.

---

### Retry and Exponential Backoff

Network requests can fail temporarily because of timeouts or transient HTTP errors.

The extraction function retries timeout failures up to three times.

The retry delay follows exponential backoff:

```text
Attempt 1 → immediate
Attempt 2 → wait 1 second
Attempt 3 → wait 2 seconds
```

This avoids continuously hitting an unavailable API and gives transient failures time to recover.

---

### Failed Record Handling

Invalid records are separated from valid records instead of stopping the entire pipeline.

Each failed record stores:

* Source
* Original record
* Validation error

Example:

```text
failed_records
├── source
├── record
└── error
```

This allows the pipeline to continue processing valid data while preserving enough information to investigate bad records later.

---

### Why PostgreSQL?

PostgreSQL is used for the cleaned and structured representation of the data.

The relational structure is appropriate for entities such as:

```text
users
posts
failed_records
```

It also provides constraints such as primary keys and supports idempotent loading through:

```sql
ON CONFLICT (id) DO NOTHING
```

---

### Why MongoDB?

MongoDB is used to preserve the raw API documents.

API responses can contain nested and flexible structures that do not necessarily need to be flattened immediately.

For example, a raw user document can retain:

```text
id
name
username
email
address
company
...
```

This gives the pipeline two useful representations:

```text
PostgreSQL → validated, transformed, structured data

MongoDB    → raw API documents
```

This also demonstrates a practical SQL vs NoSQL architecture rather than using both databases simply for demonstration purposes.

---

### Idempotent Loading

The pipeline is designed so that running it multiple times does not continuously create duplicate records.

PostgreSQL uses:

```sql
ON CONFLICT (id) DO NOTHING
```

MongoDB uses:

```python
UpdateOne(
    {"id": record["id"]},
    {"$set": record},
    upsert=True
)
```

Therefore:

```text
First run
    ↓
Insert record

Second run
    ↓
Existing record found
    ↓
Update / ignore duplicate
```

This is important for pipelines because jobs may be retried or rerun after partial failures.

---

## Docker Architecture

The complete application runs through Docker Compose.

The stack contains:

```text
DataPipe
PostgreSQL
MongoDB
```

Docker Compose creates a shared network allowing services to communicate using service names.

For example:

```text
DataPipe → postgres:5432
DataPipe → mongo:27017
```

The application does not need to know the individual container IP addresses.

---

### Docker Image vs Container

The DataPipe Docker image contains the application's runtime environment and dependencies.

The container is the running instance created from that image.

```text
Dockerfile
     │
     ▼
Docker Image
     │
     ▼
DataPipe Container
```

This makes the application environment reproducible across machines.

---

### Docker Volumes

Database containers are disposable, but database data should not be.

Therefore PostgreSQL and MongoDB use named Docker volumes:

```text
PostgreSQL
     │
     ▼
postgres_data

MongoDB
     │
     ▼
mongo_data
```

The volumes exist independently of the containers.

This means:

```text
docker compose down
        ↓
Containers removed
        ↓
Volumes remain
        ↓
docker compose up
        ↓
New containers
        ↓
Existing data restored
```

The persistence test was performed successfully for both databases.

> Note: `docker compose down -v` removes the volumes and therefore deletes the persisted database data.

---

## Reproducibility

The complete stack can be started with:

```bash
docker compose up
```

The infrastructure, networking, database services, dependencies, and application runtime are defined as code.

This reduces environment-specific setup and makes the project easier for another developer to reproduce.

---

## Running the Project

### Prerequisites

* Docker Desktop
* Docker Compose

### Start the complete stack

```bash
docker compose up
```

Or run it in detached mode:

```bash
docker compose up -d
```

### Check running services

```bash
docker compose ps
```

### View application logs

```bash
docker compose logs datapipe
```

### Stop the stack

```bash
docker compose down
```

> Do not use `docker compose down -v` unless you intentionally want to remove the database volumes and their data.

### Rebuild the application image

```bash
docker compose build datapipe
```

### Verify MongoDB

```bash
docker exec -it day13-mongo-1 mongosh
```

```javascript
use datapipe
db.users_raw.countDocuments()
db.posts_raw.countDocuments()
```

### Verify PostgreSQL

```bash
docker exec -it day13-postgres-1 psql -U datapipe -d datapipe
```

```sql
SELECT COUNT(*) FROM users;
SELECT COUNT(*) FROM posts;
SELECT COUNT(*) FROM failed_records;
```

---

## Project Structure

```text
Day 13/
│
├── main.py
├── storage.py
├── models.py
├── config.py
├── requirements.txt
├── Dockerfile
├── docker-compose.yml
├── .dockerignore
├── .gitignore
└── README.md
```

### Responsibilities

| File                 | Responsibility                           |
| -------------------- | ---------------------------------------- |
| `main.py`            | Pipeline orchestration                   |
| `models.py`          | Pydantic validation models               |
| `storage.py`         | PostgreSQL and MongoDB operations        |
| `config.py`          | Application configuration                |
| `Dockerfile`         | DataPipe container image                 |
| `docker-compose.yml` | Complete multi-container stack           |
| `requirements.txt`   | Python dependencies                      |
| `.dockerignore`      | Files excluded from Docker build context |
