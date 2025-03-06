import time
import json
import requests
from typing import List, Dict
from queue import Queue
from threading import Thread, Event
from ..utils.logging_config import get_logger
from ..utils.config import config

logger = get_logger('collector.uploader')

class UploaderQueue:
    def __init__(self, api_url: str, batch_size: int = 100, max_queue_size: int = 1000):
        self.api_url = api_url
        self.batch_size = batch_size
        self.max_queue_size = max_queue_size
        self.queue = Queue(maxsize=max_queue_size)
        self.stop_event = Event()
        self.upload_thread = None
        self.collector_config = config.get_collector_config()
        
        logger.info(f"Initializing uploader queue with batch_size={batch_size}, max_queue_size={max_queue_size}")
        logger.info(f"API URL: {api_url}")

    def validate_metric(self, metric: Dict) -> bool:
        """Validate a metric before adding it to the queue."""
        required_fields = ['device_name', 'metric_name', 'value']
        
        # Check for required fields
        for field in required_fields:
            if field not in metric:
                logger.warning(f"Invalid metric: Missing required field '{field}'")
                return False
            if metric[field] is None:
                logger.warning(f"Invalid metric: Field '{field}' is None")
                return False
        
        # Validate value is numeric
        try:
            float(metric['value'])
        except (ValueError, TypeError):
            logger.warning(f"Invalid metric: Value '{metric['value']}' is not numeric")
            return False
        
        logger.debug(f"Validated metric: {metric}")
        return True

    def add_metrics(self, metrics: List[Dict]) -> None:
        """Add metrics to the upload queue."""
        valid_metrics = []
        invalid_metrics = []
        
        for metric in metrics:
            if self.validate_metric(metric):
                valid_metrics.append(metric)
                logger.debug(f"Valid metric added to queue: {metric}")
            else:
                invalid_metrics.append(metric)
                logger.warning(f"Invalid metric skipped: {metric}")
        
        if valid_metrics:
            try:
                for metric in valid_metrics:
                    if self.queue.full():
                        logger.warning("Queue is full, dropping oldest metric")
                        self.queue.get()  # Remove oldest metric
                    self.queue.put(metric)
                logger.info(f"Added {len(valid_metrics)} valid metrics to queue")
            except Exception as e:
                logger.error(f"Error adding metrics to queue: {str(e)}", exc_info=True)
        
        if invalid_metrics:
            logger.warning(f"Skipped {len(invalid_metrics)} invalid metrics")

    def upload_batch(self) -> None:
        """Upload a batch of metrics to the server."""
        batch = []
        try:
            # Collect batch
            while len(batch) < self.batch_size and not self.queue.empty():
                metric = self.queue.get_nowait()
                batch.append(metric)
            
            if not batch:
                return
            
            logger.info(f"Uploading batch of {len(batch)} metrics")
            
            # Prepare request data
            data = {
                'metrics': batch,
                'timestamp': time.time()
            }
            
            # Send request
            response = requests.post(
                f"{self.api_url}/metrics/batch",
                json=batch,
                headers={'Content-Type': 'application/json'}
            )
            
            # Handle response
            if response.status_code == 200:
                # Log successful upload with details
                metrics_by_device = {}
                for metric in batch:
                    device = metric['device_name']
                    if device not in metrics_by_device:
                        metrics_by_device[device] = []
                    metrics_by_device[device].append(metric['metric_name'])
                
                for device, metric_names in metrics_by_device.items():
                    logger.info(f"Successfully uploaded {len(metric_names)} metrics for device '{device}': {', '.join(metric_names)}")
                
                # Log summary
                logger.info(f"Upload successful - Total metrics: {len(batch)}, Response time: {response.elapsed.total_seconds():.2f}s")
            else:
                logger.error(f"Failed to upload metrics. Status: {response.status_code}, Response: {response.text}")
                # Put failed metrics back in queue
                for metric in batch:
                    if self.queue.full():
                        logger.warning("Queue is full, dropping oldest metric")
                        self.queue.get()
                    self.queue.put(metric)
                logger.info("Failed metrics requeued for retry")
                
        except requests.exceptions.RequestException as e:
            logger.error(f"Network error while uploading metrics: {str(e)}", exc_info=True)
            # Put failed metrics back in queue
            for metric in batch:
                if self.queue.full():
                    logger.warning("Queue is full, dropping oldest metric")
                    self.queue.get()
                self.queue.put(metric)
            logger.info("Failed metrics requeued for retry")
        except Exception as e:
            logger.error(f"Unexpected error while uploading metrics: {str(e)}", exc_info=True)

    def start_uploader(self) -> None:
        """Start the uploader thread."""
        if self.upload_thread is not None and self.upload_thread.is_alive():
            logger.warning("Uploader thread is already running")
            return
        
        logger.info("Starting uploader thread")
        self.stop_event.clear()
        self.upload_thread = Thread(target=self._uploader_loop)
        self.upload_thread.daemon = True
        self.upload_thread.start()

    def stop_uploader(self) -> None:
        """Stop the uploader thread."""
        logger.info("Stopping uploader thread")
        self.stop_event.set()
        if self.upload_thread is not None:
            self.upload_thread.join()
        logger.info("Uploader thread stopped")

    def _uploader_loop(self) -> None:
        """Main loop for the uploader thread."""
        logger.info("Uploader loop started")
        while not self.stop_event.is_set():
            try:
                self.upload_batch()
                time.sleep(self.collector_config['upload_interval'])
            except Exception as e:
                logger.error(f"Error in uploader loop: {str(e)}", exc_info=True)
                time.sleep(5)  # Wait before retrying
        logger.info("Uploader loop stopped") 