from flask import Blueprint, request, jsonify
from database import get_db_connection
from auth import login_required, admin_required
from irrigation_engine import get_irrigation_status, toggle_pump, set_irrigation_mode

irrigation_bp = Blueprint('irrigation', __name__, url_prefix='/api/irrigation')

@irrigation_bp.route('/status', methods=['GET'])
@login_required
def status():
    info = get_irrigation_status()
    return jsonify(info), 200

@irrigation_bp.route('/toggle', methods=['POST'])
@login_required
def toggle():
    data = request.get_json() or {}
    target_state = data.get('state', '').upper()
    notes = data.get('notes', 'Operator manual command from web interface')

    if target_state not in ['ON', 'OFF']:
        return jsonify({'error': 'State must be either "ON" or "OFF".'}), 400

    new_status = toggle_pump(target_state, trigger_type='manual', notes=notes)

    return jsonify({
        'message': f'Irrigation pump switched {target_state} successfully.',
        'status': new_status
    }), 200

@irrigation_bp.route('/mode', methods=['POST'])
@login_required
def change_mode():
    data = request.get_json() or {}
    mode = data.get('mode', '').lower()

    if mode not in ['auto', 'manual']:
        return jsonify({'error': 'Mode must be either "auto" or "manual".'}), 400

    set_irrigation_mode(mode)
    new_status = get_irrigation_status()

    return jsonify({
        'message': f'Irrigation control mode changed to {mode.upper()}.',
        'status': new_status
    }), 200

@irrigation_bp.route('/thresholds', methods=['PUT'])
@admin_required
def update_irrigation_thresholds():
    data = request.get_json() or {}
    crit_min = data.get('critical_min')
    warn_min = data.get('warning_min')
    norm_max = data.get('normal_max')
    flow_rate = data.get('flow_rate_lpm')

    if any(v is None for v in [crit_min, warn_min, norm_max, flow_rate]):
        return jsonify({'error': 'critical_min, warning_min, normal_max, and flow_rate_lpm are all required.'}), 400

    try:
        crit_min = float(crit_min)
        warn_min = float(warn_min)
        norm_max = float(norm_max)
        flow_rate = float(flow_rate)
    except (ValueError, TypeError):
        return jsonify({'error': 'Threshold values must be numbers.'}), 400

    if not (0 <= crit_min < warn_min < norm_max <= 100):
        return jsonify({'error': 'Thresholds must satisfy: 0 <= critical_min < warning_min < normal_max <= 100'}), 400

    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("UPDATE system_settings SET value = ? WHERE key = 'soil_moisture_critical_min'", (str(crit_min),))
    cursor.execute("UPDATE system_settings SET value = ? WHERE key = 'soil_moisture_warning_min'", (str(warn_min),))
    cursor.execute("UPDATE system_settings SET value = ? WHERE key = 'soil_moisture_normal_max'", (str(norm_max),))
    cursor.execute("UPDATE system_settings SET value = ? WHERE key = 'water_flow_rate_lpm'", (str(flow_rate),))

    # Also update sensors table min/max for soil_moisture_1
    cursor.execute("UPDATE sensors SET min_threshold = ?, max_threshold = ? WHERE sensor_type = 'soil_moisture'", (crit_min, norm_max))

    conn.commit()
    conn.close()

    return jsonify({
        'message': 'Irrigation thresholds updated successfully.',
        'status': get_irrigation_status()
    }), 200

@irrigation_bp.route('/history', methods=['GET'])
@login_required
def history():
    limit = request.args.get('limit', 50, type=int)
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT id, trigger_type, action, duration_minutes, water_used_liters,
               soil_moisture_before, soil_moisture_after, notes, timestamp
        FROM irrigation_records
        ORDER BY timestamp DESC
        LIMIT ?
    """, (limit,))
    records = [dict(row) for row in cursor.fetchall()]
    conn.close()

    return jsonify({'history': records}), 200

