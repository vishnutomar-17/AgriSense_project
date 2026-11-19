import threading
import time
import math
import random
import datetime
from database import get_db_connection
from alert_engine import evaluate_sensor_alerts
from irrigation_engine import toggle_pump

class SensorSimulator:
    def __init__(self):
        self._running = False
        self._thread = None
        self._stop_event = threading.Event()

    def is_running(self):
        return self._running

    def trigger_scenario(self, scenario_name):
        """
        Immediately applies an environmental test scenario (heatwave, heavy_rain, dry_soil, optimal)
        so examiners can witness dynamic dashboard and alert updates live!
        """
        conn = get_db_connection()
        cursor = conn.cursor()
        now_ts = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')

        updates = []
        if scenario_name == 'dry_soil':
            updates = [
                ('soil_moisture_1', 18.2, '%', 'soil_moisture', 'critical'),
                ('air_temp_1', 31.5, '°C', 'air_temperature', 'optimal'),
                ('air_humidity_1', 34.0, '%', 'air_humidity', 'warning')
            ]
        elif scenario_name == 'heatwave':
            updates = [
                ('air_temp_1', 38.6, '°C', 'air_temperature', 'warning'),
                ('air_humidity_1', 22.0, '%', 'air_humidity', 'warning'),
                ('soil_moisture_1', 21.5, '%', 'soil_moisture', 'critical'),
                ('light_ldr_1', 58000.0, 'lux', 'light_intensity', 'optimal')
            ]
        elif scenario_name == 'heavy_rain':
            updates = [
                ('rain_1', 16.4, 'mm', 'rainfall', 'optimal'),
                ('soil_moisture_1', 74.0, '%', 'soil_moisture', 'warning'),
                ('air_temp_1', 20.5, '°C', 'air_temperature', 'optimal'),
                ('air_humidity_1', 88.0, '%', 'air_humidity', 'optimal')
            ]
        elif scenario_name == 'optimal':
            updates = [
                ('soil_moisture_1', 52.0, '%', 'soil_moisture', 'optimal'),
                ('air_temp_1', 24.2, '°C', 'air_temperature', 'optimal'),
                ('air_humidity_1', 61.5, '%', 'air_humidity', 'optimal'),
                ('soil_temp_1', 21.8, '°C', 'soil_temperature', 'optimal'),
                ('light_ldr_1', 36500.0, 'lux', 'light_intensity', 'optimal'),
                ('rain_1', 0.0, 'mm', 'rainfall', 'optimal')
            ]

        for s_id, val, unit, stype, status in updates:
            cursor.execute("""
                UPDATE sensors 
                SET current_reading = ?, unit = ?, status = ?, last_updated = ?
                WHERE id = ?
            """, (val, unit, status, now_ts, s_id))

            cursor.execute("""
                INSERT INTO sensor_readings (sensor_id, device_id, reading_value, unit, data_source, timestamp)
                VALUES (?, 'ESP32-AGRI-01', ?, ?, 'simulation', ?)
            """, (s_id, val, unit, now_ts))

        conn.commit()
        conn.close()

        # Evaluate alerts
        for s_id, val, unit, stype, _ in updates:
            evaluate_sensor_alerts(s_id, stype, val, unit)

        return True

    def start(self):
        if self._running:
            return
        self._stop_event.clear()
        self._running = True
        self._thread = threading.Thread(target=self._run_loop, daemon=True)
        self._thread.start()
        print("[Simulator] Sensor simulation engine started in background.")

    def stop(self):
        if not self._running:
            return
        self._stop_event.set()
        self._running = False
        if self._thread:
            self._thread.join(timeout=2.0)
        print("[Simulator] Sensor simulation engine stopped.")

    def _run_loop(self):
        while not self._stop_event.is_set():
            try:
                self._tick()
            except Exception as e:
                print(f"[Simulator Error] {e}")

            # Fetch simulation interval setting
            interval = 5
            try:
                conn = get_db_connection()
                cur = conn.cursor()
                cur.execute("SELECT value FROM system_settings WHERE key = 'simulation_interval_seconds'")
                row = cur.fetchone()
                if row:
                    interval = max(2, int(row['value']))
                conn.close()
            except Exception:
                interval = 5

            self._stop_event.wait(interval)

    def _tick(self):
        conn = get_db_connection()
        cursor = conn.cursor()

        # Check if simulation_mode is enabled in database
        cursor.execute("SELECT value FROM system_settings WHERE key = 'simulation_mode'")
        sim_setting = cursor.fetchone()
        if not sim_setting or sim_setting['value'].lower() != 'true':
            conn.close()
            return

        # Fetch current sensor states
        cursor.execute("SELECT id, sensor_type, current_reading, unit, min_threshold, max_threshold FROM sensors")
        sensors = {row['id']: dict(row) for row in cursor.fetchall()}

        cursor.execute("SELECT key, value FROM system_settings")
        settings = {row['key']: row['value'] for row in cursor.fetchall()}
        pump_state = settings.get('pump_state', 'OFF')
        irrigation_mode = settings.get('active_irrigation_mode', 'auto')
        crit_moisture = float(settings.get('soil_moisture_critical_min', 25.0))

        now = datetime.datetime.now()
        hour = now.hour + (now.minute / 60.0)

        # Baseline diurnal diurnal calculations
        # Peak heat at 14:00 (2 PM), low at 05:00
        diurnal_angle = (hour - 8) / 24.0 * 2 * math.pi
        diurnal_temp_factor = math.sin(diurnal_angle)

        target_air_temp = 24.0 + 5.0 * diurnal_temp_factor
        target_humidity = 65.0 - 20.0 * diurnal_temp_factor

        # Update sensors with smooth transition (exponential moving average / small random walk)
        updated_sensors = []
        new_readings = []

        # 1. Air Temperature
        curr_temp = sensors.get('air_temp_1', {}).get('current_reading', 24.0)
        # Small noise (-0.1 to +0.1)
        next_temp = round(curr_temp * 0.9 + target_air_temp * 0.1 + random.uniform(-0.15, 0.15), 1)
        updated_sensors.append(('air_temp_1', next_temp, '°C', 'air_temperature'))

        # 2. Air Humidity
        curr_hum = sensors.get('air_humidity_1', {}).get('current_reading', 60.0)
        next_hum = round(max(15.0, min(95.0, curr_hum * 0.9 + target_humidity * 0.1 + random.uniform(-0.3, 0.3))), 1)
        updated_sensors.append(('air_humidity_1', next_hum, '%', 'air_humidity'))

        # 3. Light Intensity (Lux)
        if 6.0 <= hour <= 18.5:
            sun_factor = math.sin((hour - 6.0) / 12.5 * math.pi)
            cloud_factor = random.uniform(0.85, 1.0)
            target_light = max(500.0, sun_factor * 65000.0 * cloud_factor)
        else:
            target_light = random.uniform(0.0, 15.0) # Night
        curr_light = sensors.get('light_ldr_1', {}).get('current_reading', 10000.0)
        next_light = round(curr_light * 0.8 + target_light * 0.2 + random.uniform(-50, 50), 0)
        next_light = max(0.0, next_light)
        updated_sensors.append(('light_ldr_1', next_light, 'lux', 'light_intensity'))

        # 4. Soil Temperature (lags air temp with smaller amplitude)
        curr_soil_t = sensors.get('soil_temp_1', {}).get('current_reading', 21.0)
        target_soil_t = 21.5 + 2.5 * math.sin((hour - 11) / 24.0 * 2 * math.pi)
        next_soil_t = round(curr_soil_t * 0.92 + target_soil_t * 0.08 + random.uniform(-0.08, 0.08), 1)
        updated_sensors.append(('soil_temp_1', next_soil_t, '°C', 'soil_temperature'))

        # 5. Soil Moisture
        curr_moist = sensors.get('soil_moisture_1', {}).get('current_reading', 45.0)
        if pump_state == 'ON':
            # Water flowing! Soil moisture increases smoothly
            next_moist = round(min(82.0, curr_moist + random.uniform(0.6, 1.2)), 1)
        else:
            # Evaporation / transpiration loss
            loss_rate = 0.08 if next_temp > 28.0 else 0.04
            next_moist = round(max(10.0, curr_moist - random.uniform(0.02, loss_rate)), 1)
        updated_sensors.append(('soil_moisture_1', next_moist, '%', 'soil_moisture'))

        # 6. Rainfall (occasional micro drizzle or 0)
        curr_rain = sensors.get('rain_1', {}).get('current_reading', 0.0)
        if curr_rain > 0:
            # Decay rain gauge
            next_rain = round(max(0.0, curr_rain - 0.2), 1)
        else:
            # 1 in 1000 chance of brief rain burst during normal simulation
            next_rain = 0.0
            if random.random() < 0.002:
                next_rain = round(random.uniform(1.2, 5.0), 1)
        updated_sensors.append(('rain_1', next_rain, 'mm', 'rainfall'))

        # Commit updates
        now_ts = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        for s_id, val, unit, stype in updated_sensors:
            # Update sensor record
            status = 'optimal'
            if stype == 'soil_moisture':
                if val < crit_moisture:
                    status = 'critical'
                elif val < 40.0:
                    status = 'warning'
                elif val > 75.0:
                    status = 'warning'
            elif stype == 'air_temperature' and (val > 35.0 or val < 8.0):
                status = 'warning'

            cursor.execute("""
                UPDATE sensors 
                SET current_reading = ?, unit = ?, status = ?, last_updated = ?
                WHERE id = ?
            """, (val, unit, status, now_ts, s_id))

            # Insert reading history
            cursor.execute("""
                INSERT INTO sensor_readings (sensor_id, device_id, reading_value, unit, data_source, timestamp)
                VALUES (?, 'ESP32-AGRI-01', ?, ?, 'simulation', ?)
            """, (s_id, val, unit, now_ts))

        conn.commit()
        conn.close()

        # Run alert engine after committing updates
        for s_id, val, unit, stype in updated_sensors:
            evaluate_sensor_alerts(s_id, stype, val, unit)

        # Handle Automated Irrigation Cycle in simulation
        if irrigation_mode == 'auto':
            if pump_state == 'OFF' and next_moist < crit_moisture:
                print(f"[Auto-Irrigation] Triggering pump due to low moisture: {next_moist}%")
                toggle_pump('ON', trigger_type='automatic', notes='Automated threshold-based irrigation cycle')
            elif pump_state == 'ON' and next_moist >= 62.0:
                print(f"[Auto-Irrigation] Halting pump. Soil moisture restored: {next_moist}%")
                toggle_pump('OFF', trigger_type='automatic', notes='Automated target moisture achieved')

simulator = SensorSimulator()
