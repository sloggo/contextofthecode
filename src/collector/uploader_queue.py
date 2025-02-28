import asyncio
import aiohttp
import json
from typing import List, Dict
from collections import deque
from datetime import datetime
from ..utils.config import get_settings
from ..utils.logging_config import setup_logger

settings = get_settings()
logger = setup_logger('uploader')

class DateTimeEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, datetime):
            return obj.isoformat()
        return super().default(obj)

class UploaderQueue:
    def __init__(self):
        self.queue = deque(maxlen=settings.MAX_QUEUE_SIZE)
        self.batch_size = settings.UPLOAD_BATCH_SIZE
        self.api_url = f"http://{settings.APP_HOST}:{settings.APP_PORT}/api/v1/aggregator/metrics/batch"
        self.headers = {'Content-Type': 'application/json'}
        logger.info(f"Initialized uploader queue with batch size: {self.batch_size}, max size: {settings.MAX_QUEUE_SIZE}")

    def validate_metric(self, metric: Dict) -> bool:
        """Validate that a metric has all required fields with non-null values"""
        required_fields = ['device_name', 'metric_name', 'value']
        for field in required_fields:
            if field not in metric or metric[field] is None:
                logger.warning(f"Invalid metric - missing or null {field}: {metric}")
                return False
        return True

    def add_metrics(self, metrics: List[Dict]):
        """Add metrics to the queue"""
        for metric in metrics:
            # Ensure metric has the correct format
            formatted_metric = {
                'device_name': metric.get('device_name'),
                'metric_name': metric.get('metric_name'),
                'value': metric.get('metric_value'),  # Note: input uses metric_value, but API expects value
                'timestamp': metric.get('timestamp', datetime.utcnow())
            }
            
            if self.validate_metric(formatted_metric):
                logger.debug(f"Adding valid metric to queue: {formatted_metric}")
                self.queue.append(formatted_metric)
            else:
                logger.warning(f"Skipping invalid metric: {formatted_metric}")

    async def upload_batch(self, session: aiohttp.ClientSession) -> bool:
        """Upload a batch of metrics to the aggregator API"""
        if not self.queue:
            return True

        # Get batch of metrics
        batch = []
        while len(batch) < self.batch_size and self.queue:
            batch.append(self.queue.popleft())

        try:
            # Serialize datetime objects properly
            json_data = json.dumps(batch, cls=DateTimeEncoder)
            logger.debug(f"Uploading batch to {self.api_url}")
            logger.debug(f"Batch data: {json_data}")
            
            async with session.post(self.api_url, data=json_data, headers=self.headers) as response:
                if response.status == 200:
                    logger.info(f"Successfully uploaded {len(batch)} metrics")
                    return True
                else:
                    error_text = await response.text()
                    logger.error(f"Failed to upload metrics. Status: {response.status}")
                    logger.error(f"Error response: {error_text}")
                    # Put metrics back in queue on failure
                    for metric in batch:
                        self.queue.append(metric)
                    return False
        except Exception as e:
            logger.error(f"Error uploading metrics: {str(e)}", exc_info=True)
            # Put metrics back in queue on error
            for metric in batch:
                self.queue.append(metric)
            return False

    async def start_uploader(self):
        """Start the uploader process"""
        logger.info(f"Starting uploader with interval: {settings.UPLOAD_INTERVAL} seconds")
        async with aiohttp.ClientSession() as session:
            while True:
                await self.upload_batch(session)
                await asyncio.sleep(settings.UPLOAD_INTERVAL) 