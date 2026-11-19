import datetime
from database import get_db_connection

def check_and_create_alert(sensor_id, category, severity, title, description, cooldown_minutes=15):
    """
    Creates an alert if an identical alert for the same sensor/category hasn't been raised
    within the cooldown window.
    """
    conn = get_db_connection()
    cursor = conn.cursor()

    cooldown_cutoff = (datetime.datetime.now() - datetime.timedelta(minutes=cooldown_minutes)).strftime('%Y-%m-%d %H:%M:%S')

    cursor.execute("""
        SELECT id FROM alerts 
        WHERE category = ? AND title = ? AND timestamp >= ?
        LIMIT 1
    """, (category, title, cooldown_cutoff))

    existing = cursor.fetchone()
    if not existing:
        cursor.execute("""
            INSERT INTO alerts (sensor_id, category, severity, title, description, is_read, timestamp)
            VALUES (?, ?, ?, ?, ?, 0, datetime('now', 'localtime'))
        """, (sensor_id, category, severity, title, description))
        conn.commit()
        alert_id = cursor.lastrowid
        conn.close()
        return alert_id

    conn.close()
    return None

def evaluate_sensor_alerts(sensor_id, sensor_type, value, unit):
    """
    Evaluates sensor values against calibrated agronomic rules and creates alerts when needed.
    """
    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("SELECT key, value FROM system_settings")
    settings = {row['key']: row['value'] for row in cursor.fetchall()}
    conn.close()

    crit_moist = float(settings.get('soil_moisture_critical_min', 25.0))
    warn_moist = float(settings.get('soil_moisture_warning_min', 40.0))
    max_moist = float(settings.get('soil_moisture_normal_max', 70.0))
    high_temp = float(settings.get('high_temp_threshold', 35.0))
    low_humid = float(settings.get('low_humidity_threshold', 30.0))

    if sensor_type == 'soil_moisture':
        if value < crit_moist:
            check_and_create_alert(
                sensor_id=sensor_id,
                category='soil_moisture',
                severity='Critical',
                title='Soil Too Dry - Water Now',
                description=f'Soil moisture is very low at {value}{unit} (below {crit_moist}%). Plants need water immediately.'
            )
        elif value < warn_moist:
            check_and_create_alert(
                sensor_id=sensor_id,
                category='soil_moisture',
                severity='Warning',
                title='Soil Moisture Getting Low',
                description=f'Soil moisture dropped to {value}{unit}. Consider running irrigation soon.'
            )
        elif value > (max_moist + 15.0):
            check_and_create_alert(
                sensor_id=sensor_id,
                category='soil_moisture',
                severity='Warning',
                title='Soil Is Too Wet',
                description=f'Soil moisture is high at {value}{unit} (above {max_moist}%). Hold off on watering.'
            )

    elif sensor_type == 'air_temperature':
        if value > high_temp:
            check_and_create_alert(
                sensor_id=sensor_id,
                category='temperature',
                severity='Warning',
                title='High Temperature Alert',
                description=f'Air temperature reached {value}{unit}. Check ventilation in greenhouse.'
            )
        elif value < 5.0:
            check_and_create_alert(
                sensor_id=sensor_id,
                category='temperature',
                severity='Critical',
                title='Low Temperature Warning',
                description=f'Temperature dropped to {value}{unit}. Risk of cold damage to crops.'
            )

    elif sensor_type == 'air_humidity':
        if value < low_humid:
            check_and_create_alert(
                sensor_id=sensor_id,
                category='humidity',
                severity='Warning',
                title='Air Is Very Dry',
                description=f'Air humidity fell to {value}{unit}. Plants may lose water quickly.'
            )

    elif sensor_type == 'rainfall':
        if value > 0.5:
            check_and_create_alert(
                sensor_id=sensor_id,
                category='rainfall',
                severity='Informational',
                title='Rain Detected',
                description=f'Measured {value}{unit} of rain. You can pause watering today.'
            )

