#!/usr/bin/env python3
"""
AgriSense CLI & Server Runner
Enables standard commands like 'python3 manage.py runserver'
"""
import sys
import os

# Ensure backend directory is in sys.path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app import create_app

def main():
    args = sys.argv[1:]
    command = args[0] if args else "runserver"

    if command in ("runserver", "run"):
        port = 5001
        # Check if port was passed, e.g. runserver 5001 or runserver 8000
        if len(args) > 1:
            try:
                # Handle syntax like 'runserver 8000' or 'runserver 127.0.0.1:8000'
                port_str = args[1].split(":")[-1]
                port = int(port_str)
            except ValueError:
                port = 5001

        app = create_app()
        print(f"\n==================================================================")
        print(f"  🌱 AgriSense Backend Telemetry & Ingestion Server Online")
        print(f"  📡 API URL: http://localhost:{port}/api")
        print(f"  🩺 Health Check: http://localhost:{port}/api/health")
        print(f"==================================================================\n")
        app.run(host="0.0.0.0", port=port, debug=False, use_reloader=False)

    elif command in ("initdb", "init_db"):
        from database import init_db, seed_initial_data
        init_db()
        seed_initial_data()
        print("Database initialized and seeded.")

    elif command in ("test", "tests"):
        import unittest
        loader = unittest.TestLoader()
        start_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "tests")
        suite = loader.discover(start_dir)
        runner = unittest.TextTestRunner()
        runner.run(suite)

    else:
        print(f"Unknown command: '{command}'")
        print("Available commands:")
        print("  python3 manage.py runserver [port]   - Start the backend server (default: 5001)")
        print("  python3 manage.py initdb             - Initialize & seed SQLite database")
        print("  python3 manage.py test               - Run the automated test suite")

if __name__ == "__main__":
    main()

