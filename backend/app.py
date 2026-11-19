import os
from flask import Flask, jsonify
from flask_cors import CORS
from database import init_db, seed_initial_data, get_db_connection
from simulation import simulator

from routes.auth_routes import auth_bp
from routes.dashboard_routes import dashboard_bp
from routes.sensor_routes import sensor_bp
from routes.device_routes import device_bp
from routes.irrigation_routes import irrigation_bp
from routes.alert_routes import alert_bp
from routes.analytics_routes import analytics_bp
from routes.export_routes import export_bp
from routes.weather_routes import weather_bp
from routes.settings_routes import settings_bp

def create_app():
    app = Flask(__name__)
    app.config['SECRET_KEY'] = 'agrisense_production_secret_key_college_eval_2026'

    # Enable CORS for React frontend on common local development ports
    CORS(app, resources={r"/api/*": {"origins": "*"}}, supports_credentials=True)

    # Initialize SQLite database and seed initial admin, devices, sensors
    init_db()
    seed_initial_data()

    # Register blueprints
    app.register_blueprint(auth_bp)
    app.register_blueprint(dashboard_bp)
    app.register_blueprint(sensor_bp)
    app.register_blueprint(device_bp)
    app.register_blueprint(irrigation_bp)
    app.register_blueprint(alert_bp)
    app.register_blueprint(analytics_bp)
    app.register_blueprint(export_bp)
    app.register_blueprint(weather_bp)
    app.register_blueprint(settings_bp)

    @app.route('/api/health', methods=['GET'])
    def health_check():
        return jsonify({
            'status': 'healthy',
            'application': 'AgriSense - Smart Agriculture and Environmental Monitoring System',
            'version': '1.0.0',
            'simulation_running': simulator.is_running()
        }), 200

    @app.errorhandler(404)
    def not_found(e):
        return jsonify({'error': 'Resource not found', 'path': str(e)}), 404

    @app.errorhandler(500)
    def internal_error(e):
        return jsonify({'error': 'Internal server error', 'details': str(e)}), 500

    # Auto-start simulation service if simulation_mode is enabled
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("SELECT value FROM system_settings WHERE key = 'simulation_mode'")
        row = cur.fetchone()
        if row and row['value'].lower() == 'true':
            simulator.start()
        conn.close()
    except Exception as e:
        print(f"Warning: Could not check simulation mode at startup: {e}")

    return app

if __name__ == '__main__':
    app = create_app()
    port = int(os.environ.get('PORT', 5001))
    print(f"\n==================================================================")
    print(f"  🌱 AgriSense Backend Telemetry & Ingestion Server Online")
    print(f"  📡 API URL: http://localhost:{port}/api")
    print(f"  🩺 Health Check: http://localhost:{port}/api/health")
    print(f"==================================================================\n")
    app.run(host='0.0.0.0', port=port, debug=False, use_reloader=False)

