from flask import Blueprint, request, jsonify
from database import get_db_connection
from auth import login_required

alert_bp = Blueprint('alerts', __name__, url_prefix='/api/alerts')

@alert_bp.route('', methods=['GET'])
@login_required
def list_alerts():
    severity = request.args.get('severity')
    category = request.args.get('category')
    is_read = request.args.get('is_read')
    limit = request.args.get('limit', 100, type=int)

    query = "SELECT id, sensor_id, category, severity, title, description, is_read, timestamp FROM alerts WHERE 1=1"
    params = []

    if severity:
        query += " AND severity = ?"
        params.append(severity)
    if category:
        query += " AND category = ?"
        params.append(category)
    if is_read is not None:
        query += " AND is_read = ?"
        params.append(int(is_read))

    query += " ORDER BY timestamp DESC LIMIT ?"
    params.append(limit)

    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(query, params)
    alerts = [dict(row) for row in cursor.fetchall()]

    # Stats
    cursor.execute("SELECT severity, COUNT(*) as count FROM alerts GROUP BY severity")
    counts_by_severity = {row['severity']: row['count'] for row in cursor.fetchall()}

    cursor.execute("SELECT COUNT(*) as unread FROM alerts WHERE is_read = 0")
    unread_total = cursor.fetchone()['unread']

    conn.close()

    return jsonify({
        'alerts': alerts,
        'counts': {
            'total': len(alerts),
            'unread': unread_total,
            'critical': counts_by_severity.get('Critical', 0),
            'warning': counts_by_severity.get('Warning', 0),
            'informational': counts_by_severity.get('Informational', 0)
        }
    }), 200

@alert_bp.route('/<int:alert_id>/read', methods=['POST'])
@login_required
def mark_read(alert_id):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("UPDATE alerts SET is_read = 1 WHERE id = ?", (alert_id,))
    conn.commit()
    conn.close()
    return jsonify({'message': f'Alert {alert_id} marked as read.'}), 200

@alert_bp.route('/mark-all-read', methods=['POST'])
@login_required
def mark_all_read():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("UPDATE alerts SET is_read = 1 WHERE is_read = 0")
    conn.commit()
    conn.close()
    return jsonify({'message': 'All alerts marked as read.'}), 200

