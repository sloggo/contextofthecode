import os
import sys
import time
from datetime import datetime
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Add the project root directory to the Python path
project_root = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, project_root)

from src.collector.pc_collector import PCCollector
from src.collector.stock_collector import StockCollector
from src.collector.uploader_queue import UploaderQueue
from src.utils.logging_config import get_logger
from src.utils.config import config

logger = get_logger('collector.main')

def main():
    """Main function to run the collector."""
    try:
        # Initialize collectors
        pc_collector = PCCollector()
        logger.info("PC collector initialized")
        
        stock_collector = StockCollector()
        logger.info("Stock collector initialized")

        # Initialize uploader queue
        web_config = config.get_web_config()
        api_url = f"http://{web_config['host']}:{web_config['port']}/api/v1/aggregator"
        uploader = UploaderQueue(api_url=api_url)
        logger.info("Uploader queue initialized")

        # Start the uploader thread
        uploader.start_uploader()
        logger.info("Uploader thread started")

        # Main collection loop
        collector_config = config.get_collector_config()
        logger.info(f"Starting collection loop with interval: {collector_config['collection_interval']} seconds")
        logger.info(f"Stock collection interval: {collector_config['stock_interval']} seconds")
        
        # Track when we last collected stock metrics
        last_stock_collection = 0
        
        while True:
            try:
                # Check if we should stop
                if not uploader.running:
                    logger.info("Collector is stopped, waiting for start command...")
                    time.sleep(collector_config['collection_interval'])
                    continue
                
                # Collect PC metrics
                pc_metrics = pc_collector.collect_metrics()
                
                # Add PC metrics to upload queue
                if pc_metrics:
                    uploader.add_metrics(pc_metrics)
                    logger.info(f"Added {len(pc_metrics)} PC metrics to upload queue")
                
                # Check if it's time to collect stock metrics
                current_time = time.time()
                if current_time - last_stock_collection >= collector_config['stock_interval']:
                    # Collect stock metrics
                    stock_metrics = stock_collector.collect_metrics()
                    
                    # Add stock metrics to upload queue
                    if stock_metrics:
                        uploader.add_metrics(stock_metrics)
                        logger.info(f"Added {len(stock_metrics)} stock metrics to upload queue")
                    
                    # Update last stock collection time
                    last_stock_collection = current_time
                
                # Wait for next collection interval
                time.sleep(collector_config['collection_interval'])
                
            except KeyboardInterrupt:
                logger.info("Received keyboard interrupt, shutting down...")
                break
            except Exception as e:
                logger.error(f"Error in main loop: {str(e)}", exc_info=True)
                time.sleep(5)  # Wait before retrying
                
    except Exception as e:
        logger.error(f"Fatal error: {str(e)}", exc_info=True)
    finally:
        # Cleanup
        if 'uploader' in locals():
            uploader.stop_uploader()
        logger.info("Collector stopped")

if __name__ == '__main__':
    main() 