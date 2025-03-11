from flask import Blueprint, request, jsonify, Response, stream_with_context
from marshmallow import Schema, fields
from datetime import datetime
from time import sleep
import json
import logging
from ...database.database import db
from ...database.models import Device, MetricInfo, MetricValue
import time

logger = logging.getLogger(__name__)

# Custom JSON encoder to handle datetime objects
class DateTimeEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, datetime):
            return obj.isoformat()
        return super().default(obj)

aggregator_bp = Blueprint('aggregator', __name__)

# In-memory storage for control status and latest metrics
class ControlState:
    def __init__(self):
        self.status = 'RUNNING'
        self._listeners = []
        self.latest_metrics = {}  # Store latest metrics for each device/metric combination
        self.commands = []  # Store commands for the collector

    def set_status(self, status):
        self.status = status
        # No need to notify listeners as they will poll

    def get_status(self):
        return self.status
        
    def add_metric(self, device_name, metric_name, value, timestamp):
        """Add a new metric value to the latest metrics store."""
        key = f"{device_name}:{metric_name}"
        
        # Convert timestamp to ISO format string if it's a datetime object
        timestamp_str = timestamp
        if isinstance(timestamp, datetime):
            timestamp_str = timestamp.isoformat()
            
        self.latest_metrics[key] = {
            'device': device_name,
            'metric': metric_name,
            'value': value,
            'timestamp': timestamp_str
        }

    def get_latest_metrics(self):
        """Get all latest metrics as a list."""
        return list(self.latest_metrics.values())

    def add_command(self, command):
        """Add a new command to the command queue."""
        self.commands.append(command)

# Global control state
control_state = ControlState()

class MetricSchema(Schema):
    device_id = fields.Str(required=True)
    device_name = fields.Str(required=True)
    metric_name = fields.Str(required=True)
    metric_value = fields.Float(required=True)
    timestamp = fields.DateTime(missing=lambda: datetime.utcnow())
    metric_metadata = fields.Dict()

metric_schema = MetricSchema()
metrics_schema = MetricSchema(many=True)

@aggregator_bp.route('/metrics', methods=['POST'])
@aggregator_bp.route('/metrics/', methods=['POST'])
def collect_metric():
    # Validate and deserialize input
    data = metric_schema.load(request.json)
    
    # Ensure timestamp is a datetime object
    if 'timestamp' in data and isinstance(data['timestamp'], str):
        try:
            data['timestamp'] = datetime.fromisoformat(data['timestamp'].replace('Z', '+00:00'))
        except ValueError:
            # If parsing fails, use current time
            data['timestamp'] = datetime.utcnow()
    
    # Get or create device
    device = Device.query.filter_by(id=data['device_id']).first()
    if not device:
        # Check if a device with the same name already exists
        existing_device = Device.query.filter_by(name=data['device_name']).first()
        if existing_device:
            # Use the existing device instead of creating a new one
            device = existing_device
            logger.info(f"Using existing device with name '{data['device_name']}' (ID: {device.id})")
        else:
            # Create a new device
            device = Device(
                id=data['device_id'],
                name=data['device_name']
            )
            db.session.add(device)
            db.session.flush()
            logger.info(f"Created new device: {data['device_name']} (ID: {device.id})")

    # Get or create metric info
    metric_info = MetricInfo.query.filter_by(name=data['metric_name']).first()
    if not metric_info:
        metric_info = MetricInfo(
            name=data['metric_name'],
            unit="units"
        )
        db.session.add(metric_info)
        db.session.flush()

    # Create metric value
    metric = MetricValue(
        device_id=device.id,
        metric_info_id=metric_info.id,
        metric_value=data['metric_value'],
        timestamp=data['timestamp'],
        metric_metadata=data.get('metric_metadata')
    )
    db.session.add(metric)
    db.session.commit()
    
    # Store the latest metric for real-time updates
    control_state.add_metric(
        device_name=data['device_name'],
        metric_name=data['metric_name'],
        value=data['metric_value'],
        timestamp=data['timestamp']
    )

    return jsonify(metric_schema.dump(data))

@aggregator_bp.route('/metrics/batch', methods=['POST'])
@aggregator_bp.route('/metrics/batch/', methods=['POST'])
def upload_metrics_batch():
    metrics_batch = request.get_json()
    
    try:
        for metric_data in metrics_batch:
            device_id = metric_data.get('device_id')
            device_name = metric_data.get('device_name')
            metric_name = metric_data.get('metric_name')
            metric_value = metric_data.get('metric_value')
            
            # Ensure timestamp is a datetime object
            if 'timestamp' in metric_data and isinstance(metric_data['timestamp'], str):
                try:
                    timestamp = datetime.fromisoformat(metric_data['timestamp'].replace('Z', '+00:00'))
                except ValueError:
                    # If parsing fails, use current time
                    timestamp = datetime.utcnow()
            else:
                timestamp = metric_data.get('timestamp', datetime.utcnow())
            
            # Get or create device
            device = Device.query.filter_by(id=device_id).first()
            if not device:
                # Check if a device with the same name already exists
                existing_device = Device.query.filter_by(name=device_name).first()
                if existing_device:
                    # Use the existing device instead of creating a new one
                    device = existing_device
                    logger.info(f"Using existing device with name '{device_name}' (ID: {device.id})")
                else:
                    # Create a new device
                    device = Device(
                        id=device_id,
                        name=device_name
                    )
                    db.session.add(device)
                    db.session.flush()
                    logger.info(f"Created new device: {device_name} (ID: {device.id})")
            
            # Get or create metric info
            metric_info = MetricInfo.query.filter_by(name=metric_name).first()
            if not metric_info:
                metric_info = MetricInfo(
                    name=metric_name,
                    unit="units"
                )
                db.session.add(metric_info)
                db.session.flush()
            
            # Create metric value
            metric = MetricValue(
                device_id=device.id,
                metric_info_id=metric_info.id,
                metric_value=metric_value,
                timestamp=timestamp,
                metric_metadata=metric_data.get('metric_metadata')
            )
            db.session.add(metric)
            
            # Store the latest metric for real-time updates
            control_state.add_metric(
                device_name=device_name,
                metric_name=metric_name,
                value=metric_value,
                timestamp=timestamp
            )
        
        db.session.commit()
        return jsonify({"status": "success", "count": len(metrics_batch)})
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": str(e)}), 500

@aggregator_bp.route('/metrics/updates', methods=['GET'])
def metrics_stream():
    """Stream metrics updates to clients using SSE."""
    client_ip = request.remote_addr
    logger.info(f"Client {client_ip} connected to metrics SSE stream")
    
    def generate():
        last_update = {}
        update_count = 0
        
        try:
            while True:
                # Get latest metrics
                latest = control_state.get_latest_metrics()
                updates = []
                
                # Check for new updates
                for metric in latest:
                    key = f"{metric['device']}:{metric['metric']}"
                    if key not in last_update or last_update[key] != metric['value']:
                        # Convert datetime objects to ISO format strings
                        if 'timestamp' in metric and isinstance(metric['timestamp'], datetime):
                            metric['timestamp'] = metric['timestamp'].isoformat()
                        updates.append(metric)
                        last_update[key] = metric['value']
                
                # Send updates if any
                if updates:
                    update_count += 1
                    logger.debug(f"Sending {len(updates)} metric updates to client {client_ip} (total: {update_count})")
                    yield f"data: {json.dumps(updates, cls=DateTimeEncoder)}\n\n"
                
                sleep(1)  # Check for updates every second
        except GeneratorExit:
            logger.info(f"Client {client_ip} disconnected from metrics SSE stream after {update_count} updates")
    
    return Response(
        generate(),
        mimetype="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
            "Connection": "keep-alive"
        }
    )

@aggregator_bp.route('/control', methods=['GET'])
def control_stream():
    """Stream control state using Server-Sent Events."""
    client_ip = request.remote_addr
    logger.info(f"Client {client_ip} connected to control SSE stream")
    
    def generate():
        update_count = 0
        last_status = None
        
        try:
            # Send initial status
            current_status = control_state.get_status()
            logger.info(f"Sending initial status '{current_status}' to client {client_ip}")
            yield f"data: {current_status}\n\n"
            last_status = current_status
            update_count += 1
            
            # Keep connection alive and send updates only when status changes
            while True:
                time.sleep(5)
                current_status = control_state.get_status()
                
                if current_status != last_status:
                    logger.info(f"Sending status update '{current_status}' to client {client_ip}")
                    yield f"data: {current_status}\n\n"
                    last_status = current_status
                    update_count += 1
                else:
                    # Send a comment to keep the connection alive without sending data
                    yield f": keepalive\n\n"
        except GeneratorExit:
            logger.info(f"Client {client_ip} disconnected from control SSE stream after {update_count} updates")
    
    return Response(
        stream_with_context(generate()),
        mimetype="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
            "Connection": "keep-alive"
        }
    )

@aggregator_bp.route('/control/<action>', methods=['POST'])
def control_collectors(action):
    """Control the collectors by setting the control state."""
    if action not in ['start', 'stop']:
        return jsonify({'status': 'error', 'message': 'Invalid action'}), 400
    
    # Set the control state
    if action == 'start':
        control_state.set_status('RUNNING')
        logger.info("Control state set to RUNNING")
    else:
        control_state.set_status('STOPPED')
        logger.info("Control state set to STOPPED")
    
    return jsonify({'status': 'success', 'message': f'Collectors {action}ed'})

@aggregator_bp.route('/register_device', methods=['POST'])
def register_device():
    """Register a device to avoid unique constraint errors."""
    try:
        data = request.json
        
        if not data or 'name' not in data:
            return jsonify({'status': 'error', 'message': 'Device name is required'}), 400
        
        # Check if device already exists
        device = Device.query.filter_by(name=data['name']).first()
        if device:
            return jsonify({'status': 'success', 'message': 'Device already exists', 'device_id': device.id}), 409
        
        # Create new device
        device = Device(
            name=data['name'],
            description=data.get('description')
        )
        db.session.add(device)
        db.session.commit()
        
        logger.info(f"Registered new device: {data['name']} (ID: {device.id})")
        
        return jsonify({
            'status': 'success', 
            'message': 'Device registered successfully',
            'device_id': device.id
        }), 201
    except Exception as e:
        db.session.rollback()
        logger.error(f"Error registering device: {str(e)}")
        return jsonify({'status': 'error', 'message': str(e)}), 500

# Add a new route to handle adding stocks
@aggregator_bp.route('/add_stock', methods=['POST'])
def add_stock():
    """Add a new stock to be monitored by the collector."""
    try:
        data = request.json
        
        if not data or 'symbol' not in data:
            return jsonify({'status': 'error', 'message': 'Stock symbol is required'}), 400
        
        symbol = data['symbol'].strip().upper()
        
        # Validate the stock symbol (basic validation)
        if not symbol or len(symbol) > 10 or not symbol.isalpha():
            return jsonify({'status': 'error', 'message': 'Invalid stock symbol'}), 400
        
        # Create a message to be sent to the collector
        message = {
            'action': 'add_stock',
            'symbol': symbol,
            'timestamp': datetime.utcnow().isoformat()
        }
        
        # Store the message in the control state for SSE
        control_state.add_command(message)
        
        logger.info(f"Added stock symbol to monitoring: {symbol}")
        
        return jsonify({
            'status': 'success', 
            'message': f'Stock {symbol} added to monitoring queue',
            'symbol': symbol
        }), 201
    except Exception as e:
        logger.error(f"Error adding stock: {str(e)}", exc_info=True)
        return jsonify({'status': 'error', 'message': f'Error adding stock: {str(e)}'}), 500

@aggregator_bp.route('/commands')
def get_commands():
    """Stream commands to the collector using Server-Sent Events."""
    def generate():
        last_command_index = 0
        
        while True:
            # Check if there are new commands
            if last_command_index < len(control_state.commands):
                # Get all new commands
                new_commands = control_state.commands[last_command_index:]
                last_command_index = len(control_state.commands)
                
                # Send the commands as SSE
                data = json.dumps(new_commands, cls=DateTimeEncoder)
                yield f"data: {data}\n\n"
            
            # Wait before checking again
            sleep(1)
    
    return Response(
        stream_with_context(generate()),
        mimetype='text/event-stream',
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
            "Connection": "keep-alive"
        }
    ) 