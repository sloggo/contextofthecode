import aiohttp
import asyncio
from datetime import datetime
from typing import Dict, List
from ..utils.config import get_settings

settings = get_settings()

class ThirdPartyCollector:
    def __init__(self, device_name: str = "Device 2"):
        self.device_name = device_name
        self.api_key = settings.DEVICE2_API_KEY

    async def collect_metric(self, session: aiohttp.ClientSession, metric_name: str) -> Dict:
        """Simulate collecting a metric from a third-party API"""
        # This is a mock implementation. Replace with actual API calls.
        await asyncio.sleep(0.1)  # Simulate API latency
        
        # Simulate random metric value between 0 and 100
        import random
        metric_value = random.uniform(0, 100)
        
        return {
            "device_name": self.device_name,
            "metric_name": metric_name,
            "metric_value": metric_value,
            "timestamp": datetime.utcnow()
        }

    async def collect_metrics(self) -> List[Dict]:
        """Collect all metrics from the third-party device"""
        async with aiohttp.ClientSession() as session:
            metrics = await asyncio.gather(
                self.collect_metric(session, "temperature"),
                self.collect_metric(session, "humidity")
            )
        return metrics 