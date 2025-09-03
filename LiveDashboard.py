import asyncio
import json
import numpy as np
from datetime import datetime
from pathlib import Path

# ===========================
# METRIC GENERATOR
# ===========================
def generate_metrics():
    """Generate one metrics event"""
    return {
        "timestamp": datetime.utcnow().isoformat(),
        "cpu_usage": round(np.clip(np.random.normal(50, 10), 0, 100), 2),
        "memory_usage": round(np.clip(np.random.normal(70, 15), 0, 100), 2),
        "latency_ms": round(np.random.lognormal(mean=2.5, sigma=0.5), 2),
        "error_count": np.random.poisson(lam=2)
    }

# ===========================
# PRODUCER
# ===========================
async def produce_events(queue, total_events, duration):
    """
    Produce `total_events` evenly over `duration` seconds
    and push them into the queue.
    """
    interval = duration / total_events  # pacing
    for _ in range(total_events):
        await queue.put(generate_metrics())
        await asyncio.sleep(interval)   # ~8.3 events/sec for 1000 over 2 mins
    print(f"✅ Produced {total_events} events in {duration} seconds")

# ===========================
# CONSUMER (Buffered)
# ===========================
async def consume_events(queue, log_file, batch_size=100, flush_interval=1.0):
    """
    Consume events in batches for higher throughput:
      - Writes after `batch_size` events OR
      - Writes after `flush_interval` seconds
    """
    log_path = Path(log_file)
    buffer = []

    while True:
        try:
            event = await asyncio.wait_for(queue.get(), timeout=flush_interval)
            buffer.append(event)

            if len(buffer) >= batch_size:
                with log_path.open("a") as f:
                    f.write("\n".join(json.dumps(e) for e in buffer) + "\n")
                print(f"✅ Wrote batch of {len(buffer)} events")
                buffer.clear()

        except asyncio.TimeoutError:
            if buffer:
                with log_path.open("a") as f:
                    f.write("\n".join(json.dumps(e) for e in buffer) + "\n")
                print(f"✅ Flushed {len(buffer)} events (timeout)")
                buffer.clear()

# ===========================
# MAIN ENTRYPOINT
# ===========================
async def main():
    total_events = 1000
    duration = 120   # seconds (2 minutes)
    log_file = "metrics_high_throughput.jsonl"

    queue = asyncio.Queue()

    producer = asyncio.create_task(produce_events(queue, total_events, duration))
    consumer = asyncio.create_task(consume_events(queue, log_file, batch_size=100, flush_interval=1.0))

    await producer
    await asyncio.sleep(2)  # allow consumer to flush remaining

if __name__ == "__main__":
    asyncio.run(main())
