from sqlalchemy import Column, Integer, String, Float, DateTime, ForeignKey
from sqlalchemy.orm import relationship, declarative_base
from datetime import datetime
from .database import db

# Create Base class for SQLAlchemy models
Base = db.Model

class Device(Base):
    __tablename__ = 'devices'

    id = Column(Integer, primary_key=True)
    name = Column(String, unique=True, nullable=False)
    device_type = Column(String, nullable=True)  # 'pc' or 'third_party'
    created_at = Column(DateTime, default=datetime.utcnow)
    metric_values = relationship('MetricValue', back_populates='device')

class MetricInfo(Base):
    __tablename__ = 'metric_info'

    id = Column(Integer, primary_key=True)
    name = Column(String, unique=True, nullable=False)
    description = Column(String, nullable=True)
    unit = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    metric_values = relationship('MetricValue', back_populates='metric_info')

class MetricValue(Base):
    __tablename__ = 'metric_values'

    id = Column(Integer, primary_key=True)
    device_id = Column(Integer, ForeignKey('devices.id'), nullable=False)
    metric_info_id = Column(Integer, ForeignKey('metric_info.id'), nullable=False)
    metric_value = Column(Float, nullable=False)
    timestamp = Column(DateTime, nullable=False, default=datetime.utcnow)

    device = relationship('Device', back_populates='metric_values')
    metric_info = relationship('MetricInfo', back_populates='metric_values') 