import asyncio
from .pc_collector import PCCollector
from .stock_collector import StockCollector
from .uploader_queue import UploaderQueue
from ..utils.config import get_settings
from ..utils.logging_config import get_logger

logger = get_logger('collector.main')
settings = get_settings()

async def collect_metrics(pc_collector: PCCollector, stock_collector: StockCollector, queue: UploaderQueue):
    """Collect metrics from all collectors and add them to the queue"""
    while True:
        # Collect PC metrics
        pc_metrics = pc_collector.collect_metrics()
        queue.add_metrics(pc_metrics)
        logger.info(f"Added {len(pc_metrics)} PC metrics to queue")

        # Collect stock metrics
        stock_metrics = stock_collector.collect_metrics()
        queue.add_metrics(stock_metrics)
        logger.info(f"Added {len(stock_metrics)} stock metrics to queue")

        # Wait for next collection interval
        logger.debug(f"Waiting {settings.COLLECTION_INTERVAL} seconds until next collection cycle")
        await asyncio.sleep(settings.COLLECTION_INTERVAL)

async def main():
    logger.info("Starting metrics collector")
    
    # Initialize components
    pc_collector = PCCollector()
    stock_collector = StockCollector()
    queue = UploaderQueue()
    
    logger.info("All collectors initialized")

    # Create tasks
    collector_task = asyncio.create_task(
        collect_metrics(pc_collector, stock_collector, queue)
    )
    uploader_task = asyncio.create_task(queue.start_uploader())

    # Run tasks
    try:
        logger.info("Starting collector tasks")
        await asyncio.gather(collector_task, uploader_task)
    except KeyboardInterrupt:
        logger.info("Shutting down collector...")
    except Exception as e:
        logger.error(f"Error in collector: {e}", exc_info=True)

if __name__ == "__main__":
    asyncio.run(main()) 