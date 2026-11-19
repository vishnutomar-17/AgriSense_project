from flask import Blueprint, jsonify
from database import get_db_connection
from irrigation_engine import get_irrigation_status
from auth import login_required
import datetime

dashboard_bp = Blueprint('dashboard', __name__, url_prefix='/api/dashboard')

@dashboard_bp.route('/summary', methods=['GET'])
@login_required
def get_summary():
    conn = get_db_connection()
    cursor = conn.cursor()

    # 1. Fetch simulation mode setting
    cursor.execute("SELECT value FROM system_settings WHERE key = 'simulation_mode'")
    sim_row = cursor.fetchone()
    simulation_active = (sim_row['value'].lower() == 'true') if sim_row else False

    # 2. Fetch all registered sensors
    cursor.execute("""
        SELECT id, device_id, name, sensor_type, unit, min_threshold, 
               max_threshold, current_reading, status, last_updated
        FROM sensors
    """)
    sensors_list = [dict(row) for row in cursor.fetchall()]
    sensors_by_type = {s['sensor_type']: s for s in sensors_list}

    # 3. Build top summary cards with previous reading comparison
    # Sensors needed: air_temperature, air_humidity, soil_moisture, light_intensity, soil_temperature, rainfall
    card_types = [
        ('air_temperature', 'Air Temperature', '°C', 'thermometer'),
        ('air_humidity', 'Air Humidity', '%', 'droplets'),
        ('soil_moisture', 'Soil Moisture', '%', 'sprout'),
        ('light_intensity', 'Light Intensity', 'lux', 'sun'),
        ('soil_temperature', 'Soil Temperature', '°C', 'flame'),
        ('rainfall', 'Rainfall', 'mm', 'cloud-rain')
    ]

    cards = []
    latest_ts = None

    for stype, title, fallback_unit, icon in card_types:
        sensor = sensors_by_type.get(stype)
        if sensor:
            val = sensor['current_reading']
            unit = sensor['unit']
            stat = sensor['status']
            s_id = sensor['id']
            if sensor['last_updated'] and (not latest_ts or sensor['last_updated'] > latest_ts):
                latest_ts = sensor['last_updated']

            # Compare with reading from ~1-2 hours ago or prior reading
            cursor.execute("""
                SELECT reading_value, timestamp 
                FROM sensor_readings 
                WHERE sensor_id = ? AND timestamp < ?
                ORDER BY timestamp DESC LIMIT 1
            """, (s_id, sensor['last_updated']))
            prev_row = cursor.fetchone()

            prev_val = prev_row['reading_value'] if prev_row else val
            diff = round(val - prev_val, 1)

            cards.append({
                'sensor_id': s_id,
                'type': stype,
                'title': title,
                'current_value': val,
                'previous_value': prev_val,
                'difference': diff,
                'unit': unit,
                'status': stat,
                'min_threshold': sensor['min_threshold'],
                'max_threshold': sensor['max_threshold'],
                'last_updated': sensor['last_updated'],
                'icon': icon
            })
        else:
            cards.append({
                'sensor_id': None,
                'type': stype,
                'title': title,
                'current_value': 0.0,
                'previous_value': 0.0,
                'difference': 0.0,
                'unit': fallback_unit,
                'status': 'offline',
                'min_threshold': None,
                'max_threshold': None,
                'last_updated': None,
                'icon': icon
            })

    # 4. Device status
    cursor.execute("SELECT COUNT(*) as total FROM devices")
    total_devices = cursor.fetchone()['total']

    cursor.execute("SELECT COUNT(*) as online_count FROM devices WHERE status = 'online'")
    online_devices = cursor.fetchone()['online_count']

    cursor.execute("SELECT id, name, status, last_seen FROM devices ORDER BY last_seen DESC")
    devices_summary = [dict(row) for row in cursor.fetchall()]

    # 5. Recent alerts (latest 5)
    cursor.execute("""
        SELECT id, sensor_id, category, severity, title, description, is_read, timestamp
        FROM alerts
        ORDER BY timestamp DESC
        LIMIT 5
    """)
    recent_alerts = [dict(row) for row in cursor.fetchall()]

    # 6. Unread alert count
    cursor.execute("SELECT COUNT(*) as unread_count FROM alerts WHERE is_read = 0")
    unread_alert_count = cursor.fetchone()['unread_count']

    # 7. Recent 24-hour graph data for main dashboard charts
    # We retrieve the last 24 records or hourly samples for air_temp_1, soil_moisture_1, and air_humidity_1
    history_charts = {
        'timestamps': [],
        'temperature': [],
        'soil_moisture': [],
        'humidity': []
    }

    # Query last 30 readings for soil_moisture_1 to align timestamps
    cursor.execute("""
        SELECT timestamp, reading_value 
        FROM sensor_readings 
        WHERE sensor_id = 'soil_moisture_1' 
        ORDER BY timestamp DESC 
        LIMIT 25
    """)
    sm_rows = list(reversed(cursor.fetchall()))

    if sm_rows:
        timestamps = [r['timestamp'] for r in sm_rows]
        history_charts['timestamps'] = [t.split(' ')[1][:5] if ' ' in t else t for t in timestamps]
        history_charts['soil_moisture'] = [round(r['reading_value'], 1) for r in sm_rows]

        # Match temperature
        for ts in timestamps:
            cursor.execute("""
                SELECT reading_value FROM sensor_readings 
                WHERE sensor_id = 'air_temp_1' AND timestamp <= ? 
                ORDER BY timestamp DESC LIMIT 1
            """, (ts,))
            t_row = cursor.fetchone()
            history_charts['temperature'].append(round(t_row['reading_value'], 1) if t_row else 24.0)

            # Match humidity
            cursor.execute("""
                SELECT reading_value FROM sensor_readings 
                WHERE sensor_id = 'air_humidity_1' AND timestamp <= ? 
                ORDER BY timestamp DESC LIMIT 1
            """, (ts,))
            h_row = cursor.fetchone()
            history_charts['humidity'].append(round(h_row['reading_value'], 1) if h_row else 60.0)

    # 8. Irrigation quick status
    irrigation_info = get_irrigation_status()

    conn.close()

    return jsonify({
        'cards': cards,
        'devices': {
            'total': total_devices,
            'online': online_devices,
            'list': devices_summary
        },
        'alerts': {
            'recent': recent_alerts,
            'unread_count': unread_alert_count
        },
        'irrigation': {
            'pump_state': irrigation_info['pump_state'],
            'mode': irrigation_info['mode'],
            'recommendation': irrigation_info['recommendation'],
            'water_usage_today_liters': irrigation_info['water_usage_today_liters']
        },
        'history_charts': history_charts,
        'system': {
            'simulation_mode': simulation_active,
            'last_sensor_update': latest_ts or datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        }
    }), 200

