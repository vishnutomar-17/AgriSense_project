# 🌱 AgriSense: Smart Agriculture and Environmental Monitoring System

> **Tagline:** *Intelligent Agriculture. Sustainable Environment.*  
> **Classification:** College Minor Project / IoT & Agronomic Telemetry System  
> **Evaluation Mode:** Practical Examination Ready  

---

## 📌 1. Project Overview

**AgriSense** is a full-stack, edge-connected IoT web application and automated decision support system engineered for high-precision agricultural monitoring and closed-loop smart irrigation.

The platform continuously measures root-zone soil hydrology and atmospheric microclimate variables, detects stress conditions, provides automated irrigation recommendations, and streams live telemetry from physical microcontrollers (ESP32 / ESP8266) while providing a background environmental simulation engine for offline demonstrations.

### Key Capabilities
- **6-Parameter Agro-Climatic Monitoring:** Air Temperature (°C), Relative Humidity (%), Soil Moisture (%), Canopy Light Intensity (lux), Subsurface Soil Temperature (°C), and Precipitation (mm).
- **Rule-Based Smart Irrigation Engine:** Autonomous calculation of crop water stress, soil water retention deficit, manual/auto pump actuation, and water volume estimation (Liters).
- **Multi-Tier Autonomous Alert Engine:** Real-time event detection (Critical wilting stress, heat hazard, frost danger, severe dry air, and sensor heartbeats) with rate-limiting de-duplication.
- **Hardware Integration & Telemetry Ingestion API:** Authenticated `POST /api/sensors/readings` endpoint validating incoming device keys, sensor units, and MAC/IP bindings.
- **Realistic Sensor Simulation Mode:** Mathematical simulation engine reflecting diurnal solar curves, exponential cooling, soil evapotranspiration, and pump recharge.
- **Longitudinal Analytics & CSV Reporting:** Time-series charts (Chart.js) with 24h, 7d, and 30d filters, statistical metrics (Min, Max, Mean), and dynamic SQLite CSV export.
- **Meteorological Forecasting:** Native integration with Open-Meteo API comparing external synoptic weather against greenhouse canopy sensors.

---

## 🛠️ 2. System Architecture & Tech Stack

| Layer | Technology | Purpose |
| :--- | :--- | :--- |
| **Frontend** | React 18, Vite 6, Chart.js, Lucide Icons | Responsive single-page application with agricultural palette (forest green, off-white, earth tones). |
| **Backend** | Python 3, Flask 3, Werkzeug, itsdangerous | Modular RESTful API with route blueprints, password hashing, and token sessions. |
| **Database** | SQLite 3 (WAL mode) | Embedded relational database with foreign keys, indexes, and ACID compliance. |
| **IoT / Edge** | ESP32 DevKit v1 / ESP8266 (C++ / Arduino) | Microcontroller firmware transmitting authenticated JSON sensor telemetry. |
| **External APIs**| Open-Meteo Meteorological API | Real-time weather, forecast, and humidity for geo-located farm coordinates. |

---

## 🔐 3. Default Examination Credentials

For evaluation and practical examination review, a default administrative account is pre-seeded in the database:

- **Username:** `admin`
- **Password:** `Admin@123`
- **Role:** Administrator (Full read/write privileges, threshold editing, device management, pump actuation)

> **Security Note:** Passwords are never stored in plaintext; they are hashed using Werkzeug's `scrypt` cryptographic key derivation function.

---

## 🔄 4. Hardware Readings vs. Simulated Readings

AgriSense strictly distinguishes between physical hardware telemetry and simulated data:

| Dimension | Physical Hardware Readings | Background Simulated Readings |
| :--- | :--- | :--- |
| **Data Source Tag** | `data_source = 'hardware'` | `data_source = 'simulation'` |
| **Origin** | Real ESP32 or ESP8266 device via `POST /api/sensors/readings` | Managed background Python thread in `backend/simulation.py` |
| **Security** | Requires valid `device_id` and registered `device_key` | Internal application state |
| **Physical Relevance** | Refers to real physical analog/digital pins | Follows diurnal mathematical curves and evapotranspiration models |
| **UI Indication** | Green status pill: **`HARDWARE MODE`** | Amber status pill: **`SIMULATION MODE`** |
| **CSV Export** | Explicitly labeled as `hardware` in CSV column 6 | Explicitly labeled as `simulation` in CSV column 6 |

Administrators can toggle simulation mode on or off at any time directly from the top navigation bar or the **System Settings** page. When switched to Hardware Mode, the background simulation stops immediately.

---

## 🚀 5. Quick-Start Setup Guide for macOS

### Prerequisites
- **macOS** (Apple Silicon or Intel)
- **Python 3.10+**
- **Node.js 18+** & **npm**

### Option A: One-Command Automated Startup (Recommended)
Open your terminal in the `Agriculture` folder and run:
```bash
./start_agrisense.sh
```
This launcher checks dependencies, initializes the SQLite database, launches the Flask backend on `http://localhost:5001`, and starts the Vite React frontend on `http://localhost:3000`.

---

### Option B: Manual Step-by-Step Setup

#### Step 1: Clone or Navigate to the Workspace
```bash
cd /Users/karanbhadouriya/Agriculture
```

#### Step 2: Set up Python Virtual Environment & Backend
```bash
# Create and activate virtual environment
python3 -m venv .venv
source .venv/bin/activate

# Install backend dependencies
pip install -r requirements.txt

# Initialize database schema and seed default data
PYTHONPATH=backend python backend/database.py

# Start Flask backend server
PYTHONPATH=backend python backend/app.py
```
*Backend is now listening at: `http://localhost:5001/api`*

#### Step 3: Set up Frontend (New Terminal Window)
```bash
cd /Users/karanbhadouriya/Agriculture/frontend

# Install npm packages
npm install

# Start Vite React development server
npm run dev
```
*Frontend is now accessible at: `http://localhost:3000`*

---

## 🧪 6. Testing & Automated Verification

AgriSense includes an automated test suite verifying all 11 core subsystems:

```bash
cd /Users/karanbhadouriya/Agriculture
PYTHONPATH=backend .venv/bin/python tests/test_agrisense.py
```

### Tests Covered:
1. `test_01_health_check`: REST API health probe and service status.
2. `test_02_authentication_admin_login`: Default administrator credential validation & password hashing.
3. `test_03_registration_and_protected_me_route`: New user registration and bearer token verification.
4. `test_04_dashboard_summary`: Multi-parameter top cards, health assessments, and history graphs.
5. `test_05_hardware_sensor_ingestion_and_security`: Validating ESP32 JSON payload, device identification, and rejecting unauthorized keys.
6. `test_06_smart_irrigation_recommendations_and_toggle`: Rule-based water deficit calculation, software pump toggle, and discharge tracking.
7. `test_07_alert_engine_and_threshold_violation`: Autonomous incident dispatch upon moisture depletion, and alert acknowledgment.
8. `test_08_analytics_and_statistics`: Statistical aggregation (Min, Max, Mean) and time-series sampling.
9. `test_09_csv_export`: Database CSV streaming with required metadata headers.
10. `test_10_weather_service_endpoint`: Open-Meteo API integration with graceful network fallback.
11. `test_11_settings_persistence`: Runtime threshold updates and SQLite persistence.

---

## 📡 7. REST API Documentation

### Base URL: `http://localhost:5001/api`

### 1. Authentication
- `POST /api/auth/login`: Authenticate with username and password. Returns signed session token.
- `POST /api/auth/register`: Create a new researcher account.
- `GET /api/auth/me`: Retrieve current profile (Requires `Authorization: Bearer <token>`).
- `POST /api/auth/logout`: Invalidate session.

### 2. Dashboard
- `GET /api/dashboard/summary`: Top 6 metric cards with deltas, device health, recent alerts, irrigation status, and 24h history graphs.

### 3. Sensors
- `GET /api/sensors`: List all 5 sensor categories with current readings, thresholds, and health.
- `PUT /api/sensors/<id>/thresholds`: Update min/max calibrated safety boundaries.
- `GET /api/sensors/<id>/history`: Query historical readings for a specific sensor.
- `POST /api/sensors/readings`: Hardware ingestion endpoint.

#### Hardware Ingestion Example (ESP32 / cURL):
```bash
curl -X POST http://localhost:5001/api/sensors/readings \
  -H "Content-Type: application/json" \
  -H "X-Device-Id: ESP32-AGRI-01" \
  -H "X-Device-Key: agri_sec_key_esp32_01_live" \
  -d '{
    "device_id": "ESP32-AGRI-01",
    "device_key": "agri_sec_key_esp32_01_live",
    "readings": [
      {"sensor_id": "air_temp_1", "value": 26.5, "unit": "°C"},
      {"sensor_id": "air_humidity_1", "value": 58.0, "unit": "%"},
      {"sensor_id": "soil_moisture_1", "value": 45.2, "unit": "%"},
      {"sensor_id": "soil_temp_1", "value": 22.0, "unit": "°C"},
      {"sensor_id": "light_ldr_1", "value": 36000, "unit": "lux"},
      {"sensor_id": "rain_1", "value": 0.0, "unit": "mm"}
    ]
  }'
```

### 4. Smart Irrigation
- `GET /api/irrigation/status`: Current pump state, auto recommendation, and water used today.
- `POST /api/irrigation/toggle`: Manual pump start/stop (`{"state": "ON"|"OFF"}`).
- `POST /api/irrigation/mode`: Switch mode (`{"mode": "auto"|"manual"}`).
- `PUT /api/irrigation/thresholds`: Update critical, warning, and cutoff moisture levels.
- `GET /api/irrigation/history`: Historical log of all irrigation runs.

### 5. Alerts & Incidents
- `GET /api/alerts`: List alerts with optional filters (`severity=Critical|Warning|Informational`, `is_read=0|1`).
- `POST /api/alerts/<id>/read`: Acknowledge individual incident.
- `POST /api/alerts/mark-all-read`: Acknowledge all active alerts.

### 6. Analytics & CSV Export
- `GET /api/analytics/trends?range=24h|7d|30d`: Time-series trends and statistical parameters.
- `GET /api/export/readings.csv?range=24h|7d|30d|all`: Streams SQLite telemetry as downloadable CSV.

### 7. Settings & Diagnostics
- `GET /api/settings`: Returns operational settings, SQLite file size, and uptime.
- `PUT /api/settings`: Update thresholds, simulation intervals, and farm location.
- `POST /api/settings/toggle-simulation`: Immediate toggle of simulation mode.

---

## 🔌 8. Hardware Connection Guide (ESP32 DevKit v1)

The file `esp32/agrisense_esp32.ino` contains production firmware for the ESP32 microcontroller.

### Wiring Schematic Table:

| Sensor / Module | Signal Type | ESP32 GPIO Pin | Description |
| :--- | :--- | :--- | :--- |
| **DHT22 (AM2302)** | Digital 1-Wire | `GPIO 4` (D4) | Ambient Air Temperature & Relative Humidity (Pullup 4.7kΩ). |
| **Capacitive Soil Probe** | Analog Voltage | `GPIO 34` (ADC1_CH6) | Corrosion-free capacitive soil moisture probe (3.3V). |
| **DS18B20 Waterproof** | OneWire Bus | `GPIO 5` (D5) | Subsurface Root-Zone Soil Temperature (Pullup 4.7kΩ). |
| **LDR / Photocell** | Analog Voltage | `GPIO 35` (ADC1_CH7) | Ambient Light Intensity / Canopy Solar Irradiance. |
| **Rain Gauge Module** | Analog / Digital | `GPIO 32` (ADC1_CH4) | Tipping bucket or droplet detection sensor. |
| **5V Relay Module** | Digital Output | `GPIO 18` (D18) | 12V DC Solenoid Drip Irrigation Water Valve. |
| **Status LED** | Digital Output | `GPIO 2` | On-board indicator for WiFi and telemetry heartbeat. |

### Flashing Instructions:
1. Open Arduino IDE.
2. Install the **ESP32 Board Package** via Boards Manager.
3. Install required libraries: `DHT sensor library`, `DallasTemperature`, and `OneWire`.
4. Open `esp32/agrisense_esp32.ino`.
5. Update `WIFI_SSID`, `WIFI_PASSWORD`, and `SERVER_URL` to match your local network IP (e.g., `http://192.168.1.100:5001/api/sensors/readings`).
6. Select board **ESP32 Dev Module** and upload.

---

## 👨‍🎓 9. Practical Examination Demonstration Guide

During evaluation, follow this structured demonstration flow:

1. **Sign-In:** Log in using `admin` / `Admin@123`.
2. **Dashboard Review:** Highlight the 6 primary telemetry cards, the historical trend lines, and the root-zone soil health assessment.
3. **Simulation vs. Hardware Verification:**
   - Note the amber `SIMULATION MODE` indicator.
   - Click **Switch** in the header to demonstrate switching to `HARDWARE MODE`.
   - Point out that the system accurately differentiates telemetry origins and does not falsely claim hardware is attached.
4. **Hardware Ingest Tester:**
   - Navigate to **Sensor Monitoring**.
   - Scroll down to the **Live Hardware Telemetry Ingest Tester**.
   - Transmit a custom reading (e.g. Soil Moisture = `18.5%`).
   - Observe that the reading updates instantly in SQLite and triggers a **Critical Soil Moisture Depletion** alert.
5. **Smart Irrigation Demo:**
   - Navigate to **Smart Irrigation**.
   - Show the rule-based recommendation (`Immediate Irrigation Required`).
   - Click **Start Pump** to demonstrate software actuation simulation and watch water volumetric tracking begin.
   - Click **Stop Pump** to observe the completed cycle recorded in the irrigation history log.
6. **Alert Center:**
   - Navigate to **Alerts & Incidents**.
   - Filter by **Critical** and acknowledge the alert.
7. **Analytics & CSV Download:**
   - Navigate to **Analytics & Reports**.
   - Switch between **Last 24 Hours** and **Last 7 Days**.
   - Click **Export SQLite CSV** to download the complete database log with Date/Time, Sensor Name, Value, Unit, and Data Source.
8. **System Diagnostics:**
   - Navigate to **System Settings**.
   - Display SQLite database size (in KB), total telemetry rows, active devices, and uptime.

---

## 📜 10. License

Developed for academic and research evaluation. Open-source under the MIT License.

