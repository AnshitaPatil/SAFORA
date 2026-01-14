# auth_helpers.py
from functools import wraps
from flask import request, jsonify, g
from firebase_admin import auth
import firebase_utils  # initialize firebase

def verify_firebase_token(id_token):
    try:
        decoded = auth.verify_id_token(id_token)
        return decoded
    except Exception:
        return None

def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        auth_header = request.headers.get('Authorization', None)
        if not auth_header:
            return jsonify({"error": "Authorization header missing"}), 401
        parts = auth_header.split()
        if parts[0].lower() != 'bearer' or len(parts) != 2:
            return jsonify({"error": "Invalid Authorization header"}), 401
        token = parts[1]
        decoded = verify_firebase_token(token)
        if not decoded:
            return jsonify({"error": "Invalid or expired token"}), 401
        g.user = decoded  # contains uid, email, etc.
        return f(*args, **kwargs)
    return decorated
