from flask import Blueprint, jsonify
from weather_service import get_weather_forecast
from auth import login_required

weather_bp = Blueprint('weather', __name__, url_prefix='/api/weather')

@weather_bp.route('', methods=['GET'])
@login_required
def get_weather():
    data = get_weather_forecast()
    return jsonify(data), 200

