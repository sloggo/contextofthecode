from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List
from datetime import datetime
from pydantic import BaseModel

from ...database.database import get_db
from ...database.models import Device, MetricInfo, MetricValue

router = APIRouter()

class MetricData(BaseModel):
    device_name: str
    metric_name: str
    metric_value: float
    timestamp: datetime = None

    class Config:
        from_attributes = True

@router.post("/metrics/", response_model=MetricData)
async def collect_metric(metric: MetricData, db: Session = Depends(get_db)):
    # Get or create device
    device = db.query(Device).filter(Device.name == metric.device_name).first()
    if not device:
        device = Device(
            name=metric.device_name,
            device_type='pc' if 'Device 1' in metric.device_name else 'third_party'
        )
        db.add(device)
        db.commit()
        db.refresh(device)

    # Get or create metric info
    metric_info = db.query(MetricInfo).filter(MetricInfo.name == metric.metric_name).first()
    if not metric_info:
        metric_info = MetricInfo(
            name=metric.metric_name,
            description=f"Metric for {metric.metric_name}",
            unit="units"
        )
        db.add(metric_info)
        db.commit()
        db.refresh(metric_info)

    # Create metric value
    db_metric = MetricValue(
        device_id=device.id,
        metric_info_id=metric_info.id,
        metric_value=metric.metric_value,
        timestamp=metric.timestamp or datetime.utcnow()
    )
    db.add(db_metric)
    db.commit()
    db.refresh(db_metric)

    return metric

@router.post("/metrics/batch/", response_model=List[MetricData])
async def collect_metrics_batch(metrics: List[MetricData], db: Session = Depends(get_db)):
    result = []
    for metric in metrics:
        result.append(await collect_metric(metric, db))
    return result 