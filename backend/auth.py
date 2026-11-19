import functools
from flask import request, jsonify, g
from itsdangerous import URLSafeTimedSerializer, SignatureExpired, BadTimeSignature
from werkzeug.security import generate_password_hash, check_password_hash
from database import get_db_connection

SECRET_KEY = "agrisense_super_secret_college_evaluation_key_2026"
serializer = URLSafeTimedSerializer(SECRET_KEY)
TOKEN_MAX_AGE = 86400 * 7 # 7 days

def generate_auth_token(user_id, username, role):
    return serializer.dumps({
        'user_id': user_id,
        'username': username,
        'role': role
    })

def verify_auth_token(token):
    try:
        data = serializer.loads(token, max_age=TOKEN_MAX_AGE)
        return data
    except (SignatureExpired, BadTimeSignature, Exception):
        return None

def login_required(f):
    @functools.wraps(f)
    def decorated_function(*args, **kwargs):
        auth_header = request.headers.get('Authorization', '')
        token = None
        if auth_header.startswith('Bearer '):
            token = auth_header.split(' ', 1)[1]
        elif 'session_token' in request.cookies:
            token = request.cookies.get('session_token')

        if not token:
            return jsonify({'error': 'Authentication required. Missing Authorization token.'}), 401

        payload = verify_auth_token(token)
        if not payload:
            return jsonify({'error': 'Invalid or expired session. Please log in again.'}), 401

        g.current_user = payload
        return f(*args, **kwargs)
    return decorated_function

def admin_required(f):
    @functools.wraps(f)
    def decorated_function(*args, **kwargs):
        auth_header = request.headers.get('Authorization', '')
        token = None
        if auth_header.startswith('Bearer '):
            token = auth_header.split(' ', 1)[1]
        elif 'session_token' in request.cookies:
            token = request.cookies.get('session_token')

        if not token:
            return jsonify({'error': 'Authentication required.'}), 401

        payload = verify_auth_token(token)
        if not payload or payload.get('role') != 'admin':
            return jsonify({'error': 'Administrative privileges required.'}), 403

        g.current_user = payload
        return f(*args, **kwargs)
    return decorated_function

