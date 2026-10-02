# OrderFlow: Asynchronous Task Processing & Event Streaming Pipeline

A lightweight distributed systems reference implementation demonstrating the architectural trade-offs and complementary usage of **RabbitMQ** (as a transactional, transient work queue) and **Apache Kafka in KRaft mode** (as an immutable, persistent event log).

---

## 1. System Architecture & Flow

```text
[Task Ingest]
       │
       ▼ (Port 5672)
[RabbitMQ: orders.process.queue]
       │
       ▼ (Pull task)
[Worker Process]
       │
       ├─── [Success] ──► 1. Emit event to Kafka (Port 9094, Key: customer_id)
       │                  2. Send basic_ack to RabbitMQ (Destructive read)
       │
       └─── [Failure] ──► 1. Send basic_nack(requeue=False) to RabbitMQ
                          2. RabbitMQ DLX routes task to orders.dlq.queue
                                  │
                                  ▼
                     [Kafka (KRaft): order-events]
                           │ (Partitioned Log)
                    ───────┴───────
                   ▼               ▼
         [Consumer Group A]  [Consumer Group B]
         (Analytics Engine)  (Notifications)

```

### Architectural Responsibilities

| Dimension | RabbitMQ | Apache Kafka |
| --- | --- | --- |
| **Primary Role** | Transactional Task Queue (Execution) | Append-Only Distributed Log (Audit & Analytics) |
| **Data Lifecycle** | Ephemeral: Removed on explicit `basic_ack`. | Persistent: Retained on disk according to time/size policy. |
| **Consumer Tracking** | Broker tracks state and delivery tags. | Consumers manage and commit their own partition **offsets**. |
| **Failure Mode** | Dead-Letter Exchange (DLX) re-routes failed jobs. | Uncommitted offsets reprocess on consumer group rebalance. |
| **Replayability** | None (consumed data is permanently deleted). | Full historical replay by rewinding consumer group offsets. |

---

## 2. Infrastructure Setup

The infrastructure runs in Docker via a shared bridge network (`orderflow-net`):

* **RabbitMQ 3.13 (Management Alpine):** Exposed on `5672` (AMQP protocol) and `15672` (Web UI).
* **Apache Kafka (KRaft Mode):** Operates without ZooKeeper using internal Raft consensus. Configured with dual listeners:
* `PLAINTEXT://kafka:9092`: Internal Docker network access (used by Kafka UI).
* `EXTERNAL://localhost:9094`: Host machine listener (used by local Python drivers).


* **Kafka UI:** Accessible on port `8080` for inspecting cluster metadata, partitions, and message offsets.

---

## 3. Directory Layout

```text
orderflow-demo/
├── docker-compose.yml       # RabbitMQ, Kafka (KRaft), and Kafka UI services
├── rabbitmq_drill.py        # RabbitMQ exchange/queue setup and DLX verification
├── orderflow_pipeline.py    # End-to-end task ingestion, worker, and Kafka streaming
└── kafka_consumer.py        # Consumer group subscription and replay demonstration

```

---

## 4. Step-by-Step Execution Guide

### Prerequisites

* Docker & Docker Compose
* Python 3.10+
* Virtual environment with required drivers:
```bash
pip install pika kafka-python-ng

```



### Step 1: Boot Up Infrastructure

```bash
docker compose up -d

```

* Verify RabbitMQ Dashboard: `http://localhost:15672` (`guest` / `guest`)
* Verify Kafka UI: `http://localhost:8080`

### Step 2: Provision Topics in Kafka

Create a 3-partition topic with a replication factor of 1:

```bash
docker exec -it orderflow-kafka /opt/kafka/bin/kafka-topics.sh \
  --bootstrap-server localhost:9092 \
  --create \
  --topic order-events \
  --partitions 3 \
  --replication-factor 1

```

### Step 3: Run the Orchestration Pipeline

Execute the end-to-end ingestion and worker script:

```bash
python orderflow_pipeline.py

```

* **Tasks Queued:** Three orders are sent to RabbitMQ (`orders.process.queue`).
* **Valid Tasks:** Amounts $> 0$ are processed, streamed to Kafka, and acknowledged (`basic_ack`).
* **Invalid Tasks:** Amounts $\le 0$ are rejected (`basic_nack(requeue=False)`), causing RabbitMQ to forward the message to `orders.dlq.queue` via the Dead-Letter Exchange (`order.dlx.exchange`).

### Step 4: Consume and Scale with Consumer Groups

Start an active consumer instance:

```bash
python kafka_consumer.py worker_1

```

To observe dynamic partition assignment and load balancing, open a second terminal and run:

```bash
python kafka_consumer.py worker_2

```

Kafka automatically balances partitions across both workers in `analytics-service-group`.

### Step 5: Time-Machine Log Replay Drill

Unlike RabbitMQ, consumed records remain persistent in Kafka. Stop all running consumers, reset the consumer group offset to the beginning, and re-run:

```bash
# 1. Reset consumer group offset to 0 across all partitions
docker exec -it orderflow-kafka /opt/kafka/bin/kafka-consumer-groups.sh \
  --bootstrap-server localhost:9092 \
  --group analytics-service-group \
  --reset-offsets \
  --to-earliest \
  --execute \
  --topic order-events

# 2. Restart the consumer to stream the full historical audit log
python kafka_consumer.py worker_1

```

---

## 5. Key Engineering Insights

1. **Deterministic Hashing:** Providing `customer_id` as the Kafka message key ensures that all state mutations for a specific customer hash deterministically to the identical partition ($\text{murmur2}(\text{key}) \pmod N$), enforcing strict chronological ordering.
2. **At-Least-Once Delivery Boundaries:** In the worker implementation, the Kafka event is flushed and committed *before* acknowledging the message in RabbitMQ (`basic_ack`). This prevents data loss in the event of an unhandled process termination between ingestion and auditing.
3. **Poison Pill Isolation:** Unprocessable or corrupted messages are routed to the DLQ rather than retried infinitely, preventing pipeline head-of-line blocking.

