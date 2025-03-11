from flask import Blueprint, request, jsonify
from marshmallow import Schema, fields
from datetime import datetime, timedelta
from sqlalchemy import func
from ...database.database import db
from ...database.models import Device, MetricInfo, MetricValue

reporting_bp = Blueprint('reporting', __name__)

class MetricReportSchema(Schema):
    device_name = fields.Str()
    metric_name = fields.Str()
    metric_value = fields.Float()
    timestamp = fields.DateTime()

class MetricsSummarySchema(Schema):
    device_name = fields.Str()
    metric_name = fields.Str()
    avg_value = fields.Float()
    min_value = fields.Float()
    max_value = fields.Float()
    last_updated = fields.DateTime()

metric_report_schema = MetricReportSchema(many=True)
metrics_summary_schema = MetricsSummarySchema(many=True)

@reporting_bp.route('/metrics/<device_name>', methods=['GET'])
def get_device_metrics(device_name):
    # Get query parameters
    start_time = request.args.get('start_time', type=lambda x: datetime.fromisoformat(x) if x else None)
    end_time = request.args.get('end_time', type=lambda x: datetime.fromisoformat(x) if x else None)
    
    # Build query
    query = db.session.query(MetricValue, Device).join(Device)
    query = query.filter(Device.name == device_name)
    
    if start_time:
        query = query.filter(MetricValue.timestamp >= start_time)
    if end_time:
        query = query.filter(MetricValue.timestamp <= end_time)
    
    results = query.order_by(MetricValue.timestamp.desc()).all()
    
    # Format results
    metrics_data = [
        {
            'device_name': device.name,
            'metric_name': metric.metric_name,
            'metric_value': metric.metric_value,
            'timestamp': metric.timestamp
        }
        for metric, device in results
    ]
    
    return jsonify(metric_report_schema.dump(metrics_data))

@reporting_bp.route('/summary', methods=['GET'])
def get_metrics_summary():
    # Get time range from query parameters (default 24 hours)
    time_range = request.args.get('time_range', default=24, type=int)
    start_time = datetime.utcnow() - timedelta(hours=time_range)
    
    # Build query
    results = db.session.query(
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
    
    # Format results
    summary_data = [
        {
            'device_name': result.device_name,
            'metric_name': result.metric_name,
            'avg_value': float(result.avg_value),
            'min_value': float(result.min_value),
            'max_value': float(result.max_value),
            'last_updated': result.last_updated,
            'count': result.count
        }
        for result in results
    ]
    
    return jsonify(metrics_summary_schema.dump(summary_data)) 