import os
import sys
import time
import logging
import socket
import requests
import json
import threading
from datetime import datetime
from dotenv import load_dotenv
import sseclient  # You may need to install this: pip install sseclient-py
from threading import Thread, Event
from src.utils.time_utils import get_utc_timestamp

# Load environment variables from .env file
load_dotenv()

# Add the project root directory to the Python path
project_root = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, project_root)

from src.collector.pc_collector import PCCollector
from src.collector.stock_collector import StockCollector
from src.collector.uploader_queue import UploaderQueue
from src.utils.logging_config import get_logger, setup_logger
from src.utils.config import config

# Set up logging
setup_logger("collector")
logger = logging.getLogger(__name__)

def register_device(api_url, device_name, device_description=None):
    """Register a device with the API."""
    max_retries = 5
    retry_delay = 5  # seconds
    timeout = 30     # seconds
    
    # Create device payload with timestamp
    device_data = {
        "name": device_name,
        "description": device_description or f"Device: {device_name}",
        "timestamp": get_utc_timestamp()  # Add timestamp to registration
    }
    
    # Create the registration URL
    register_url = f"{api_url}/register_device"
    logger.info(f"Registering device {device_name} at {register_url}")
    
    for attempt in range(1, max_retries + 1):
        try:
            logger.info(f"Attempt {attempt}/{max_retries} to register device {device_name}")
            
            # Send the request with increased timeout
            response = requests.post(
                register_url,
                json=device_data,
                headers={"Content-Type": "application/json"},
                timeout=timeout
            )
            
            # Check for success (200, 201) or already exists (409)
            if response.status_code in (200, 201, 409):
                logger.info(f"Device {device_name} registered successfully or already exists: {response.status_code}")
                return True
                
            # Handle other status codes
            logger.warning(f"Failed to register device {device_name}: {response.status_code} - {response.text}")
            
        except requests.exceptions.Timeout:
            logger.error(f"Timeout while registering device {device_name} (attempt {attempt}/{max_retries})")
        except requests.exceptions.ConnectionError as e:
            logger.error(f"Connection error while registering device {device_name}: {str(e)}")
        except Exception as e:
            logger.error(f"Error registering device {device_name}: {str(e)}")
        
        # Retry if not the last attempt
        if attempt < max_retries:
            # Use exponential backoff for retries
            current_delay = retry_delay * (2 ** (attempt - 1))
            logger.info(f"Retrying device registration in {current_delay} seconds (attempt {attempt}/{max_retries})...")
            time.sleep(current_delay)
    
    # If we've reached this point, all attempts failed
    logger.error(f"All {max_retries} attempts to register device {device_name} failed")
    
    # For the STOCK device, we can continue without registration
    if device_name == "STOCK":
        logger.warning("Continuing without STOCK device registration. Will attempt to use it anyway.")
        return True
    
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
        logger.info("Starting collector...")
        
        # Get API URL from config
        api_url = config.get_api_url()
        
        # Fix URL if needed
        if api_url.startswith("http://https://"):
            api_url = api_url.replace("http://https://", "https://")
        elif api_url.startswith("https://http://"):
            api_url = api_url.replace("https://http://", "http://")
            
        logger.info(f"Using API URL: {api_url}")
        
        # Get device name (hostname)
        device_name = socket.gethostname()
        logger.info(f"Device name: {device_name}")
        
        # Register the device
        if not register_device(api_url, device_name):
            logger.error("Failed to register device. Exiting.")
            return
            
        # Register STOCK device for stock metrics
        stock_device_name = "STOCK"
        if not register_device(api_url, stock_device_name, "Stock market data collector"):
            logger.warning("Failed to register STOCK device. Stock metrics may not be properly associated.")
        
        # Initialize collectors
        pc_collector = PCCollector(device_name=device_name)
        stock_collector = StockCollector(device_name=stock_device_name)
        
        # Initialize uploader
        uploader = UploaderQueue(api_url=api_url)
        
        # Start the uploader thread
        uploader.start()
        
        # Collection loop
        try:
            while uploader.running:
                try:
                    # Collect PC metrics
                    pc_metrics = pc_collector.collect_metrics()
                    if pc_metrics:
                        # Add device name to metrics if PCCollector doesn't set it
                        for metric in pc_metrics:
                            if 'device_name' not in metric:
                                metric['device_name'] = device_name
                        uploader.add_metrics(pc_metrics)
                    
                    # Collect stock metrics (less frequently)
                    stock_metrics = stock_collector.collect_metrics()
                    if stock_metrics:
                        uploader.add_metrics(stock_metrics)
                        
                except Exception as e:
                    logger.error(f"Error in collection loop: {str(e)}")
                
                # Sleep until next collection
                time.sleep(config.collector.collection_interval)
                
        except KeyboardInterrupt:
            logger.info("Keyboard interrupt received. Stopping collector...")
        finally:
            # Stop the uploader
            uploader.stop()
            logger.info("Collector stopped.")
            
    except Exception as e:
        logger.error(f"Fatal error: {str(e)}")
        
if __name__ == "__main__":
    main() 