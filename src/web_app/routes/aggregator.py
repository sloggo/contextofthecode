from flask import Blueprint, request, jsonify
from marshmallow import Schema, fields
from datetime import datetime
from ...database.database import db
from ...database.models import Device, MetricInfo, MetricValue

aggregator_bp = Blueprint('aggregator', __name__)

class MetricSchema(Schema):
    device_name = fields.Str(required=True)
    metric_name = fields.Str(required=True)
    metric_value = fields.Float(required=True)
    timestamp = fields.DateTime(missing=lambda: datetime.utcnow())

metric_schema = MetricSchema()
metrics_schema = MetricSchema(many=True)

@aggregator_bp.route('/metrics', methods=['POST'])
@aggregator_bp.route('/metrics/', methods=['POST'])
def collect_metric():
    # Validate and deserialize input
    data = metric_schema.load(request.json)
    
    # Get or create device
    device = Device.query.filter_by(name=data['device_name']).first()
    if not device:
        device = Device(name=data['device_name'])
        db.session.add(device)
        db.session.flush()

    # Get or create metric info
    metric_info = MetricInfo.query.filter_by(name=data['metric_name']).first()
    if not metric_info:
        metric_info = MetricInfo(
            name=data['metric_name'],
            description=f"Metric for {data['metric_name']}",
            unit="units"
        )
        db.session.add(metric_info)
        db.session.flush()

    # Create metric value
    metric = MetricValue(
        device_id=device.id,
        metric_info_id=metric_info.id,
        metric_value=data['metric_value'],
        timestamp=data['timestamp']
    )
    db.session.add(metric)
    db.session.commit()

    return jsonify(metric_schema.dump(data))

@aggregator_bp.route('/metrics/batch', methods=['POST'])
@aggregator_bp.route('/metrics/batch/', methods=['POST'])
def upload_metrics_batch():
    metrics_batch = request.get_json()
    
    try:
        for metric_data in metrics_batch:
            device_name = metric_data.get('device_name')
            metric_name = metric_data.get('metric_name')
            metric_value = metric_data.get('value')
            timestamp = datetime.fromisoformat(metric_data.get('timestamp'))

            # Get or create device
            device = Device.query.filter_by(name=device_name).first()
            if not device:
                device = Device(name=device_name)
                db.session.add(device)
                db.session.flush()

            # Get or create metric info
            metric_info = MetricInfo.query.filter_by(name=metric_name).first()
            if not metric_info:
                metric_info = MetricInfo(
                    name=metric_name,
                    description=f"Metric for {metric_name}",
                    unit="units"
                )
                db.session.add(metric_info)
                db.session.flush()

            # Create metric value
            metric = MetricValue(
                device_id=device.id,
                metric_info_id=metric_info.id,
                metric_value=metric_value,
                timestamp=timestamp
            )
            db.session.add(metric)

        db.session.commit()
        return jsonify({"message": "Metrics batch uploaded successfully"}), 200
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": str(e)}), 500 