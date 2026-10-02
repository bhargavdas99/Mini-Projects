import json
import time
import pika

# 1. Establish connection to RabbitMQ host port (5672)
credentials = pika.PlainCredentials("guest", "guest")
parameters = pika.ConnectionParameters(
    host="localhost",
    port=5672,
    virtual_host="/",
    credentials=credentials,
)
connection = pika.BlockingConnection(parameters)
channel = connection.channel()

# 2. Declare Exchanges
# Primary exchange for valid order tasks
channel.exchange_declare(
    exchange="order.direct.exchange",
    exchange_type="direct",
    durable=True,
)

# Dead Letter Exchange (DLX) for rejected tasks
channel.exchange_declare(
    exchange="order.dlx.exchange",
    exchange_type="direct",
    durable=True,
)

# 3. Declare Queues
# The DLQ where failed messages end up
channel.queue_declare(queue="orders.dlq.queue", durable=True)
channel.queue_bind(
    queue="orders.dlq.queue",
    exchange="order.dlx.exchange",
    routing_key="order.dead",
)

# The Main Processing Queue with DLX configuration
# If a message is rejected/nacked on this queue, RabbitMQ automatically
# forwards it to 'order.dlx.exchange' using routing key 'order.dead'.
queue_arguments = {
    "x-dead-letter-exchange": "order.dlx.exchange",
    "x-dead-letter-routing-key": "order.dead",
}

channel.queue_declare(
    queue="orders.process.queue",
    durable=True,
    arguments=queue_arguments,
)
channel.queue_bind(
    queue="orders.process.queue",
    exchange="order.direct.exchange",
    routing_key="order.process",
)

print("[✓] RabbitMQ exchanges, queues, and DLX routing configured successfully.")

# 4. Produce Two Messages
tasks = [
    {"order_id": 101, "customer_id": "cust_A", "amount": 250, "status": "VALID"},
    {"order_id": 102, "customer_id": "cust_B", "amount": -50, "status": "INVALID_AMOUNT"},
]

for task in tasks:
    payload = json.dumps(task)
    channel.basic_publish(
        exchange="order.direct.exchange",
        routing_key="order.process",
        body=payload,
        properties=pika.BasicProperties(
            delivery_mode=2,  # Make message persistent on disk
            content_type="application/json",
        ),
    )
    print(f"[>] Published task: {payload}")

# 5. Worker Simulation
print("\n[*] Worker consuming from 'orders.process.queue'...\n")

def process_order(ch, method, properties, body):
    order = json.loads(body)
    order_id = order.get("order_id")
    amount = order.get("amount")

    print(f"[Worker] Received order #{order_id} (Amount: {amount})")

    if amount > 0:
        print(f"[Worker] Payment succeeded for order #{order_id}. Sending ACK.")
        # Acknowledge: deletes message from orders.process.queue
        ch.basic_ack(delivery_tag=method.delivery_tag)
    else:
        print(f"[Worker] Invalid payment for order #{order_id}! Sending NACK (requeue=False)...")
        # Negative Ack without requeue: RabbitMQ routes it straight to DLX!
        ch.basic_nack(delivery_tag=method.delivery_tag, requeue=False)

    # Stop after processing both drill messages
    if order_id == 102:
        ch.stop_consuming()

# Set prefetch_count=1 for fair dispatch (worker takes 1 task at a time)
channel.basic_qos(prefetch_count=1)
channel.basic_consume(
    queue="orders.process.queue",
    on_message_callback=process_order,
    auto_ack=False,
)

channel.start_consuming()
connection.close()
print("\n[✓] Processing finished.")