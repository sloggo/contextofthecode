import os
import sys
import time
import requests
import json
import threading
from datetime import datetime
from dotenv import load_dotenv
import sseclient  # You may need to install this: pip install sseclient-py

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

def register_stock_device(api_url):
    """Register the STOCK device in the database to avoid unique constraint errors."""
    max_retries = 3
    retry_delay = 2  # seconds
    
    for attempt in range(1, max_retries + 1):
        try:
            # Create a device registration endpoint URL
            device_url = f"{api_url}/register_device"
            
            # Prepare the device data
            device_data = {
                "name": "STOCK",
                "description": "Stock price collector"
            }
            
            logger.info(f"Attempting to register STOCK device (attempt {attempt}/{max_retries})")
            
            # Send the request
            response = requests.post(
                device_url,
                json=device_data,
                headers={"Content-Type": "application/json"},
                timeout=10  # Add timeout to prevent hanging
            )
            
            # Check the response
            if response.status_code == 200 or response.status_code == 201:
                logger.info("Successfully registered STOCK device")
                return True
            elif response.status_code == 409:  # Conflict - device already exists
                logger.info("STOCK device already registered")
                return True
            else:
                logger.warning(f"Failed to register STOCK device. Status: {response.status_code}, Response: {response.text}")
                if attempt < max_retries:
                    logger.info(f"Retrying in {retry_delay} seconds...")
                    time.sleep(retry_delay)
                    retry_delay *= 2  # Exponential backoff
                else:
                    logger.error("Max retries reached. Could not register STOCK device.")
                    return False
        except Exception as e:
            logger.error(f"Error registering STOCK device: {str(e)}", exc_info=True)
            if attempt < max_retries:
                logger.info(f"Retrying in {retry_delay} seconds...")
                time.sleep(retry_delay)
                retry_delay *= 2  # Exponential backoff
            else:
                logger.error("Max retries reached. Could not register STOCK device.")
                return False
    
    return False

def listen_for_commands(api_url, stock_collector):
    """Listen for commands from the web server via SSE."""
    commands_url = f"{api_url}/commands"
    logger.info(f"Starting command listener on {commands_url}")
    
    while True:
        try:
            headers = {'Accept': 'text/event-stream'}
            # Increase timeout to 60 seconds and add backoff mechanism
            response = requests.get(commands_url, headers=headers, stream=True, timeout=60)
            client = sseclient.SSEClient(response)
            
            for event in client.events():
                try:
                    commands = json.loads(event.data)
                    logger.info(f"Received commands: {commands}")
                    
                    for command in commands:
                        if command['action'] == 'add_stock' and 'symbol' in command:
                            symbol = command['symbol'].strip().upper()
                            logger.info(f"Adding stock {symbol} from command")
                            stock_collector.add_stock(symbol)
                except Exception as e:
                    logger.error(f"Error processing command: {str(e)}", exc_info=True)
                    
        except requests.exceptions.Timeout:
            logger.warning("Command listener timed out, reconnecting...")
            time.sleep(5)  # Wait before reconnecting
        except requests.exceptions.ConnectionError:
            logger.warning("Connection error in command listener, reconnecting in 10 seconds...")
            time.sleep(10)  # Longer wait for connection errors
        except Exception as e:
            logger.error(f"Error in command listener: {str(e)}", exc_info=True)
            # Wait before reconnecting with exponential backoff
            time.sleep(15)

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
        api_url = f"http://127.0.0.1:{web_config['port']}/api/v1/aggregator"
        uploader = UploaderQueue(api_url=api_url)
        logger.info(f"Uploader queue initialized with API URL: {api_url}")

        # Register the STOCK device - this is critical to avoid unique constraint errors
        logger.info("Registering STOCK device...")
        registration_success = register_stock_device(api_url)
        
        if not registration_success:
            logger.warning("Failed to register STOCK device. Stock metrics may fail to upload.")
            logger.warning("Continuing with collection, but expect errors for stock metrics.")

        # Start the uploader thread
        uploader.start_uploader()
        logger.info("Uploader thread started")
        
        # Start the command listener thread
        command_thread = threading.Thread(
            target=listen_for_commands,
            args=(api_url, stock_collector),
            daemon=True
        )
        command_thread.start()
        logger.info("Command listener thread started")

        # Main collection loop
        collector_config = config.get_collector_config()
        logger.info(f"Starting collection loop with interval: {collector_config['collection_interval']} seconds")
        logger.info(f"Stock collection interval: {collector_config['stock_interval']} seconds")
        
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