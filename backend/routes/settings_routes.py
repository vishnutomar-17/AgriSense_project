import os
import datetime
from flask import Blueprint, request, jsonify
from database import get_db_connection, DB_PATH
from auth import login_required, admin_required
from simulation import simulator

settings_bp = Blueprint('settings', __name__, url_prefix='/api/settings')

START_TIME = datetime.datetime.now()

@settings_bp.route('', methods=['GET'])
@login_required
def get_settings():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT key, value, description, updated_at FROM system_settings")
    settings_rows = cursor.fetchall()
    settings_dict = {row['key']: row['value'] for row in settings_rows}

    # System Diagnostics
    cursor.execute("SELECT COUNT(*) as count FROM sensor_readings")
    total_readings = cursor.fetchone()['count']

    cursor.execute("SELECT COUNT(*) as count FROM alerts")
    total_alerts = cursor.fetchone()['count']

    cursor.execute("SELECT COUNT(*) as count FROM devices")
    total_devices = cursor.fetchone()['count']

    cursor.execute("SELECT COUNT(*) as count FROM sensors")
    total_sensors = cursor.fetchone()['count']

    cursor.execute("SELECT COUNT(*) as count FROM users")
    total_users = cursor.fetchone()['count']

    conn.close()

    db_size_kb = 0
    if os.path.exists(DB_PATH):
        db_size_kb = round(os.path.getsize(DB_PATH) / 1024, 1)

    uptime_seconds = int((datetime.datetime.now() - START_TIME).total_seconds())

    return jsonify({
        'settings': settings_dict,
        'diagnostics': {
            'total_readings': total_readings,
            'total_alerts': total_alerts,
            'total_devices': total_devices,
            'total_sensors': total_sensors,
            'total_users': total_users,
            'db_size_kb': db_size_kb,
            'uptime_seconds': uptime_seconds,
            'simulator_running': simulator.is_running()
        }
    }), 200

@settings_bp.route('', methods=['PUT'])
@admin_required
def update_settings():
    data = request.get_json() or {}
    if not data or not isinstance(data, dict):
        return jsonify({'error': 'Invalid payload.'}), 400

    conn = get_db_connection()
    cursor = conn.cursor()

    now_ts = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    updated_keys = []

    for k, v in data.items():
        cursor.execute("SELECT key FROM system_settings WHERE key = ?", (k,))
        if cursor.fetchone():
            cursor.execute("UPDATE system_settings SET value = ?, updated_at = ? WHERE key = ?", (str(v), now_ts, k))
            updated_keys.append(k)

            # Check if simulation_mode was toggled
            if k == 'simulation_mode':
                if str(v).lower() == 'true':
                    simulator.start()
                else:
                    simulator.stop()

    conn.commit()
    conn.close()

    return jsonify({
        'message': f'Updated {len(updated_keys)} configuration parameter(s).',
        'updated_keys': updated_keys
    }), 200

@settings_bp.route('/toggle-simulation', methods=['POST'])
@admin_required
def toggle_simulation():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT value FROM system_settings WHERE key = 'simulation_mode'")
    row = cursor.fetchone()
    current_val = (row['value'].lower() == 'true') if row else False
    new_val = not current_val
    new_str = 'true' if new_val else 'false'

    now_ts = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    cursor.execute("UPDATE system_settings SET value = ?, updated_at = ? WHERE key = 'simulation_mode'", (new_str, now_ts))
    conn.commit()
    conn.close()

    if new_val:
        simulator.start()
    else:
        simulator.stop()

    return jsonify({
        'message': f'Sensor simulation mode {"activated" if new_val else "deactivated"}.',
        'simulation_mode': new_val
    }), 200

@settings_bp.route('/scenario', methods=['POST'])
@login_required
def trigger_scenario():
    data = request.get_json() or {}
    scenario = data.get('scenario', 'optimal')
    valid = ['dry_soil', 'heatwave', 'heavy_rain', 'optimal']
    if scenario not in valid:
        return jsonify({'error': f'Invalid scenario. Allowed: {valid}'}), 400

    simulator.trigger_scenario(scenario)

    return jsonify({
        'status': 'success',
        'message': f'Scenario "{scenario}" applied to live farm sensors.',
        'scenario': scenario
    }), 200

