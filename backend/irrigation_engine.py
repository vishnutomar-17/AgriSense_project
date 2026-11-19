import datetime
from database import get_db_connection

def get_irrigation_status():
    """
    Returns current irrigation status, rule-based recommendation, pump state,
    and recent activity records.
    """
    conn = get_db_connection()
    cursor = conn.cursor()

    # Get settings
    cursor.execute("SELECT key, value FROM system_settings")
    settings = {row['key']: row['value'] for row in cursor.fetchall()}

    crit_moist = float(settings.get('soil_moisture_critical_min', 25.0))
    warn_moist = float(settings.get('soil_moisture_warning_min', 40.0))
    norm_max = float(settings.get('soil_moisture_normal_max', 70.0))
    pump_state = settings.get('pump_state', 'OFF')
    mode = settings.get('active_irrigation_mode', 'auto')
    flow_rate = float(settings.get('water_flow_rate_lpm', 12.5))
    pump_started_at = settings.get('pump_started_at', '')

    # Get latest soil moisture reading
    cursor.execute("""
        SELECT current_reading FROM sensors 
        WHERE sensor_type = 'soil_moisture' 
        ORDER BY last_updated DESC LIMIT 1
    """)
    sm_row = cursor.fetchone()
    current_moisture = sm_row['current_reading'] if sm_row else 50.0

    # Calculate recommendation
    if current_moisture < crit_moist:
        rec_status = "CRITICAL"
        rec_title = "Water Crops Now"
        rec_desc = f"Soil moisture is at {current_moisture:.1f}% (target: above {crit_moist:.0f}%). Turn on the pump to water the crops."
        rec_action = "START_PUMP"
    elif current_moisture < warn_moist:
        rec_status = "WARNING"
        rec_title = "Watering Needed Soon"
        rec_desc = f"Soil moisture is at {current_moisture:.1f}%. Soil is starting to dry out."
        rec_action = "STANDBY"
    elif current_moisture <= norm_max:
        rec_status = "OPTIMAL"
        rec_title = "Moisture Level Is Good"
        rec_desc = f"Soil moisture is at {current_moisture:.1f}%. Soil has plenty of water. No watering needed right now."
        rec_action = "STOP_PUMP"
    else:
        rec_status = "EXCESS"
        rec_title = "Soil Is Too Wet"
        rec_desc = f"Soil moisture is at {current_moisture:.1f}%. Keep pump off so the soil can breathe and drain."
        rec_action = "STOP_PUMP"

    # Active run calculation if pump is running
    active_duration_minutes = 0.0
    active_water_used = 0.0
    if pump_state == 'ON' and pump_started_at:
        try:
            started = datetime.datetime.strptime(pump_started_at, '%Y-%m-%d %H:%M:%S')
            diff_seconds = (datetime.datetime.now() - started).total_seconds()
            active_duration_minutes = round(max(0.0, diff_seconds / 60.0), 2)
            active_water_used = round(active_duration_minutes * flow_rate, 1)
        except Exception:
            pass

    # Total water used today
    cursor.execute("""
        SELECT COALESCE(SUM(water_used_liters), 0) as total_liters 
        FROM irrigation_records 
        WHERE date(timestamp) = date('now', 'localtime')
    """)
    today_water = round(cursor.fetchone()['total_liters'] + active_water_used, 1)

    # Recent history
    cursor.execute("""
        SELECT id, trigger_type, action, duration_minutes, water_used_liters, 
               soil_moisture_before, soil_moisture_after, notes, timestamp
        FROM irrigation_records
        ORDER BY timestamp DESC
        LIMIT 10
    """)
    history = [dict(row) for row in cursor.fetchall()]

    conn.close()

    return {
        "pump_state": pump_state,
        "mode": mode,
        "current_soil_moisture": current_moisture,
        "thresholds": {
            "critical_min": crit_moist,
            "warning_min": warn_moist,
            "normal_max": norm_max,
            "flow_rate_lpm": flow_rate
        },
        "recommendation": {
            "status": rec_status,
            "title": rec_title,
            "description": rec_desc,
            "suggested_action": rec_action
        },
        "active_cycle": {
            "started_at": pump_started_at,
            "running_duration_minutes": active_duration_minutes,
            "estimated_water_liters": active_water_used
        },
        "water_usage_today_liters": today_water,
        "history": history
    }

def toggle_pump(target_state, trigger_type="manual", notes="Manual operator toggle"):
    """
    Toggles the pump state ON or OFF and updates irrigation records.
    """
    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("SELECT key, value FROM system_settings")
    settings = {row['key']: row['value'] for row in cursor.fetchall()}
    current_state = settings.get('pump_state', 'OFF')
    pump_started_at = settings.get('pump_started_at', '')
    flow_rate = float(settings.get('water_flow_rate_lpm', 12.5))

    # Fetch current moisture
    cursor.execute("SELECT current_reading FROM sensors WHERE sensor_type = 'soil_moisture' LIMIT 1")
    sm_row = cursor.fetchone()
    current_moist = sm_row['current_reading'] if sm_row else 45.0

    now_str = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')

    if target_state == 'ON' and current_state != 'ON':
        cursor.execute("UPDATE system_settings SET value = 'ON' WHERE key = 'pump_state'")
        cursor.execute("UPDATE system_settings SET value = ? WHERE key = 'pump_started_at'", (now_str,))
        cursor.execute("""
            INSERT INTO irrigation_records (trigger_type, action, duration_minutes, water_used_liters, soil_moisture_before, notes, timestamp)
            VALUES (?, 'STARTED', 0, 0.0, ?, ?, datetime('now', 'localtime'))
        """, (trigger_type, current_moist, f"{notes} (Pump Activated)"))
        conn.commit()

    elif target_state == 'OFF' and current_state == 'ON':
        # Calculate duration
        duration_minutes = 1
        if pump_started_at:
            try:
                st = datetime.datetime.strptime(pump_started_at, '%Y-%m-%d %H:%M:%S')
                duration_minutes = max(1, int(round((datetime.datetime.now() - st).total_seconds() / 60.0)))
            except Exception:
                duration_minutes = 1

        water_liters = round(duration_minutes * flow_rate, 1)

        cursor.execute("UPDATE system_settings SET value = 'OFF' WHERE key = 'pump_state'")
        cursor.execute("UPDATE system_settings SET value = '' WHERE key = 'pump_started_at'")
        cursor.execute("""
            INSERT INTO irrigation_records (trigger_type, action, duration_minutes, water_used_liters, soil_moisture_after, notes, timestamp)
            VALUES (?, 'COMPLETED', ?, ?, ?, ?, datetime('now', 'localtime'))
        """, (trigger_type, duration_minutes, water_liters, current_moist, f"{notes} (Pump Stopped - Cycle complete)"))
        conn.commit()

    conn.close()
    return get_irrigation_status()

def set_irrigation_mode(mode):
    if mode not in ['auto', 'manual']:
        return False
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("UPDATE system_settings SET value = ? WHERE key = 'active_irrigation_mode'", (mode,))
    conn.commit()
    conn.close()
    return True

