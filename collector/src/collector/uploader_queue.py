import time
import json
import requests
import threading
from typing import List, Dict
from queue import Queue, Empty, Full
from threading import Thread, Event
from ..utils.logging_config import get_logger
from ..utils.config import config
from datetime import datetime
from ..utils.time_utils import get_utc_timestamp, format_timestamp

logger = get_logger('collector.uploader')

class SSEClient:
    def __init__(self, url):
        self.url = url
        self.session = requests.Session()
        self.running = True
        
    def events(self):
        """Generator for SSE events."""
        while self.running:
            try:
                response = self.session.get(
                    self.url, 
                    stream=True,
                    headers={'Accept': 'text/event-stream'}
                )
                
                if response.status_code != 200:
                    logger.error(f"SSE connection failed with status {response.status_code}")
                    time.sleep(5)
                    continue
                
                # Process the stream
                buffer = ""
                for chunk in response.iter_content(chunk_size=1):
                    if not self.running:
                        break
                        
                    if chunk:
                        chunk_str = chunk.decode('utf-8')
                        buffer += chunk_str
                        
                        if buffer.endswith('\n\n'):
                            # Complete event received
                            lines = buffer.split('\n')
                            data = None
                            
                            for line in lines:
                                if line.startswith('data:'):
                                    data = line[5:].strip()
                            
                            if data:
                                yield data
                                
                            buffer = ""
            except Exception as e:
                logger.error(f"SSE connection error: {e}")
                time.sleep(5)
                
    def close(self):
        """Close the SSE connection."""
        self.running = False
        self.session.close()

class UploaderQueue:
    def __init__(self, api_url: str, batch_size: int = None, max_queue_size: int = None):
        self.api_url = api_url
        self.batch_size = batch_size or config.collector.batch_size
        self.max_queue_size = max_queue_size or config.collector.max_queue_size
        self.queue = Queue(maxsize=self.max_queue_size)
        self.stop_event = Event()
        self.upload_thread = None
        self.running = True
        
        logger.info(f"Initializing uploader queue with batch_size={self.batch_size}, max_queue_size={self.max_queue_size}")
        logger.info(f"API URL: {self.api_url}")

        # Start the control listener thread
        self.control_thread = Thread(target=self._listen_for_control, daemon=True)
        self.control_thread.start()

    def _listen_for_control(self):
        """Listen for control messages from the server."""
        control_url = f"{self.api_url}/control"
        logger.info(f"Starting SSE control listener at {control_url}")
        
        while not self.stop_event.is_set():
            try:
                response = requests.get(
                    control_url, 
                    stream=True,
                    headers={'Accept': 'text/event-stream'},
                    timeout=30
                )
                
                if response.status_code != 200:
                    logger.error(f"SSE connection failed with status {response.status_code}")
                    time.sleep(5)
                    continue
                
                # Process the stream
                buffer = ""
                for chunk in response.iter_content(chunk_size=1):
                    if not chunk:
                        continue
                        
                    chunk_str = chunk.decode('utf-8')
                    buffer += chunk_str
                    
                    if buffer.endswith('\n\n'):
                        lines = buffer.split('\n')
                        for line in lines:
                            # Skip empty lines and comment lines (keepalive)
                            if not line or line.startswith(':'):
                                continue
                                
                            if line.startswith('data:'):
                                data = line[5:].strip()
                                logger.info(f"Received control message: {data}")
                                
                                if data == 'STOPPED' and self.running:
                                    self.running = False
                                    logger.info("Stopping collector due to control message")
                                elif data == 'RUNNING' and not self.running:
                                    self.running = True
                                    logger.info("Starting collector due to control message")
                        
                        buffer = ""
            except requests.exceptions.Timeout:
                logger.warning("Control SSE connection timed out, reconnecting...")
            except requests.exceptions.ConnectionError:
                logger.warning("Control SSE connection error, reconnecting in 5 seconds...")
                time.sleep(5)
            except Exception as e:
                logger.error(f"Control listener error: {e}")
                time.sleep(10)

    def validate_metric(self, metric: Dict) -> bool:
        """Validate a metric."""
        # Check required fields
        if 'device_name' not in metric or metric['device_name'] is None:
            logger.warning(f"Invalid metric: Missing or null device_name")
            return False
        
        if 'metric_name' not in metric or metric['metric_name'] is None:
            logger.warning(f"Invalid metric: Missing or null metric_name")
            return False
        
        # Check for value (could be in 'value' or 'metric_value')
        value = None
        if 'value' in metric and metric['value'] is not None:
            value = metric['value']
        elif 'metric_value' in metric and metric['metric_value'] is not None:
            value = metric['metric_value']
        else:
            logger.warning(f"Invalid metric: Missing or null value/metric_value")
            return False
        
        # Validate value is numeric
        try:
            value = float(value)
            if value is None:
                logger.warning(f"Invalid metric: Value is None")
                return False
            
            # Update the metric with the validated value
            if 'value' in metric:
                metric['value'] = value
            if 'metric_value' in metric:
                metric['metric_value'] = value
            
        except (ValueError, TypeError):
            logger.warning(f"Invalid metric: Value '{value}' is not numeric")
            return False
        
        logger.debug(f"Validated metric: {metric}")
        return True

    def _prepare_metric(self, metric: Dict) -> Dict:
        """Prepare a metric for sending to the server."""
        # Create a copy to avoid modifying the original
        prepared = metric.copy()
        
        # Ensure the metric has the correct field names
        if 'value' in prepared and 'metric_value' not in prepared:
            prepared['metric_value'] = prepared['value']
            
        # Ensure timestamp is in the correct format
        if 'timestamp' in prepared and not isinstance(prepared['timestamp'], str):
            if isinstance(prepared['timestamp'], datetime):
                prepared['timestamp'] = prepared['timestamp'].isoformat()
                
        return prepared

    def add_metrics(self, metrics: List[Dict]) -> None:
        """Add metrics to the upload queue."""
        if not self.running:
            logger.info("Collector is stopped, skipping metrics")
            return
            
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

    def _upload_metrics_batch(self, metrics_batch):
        """Upload a batch of metrics to the server."""
        try:
            # Ensure all metrics have the correct format
            formatted_batch = []
            for metric in metrics_batch:
                # Create a properly formatted metric
                formatted_metric = {
                    "device_name": metric.get('device_name'),
                    "metric_name": metric.get('metric_name'),
                    # Ensure we have a valid metric value
                    "metric_value": metric.get('metric_value', metric.get('value')),
                    # Use the timestamp from the metric or generate a new one
                    "timestamp": metric.get('timestamp', get_utc_timestamp())
                }
                
                # Add device_id if available
                if 'device_id' in metric:
                    formatted_metric['device_id'] = metric['device_id']
                    
                # Add metadata if available
                if 'metadata' in metric:
                    formatted_metric['metadata'] = metric['metadata']
                    
                formatted_batch.append(formatted_metric)
                
            if not formatted_batch:
                logger.warning("No valid metrics to upload after formatting")
                return True  # Return success since there's nothing to upload
                
            # Use the correct endpoint for batch uploads
            upload_url = f"{self.api_url}/metrics/batch"
            
            logger.info(f"Uploading {len(formatted_batch)} metrics to {upload_url}")
            
            # Send the batch to the server
            response = requests.post(
                upload_url,
                json=formatted_batch,
                headers={"Content-Type": "application/json"},
                timeout=30
            )
            
            # Check the response
            if response.status_code == 200:
                logger.info(f"Successfully uploaded {len(formatted_batch)} metrics")
                return True
            else:
                logger.error(f"Failed to upload metrics batch: {response.status_code} - {response.text}")
                return False
        except requests.exceptions.Timeout:
            logger.error("Timeout while uploading metrics batch")
            return False
        except requests.exceptions.ConnectionError as e:
            logger.error(f"Connection error while uploading metrics batch: {str(e)}")
            return False
        except Exception as e:
            logger.error(f"Error uploading metrics batch: {str(e)}")
            return False

    def start(self):
        """Start the uploader thread."""
        if self.upload_thread is None or not self.upload_thread.is_alive():
            logger.info("Starting uploader thread")
            self.stop_event.clear()
            self.running = True
            self.upload_thread = Thread(target=self._upload_worker, daemon=True)
            self.upload_thread.start()
        else:
            logger.warning("Uploader thread is already running")

    def stop(self):
        """Stop the uploader thread."""
        logger.info("Stopping uploader thread")
        self.running = False
        self.stop_event.set()
        
        # Wait for the thread to finish
        if self.upload_thread and self.upload_thread.is_alive():
            self.upload_thread.join(timeout=5)
            
        logger.info("Uploader thread stopped")

    def _upload_worker(self):
        """Worker thread to upload metrics in batches."""
        logger.info("Uploader worker thread started")
        
        while not self.stop_event.is_set():
            try:
                # Collect metrics from the queue
                batch = []
                
                # Try to get at least one metric (blocking)
                try:
                    metric = self.queue.get(block=True, timeout=config.collector.upload_interval)
                    batch.append(metric)
                    self.queue.task_done()
                except Empty:
                    # No metrics available, continue the loop
                    continue
                
                # Try to get more metrics (non-blocking)
                try:
                    while len(batch) < self.batch_size:
                        metric = self.queue.get(block=False)
                        batch.append(metric)
                        self.queue.task_done()
                except Empty:
                    # No more metrics available
                    pass
                
                # Upload the batch
                if batch:
                    logger.info(f"Uploading batch of {len(batch)} metrics")
                    if self._upload_metrics_batch(batch):
                        logger.info(f"Successfully uploaded {len(batch)} metrics")
                    else:
                        logger.error(f"Failed to upload {len(batch)} metrics")
                
            except Exception as e:
                logger.error(f"Error in uploader worker: {str(e)}")
                
            # Sleep briefly to avoid tight loop
            time.sleep(0.1)
        
        logger.info("Uploader worker thread exiting")

    def _uploader_loop(self) -> None:
        """Main loop for the uploader thread."""
        logger.info("Uploader loop started")
        while not self.stop_event.is_set():
            try:
                if self.running:
                    self._upload_worker()
                time.sleep(config.collector.upload_interval)
            except Exception as e:
                logger.error(f"Error in uploader loop: {str(e)}", exc_info=True)
                time.sleep(5)  # Wait before retrying
        logger.info("Uploader loop stopped") 