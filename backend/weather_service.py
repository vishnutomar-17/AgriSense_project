import requests
import datetime
from database import get_db_connection

# Cache weather data in memory to avoid redundant external network calls
_weather_cache = {
    "timestamp": None,
    "data": None
}

WEATHER_CODE_MAP = {
    0: ("Clear sky", "Sun"),
    1: ("Mainly clear", "SunCloud"),
    2: ("Partly cloudy", "CloudSun"),
    3: ("Overcast", "Cloud"),
    45: ("Foggy", "CloudFog"),
    48: ("Depositing rime fog", "CloudFog"),
    51: ("Light drizzle", "CloudDrizzle"),
    53: ("Moderate drizzle", "CloudDrizzle"),
    55: ("Dense drizzle", "CloudRain"),
    61: ("Slight rain", "CloudRain"),
    63: ("Moderate rain", "CloudRain"),
    65: ("Heavy rain", "CloudRainHeavy"),
    71: ("Slight snow", "Snowflake"),
    80: ("Rain showers", "CloudRain"),
    95: ("Thunderstorm", "CloudLightning")
}

def get_weather_forecast():
    global _weather_cache

    # Check cache (valid for 10 minutes)
    now = datetime.datetime.now()
    if _weather_cache["timestamp"] and _weather_cache["data"]:
        elapsed = (now - _weather_cache["timestamp"]).total_seconds()
        if elapsed < 600:
            return _weather_cache["data"]

    # Get farm coordinates from system settings
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT key, value FROM system_settings WHERE key IN ('farm_latitude', 'farm_longitude', 'farm_location_name')")
    settings = {row['key']: row['value'] for row in cursor.fetchall()}
    conn.close()

    lat = float(settings.get('farm_latitude', 28.6139))
    lon = float(settings.get('farm_longitude', 77.2090))
    location_name = settings.get('farm_location_name', 'AgriSense Demonstration Farm')

    url = f"https://api.open-meteo.com/v1/forecast?latitude={lat}&longitude={lon}&current=temperature_2m,relative_humidity_2m,apparent_temperature,precipitation,weather_code,wind_speed_10m&hourly=temperature_2m,precipitation_probability&daily=weather_code,temperature_2m_max,temperature_2m_min,precipitation_sum&timezone=auto"

    try:
        resp = requests.get(url, timeout=4.0)
        if resp.status_code == 200:
            raw = resp.json()
            curr = raw.get("current", {})
            w_code = curr.get("weather_code", 0)
            condition_text, icon_name = WEATHER_CODE_MAP.get(w_code, ("Fair", "Sun"))

            # Build structured response
            daily = raw.get("daily", {})
            forecast_days = []
            if daily and "time" in daily:
                for i in range(min(5, len(daily["time"]))):
                    code = daily["weather_code"][i] if "weather_code" in daily else 0
                    c_text, c_icon = WEATHER_CODE_MAP.get(code, ("Clear", "Sun"))
                    forecast_days.append({
                        "date": daily["time"][i],
                        "max_temp": daily.get("temperature_2m_max", [None])[i],
                        "min_temp": daily.get("temperature_2m_min", [None])[i],
                        "precipitation_sum": daily.get("precipitation_sum", [0])[i],
                        "condition": c_text,
                        "icon": c_icon
                    })

            result = {
                "status": "online",
                "location": location_name,
                "coordinates": {"lat": lat, "lon": lon},
                "temperature": curr.get("temperature_2m"),
                "apparent_temperature": curr.get("apparent_temperature"),
                "humidity": curr.get("relative_humidity_2m"),
                "precipitation": curr.get("precipitation", 0.0),
                "wind_speed": curr.get("wind_speed_10m"),
                "weather_code": w_code,
                "condition": condition_text,
                "icon": icon_name,
                "forecast": forecast_days,
                "last_synced": now.strftime('%Y-%m-%d %H:%M:%S'),
                "provider": "Open-Meteo Public Meteorological API"
            }
            _weather_cache["timestamp"] = now
            _weather_cache["data"] = result
            return result
        else:
            return {
                "status": "unavailable",
                "location": location_name,
                "message": f"Open-Meteo returned HTTP {resp.status_code}",
                "last_synced": None
            }
    except Exception as e:
        # Graceful fallback when network is unavailable or offline
        return {
            "status": "unavailable",
            "location": location_name,
            "message": f"External weather network unreachable ({str(e)})",
            "last_synced": None
        }

