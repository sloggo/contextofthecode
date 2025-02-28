from flask import Blueprint, render_template, Response, stream_with_context, request, jsonify
from sqlalchemy import func
from datetime import datetime, timedelta
from ...database.database import db
from ...database.models import Device, MetricInfo, MetricValue
from ...utils.logging_config import setup_logger
import json
import time

logger = setup_logger('views')

views_bp = Blueprint('views', __name__, template_folder='../templates')

@views_bp.route('/api/devices')
def get_devices():
    """Get list of available devices"""
    try:
        devices = db.session.query(Device.name).distinct().all()
        device_list = [device[0] for device in devices]
        logger.info(f"Retrieved devices: {device_list}")
        return jsonify(device_list)
    except Exception as e:
        logger.error(f"Error getting devices: {str(e)}")
        return jsonify([])

@views_bp.route('/api/metrics')
def get_metrics():
    """Get list of available metrics for a device"""
    try:
        device_name = request.args.get('device')
        logger.info(f"Getting metrics for device: {device_name}")
        
        if not device_name:
            metrics = db.session.query(MetricInfo.name).distinct().all()
        else:
            metrics = db.session.query(MetricInfo.name)\
                .join(MetricValue)\
                .join(Device)\
                .filter(Device.name == device_name)\
                .distinct().all()
        
        metric_list = [metric[0] for metric in metrics]
        logger.info(f"Retrieved metrics: {metric_list}")
        return jsonify(metric_list)
    except Exception as e:
        logger.error(f"Error getting metrics: {str(e)}")
        return jsonify([])

@views_bp.route('/api/metric-values')
def get_metric_values():
    """Get paginated metric values"""
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 10, type=int)
    device_name = request.args.get('device')
    metric_name = request.args.get('metric')
    
    query = db.session.query(
        Device.name.label('device_name'),
        MetricInfo.name.label('metric_name'),
        MetricValue.metric_value,
        MetricValue.timestamp
    ).join(Device).join(MetricInfo)
    
    if device_name:
        query = query.filter(Device.name == device_name)
    if metric_name:
        query = query.filter(MetricInfo.name == metric_name)
    
    total = query.count()
    values = query.order_by(MetricValue.timestamp.desc())\
        .offset((page - 1) * per_page)\
        .limit(per_page)\
        .all()
    
    return jsonify({
        'total': total,
        'page': page,
        'per_page': per_page,
        'total_pages': (total + per_page - 1) // per_page,
        'data': [{
            'device_name': value.device_name,
            'metric_name': value.metric_name,
            'value': float(value.metric_value),
            'timestamp': value.timestamp.strftime('%Y-%m-%d %H:%M:%S')
        } for value in values]
    })

def get_metrics_data(device_name=None, metric_name=None):
    """Get metrics data for the dashboard"""
    start_time = datetime.utcnow() - timedelta(hours=24)
    
    # Base query for time series
    time_series_query = db.session.query(
        Device.name,
        MetricInfo.name.label('metric_name'),
        MetricValue.metric_value,
        MetricValue.timestamp
    ).join(Device).join(MetricInfo)\
    .filter(MetricValue.timestamp >= start_time)
    
    # Apply filters if provided
    if device_name:
        time_series_query = time_series_query.filter(Device.name == device_name)
    if metric_name:
        time_series_query = time_series_query.filter(MetricInfo.name == metric_name)
    
    time_series = time_series_query.order_by(
        Device.name, MetricInfo.name, MetricValue.timestamp
    ).all()

    # Base query for summary metrics
    summary_query = db.session.query(
        Device.name,
        MetricInfo.name.label('metric_name'),
        func.avg(MetricValue.metric_value).label('avg_value'),
        func.min(MetricValue.metric_value).label('min_value'),
        func.max(MetricValue.metric_value).label('max_value'),
        func.max(MetricValue.timestamp).label('last_updated')
    ).join(Device).join(MetricInfo)\
    .filter(MetricValue.timestamp >= start_time)
    
    # Apply filters if provided
    if device_name:
        summary_query = summary_query.filter(Device.name == device_name)
    if metric_name:
        summary_query = summary_query.filter(MetricInfo.name == metric_name)
    
    summary_metrics = summary_query.group_by(Device.name, MetricInfo.name).all()

    # Organize metrics by device and metric name
    metrics = {}
    
    # First, organize time series data
    for record in time_series:
        if record.name not in metrics:
            metrics[record.name] = {}
        if record.metric_name not in metrics[record.name]:
            metrics[record.name][record.metric_name] = {
                'timestamps': [],
                'values': []
            }
        metrics[record.name][record.metric_name]['timestamps'].append(
            record.timestamp.strftime('%Y-%m-%d %H:%M:%S')
        )
        metrics[record.name][record.metric_name]['values'].append(
            float(record.metric_value)
        )

    # Then add summary data
    for summary in summary_metrics:
        if summary.name not in metrics:
            metrics[summary.name] = {}
        if summary.metric_name not in metrics[summary.name]:
            metrics[summary.name][summary.metric_name] = {
                'timestamps': [],
                'values': []
            }
        
        # Get the most recent value
        current_value = metrics[summary.name][summary.metric_name]['values'][-1] \
            if metrics[summary.name][summary.metric_name]['values'] else 0.0
        
        metrics[summary.name][summary.metric_name].update({
            'current_value': float(current_value),
            'avg_value': float(summary.avg_value),
            'min_value': float(summary.min_value),
            'max_value': float(summary.max_value),
            'last_updated': summary.last_updated.strftime('%Y-%m-%d %H:%M:%S')
        })
    
    return metrics

@views_bp.route('/dashboard')
def dashboard():
    """Render the dashboard template"""
    try:
        # Check if we have any data
        device_count = db.session.query(Device).count()
        metric_count = db.session.query(MetricInfo).count()
        value_count = db.session.query(MetricValue).count()
        
        logger.info(f"Database status - Devices: {device_count}, Metrics: {metric_count}, Values: {value_count}")
        
        # Get filter parameters
        device_name = request.args.get('device')
        metric_name = request.args.get('metric')
        
        # Get initial devices
        devices = db.session.query(Device.name).distinct().all()
        device_list = [device[0] for device in devices]
        logger.info(f"Available devices: {device_list}")
        
        # Get initial metrics
        metrics_query = db.session.query(MetricInfo.name)
        if device_name:
            metrics_query = metrics_query.join(MetricValue).join(Device).filter(Device.name == device_name)
        metrics_list = [metric[0] for metric in metrics_query.distinct().all()]
        logger.info(f"Available metrics: {metrics_list}")
        
        # Get metrics data
        metrics = get_metrics_data(device_name, metric_name)
        logger.info(f"Number of devices with metrics: {len(metrics)}")
        for device, device_metrics in metrics.items():
            logger.info(f"Device {device} has {len(device_metrics)} metrics")
        
        # Prepare template data
        template_data = {
            'metrics': metrics,
            'initial_devices': device_list,
            'initial_metrics': metrics_list,
            'selected_device': device_name,
            'selected_metric': metric_name
        }
        
        logger.info("Rendering dashboard template with data")
        return render_template('metrics.html', **template_data)
        
    except Exception as e:
        logger.error(f"Error rendering dashboard: {str(e)}")
        return render_template(
            'metrics.html',
            metrics={},
            initial_devices=[],
            initial_metrics=[],
            selected_device=None,
            selected_metric=None
        )

@views_bp.route('/metrics/stream')
def stream_metrics():
    """Stream metrics updates using Server-Sent Events"""
    device_name = request.args.get('device')
    metric_name = request.args.get('metric')
    
    @stream_with_context
    def generate_metrics():
        while True:
            # Get latest metrics
            metrics = get_metrics_data(device_name, metric_name)
            
            # Format the SSE data
            data = json.dumps({
                'metrics': metrics,
                'timestamp': datetime.utcnow().isoformat()
            })
            
            # Send the SSE message
            yield f"data: {data}\n\n"
            
            # Wait before sending next update
            time.sleep(5)  # Update every 5 seconds
    
    return Response(generate_metrics(), mimetype='text/event-stream') 