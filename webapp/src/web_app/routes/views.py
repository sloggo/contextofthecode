from flask import Blueprint, render_template, Response, stream_with_context, request, jsonify, redirect, url_for
from sqlalchemy import func
from datetime import datetime, timedelta
from ...database.database import db
from ...database.models import Device, MetricInfo, MetricValue
from ...utils.logging_config import setup_logger
import json
import time
import random

logger = setup_logger('views')

views_bp = Blueprint('views', __name__, template_folder='../templates')

@views_bp.route('/')
def index():
    """Redirect to dashboard"""
    logger.info("Root route accessed, redirecting to dashboard")
    return redirect(url_for('views.dashboard'))

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
    ).join(Device, MetricValue.device_id == Device.id)\
      .join(MetricInfo, MetricValue.metric_info_id == MetricInfo.id)
    
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
    try:
        # Get date range from request parameters
        start_date = request.args.get('start_date')
        end_date = request.args.get('end_date')
        
        # Convert string dates to datetime objects
        try:
            if start_date:
                start_time = datetime.fromisoformat(start_date.replace('Z', '+00:00'))
            else:
                start_time = datetime.utcnow() - timedelta(hours=24)
                
            if end_date:
                end_time = datetime.fromisoformat(end_date.replace('Z', '+00:00'))
            else:
                end_time = datetime.utcnow()
        except ValueError as e:
            logger.error(f"Invalid date format: {e}")
            start_time = datetime.utcnow() - timedelta(hours=24)
            end_time = datetime.utcnow()
        
        # Ensure start_time is before end_time
        if start_time > end_time:
            start_time, end_time = end_time, start_time
        
        logger.info(f"Fetching metrics from {start_time} to {end_time}")
        
        # Check if we have any metrics in the database
        total_metrics = db.session.query(MetricValue).count()
        logger.info(f"Total metrics in database: {total_metrics}")
        
        # Base query for time series
        time_series_query = db.session.query(
            Device.name,
            MetricInfo.name.label('metric_name'),
            MetricValue.metric_value,
            MetricValue.timestamp
        ).join(Device, MetricValue.device_id == Device.id)\
          .join(MetricInfo, MetricValue.metric_info_id == MetricInfo.id)\
          .filter(MetricValue.timestamp >= start_time)\
          .filter(MetricValue.timestamp <= end_time)
        
        # Apply filters if provided
        if device_name:
            logger.info(f"Filtering time series by device: {device_name}")
            time_series_query = time_series_query.filter(Device.name == device_name)
        if metric_name:
            logger.info(f"Filtering time series by metric: {metric_name}")
            time_series_query = time_series_query.filter(MetricInfo.name == metric_name)
        
        # Log the SQL query for debugging
        logger.info(f"Time series query: {str(time_series_query)}")
        
        time_series = time_series_query.order_by(
            Device.name, MetricInfo.name, MetricValue.timestamp
        ).all()
        
        logger.info(f"Retrieved {len(time_series)} time series data points")

        # Base query for summary metrics
        summary_query = db.session.query(
            Device.name,
            MetricInfo.name.label('metric_name'),
            func.avg(MetricValue.metric_value).label('avg_value'),
            func.min(MetricValue.metric_value).label('min_value'),
            func.max(MetricValue.metric_value).label('max_value'),
            func.max(MetricValue.timestamp).label('last_updated')
        ).join(Device, MetricValue.device_id == Device.id)\
          .join(MetricInfo, MetricValue.metric_info_id == MetricInfo.id)\
          .filter(MetricValue.timestamp >= start_time)\
          .filter(MetricValue.timestamp <= end_time)
        
        # Apply filters if provided
        if device_name:
            logger.info(f"Filtering summary by device: {device_name}")
            summary_query = summary_query.filter(Device.name == device_name)
        if metric_name:
            logger.info(f"Filtering summary by metric: {metric_name}")
            summary_query = summary_query.filter(MetricInfo.name == metric_name)
        
        # Log the SQL query for debugging
        logger.info(f"Summary query: {str(summary_query)}")
        
        summary_metrics = summary_query.group_by(Device.name, MetricInfo.name).all()
        
        logger.info(f"Retrieved {len(summary_metrics)} summary metrics")

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
                # If we have summary data but no time series data, create empty arrays
                metrics[summary.name][summary.metric_name] = {
                    'timestamps': [],
                    'values': []
                }
            
            # Get the most recent value
            current_value = metrics[summary.name][summary.metric_name]['values'][-1] \
                if metrics[summary.name][summary.metric_name]['values'] else 0.0
            
            # Ensure all values are floats
            metrics[summary.name][summary.metric_name].update({
                'current_value': float(current_value),
                'avg_value': float(summary.avg_value) if summary.avg_value is not None else 0.0,
                'min_value': float(summary.min_value) if summary.min_value is not None else 0.0,
                'max_value': float(summary.max_value) if summary.max_value is not None else 100.0,
                'last_updated': summary.last_updated.strftime('%Y-%m-%d %H:%M:%S') if summary.last_updated else datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')
            })
        
        # If no metrics were found AND there are no metrics in the database, create a dummy entry for demonstration
        if not metrics and total_metrics == 0:
            logger.warning("No metrics found in database, creating dummy data for demonstration")
            now = datetime.utcnow()
            timestamps = [(now - timedelta(minutes=i)).strftime('%Y-%m-%d %H:%M:%S') for i in range(10, 0, -1)]
            
            metrics = {
                "Demo Device": {
                    "CPU Usage": {
                        "timestamps": timestamps,
                        "values": [random.randint(10, 90) for _ in range(10)],
                        "current_value": 50.0,
                        "avg_value": 50.0,
                        "min_value": 10.0,
                        "max_value": 90.0,
                        "last_updated": now.strftime('%Y-%m-%d %H:%M:%S')
                    }
                }
            }
        elif not metrics:
            # If we have metrics in the database but none match our filters
            logger.warning("No metrics match the current filters, but metrics exist in the database")
        
        logger.info(f"Retrieved metrics for {len(metrics)} devices")
        return metrics
        
    except Exception as e:
        logger.error(f"Error getting metrics data: {str(e)}", exc_info=True)
        # Return empty data structure with proper format
        return {}

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
        device_name = request.args.get('device', '')
        metric_name = request.args.get('metric', '')
        start_date = request.args.get('start_date')
        end_date = request.args.get('end_date')
        page = request.args.get('page', 1, type=int)
        per_page = request.args.get('per_page', 10, type=int)
        
        # Log the raw filter parameters
        logger.info(f"Raw filter parameters - Device: '{device_name}', Metric: '{metric_name}', Start: {start_date}, End: {end_date}")
        
        # Convert empty strings to None for proper filtering
        if device_name == '':
            device_name = None
            logger.info("Device filter is empty, showing all devices")
        if metric_name == '':
            metric_name = None
            logger.info("Metric filter is empty, showing all metrics")
            
        logger.info(f"Processed filter parameters - Device: {device_name}, Metric: {metric_name}, Start: {start_date}, End: {end_date}")
        
        # Get all devices from the database
        devices = db.session.query(Device.name).distinct().all()
        device_list = [device[0] for device in devices]
        
        # Ensure STOCK is in the device list if it exists in the database
        stock_device = db.session.query(Device).filter(Device.name == "STOCK").first()
        if stock_device and "STOCK" not in device_list:
            device_list.append("STOCK")
            
        logger.info(f"Available devices: {device_list}")
        
        # Get metrics based on selected device
        if device_name:
            # Get metrics for the selected device
            metrics_query = db.session.query(MetricInfo.name)\
                .join(MetricValue)\
                .join(Device)\
                .filter(Device.name == device_name)\
                .distinct()
        else:
            # Get all metrics
            metrics_query = db.session.query(MetricInfo.name).distinct()
            
        metrics_list = [metric[0] for metric in metrics_query.all()]
        logger.info(f"Available metrics: {metrics_list}")
        
        # Get metrics data for gauges and charts
        metrics = get_metrics_data(device_name, metric_name)
        
        # Get paginated metrics data for the table
        paginated_metrics = get_paginated_metrics(device_name, metric_name, start_date, end_date, page, per_page)
        
        # Pass empty string instead of None for selected values to ensure proper template rendering
        selected_device = device_name if device_name is not None else ''
        selected_metric = metric_name if metric_name is not None else ''
        
        return render_template(
            'metrics.html',
            metrics=metrics,
            initial_devices=device_list,
            initial_metrics=metrics_list,
            selected_device=selected_device,
            selected_metric=selected_metric,
            paginated_metrics=paginated_metrics,
            current_page=page,
            per_page=per_page
        )
        
    except Exception as e:
        logger.error(f"Error rendering dashboard: {str(e)}", exc_info=True)
        # Return a simple template with no data in case of error
        return render_template(
            'metrics.html',
            metrics={},
            initial_devices=[],
            initial_metrics=[],
            selected_device='',
            selected_metric='',
            paginated_metrics={'data': [], 'total': 0, 'total_pages': 0},
            current_page=1,
            per_page=10
        )

def get_paginated_metrics(device_name=None, metric_name=None, start_date=None, end_date=None, page=1, per_page=10):
    """Get paginated metrics data for the table"""
    try:
        # Convert string dates to datetime objects
        try:
            if start_date:
                start_time = datetime.fromisoformat(start_date.replace('Z', '+00:00'))
            else:
                start_time = datetime.utcnow() - timedelta(hours=24)
                
            if end_date:
                end_time = datetime.fromisoformat(end_date.replace('Z', '+00:00'))
            else:
                end_time = datetime.utcnow()
        except ValueError as e:
            logger.error(f"Invalid date format: {e}")
            start_time = datetime.utcnow() - timedelta(hours=24)
            end_time = datetime.utcnow()
        
        # Ensure start_time is before end_time
        if start_time > end_time:
            start_time, end_time = end_time, start_time
        
        # Build query for paginated metrics
        query = db.session.query(
            Device.name.label('device_name'),
            MetricInfo.name.label('metric_name'),
            MetricValue.metric_value,
            MetricValue.timestamp
        ).join(Device, MetricValue.device_id == Device.id)\
          .join(MetricInfo, MetricValue.metric_info_id == MetricInfo.id)\
          .filter(MetricValue.timestamp >= start_time)\
          .filter(MetricValue.timestamp <= end_time)
        
        # Apply filters if provided
        if device_name:
            query = query.filter(Device.name == device_name)
        if metric_name:
            query = query.filter(MetricInfo.name == metric_name)
        
        # Get total count for pagination
        total = query.count()
        
        # Get paginated data
        metrics_data = query.order_by(MetricValue.timestamp.desc())\
            .offset((page - 1) * per_page)\
            .limit(per_page)\
            .all()
        
        # Format the data
        result = {
            'total': total,
            'page': page,
            'per_page': per_page,
            'total_pages': (total + per_page - 1) // per_page,
            'data': [{
                'device_name': metric.device_name,
                'metric_name': metric.metric_name,
                'value': float(metric.metric_value),
                'timestamp': metric.timestamp.strftime('%Y-%m-%d %H:%M:%S')
            } for metric in metrics_data]
        }
        
        return result
    except Exception as e:
        logger.error(f"Error getting paginated metrics: {str(e)}")
        return {'data': [], 'total': 0, 'page': page, 'per_page': per_page, 'total_pages': 0}

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

@views_bp.route('/test-charts')
def test_charts():
    """Test page for Chart.js and Gauge.js"""
    return render_template('test_charts.html') 