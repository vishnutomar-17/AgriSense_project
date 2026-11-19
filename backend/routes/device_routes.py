import secrets
import datetime
from flask import Blueprint, request, jsonify
from database import get_db_connection
from auth import login_required, admin_required

device_bp = Blueprint('devices', __name__, url_prefix='/api/devices')

@device_bp.route('', methods=['GET'])
@login_required
def list_devices():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT d.id, d.name, d.location, d.device_type, d.api_key, 
               d.status, d.ip_address, d.last_seen, d.created_at,
               COUNT(s.id) as sensor_count
        FROM devices d
        LEFT JOIN sensors s ON d.id = s.device_id
        GROUP BY d.id
        ORDER BY d.created_at ASC
    """)
    devices = [dict(row) for row in cursor.fetchall()]
    conn.close()

    return jsonify({'devices': devices}), 200

@device_bp.route('', methods=['POST'])
@admin_required
def register_device():
    data = request.get_json() or {}
    device_id = data.get('id', '').strip()
    name = data.get('name', '').strip()
    location = data.get('location', '').strip()
    device_type = data.get('device_type', 'ESP32 NodeMCU DevKit v1').strip()

    if not device_id or not name or not location:
        return jsonify({'error': 'Device ID, Name, and Location are required.'}), 400

    api_key = f"agri_sec_{secrets.token_hex(16)}"

    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("SELECT id FROM devices WHERE id = ?", (device_id,))
    if cursor.fetchone():
        conn.close()
        return jsonify({'error': f'Device with ID "{device_id}" is already registered.'}), 409

    now_ts = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    cursor.execute("""
        INSERT INTO devices (id, name, location, device_type, api_key, status, ip_address, last_seen, created_at)
        VALUES (?, ?, ?, ?, ?, 'offline', NULL, ?, ?)
    """, (device_id, name, location, device_type, api_key, now_ts, now_ts))
    conn.commit()
    conn.close()

    return jsonify({
        'message': f'Device {device_id} registered successfully.',
        'device': {
            'id': device_id,
            'name': name,
            'location': location,
            'device_type': device_type,
            'api_key': api_key,
            'status': 'offline'
        }
    }), 201

@device_bp.route('/<device_id>/regenerate-key', methods=['POST'])
@admin_required
def regenerate_key(device_id):
    new_key = f"agri_sec_{secrets.token_hex(16)}"
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT id FROM devices WHERE id = ?", (device_id,))
    if not cursor.fetchone():
        conn.close()
        return jsonify({'error': 'Device not found.'}), 404

    cursor.execute("UPDATE devices SET api_key = ? WHERE id = ?", (new_key, device_id))
    conn.commit()
    conn.close()

    return jsonify({
        'message': f'New API key generated for {device_id}. Update your ESP32 firmware config.',
        'device_id': device_id,
        'new_api_key': new_key
    }), 200

@device_bp.route('/<device_id>', methods=['DELETE'])
@admin_required
def delete_device(device_id):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT id FROM devices WHERE id = ?", (device_id,))
    if not cursor.fetchone():
        conn.close()
        return jsonify({'error': 'Device not found.'}), 404

    cursor.execute("DELETE FROM devices WHERE id = ?", (device_id,))
    conn.commit()
    conn.close()

    return jsonify({'message': f'Device {device_id} deleted successfully.'}), 200

