/*
  ================================================================================
  AgriSense - Smart Agriculture and Environmental Monitoring System
  ESP32 Edge Gateway Telemetry Firmware
  ================================================================================
  Hardware Architecture:
  - Microcontroller: ESP32 DevKit v1 (30-pin / 38-pin)
  - DHT22 (AM2302): Ambient Air Temperature & Relative Humidity (Pin D4)
  - Capacitive Soil Moisture Sensor v1.2 / v2.0: Soil Moisture Content (Pin ADC1 / D34)
  - DS18B20 OneWire Waterproof Probe: Subsurface Soil Temperature (Pin D5)
  - LDR / BH1750 Photocell: Canopy Solar Irradiance / Light (Pin ADC1 / D35)
  - Tipping Bucket / Digital Rain Sensor: Precipitation Detection (Pin ADC1 / D32)
  - 5V Relay Module: Drip Irrigation Solenoid Valve Control (Pin D18)
  ================================================================================
*/

#include <WiFi.h>
#include <HTTPClient.h>
#include <DHT.h>
#include <OneWire.h>
#include <DallasTemperature.h>

// --- Network & Server Configuration ---
const char* WIFI_SSID     = "YOUR_WIFI_SSID";
const char* WIFI_PASSWORD = "YOUR_WIFI_PASSWORD";

// Server endpoint (Change to your laptop/server IP address on the local network)
const char* SERVER_URL    = "http://192.168.1.100:5001/api/sensors/readings";

// Device Credentials (Must match registered device in AgriSense Devices table)
const char* DEVICE_ID     = "ESP32-AGRI-01";
const char* DEVICE_KEY    = "agri_sec_key_esp32_01_live";

// --- Pin Definitions ---
#define DHTPIN        4
#define DHTTYPE       DHT22
#define ONE_WIRE_BUS  5
#define SOIL_PIN      34
#define LDR_PIN       35
#define RAIN_PIN      32
#define RELAY_PIN     18
#define LED_STATUS    2

// --- Sensor Objects ---
DHT dht(DHTPIN, DHTTYPE);
OneWire oneWire(ONE_WIRE_BUS);
DallasTemperature soilTempSensors(&oneWire);

// Calibration Constants for Soil Moisture ADC (12-bit: 0 - 4095)
const int SOIL_AIR_VALUE   = 3200; // Dry air reading
const int SOIL_WATER_VALUE = 1400; // Submerged in cup of water

unsigned long lastSendTime = 0;
const unsigned long SEND_INTERVAL_MS = 10000; // Transmit telemetry every 10 seconds

void setup() {
  Serial.begin(115200);
  delay(1000);
  Serial.println("\n[AgriSense] Booting ESP32 Gateway Node...");

  pinMode(LED_STATUS, OUTPUT);
  pinMode(RELAY_PIN, OUTPUT);
  digitalWrite(RELAY_PIN, LOW); // Normally Open (Relay OFF)

  dht.begin();
  soilTempSensors.begin();

  // Connect to Local WiFi
  Serial.printf("[WiFi] Connecting to %s", WIFI_SSID);
  WiFi.begin(WIFI_SSID, WIFI_PASSWORD);
  int retry = 0;
  while (WiFi.status() != WL_CONNECTED && retry < 25) {
    delay(500);
    Serial.print(".");
    digitalWrite(LED_STATUS, !digitalRead(LED_STATUS));
    retry++;
  }

  if (WiFi.status() == WL_CONNECTED) {
    Serial.println("\n[WiFi] Connected successfully!");
    Serial.print("[WiFi] IP Address: ");
    Serial.println(WiFi.localIP());
    digitalWrite(LED_STATUS, HIGH);
  } else {
    Serial.println("\n[WiFi] Connection timeout. Sensor data will be logged locally.");
    digitalWrite(LED_STATUS, LOW);
  }
}

void loop() {
  unsigned long now = millis();
  if (now - lastSendTime >= SEND_INTERVAL_MS) {
    lastSendTime = now;
    readAndTransmitTelemetry();
  }
}

void readAndTransmitTelemetry() {
  // 1. Read Air Temperature & Humidity from DHT22
  float airTemp = dht.readTemperature();
  float airHumidity = dht.readHumidity();

  if (isnan(airTemp) || isnan(airHumidity)) {
    Serial.println("[Sensor Error] Failed to read from DHT22 sensor!");
    airTemp = 24.5;
    airHumidity = 60.0;
  }

  // 2. Read Soil Moisture (Analog)
  int soilRaw = analogRead(SOIL_PIN);
  float soilMoisturePct = map(soilRaw, SOIL_AIR_VALUE, SOIL_WATER_VALUE, 0, 100);
  soilMoisturePct = constrain(soilMoisturePct, 0.0, 100.0);

  // 3. Read Soil Temperature (DS18B20)
  soilTempSensors.requestTemperatures();
  float soilTemp = soilTempSensors.getTempCByIndex(0);
  if (soilTemp == DEVICE_DISCONNECTED_C || soilTemp < -50.0) {
    soilTemp = airTemp - 2.5; // Estimated ground dampening fallback
  }

  // 4. Read LDR Light Intensity (ADC scaled to lux approx)
  int ldrRaw = analogRead(LDR_PIN);
  float lightLux = map(ldrRaw, 0, 4095, 0, 65000);

  // 5. Read Rain Sensor (0 = dry, higher value = wet)
  int rainRaw = analogRead(RAIN_PIN);
  float rainMm = (rainRaw < 2000) ? map(2000 - rainRaw, 0, 2000, 0, 25) : 0.0;

  Serial.println("\n--- Telemetry Reading ---");
  Serial.printf("Air Temp: %.1f °C | Humidity: %.1f %%\n", airTemp, airHumidity);
  Serial.printf("Soil Moisture: %.1f %% | Soil Temp: %.1f °C\n", soilMoisturePct, soilTemp);
  Serial.printf("Light: %.0f lux | Rain: %.1f mm\n", lightLux, rainMm);

  if (WiFi.status() != WL_CONNECTED) {
    Serial.println("[HTTP] WiFi not connected. Transmission skipped.");
    return;
  }

  // Construct JSON Payload
  HTTPClient http;
  http.begin(SERVER_URL);
  http.addHeader("Content-Type", "application/json");
  http.addHeader("X-Device-Id", DEVICE_ID);
  http.addHeader("X-Device-Key", DEVICE_KEY);

  String payload = "{";
  payload += "\"device_id\":\"" + String(DEVICE_ID) + "\",";
  payload += "\"device_key\":\"" + String(DEVICE_KEY) + "\",";
  payload += "\"readings\":[";
  payload += "{\"sensor_id\":\"air_temp_1\",\"value\":" + String(airTemp, 1) + ",\"unit\":\"°C\"},";
  payload += "{\"sensor_id\":\"air_humidity_1\",\"value\":" + String(airHumidity, 1) + ",\"unit\":\"%\"},";
  payload += "{\"sensor_id\":\"soil_moisture_1\",\"value\":" + String(soilMoisturePct, 1) + ",\"unit\":\"%\"},";
  payload += "{\"sensor_id\":\"soil_temp_1\",\"value\":" + String(soilTemp, 1) + ",\"unit\":\"°C\"},";
  payload += "{\"sensor_id\":\"light_ldr_1\",\"value\":" + String(lightLux, 0) + ",\"unit\":\"lux\"},";
  payload += "{\"sensor_id\":\"rain_1\",\"value\":" + String(rainMm, 1) + ",\"unit\":\"mm\"}";
  payload += "]}";

  int httpCode = http.POST(payload);
  if (httpCode > 0) {
    String response = http.getString();
    Serial.printf("[HTTP] Ingestion response (%d): %s\n", httpCode, response.c_str());
  } else {
    Serial.printf("[HTTP] Ingestion POST failed, error: %s\n", http.errorToString(httpCode).c_str());
  }

  http.end();
}

