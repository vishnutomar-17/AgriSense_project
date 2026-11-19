from flask import Blueprint, request, jsonify
from database import get_db_connection
from auth import login_required
import datetime

analytics_bp = Blueprint('analytics', __name__, url_prefix='/api/analytics')

@analytics_bp.route('/trends', methods=['GET'])
@login_required
def get_trends():
    time_range = request.args.get('range', '24h') # 24h, 7d, 30d

    now = datetime.datetime.now()
    if time_range == '7d':
        cutoff = (now - datetime.timedelta(days=7)).strftime('%Y-%m-%d %H:%M:%S')
        # Bucket or sample to keep payload manageable (e.g. limit to 100 points)
        sample_limit = 120
    elif time_range == '30d':
        cutoff = (now - datetime.timedelta(days=30)).strftime('%Y-%m-%d %H:%M:%S')
        sample_limit = 150
    else: # 24h
        cutoff = (now - datetime.timedelta(hours=24)).strftime('%Y-%m-%d %H:%M:%S')
        sample_limit = 100

    conn = get_db_connection()
    cursor = conn.cursor()

    # Sensor IDs mapping
    target_sensors = [
        ('air_temp_1', 'temperature'),
        ('soil_moisture_1', 'soil_moisture'),
        ('air_humidity_1', 'humidity'),
        ('light_ldr_1', 'light'),
        ('rain_1', 'rainfall'),
        ('soil_temp_1', 'soil_temperature')
    ]

    trends = {}
    stats = {}

    for s_id, key in target_sensors:
        cursor.execute("""
            SELECT reading_value, unit, data_source, timestamp
            FROM sensor_readings
            WHERE sensor_id = ? AND timestamp >= ?
            ORDER BY timestamp ASC
        """, (s_id, cutoff))
        rows = cursor.fetchall()

        if len(rows) > sample_limit:
            step = max(1, len(rows) // sample_limit)
            sampled = rows[::step]
        else:
            sampled = rows

        data_points = []
        vals = []
        for r in sampled:
            vals.append(r['reading_value'])
            data_points.append({
                'timestamp': r['timestamp'],
                'value': round(r['reading_value'], 1),
                'unit': r['unit'],
                'source': r['data_source']
            })

        trends[key] = data_points

        # Calculate statistics
        if vals:
            stats[key] = {
                'min': round(min(vals), 1),
                'max': round(max(vals), 1),
                'avg': round(sum(vals) / len(vals), 1),
                'count': len(vals)
            }
        else:
            stats[key] = {'min': 0, 'max': 0, 'avg': 0, 'count': 0}

    # Fetch irrigation events during this window
    cursor.execute("""
        SELECT id, trigger_type, action, duration_minutes, water_used_liters, timestamp
        FROM irrigation_records
        WHERE timestamp >= ?
        ORDER BY timestamp ASC
    """, (cutoff,))
    irrigation_events = [dict(row) for row in cursor.fetchall()]

    conn.close()

    return jsonify({
        'range': time_range,
        'cutoff': cutoff,
        'trends': trends,
        'statistics': stats,
        'irrigation_events': irrigation_events
    }), 200

