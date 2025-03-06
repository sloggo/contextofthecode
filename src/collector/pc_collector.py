import psutil
import time
from datetime import datetime
from typing import List, Dict, Optional
from ..utils.logging_config import get_logger
from ..utils.system_info import get_system_info

logger = get_logger('collector.pc')

class PCCollector:
    def __init__(self):
        system_info = get_system_info()
        if not system_info:
            raise RuntimeError("Could not get system information")
        self.system_uuid = system_info['uuid']
        self.device_name = system_info['name']
        logger.info(f"Initializing PC collector for device: {self.device_name} (UUID: {self.system_uuid})")

    def collect_cpu_metrics(self) -> Optional[Dict]:
        """Collect CPU metrics from the system."""
        try:
            cpu_percent = psutil.cpu_percent(interval=1)
            cpu_count = psutil.cpu_count()
            cpu_freq = psutil.cpu_freq()
            
            metrics = {
                'device_id': self.system_uuid,
                'device_name': self.device_name,
                'metric_name': 'cpu_usage',
                'value': cpu_percent,
                'timestamp': datetime.now().isoformat(),
                'metric_metadata': {
                    'cpu_count': cpu_count,
                    'cpu_freq': cpu_freq.current if cpu_freq else None
                }
            }
            
            logger.debug(f"Collected CPU metrics: {metrics}")
            return metrics
        except Exception as e:
            logger.error(f"Error collecting CPU metrics: {str(e)}", exc_info=True)
            return None

    def collect_memory_metrics(self) -> Optional[Dict]:
        """Collect memory metrics from the system."""
        try:
            memory = psutil.virtual_memory()
            swap = psutil.swap_memory()
            
            metrics = {
                'device_id': self.system_uuid,
                'device_name': self.device_name,
                'metric_name': 'memory_usage',
                'value': memory.percent,
                'timestamp': datetime.now().isoformat(),
                'metric_metadata': {
                    'total_memory': memory.total,
                    'available_memory': memory.available,
                    'swap_total': swap.total,
                    'swap_used': swap.used
                }
            }
            
            logger.debug(f"Collected memory metrics: {metrics}")
            return metrics
        except Exception as e:
            logger.error(f"Error collecting memory metrics: {str(e)}", exc_info=True)
            return None

    def collect_metrics(self) -> List[Dict]:
        """Collect all metrics from the system."""
        logger.info(f"Starting metric collection for device: {self.device_name}")
        
        metrics = []
        
        # Collect CPU metrics
        cpu_metrics = self.collect_cpu_metrics()
        if cpu_metrics:
            metrics.append(cpu_metrics)
            logger.info(f"Successfully collected CPU metrics: {cpu_metrics['value']}%")
        else:
            logger.warning("Failed to collect CPU metrics")
        
        # Collect memory metrics
        memory_metrics = self.collect_memory_metrics()
        if memory_metrics:
            metrics.append(memory_metrics)
            logger.info(f"Successfully collected memory metrics: {memory_metrics['value']}%")
        else:
            logger.warning("Failed to collect memory metrics")
        
        logger.info(f"Completed metric collection. Total metrics collected: {len(metrics)}")
        return metrics 