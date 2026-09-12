# Celery + RabbitMQ Prefetch Starvation & Durability Lab

A hands-on systems drill demonstrating **head-of-line blocking** caused by Celery's default AMQP prefetch behavior, and how to achieve fair dispatch and task durability under worker crashes.

---

## The Architecture & Failure Modes

### 1. The Bottleneck: Head-of-Line Blocking (`prefetch_multiplier`)
By default, Celery configures its AMQP consumer with `worker_prefetch_multiplier=4`. For a worker with `concurrency=1`, RabbitMQ eagerly hands it **4 tasks at once** into its local process buffer:
* **The Symptom:** If a batch contains long-running jobs (e.g., 8s) mixed with near-instant jobs (e.g., 1ms), fast tasks get buffered behind heavy tasks on the same worker.
* **The Failure:** Idle workers elsewhere in the cluster sit starved of work because RabbitMQ considers the pre-fetched messages already delivered. Fast operations (e.g., password-reset emails, OTP notifications) experience massive latency spikes despite idle cluster capacity.

### 2. The Vulnerability: Message Loss on Worker Crashes (`acks_late`)
By default, Celery acknowledges messages upon receipt (`acks_late=False`):
* If a worker process is terminated (OOM-killed or machine failure) while executing a task, all in-flight and locally buffered uncompleted tasks are permanently lost.

---

## Tech Stack
* **Web Framework:** Django
* **Task Queue:** Celery
* **Message Broker:** RabbitMQ 3 (`rabbitmq:3-management`)
* **Orchestration:** Docker Compose (Compose v2)

---

## Project Structure

```text
celery_drill/
├── docker-compose.yml
├── Dockerfile
├── manage.py
├── README.md
└── core/
    ├── __init__.py
    ├── celery.py       # Celery application initialization
    ├── settings.py     # Django & Celery runtime configuration
    ├── tasks.py        # Heavy (8s) and Quick (1ms) task definitions
    └── urls.py         # /trigger/ endpoint to dispatch mixed workloads

```

---

## Running the Experiments

### Step 1: Reproduce Head-of-Line Starvation

1. Ensure the default settings are active (comment out or omit custom prefetch settings in `core/settings.py`):
```python
# CELERY_WORKER_PREFETCH_MULTIPLIER = 1
# CELERY_TASK_ACKS_LATE = True

```


2. Spin up the infrastructure:
```bash
docker compose up --build

```


3. In a separate terminal, dispatch a batch of 4 heavy tasks followed by 4 quick tasks:
```bash
curl http://localhost:8000/trigger/

```


4. **Observation:**
* Each worker eagerly pre-fetches 4 tasks.
* `quick_task` jobs sit blocked in worker process buffers and do not execute until all 8-second heavy tasks finish (~16 seconds total lag).



---

### Step 2: Implement Fair Dispatch

1. Update `core/settings.py` with:
```python
# Disable greedy prefetching (1 task per concurrency slot)
CELERY_WORKER_PREFETCH_MULTIPLIER = 1

# Acknowledge messages only after successful execution
CELERY_TASK_ACKS_LATE = True

```


2. Restart the workers:
```bash
docker compose restart worker-1 worker-2

```


3. Retrigger the batch:
```bash
curl http://localhost:8000/trigger/

```


4. **Observation:**
* Workers only hold the single task they are actively executing.
* As soon as an execution slot frees up, quick tasks are drained from RabbitMQ and executed in milliseconds without waiting behind long-running jobs.



---

### Step 3: Verify Task Durability via Worker Crash

1. Fire the batch again:
```bash
curl http://localhost:8000/trigger/

```


2. Immediately kill `worker-1` mid-execution:
```bash
docker compose kill worker-1

```


3. **Observation:**
* RabbitMQ detects the severed TCP socket:
```text
[warning] client unexpectedly closed TCP connection

```


* Because `CELERY_TASK_ACKS_LATE=True`, no `basic.ack` was sent.
* RabbitMQ immediately requeues the unfinished task to `worker-2`, guaranteeing zero message loss.



---

## Cleanup

To stop and remove all containers, networks, and volumes:

```bash
docker compose down

```