import psutil
import time
from datetime import datetime
from typing import Dict, List
from ..utils.logging_config import setup_logger

logger = setup_logger('pc_collector')

class PCCollector:
    def __init__(self, device_name: str = "Device 1"):
        self.device_name = device_name
        logger.info(f"Initialized PC collector for device: {device_name}")

    def collect_cpu_metrics(self) -> Dict:
        try:
            cpu_percent = psutil.cpu_percent(interval=1)
            logger.debug(f"Collected CPU usage: {cpu_percent}%")
            return {
                "device_name": self.device_name,
                "metric_name": "cpu_usage",
                "metric_value": cpu_percent,
                "timestamp": datetime.utcnow()
            }
        except Exception as e:
            logger.error(f"Error collecting CPU metrics: {e}", exc_info=True)
            return None

    def collect_memory_metrics(self) -> Dict:
        try:
            memory = psutil.virtual_memory()
            logger.debug(f"Collected memory usage: {memory.percent}%")
            return {
                "device_name": self.device_name,
                "metric_name": "memory_usage",
                "metric_value": memory.percent,
                "timestamp": datetime.utcnow()
            }
        except Exception as e:
            logger.error(f"Error collecting memory metrics: {e}", exc_info=True)
            return None

    def collect_metrics(self) -> List[Dict]:
        """Collect all metrics from the PC"""
        metrics = []
        cpu_metrics = self.collect_cpu_metrics()
        if cpu_metrics:
            metrics.append(cpu_metrics)
        
        memory_metrics = self.collect_memory_metrics()
        if memory_metrics:
            metrics.append(memory_metrics)
        
        logger.info(f"Collected {len(metrics)} PC metrics")
        return metrics 