import asyncio
from .pc_collector import PCCollector
from .third_party_collector import ThirdPartyCollector
from .uploader_queue import UploaderQueue
from ..utils.config import get_settings

settings = get_settings()

async def collect_metrics(pc_collector: PCCollector, third_party_collector: ThirdPartyCollector, queue: UploaderQueue):
    """Collect metrics from both collectors and add them to the queue"""
    while True:
        # Collect PC metrics
        pc_metrics = pc_collector.collect_metrics()
        queue.add_metrics(pc_metrics)

        # Collect third-party metrics
        third_party_metrics = await third_party_collector.collect_metrics()
        queue.add_metrics(third_party_metrics)

        # Wait for next collection interval
        await asyncio.sleep(settings.COLLECTION_INTERVAL)

async def main():
    # Initialize components
    pc_collector = PCCollector()
    third_party_collector = ThirdPartyCollector()
    queue = UploaderQueue()

    # Create tasks
    collector_task = asyncio.create_task(collect_metrics(pc_collector, third_party_collector, queue))
    uploader_task = asyncio.create_task(queue.start_uploader())

    # Run tasks
    try:
        await asyncio.gather(collector_task, uploader_task)
    except KeyboardInterrupt:
        print("Shutting down collector...")
    except Exception as e:
        print(f"Error in collector: {e}")

if __name__ == "__main__":
    asyncio.run(main()) 