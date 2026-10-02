import sys
import json
from kafka import KafkaConsumer

# Pass an identifier argument when running: python kafka_consumer.py worker_1
consumer_id = sys.argv[1] if len(sys.argv) > 1 else "worker_default"

consumer = KafkaConsumer(
    "order-events",
    bootstrap_servers=["localhost:9094"],
    group_id="analytics-service-group",  # Shared Consumer Group ID
    auto_offset_reset="earliest",         # If no offset committed, start from beginning
    enable_auto_commit=True,             # Kafka periodically saves consumer progress
    value_deserializer=lambda m: json.loads(m.decode("utf-8")),
    key_deserializer=lambda k: k.decode("utf-8") if k else None,
)

print(f"[{consumer_id}] Joined consumer group 'analytics-service-group'. Listening for events...\n")

try:
    for message in consumer:
        print(
            f"[{consumer_id}] Received from [Partition {message.partition} | Offset {message.offset}] "
            f"Key: {message.key} -> Value: {message.value}"
        )
except KeyboardInterrupt:
    print(f"\n[{consumer_id}] Shutting down...")
finally:
    consumer.close()