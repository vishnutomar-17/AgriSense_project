import sqlite3
import os
import datetime
from werkzeug.security import generate_password_hash

DB_PATH = os.path.join(os.path.dirname(__file__), 'agrisense.db')

def get_db_connection():
    conn = sqlite3.connect(DB_PATH, timeout=30.0)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA journal_mode = WAL")
    return conn

def init_db():
    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.executescript('''
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT UNIQUE NOT NULL,
        email TEXT UNIQUE NOT NULL,
        password_hash TEXT NOT NULL,
        role TEXT NOT NULL DEFAULT 'admin',
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );

    CREATE TABLE IF NOT EXISTS devices (
        id TEXT PRIMARY KEY,
        name TEXT NOT NULL,
        location TEXT NOT NULL,
        device_type TEXT NOT NULL,
        api_key TEXT UNIQUE NOT NULL,
        status TEXT NOT NULL DEFAULT 'online',
        ip_address TEXT,
        last_seen TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );

    CREATE TABLE IF NOT EXISTS sensors (
        id TEXT PRIMARY KEY,
        device_id TEXT NOT NULL,
        name TEXT NOT NULL,
        sensor_type TEXT NOT NULL,
        unit TEXT NOT NULL,
        min_threshold REAL,
        max_threshold REAL,
        current_reading REAL,
        status TEXT NOT NULL DEFAULT 'optimal',
        last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (device_id) REFERENCES devices (id) ON DELETE CASCADE
    );

    CREATE TABLE IF NOT EXISTS sensor_readings (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        sensor_id TEXT NOT NULL,
        device_id TEXT NOT NULL,
        reading_value REAL NOT NULL,
        unit TEXT NOT NULL,
        data_source TEXT NOT NULL,
        timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (sensor_id) REFERENCES sensors (id) ON DELETE CASCADE
    );

    CREATE INDEX IF NOT EXISTS idx_readings_sensor_time ON sensor_readings(sensor_id, timestamp);
    CREATE INDEX IF NOT EXISTS idx_readings_time ON sensor_readings(timestamp);

    CREATE TABLE IF NOT EXISTS alerts (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        sensor_id TEXT,
        category TEXT NOT NULL,
        severity TEXT NOT NULL,
        title TEXT NOT NULL,
        description TEXT NOT NULL,
        is_read INTEGER DEFAULT 0,
        timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );

    CREATE INDEX IF NOT EXISTS idx_alerts_time ON alerts(timestamp);

    CREATE TABLE IF NOT EXISTS irrigation_records (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        trigger_type TEXT NOT NULL,
        action TEXT NOT NULL,
        duration_minutes INTEGER DEFAULT 0,
        water_used_liters REAL DEFAULT 0.0,
        soil_moisture_before REAL,
        soil_moisture_after REAL,
        notes TEXT,
        timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );

    CREATE TABLE IF NOT EXISTS system_settings (
        key TEXT PRIMARY KEY,
        value TEXT NOT NULL,
        description TEXT,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
    ''')
    conn.commit()
    conn.close()

def seed_initial_data():
    conn = get_db_connection()
    cursor = conn.cursor()

    # 1. Default Admin user
    cursor.execute("SELECT id FROM users WHERE username = 'admin'")
    if not cursor.fetchone():
        hashed = generate_password_hash("Admin@123")
        cursor.execute(
            "INSERT INTO users (username, email, password_hash, role) VALUES (?, ?, ?, ?)",
            ("admin", "admin@agrisense.local", hashed, "admin")
        )

    # 2. Default System Settings
    default_settings = [
        ('simulation_mode', 'true', 'Enable or disable realistic background sensor simulation'),
        ('simulation_interval_seconds', '5', 'Simulation tick interval in seconds'),
        ('active_irrigation_mode', 'auto', 'Irrigation mode: auto or manual'),
        ('pump_state', 'OFF', 'Physical/simulated pump state (ON or OFF)'),
        ('pump_started_at', '', 'Timestamp when pump was turned ON'),
        ('water_flow_rate_lpm', '12.5', 'Irrigation water discharge rate in liters per minute'),
        ('soil_moisture_critical_min', '25.0', 'Threshold for critical dry soil requiring immediate irrigation (%)'),
        ('soil_moisture_warning_min', '40.0', 'Threshold for low moisture warning (%)'),
        ('soil_moisture_normal_max', '70.0', 'Optimal upper limit for soil moisture (%)'),
        ('high_temp_threshold', '35.0', 'High air temperature alert threshold (°C)'),
        ('low_humidity_threshold', '30.0', 'Low air humidity alert threshold (%)'),
        ('farm_location_name', 'Green Valley Research Farm, Polyhouse A', 'Agricultural location description'),
        ('farm_latitude', '28.6139', 'Farm latitude for meteorological forecasts'),
        ('farm_longitude', '77.2090', 'Farm longitude for meteorological forecasts')
    ]

    for key, val, desc in default_settings:
        cursor.execute(
            "INSERT OR IGNORE INTO system_settings (key, value, description) VALUES (?, ?, ?)",
            (key, val, desc)
        )

    # 3. Default IoT Devices
    default_devices = [
        ('ESP32-AGRI-01', 'Greenhouse Gateway Node Alpha', 'Polyhouse A - Sector 1', 'ESP32 NodeMCU DevKit v1', 'agri_sec_key_esp32_01_live', 'online', '192.168.1.120'),
        ('ESP8266-FIELD-02', 'Open Field Telemetry Node Beta', 'Outdoor Wheat Field - Plot B', 'ESP8266 NodeMCU v3', 'agri_sec_key_esp8266_02_field', 'online', '192.168.1.121')
    ]

    for d_id, name, loc, dtype, key, status, ip in default_devices:
        cursor.execute(
            """INSERT OR IGNORE INTO devices (id, name, location, device_type, api_key, status, ip_address)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (d_id, name, loc, dtype, key, status, ip)
        )

    # 4. Default Sensors
    default_sensors = [
        ('air_temp_1', 'ESP32-AGRI-01', 'Air Temperature (DHT22)', 'air_temperature', '°C', 10.0, 35.0, 24.5, 'optimal'),
        ('air_humidity_1', 'ESP32-AGRI-01', 'Air Humidity (DHT22)', 'air_humidity', '%', 30.0, 85.0, 62.0, 'optimal'),
        ('soil_moisture_1', 'ESP32-AGRI-01', 'Capacitive Soil Moisture Probe 1', 'soil_moisture', '%', 25.0, 70.0, 48.0, 'optimal'),
        ('soil_temp_1', 'ESP32-AGRI-01', 'Subsurface Soil Temperature (DS18B20)', 'soil_temperature', '°C', 15.0, 32.0, 21.8, 'optimal'),
        ('light_ldr_1', 'ESP32-AGRI-01', 'Canopy Ambient Light Sensor (BH1750/LDR)', 'light_intensity', 'lux', 100.0, 80000.0, 38500.0, 'optimal'),
        ('rain_1', 'ESP32-AGRI-01', 'Tipping Bucket Rain Gauge', 'rainfall', 'mm', 0.0, 50.0, 0.0, 'optimal')
    ]

    for s_id, dev_id, name, stype, unit, min_t, max_t, curr, stat in default_sensors:
        cursor.execute(
            """INSERT OR IGNORE INTO sensors (id, device_id, name, sensor_type, unit, min_threshold, max_threshold, current_reading, status)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (s_id, dev_id, name, stype, unit, min_t, max_t, curr, stat)
        )

    # 5. Populate realistic 24-hour baseline history if table is empty
    cursor.execute("SELECT COUNT(*) FROM sensor_readings")
    count = cursor.fetchone()[0]
    if count == 0:
        import math
        now = datetime.datetime.now()
        readings = []
        # Generate 24 hours of hourly baseline readings
        for hours_ago in range(24, 0, -1):
            ts = (now - datetime.timedelta(hours=hours_ago)).strftime('%Y-%m-%d %H:%M:%S')
            hour_of_day = (now - datetime.timedelta(hours=hours_ago)).hour

            # Realistic daily diurnal curves
            # Temperature peaks at 14:00 (2pm)
            temp_var = math.sin((hour_of_day - 8) / 24.0 * 2 * math.pi)
            temp = round(23.5 + 4.5 * temp_var, 1)

            # Humidity is inverse of temperature
            humidity = round(65.0 - 18.0 * temp_var, 1)

            # Light curve: 0 at night, peak around noon
            if 6 <= hour_of_day <= 18:
                light = round(math.sin((hour_of_day - 6) / 12.0 * math.pi) * 55000 + 2000)
            else:
                light = 0.0

            # Soil temp lags air temp
            soil_temp = round(21.0 + 2.0 * math.sin((hour_of_day - 11) / 24.0 * 2 * math.pi), 1)

            # Soil moisture slowly dries down unless irrigated
            soil_moist = round(52.0 - (24 - hours_ago) * 0.25, 1)
            rain = 0.0

            readings.extend([
                ('air_temp_1', 'ESP32-AGRI-01', temp, '°C', 'simulation', ts),
                ('air_humidity_1', 'ESP32-AGRI-01', humidity, '%', 'simulation', ts),
                ('soil_moisture_1', 'ESP32-AGRI-01', soil_moist, '%', 'simulation', ts),
                ('soil_temp_1', 'ESP32-AGRI-01', soil_temp, '°C', 'simulation', ts),
                ('light_ldr_1', 'ESP32-AGRI-01', light, 'lux', 'simulation', ts),
                ('rain_1', 'ESP32-AGRI-01', rain, 'mm', 'simulation', ts)
            ])

        cursor.executemany(
            """INSERT INTO sensor_readings (sensor_id, device_id, reading_value, unit, data_source, timestamp)
               VALUES (?, ?, ?, ?, ?, ?)""",
            readings
        )

        # Update sensor current reading to last historical reading
        cursor.execute("UPDATE sensors SET current_reading = ? WHERE id = 'air_temp_1'", (readings[-6][2],))
        cursor.execute("UPDATE sensors SET current_reading = ? WHERE id = 'air_humidity_1'", (readings[-5][2],))
        cursor.execute("UPDATE sensors SET current_reading = ? WHERE id = 'soil_moisture_1'", (readings[-4][2],))
        cursor.execute("UPDATE sensors SET current_reading = ? WHERE id = 'soil_temp_1'", (readings[-3][2],))
        cursor.execute("UPDATE sensors SET current_reading = ? WHERE id = 'light_ldr_1'", (readings[-2][2],))
        cursor.execute("UPDATE sensors SET current_reading = ? WHERE id = 'rain_1'", (readings[-1][2],))

    # 6. Sample Initial Alerts if empty
    cursor.execute("SELECT COUNT(*) FROM alerts")
    if cursor.fetchone()[0] == 0:
        now_str = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        earlier_str = (datetime.datetime.now() - datetime.timedelta(hours=2)).strftime('%Y-%m-%d %H:%M:%S')
        cursor.execute("""
            INSERT INTO alerts (sensor_id, category, severity, title, description, is_read, timestamp)
            VALUES 
            (NULL, 'system', 'Informational', 'AgriSense System Initialized', 'AgriSense monitoring core and telemetry channels online.', 0, ?),
            ('soil_moisture_1', 'soil_moisture', 'Warning', 'Soil Moisture Approaching Lower Bound', 'Root-zone moisture dropped to 48.0%. Auto-irrigation standing by.', 0, ?)
        """, (now_str, earlier_str))

    # 7. Sample Initial Irrigation Record if empty
    cursor.execute("SELECT COUNT(*) FROM irrigation_records")
    if cursor.fetchone()[0] == 0:
        yest_str = (datetime.datetime.now() - datetime.timedelta(hours=14)).strftime('%Y-%m-%d %H:%M:%S')
        cursor.execute("""
            INSERT INTO irrigation_records (trigger_type, action, duration_minutes, water_used_liters, soil_moisture_before, soil_moisture_after, notes, timestamp)
            VALUES ('automatic', 'COMPLETED', 15, 187.5, 34.2, 54.0, 'Automated drip irrigation cycle triggered by soil threshold breach', ?)
        """, (yest_str,))

    conn.commit()
    conn.close()

if __name__ == '__main__':
    init_db()
    seed_initial_data()
    print("Database initialized and seeded successfully.")
