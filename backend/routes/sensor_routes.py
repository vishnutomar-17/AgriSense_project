from flask import Blueprint, request, jsonify
from database import get_db_connection
from auth import login_required, admin_required
from alert_engine import evaluate_sensor_alerts
import datetime

sensor_bp = Blueprint('sensors', __name__, url_prefix='/api/sensors')

@sensor_bp.route('', methods=['GET'])
@login_required
def list_sensors():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT s.id, s.device_id, s.name, s.sensor_type, s.unit, 
               s.min_threshold, s.max_threshold, s.current_reading, 
               s.status, s.last_updated, d.name as device_name, d.location as device_location,
               d.status as device_status
        FROM sensors s
        LEFT JOIN devices d ON s.device_id = d.id
        ORDER BY s.id ASC
    """)
    sensors = [dict(row) for row in cursor.fetchall()]
    conn.close()

    return jsonify({'sensors': sensors}), 200

@sensor_bp.route('/<sensor_id>/thresholds', methods=['PUT'])
@admin_required
def update_thresholds(sensor_id):
    data = request.get_json() or {}
    min_thresh = data.get('min_threshold')
    max_thresh = data.get('max_threshold')

    if min_thresh is None or max_thresh is None:
        return jsonify({'error': 'Both min_threshold and max_threshold are required.'}), 400

    try:
        min_thresh = float(min_thresh)
        max_thresh = float(max_thresh)
    except (ValueError, TypeError):
        return jsonify({'error': 'Threshold values must be valid numbers.'}), 400

    if min_thresh > max_thresh:
        return jsonify({'error': 'min_threshold cannot be greater than max_threshold.'}), 400

    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT id FROM sensors WHERE id = ?", (sensor_id,))
    if not cursor.fetchone():
        conn.close()
        return jsonify({'error': 'Sensor not found.'}), 404

    cursor.execute("""
        UPDATE sensors 
        SET min_threshold = ?, max_threshold = ? 
        WHERE id = ?
    """, (min_thresh, max_thresh, sensor_id))
    conn.commit()
    conn.close()

    return jsonify({
        'message': f'Thresholds updated successfully for {sensor_id}.',
        'sensor_id': sensor_id,
        'min_threshold': min_thresh,
        'max_threshold': max_thresh
    }), 200

@sensor_bp.route('/<sensor_id>/history', methods=['GET'])
@login_required
def get_sensor_history(sensor_id):
    limit = request.args.get('limit', 50, type=int)
    limit = min(max(1, limit), 200)

    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT id, name, unit, sensor_type FROM sensors WHERE id = ?", (sensor_id,))
    sensor = cursor.fetchone()
    if not sensor:
        conn.close()
        return jsonify({'error': 'Sensor not found.'}), 404

    cursor.execute("""
        SELECT id, reading_value, unit, data_source, timestamp
        FROM sensor_readings
        WHERE sensor_id = ?
        ORDER BY timestamp DESC
        LIMIT ?
    """, (sensor_id, limit))
    readings = [dict(row) for row in cursor.fetchall()]
    conn.close()

    return jsonify({
        'sensor': dict(sensor),
        'readings': readings
    }), 200

@sensor_bp.route('/readings', methods=['POST'])
def ingest_readings():
    """
    Production REST endpoint for receiving hardware telemetry from ESP32 / ESP8266.
    
    Headers:
        X-Device-Id: ESP32-AGRI-01 (or in JSON body)
        X-Device-Key: agri_sec_key_esp32_01_live (or in JSON body)
        
    JSON payload example:
    {
        "device_id": "ESP32-AGRI-01",
        "device_key": "agri_sec_key_esp32_01_live",
        "readings": [
            {"sensor_id": "air_temp_1", "value": 26.4, "unit": "°C"},
            {"sensor_id": "air_humidity_1", "value": 58.2, "unit": "%"},
            {"sensor_id": "soil_moisture_1", "value": 44.1, "unit": "%"},
            {"sensor_id": "soil_temp_1", "value": 22.0, "unit": "°C"},
            {"sensor_id": "light_ldr_1", "value": 34200.0, "unit": "lux"},
            {"sensor_id": "rain_1", "value": 0.0, "unit": "mm"}
        ]
    }
    """
    data = request.get_json(silent=True)
    if not data or not isinstance(data, dict):
        return jsonify({'error': 'Invalid request payload. Expected JSON object.'}), 400

    # 1. Device Identification & Authentication
    device_id = request.headers.get('X-Device-Id') or data.get('device_id')
    device_key = request.headers.get('X-Device-Key') or data.get('device_key')

    if not device_id or not device_key:
        return jsonify({
            'error': 'Unauthorized device. Device ID and API security key are required either in headers (X-Device-Id, X-Device-Key) or JSON body.'
        }), 401

    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("SELECT id, api_key, status FROM devices WHERE id = ?", (device_id,))
    device = cursor.fetchone()

    if not device:
        conn.close()
        return jsonify({'error': f'Device with ID "{device_id}" is not registered in the system.'}), 404

    if device['api_key'] != device_key:
        conn.close()
        return jsonify({'error': 'Authentication failed. Invalid API security key for this device.'}), 403

    # 2. Validate Readings array
    readings = data.get('readings')
    if not readings or not isinstance(readings, list):
        conn.close()
        return jsonify({'error': 'Missing or invalid "readings" array in payload.'}), 400

    now_ts = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    client_ip = request.remote_addr or request.headers.get('X-Forwarded-For', '')

    # Update device heartbeat and ip
    cursor.execute("""
        UPDATE devices 
        SET status = 'online', last_seen = ?, ip_address = ? 
        WHERE id = ?
    """, (now_ts, client_ip, device_id))

    saved_count = 0
    errors = []
    alerts_to_evaluate = []

    for item in readings:
        s_id = item.get('sensor_id')
        val = item.get('value')
        unit = item.get('unit')

        if not s_id or val is None:
            errors.append(f'Reading missing sensor_id or value: {item}')
            continue

        try:
            val_float = float(val)
        except (ValueError, TypeError):
            errors.append(f'Invalid numeric value for {s_id}: {val}')
            continue

        # Look up sensor
        cursor.execute("SELECT id, sensor_type, unit, min_threshold, max_threshold FROM sensors WHERE id = ?", (s_id,))
        sensor_row = cursor.fetchone()

        if not sensor_row:
            errors.append(f'Sensor {s_id} not registered in database.')
            continue

        assigned_unit = unit or sensor_row['unit']

        # Determine status based on thresholds
        status = 'optimal'
        min_t = sensor_row['min_threshold']
        max_t = sensor_row['max_threshold']
        if min_t is not None and val_float < min_t:
            status = 'critical' if sensor_row['sensor_type'] == 'soil_moisture' else 'warning'
        elif max_t is not None and val_float > max_t:
            status = 'warning'

        # Update sensor record
        cursor.execute("""
            UPDATE sensors 
            SET current_reading = ?, unit = ?, status = ?, last_updated = ?
            WHERE id = ?
        """, (val_float, assigned_unit, status, now_ts, s_id))

        # Insert historical reading tagged strictly as hardware
        cursor.execute("""
            INSERT INTO sensor_readings (sensor_id, device_id, reading_value, unit, data_source, timestamp)
            VALUES (?, ?, ?, ?, 'hardware', ?)
        """, (s_id, device_id, val_float, assigned_unit, now_ts))

        alerts_to_evaluate.append((s_id, sensor_row['sensor_type'], val_float, assigned_unit))
        saved_count += 1

    conn.commit()
    conn.close()

    # Trigger real-time alert evaluation after committing transactions
    for s_id, s_type, v_float, a_unit in alerts_to_evaluate:
        evaluate_sensor_alerts(s_id, s_type, v_float, a_unit)

    return jsonify({
        'status': 'success',
        'message': f'Ingested {saved_count} physical telemetry reading(s) from device {device_id}.',
        'device_id': device_id,
        'timestamp': now_ts,
        'data_source': 'hardware',
        'ingested_count': saved_count,
        'warnings': errors if errors else None
    }), 201
