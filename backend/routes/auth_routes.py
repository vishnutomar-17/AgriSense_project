from flask import Blueprint, request, jsonify, g
from werkzeug.security import generate_password_hash, check_password_hash
from database import get_db_connection
from auth import generate_auth_token, login_required

auth_bp = Blueprint('auth', __name__, url_prefix='/api/auth')

@auth_bp.route('/login', methods=['POST'])
def login():
    data = request.get_json() or {}
    username = data.get('username', '').strip()
    password = data.get('password', '')

    if not username or not password:
        return jsonify({'error': 'Username and password are required.'}), 400

    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT id, username, email, password_hash, role FROM users WHERE username = ? OR email = ?", (username, username))
    user = cursor.fetchone()
    conn.close()

    if not user or not check_password_hash(user['password_hash'], password):
        return jsonify({'error': 'Invalid username or password.'}), 401

    token = generate_auth_token(user['id'], user['username'], user['role'])

    return jsonify({
        'message': 'Login successful.',
        'token': token,
        'user': {
            'id': user['id'],
            'username': user['username'],
            'email': user['email'],
            'role': user['role']
        }
    }), 200

@auth_bp.route('/register', methods=['POST'])
def register():
    data = request.get_json() or {}
    username = data.get('username', '').strip()
    email = data.get('email', '').strip()
    password = data.get('password', '')

    if not username or not email or not password:
        return jsonify({'error': 'Username, email, and password are required.'}), 400

    if len(password) < 6:
        return jsonify({'error': 'Password must be at least 6 characters long.'}), 400

    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("SELECT id FROM users WHERE username = ? OR email = ?", (username, email))
    if cursor.fetchone():
        conn.close()
        return jsonify({'error': 'A user with this username or email already exists.'}), 409

    hashed = generate_password_hash(password)
    cursor.execute(
        "INSERT INTO users (username, email, password_hash, role) VALUES (?, ?, ?, 'admin')",
        (username, email, hashed)
    )
    conn.commit()
    user_id = cursor.lastrowid
    conn.close()

    token = generate_auth_token(user_id, username, 'admin')

    return jsonify({
        'message': 'Registration successful.',
        'token': token,
        'user': {
            'id': user_id,
            'username': username,
            'email': email,
            'role': 'admin'
        }
    }), 201

@auth_bp.route('/me', methods=['GET'])
@login_required
def me():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT id, username, email, role, created_at FROM users WHERE id = ?", (g.current_user['user_id'],))
    user = cursor.fetchone()
    conn.close()

    if not user:
        return jsonify({'error': 'User not found.'}), 404

    return jsonify({
        'user': dict(user)
    }), 200

@auth_bp.route('/logout', methods=['POST'])
def logout():
    return jsonify({'message': 'Logged out successfully.'}), 200

