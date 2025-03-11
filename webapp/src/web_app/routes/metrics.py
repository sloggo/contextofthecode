from datetime import datetime
from flask import Blueprint, request, jsonify
from ...database.database import db
from ...database.models import Device, MetricInfo, MetricValue

metrics_bp = Blueprint('metrics', __name__)

@metrics_bp.route('/metrics', methods=['POST'])
def upload_metrics():
    data = request.get_json()
    device_name = data.get('device_name')
    metrics = data.get('metrics', [])

    # Get or create device
    device = Device.query.filter_by(name=device_name).first()
    if not device:
        device = Device(name=device_name)
        db.session.add(device)
        db.session.flush()  # Get the device ID

    for metric in metrics:
        metric_name = metric.get('name')
        metric_value = metric.get('value')
        timestamp = datetime.fromisoformat(metric.get('timestamp'))

        # Get or create metric info
        metric_info = MetricInfo.query.filter_by(name=metric_name).first()
        if not metric_info:
            metric_info = MetricInfo(
                name=metric_name,
                description=f"Metric for {metric_name}",
                unit="units"  # You might want to make this configurable
            )
            db.session.add(metric_info)
            db.session.flush()  # Get the metric_info ID

        # Create metric value
        metric_value = MetricValue(
            device_id=device.id,
            metric_info_id=metric_info.id,
            metric_value=metric_value,
            timestamp=timestamp
        )
        db.session.add(metric_value)

    try:
        db.session.commit()
        return jsonify({"message": "Metrics uploaded successfully"}), 200
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": str(e)}), 500

@metrics_bp.route('/metrics', methods=['GET'])
def get_metrics():
    metrics = db.session.query(
        Device.name.label('device_name'),
        MetricInfo.name.label('metric_name'),
        MetricValue.metric_value,
        MetricValue.timestamp
    ).join(Device).join(MetricInfo).all()

    result = []
    for metric in metrics:
        result.append({
            'device_name': metric.device_name,
            'metric_name': metric.metric_name,
            'value': metric.metric_value,
            'timestamp': metric.timestamp.isoformat()
        })

    return jsonify(result) 