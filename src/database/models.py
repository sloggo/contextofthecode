from datetime import datetime
from sqlalchemy import Column, Integer, String, Float, DateTime, ForeignKey, JSON
from sqlalchemy.orm import relationship
from .database import db
from src.utils.logging_config import get_logger
import uuid

logger = get_logger('database.models')

class Device(db.Model):
    """Model for storing device information."""
    __tablename__ = 'devices'
    
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    name = Column(String(100), unique=True, nullable=False)
    description = Column(String(500))
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    metric_values = relationship('MetricValue', back_populates='device')
    
    def __repr__(self):
        return f"<Device {self.name}>"

class MetricInfo(db.Model):
    """Model for storing metric metadata."""
    __tablename__ = 'metric_info'
    
    id = Column(Integer, primary_key=True)
    name = Column(String(100), nullable=False, unique=True)
    unit = Column(String(50))
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    values = relationship('MetricValue', back_populates='metric_info')
    
    def __repr__(self):
        return f"<MetricInfo {self.name}>"

class MetricValue(db.Model):
    """Model for storing metric values."""
    __tablename__ = 'metric_values'
    
    id = Column(Integer, primary_key=True)
    device_id = Column(String(36), ForeignKey('devices.id'), nullable=False)
    metric_info_id = Column(Integer, ForeignKey('metric_info.id'), nullable=False)
    metric_value = Column(Float, nullable=False)
    timestamp = Column(DateTime, nullable=False)
    metric_metadata = Column(JSON)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Relationships
    device = relationship('Device', back_populates='metric_values')
    metric_info = relationship('MetricInfo', back_populates='values')
    
    def __repr__(self):
        return f"<MetricValue {self.metric_value} for Device {self.device_id} at {self.timestamp}>" 