import json
import time
import pika
from kafka import KafkaProducer

# ---------------------------------------------------------
# 1. Initialize Clients
# ---------------------------------------------------------
# RabbitMQ on AMQP port 5672
rmq_creds = pika.PlainCredentials("guest", "guest")
rmq_params = pika.ConnectionParameters(
    host="localhost",
    port=5672,
    virtual_host="/",
    credentials=rmq_creds,
)
rmq_conn = pika.BlockingConnection(rmq_params)
rmq_channel = rmq_conn.channel()

# Kafka Producer pointing to our external host listener (Port 9094)
kafka_producer = KafkaProducer(
    bootstrap_servers=["localhost:9094"],
    key_serializer=lambda k: k.encode("utf-8"),
    value_serializer=lambda v: json.dumps(v).encode("utf-8"),
    acks="all",  # Wait for broker leader commit confirmation
)

print("[✓] Connected to RabbitMQ (port 5672) and Kafka (port 9094).")

# ---------------------------------------------------------
# 2. Worker Callback: The Bridge between RabbitMQ and Kafka
# ---------------------------------------------------------
def process_order_and_stream(ch, method, properties, body):
    task = json.loads(body)
    order_id = task.get("order_id")
    customer_id = task.get("customer_id")
    amount = task.get("amount")

    print(f"\n[Worker] Received order #{order_id} for {customer_id} (Amount: ${amount})")

    if amount > 0:
        # Simulate successful settlement logic
        event_payload = {
            "event": "PAYMENT_SETTLED",
            "order_id": order_id,
            "customer_id": customer_id,
            "amount": amount,
            "timestamp": time.time(),
        }

        # 1. Write immutable event to Kafka partitioned by customer_id
        future = kafka_producer.send(
            topic="order-events",
            key=customer_id,
            value=event_payload,
        )
        record_metadata = future.get(timeout=10)

        print(
            f"[Kafka Audit] Streamed event to topic '{record_metadata.topic}' "
            f"[Partition: {record_metadata.partition}] at Offset {record_metadata.offset}"
        )

        # 2. Acknowledge RabbitMQ message (destructive delete)
        ch.basic_ack(delivery_tag=method.delivery_tag)
        print(f"[RabbitMQ] Order #{order_id} ACKed and cleared from queue.")

    else:
        # Business logic failed
        print(f"[Worker] Order #{order_id} rejected due to invalid amount.")
        
        # 1. Reject on RabbitMQ without requeue -> triggers DLX
        ch.basic_nack(delivery_tag=method.delivery_tag, requeue=False)
        print(f"[RabbitMQ] Order #{order_id} NACKed -> Routed to DLQ.")

    # Stop consumption once our test orders are processed
    if order_id == 203:
        ch.stop_consuming()


# ---------------------------------------------------------
# 3. Publish Test Orders to RabbitMQ
# ---------------------------------------------------------
test_orders = [
    {"order_id": 201, "customer_id": "cust_X", "amount": 350},
    {"order_id": 202, "customer_id": "cust_Y", "amount": -10},  # will fail -> DLQ
    {"order_id": 203, "customer_id": "cust_X", "amount": 80},   # same customer -> same Kafka partition
]

print("\n--- Step 1: Ingesting tasks into RabbitMQ ---")
for order in test_orders:
    rmq_channel.basic_publish(
        exchange="order.direct.exchange",
        routing_key="order.process",
        body=json.dumps(order),
        properties=pika.BasicProperties(delivery_mode=2),
    )
    print(f"[RabbitMQ Ingest] Queued order #{order['order_id']}")

# ---------------------------------------------------------
# 4. Start Worker Loop
# ---------------------------------------------------------
print("\n--- Step 2: Worker processing and streaming to Kafka ---")
rmq_channel.basic_qos(prefetch_count=1)
rmq_channel.basic_consume(
    queue="orders.process.queue",
    on_message_callback=process_order_and_stream,
    auto_ack=False,
)

rmq_channel.start_consuming()

# Clean up connections
kafka_producer.flush()
kafka_producer.close()
rmq_conn.close()
print("\n[✓] Pipeline execution finished.")