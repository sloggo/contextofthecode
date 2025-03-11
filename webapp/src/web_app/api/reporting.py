from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import func
from typing import List, Optional
from datetime import datetime, timedelta
from pydantic import BaseModel

from ...database.database import get_db
from ...database.models import Device, MetricInfo, MetricValue

router = APIRouter()

class MetricReport(BaseModel):
    device_name: str
    metric_name: str
    metric_value: float
    timestamp: datetime

    class Config:
        from_attributes = True

class DeviceMetricsSummary(BaseModel):
    device_name: str
    metric_name: str
    avg_value: float
    min_value: float
    max_value: float
    last_updated: datetime

@router.get("/metrics/{device_name}", response_model=List[MetricReport])
async def get_device_metrics(
    device_name: str,
    start_time: Optional[datetime] = Query(None),
    end_time: Optional[datetime] = Query(None),
    db: Session = Depends(get_db)
):
    query = db.query(
        Device.name.label('device_name'),
        MetricInfo.name.label('metric_name'),
        MetricValue.metric_value,
        MetricValue.timestamp
    ).join(Device)\
    .join(MetricInfo)\
    .filter(Device.name == device_name)
    
    if start_time:
        query = query.filter(MetricValue.timestamp >= start_time)
    if end_time:
        query = query.filter(MetricValue.timestamp <= end_time)
    
    results = query.order_by(MetricValue.timestamp.desc()).all()
    
    return [
        MetricReport(
            device_name=result.device_name,
            metric_name=result.metric_name,
            metric_value=float(result.metric_value),
            timestamp=result.timestamp
        )
        for result in results
    ]

@router.get("/summary", response_model=List[DeviceMetricsSummary])
async def get_metrics_summary(
    time_range: Optional[int] = Query(24, description="Time range in hours"),
    db: Session = Depends(get_db)
):
    start_time = datetime.utcnow() - timedelta(hours=time_range)
    
    results = db.query(
        Device.name.label('device_name'),
        MetricInfo.name.label('metric_name'),
        func.avg(MetricValue.metric_value).label('avg_value'),
        func.min(MetricValue.metric_value).label('min_value'),
        func.max(MetricValue.metric_value).label('max_value'),
        func.max(MetricValue.timestamp).label('last_updated'),
        func.count(MetricValue.id).label('count')
    ).join(Device)\
    .join(MetricInfo)\
    .filter(MetricValue.timestamp >= start_time)\
    .group_by(Device.name, MetricInfo.name)\
    .all()
    
    return [
        DeviceMetricsSummary(
            device_name=result.device_name,
            metric_name=result.metric_name,
            avg_value=float(result.avg_value),
            min_value=float(result.min_value),
            max_value=float(result.max_value),
            last_updated=result.last_updated
        )
        for result in results
    ] 