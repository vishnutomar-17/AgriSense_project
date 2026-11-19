import io
import csv
import datetime
from flask import Blueprint, request, Response
from database import get_db_connection
from auth import login_required

export_bp = Blueprint('export', __name__, url_prefix='/api/export')

@export_bp.route('/readings.csv', methods=['GET'])
@login_required
def export_csv():
    time_range = request.args.get('range', 'all') # 24h, 7d, 30d, all
    sensor_id = request.args.get('sensor_id')

    query = """
        SELECT r.timestamp, s.name as sensor_name, r.sensor_id, 
               r.reading_value, r.unit, r.data_source, r.device_id
        FROM sensor_readings r
        JOIN sensors s ON r.sensor_id = s.id
        WHERE 1=1
    """
    params = []

    now = datetime.datetime.now()
    if time_range == '24h':
        cutoff = (now - datetime.timedelta(hours=24)).strftime('%Y-%m-%d %H:%M:%S')
        query += " AND r.timestamp >= ?"
        params.append(cutoff)
    elif time_range == '7d':
        cutoff = (now - datetime.timedelta(days=7)).strftime('%Y-%m-%d %H:%M:%S')
        query += " AND r.timestamp >= ?"
        params.append(cutoff)
    elif time_range == '30d':
        cutoff = (now - datetime.timedelta(days=30)).strftime('%Y-%m-%d %H:%M:%S')
        query += " AND r.timestamp >= ?"
        params.append(cutoff)

    if sensor_id:
        query += " AND r.sensor_id = ?"
        params.append(sensor_id)

    query += " ORDER BY r.timestamp DESC LIMIT 10000"

    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(query, params)
    rows = cursor.fetchall()
    conn.close()

    output = io.StringIO()
    writer = csv.writer(output)

    # Required CSV header
    writer.writerow([
        'Date and Time',
        'Sensor ID',
        'Sensor Name',
        'Sensor Value',
        'Measurement Unit',
        'Data Source',
        'Device ID'
    ])

    for row in rows:
        writer.writerow([
            row['timestamp'],
            row['sensor_id'],
            row['sensor_name'],
            row['reading_value'],
            row['unit'],
            row['data_source'],
            row['device_id']
        ])

    csv_content = output.getvalue()
    output.close()

    filename = f"agrisense_telemetry_{time_range}_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"

    return Response(
        csv_content,
        mimetype="text/csv",
        headers={
            "Content-Disposition": f"attachment; filename={filename}",
            "Content-Type": "text/csv; charset=utf-8"
        }
    )

