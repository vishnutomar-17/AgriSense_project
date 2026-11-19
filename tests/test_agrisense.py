import os
import sys
import unittest
import json
import datetime

# Add backend directory to sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'backend')))

from app import create_app
from database import get_db_connection

class AgriSenseComprehensiveTestSuite(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = create_app()
        cls.client = cls.app.test_client()

    def test_01_health_check(self):
        """Verify API Health Check Endpoint"""
        res = self.client.get('/api/health')
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertEqual(data['status'], 'healthy')
        self.assertIn('AgriSense', data['application'])

    def test_02_authentication_admin_login(self):
        """Verify Default Admin Authentication with Password Hashing"""
        res = self.client.post('/api/auth/login', json={
            'username': 'admin',
            'password': 'Admin@123'
        })
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertIn('token', data)
        self.assertEqual(data['user']['username'], 'admin')
        self.assertEqual(data['user']['role'], 'admin')

        # Invalid password check
        bad_res = self.client.post('/api/auth/login', json={
            'username': 'admin',
            'password': 'WrongPassword999'
        })
        self.assertEqual(bad_res.status_code, 401)

    def test_03_registration_and_protected_me_route(self):
        """Verify New User Registration and Session Token Verification"""
        test_user = f"tester_{int(datetime.datetime.now().timestamp())}"
        reg_res = self.client.post('/api/auth/register', json={
            'username': test_user,
            'email': f'{test_user}@test.local',
            'password': 'Password@123'
        })
        self.assertEqual(reg_res.status_code, 201)
        token = reg_res.get_json()['token']

        # Verify /api/auth/me with bearer token
        me_res = self.client.get('/api/auth/me', headers={'Authorization': f'Bearer {token}'})
        self.assertEqual(me_res.status_code, 200)
        self.assertEqual(me_res.get_json()['user']['username'], test_user)

        # Unauthenticated request should be rejected (401)
        unauth_res = self.client.get('/api/auth/me')
        self.assertEqual(unauth_res.status_code, 401)

    def test_04_dashboard_summary(self):
        """Verify Dashboard Statistics and Summary Aggregations"""
        login_res = self.client.post('/api/auth/login', json={'username': 'admin', 'password': 'Admin@123'})
        token = login_res.get_json()['token']

        res = self.client.get('/api/dashboard/summary', headers={'Authorization': f'Bearer {token}'})
        self.assertEqual(res.status_code, 200)
        data = res.get_json()

        # Check required top cards
        self.assertIn('cards', data)
        card_types = [c['type'] for c in data['cards']]
        for required_type in ['air_temperature', 'air_humidity', 'soil_moisture', 'light_intensity', 'soil_temperature', 'rainfall']:
            self.assertIn(required_type, card_types)

        # Check history charts, irrigation, and device status
        self.assertIn('history_charts', data)
        self.assertIn('devices', data)
        self.assertIn('irrigation', data)
        self.assertIn('system', data)

    def test_05_hardware_sensor_ingestion_and_security(self):
        """Verify Hardware REST API (POST /api/sensors/readings) Security and Ingestion"""
        # 1. Reject unauthorized device without key
        unauth = self.client.post('/api/sensors/readings', json={
            'device_id': 'ESP32-AGRI-01',
            'readings': [{'sensor_id': 'soil_moisture_1', 'value': 40.0}]
        })
        self.assertEqual(unauth.status_code, 401)

        # 2. Reject fake device key
        wrong_key = self.client.post('/api/sensors/readings', json={
            'device_id': 'ESP32-AGRI-01',
            'device_key': 'invalid_secret_key_xyz',
            'readings': [{'sensor_id': 'soil_moisture_1', 'value': 40.0}]
        })
        self.assertEqual(wrong_key.status_code, 403)

        # 3. Successful ingestion from authorized device
        valid_res = self.client.post('/api/sensors/readings', json={
            'device_id': 'ESP32-AGRI-01',
            'device_key': 'agri_sec_key_esp32_01_live',
            'readings': [
                {'sensor_id': 'air_temp_1', 'value': 27.2, 'unit': '°C'},
                {'sensor_id': 'air_humidity_1', 'value': 54.0, 'unit': '%'},
                {'sensor_id': 'soil_moisture_1', 'value': 42.5, 'unit': '%'}
            ]
        })
        self.assertEqual(valid_res.status_code, 201)
        data = valid_res.get_json()
        self.assertEqual(data['status'], 'success')
        self.assertEqual(data['data_source'], 'hardware')
        self.assertEqual(data['ingested_count'], 3)

    def test_06_smart_irrigation_recommendations_and_toggle(self):
        """Verify Rule-Based Irrigation Recommendation & Software Pump Control"""
        login_res = self.client.post('/api/auth/login', json={'username': 'admin', 'password': 'Admin@123'})
        token = login_res.get_json()['token']
        headers = {'Authorization': f'Bearer {token}'}

        # Query status
        status_res = self.client.get('/api/irrigation/status', headers=headers)
        self.assertEqual(status_res.status_code, 200)
        status_data = status_res.get_json()
        self.assertIn('pump_state', status_data)
        self.assertIn('recommendation', status_data)
        self.assertIn('status', status_data['recommendation'])

        # Test toggle ON
        toggle_on = self.client.post('/api/irrigation/toggle', headers=headers, json={'state': 'ON', 'notes': 'Test run ON'})
        self.assertEqual(toggle_on.status_code, 200)
        self.assertEqual(toggle_on.get_json()['status']['pump_state'], 'ON')

        # Test toggle OFF
        toggle_off = self.client.post('/api/irrigation/toggle', headers=headers, json={'state': 'OFF', 'notes': 'Test run OFF'})
        self.assertEqual(toggle_off.status_code, 200)
        self.assertEqual(toggle_off.get_json()['status']['pump_state'], 'OFF')

    def test_07_alert_engine_and_threshold_violation(self):
        """Verify Autonomous Alert Generation on Extreme Values & De-duplication"""
        # Inject critical low soil moisture (12.0%)
        self.client.post('/api/sensors/readings', json={
            'device_id': 'ESP32-AGRI-01',
            'device_key': 'agri_sec_key_esp32_01_live',
            'readings': [
                {'sensor_id': 'soil_moisture_1', 'value': 12.0, 'unit': '%'}
            ]
        })

        # Fetch alerts
        login_res = self.client.post('/api/auth/login', json={'username': 'admin', 'password': 'Admin@123'})
        token = login_res.get_json()['token']
        headers = {'Authorization': f'Bearer {token}'}

        res = self.client.get('/api/alerts?severity=Critical', headers=headers)
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertGreaterEqual(len(data['alerts']), 1)
        alert_item = data['alerts'][0]
        self.assertEqual(alert_item['severity'], 'Critical')

        # Test acknowledge alert
        ack_res = self.client.post(f"/api/alerts/{alert_item['id']}/read", headers=headers)
        self.assertEqual(ack_res.status_code, 200)

    def test_08_analytics_and_statistics(self):
        """Verify Analytics Trends and Statistical Calculations"""
        login_res = self.client.post('/api/auth/login', json={'username': 'admin', 'password': 'Admin@123'})
        token = login_res.get_json()['token']
        headers = {'Authorization': f'Bearer {token}'}

        res = self.client.get('/api/analytics/trends?range=24h', headers=headers)
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertIn('trends', data)
        self.assertIn('statistics', data)
        self.assertIn('temperature', data['statistics'])
        self.assertIn('avg', data['statistics']['temperature'])

    def test_09_csv_export(self):
        """Verify Database CSV Report Generation and Headers"""
        login_res = self.client.post('/api/auth/login', json={'username': 'admin', 'password': 'Admin@123'})
        token = login_res.get_json()['token']
        headers = {'Authorization': f'Bearer {token}'}

        res = self.client.get('/api/export/readings.csv?range=24h', headers=headers)
        self.assertEqual(res.status_code, 200)
        self.assertIn('text/csv', res.headers.get('Content-Type'))
        csv_text = res.get_data(as_text=True)

        # Check required columns
        header_line = csv_text.strip().split('\n')[0]
        for col in ['Date and Time', 'Sensor Name', 'Sensor Value', 'Measurement Unit', 'Data Source']:
            self.assertIn(col, header_line)

    def test_10_weather_service_endpoint(self):
        """Verify Weather Endpoint Graceful Handling"""
        login_res = self.client.post('/api/auth/login', json={'username': 'admin', 'password': 'Admin@123'})
        token = login_res.get_json()['token']
        headers = {'Authorization': f'Bearer {token}'}

        res = self.client.get('/api/weather', headers=headers)
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertIn(data['status'], ['online', 'unavailable'])
        self.assertIn('location', data)

    def test_11_settings_persistence(self):
        """Verify Settings Update and SQLite Persistence"""
        login_res = self.client.post('/api/auth/login', json={'username': 'admin', 'password': 'Admin@123'})
        token = login_res.get_json()['token']
        headers = {'Authorization': f'Bearer {token}'}

        # Update high temp threshold to 38.5
        update_res = self.client.put('/api/settings', headers=headers, json={
            'high_temp_threshold': '38.5'
        })
        self.assertEqual(update_res.status_code, 200)

        # Query settings to verify persistence
        get_res = self.client.get('/api/settings', headers=headers)
        self.assertEqual(get_res.status_code, 200)
        self.assertEqual(get_res.get_json()['settings']['high_temp_threshold'], '38.5')

if __name__ == '__main__':
    unittest.main()

