# auth_routes.py
from flask import Blueprint, request, jsonify, g
from auth_db import get_conn, init_db
from auth_helpers import login_required
import auth_db

bp = Blueprint('auth', __name__, url_prefix='/api')

init_db()

@bp.route('/register', methods=['POST'])
def register_user():
    # This endpoint is optional if you register via Firebase in Flutter.
    data = request.json or {}
    email = data.get('email')
    password = data.get('password')
    try:
        # create local user record
        conn = get_conn()
        conn.execute("INSERT OR IGNORE INTO users (firebase_uid, email) VALUES (?, ?)", (email, email))
        conn.commit()
        conn.close()
        return jsonify({"message":"Registered", "uid": email}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 400

@bp.route('/login', methods=['POST'])
def login_user():
    data = request.json or {}
    email = data.get('email')
    password = data.get('password')
    try:
        # For now, we'll just verify the user exists in our local database
        # In a production app, you would use Firebase Authentication
        conn = get_conn()
        cur = conn.execute("SELECT * FROM users WHERE email = ?", (email,))
        user = cur.fetchone()
        conn.close()
        
        if user:
            return jsonify({"message": "Login successful", "uid": user['firebase_uid'], "email": user['email']}), 200
        else:
            return jsonify({"error": "Invalid credentials"}), 401
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@bp.route('/forgot-password', methods=['POST'])
def forgot_password():
    data = request.json or {}
    email = data.get('email')
    try:
        # In a production app, you would send a password reset email
        # For now, we'll just return a success message
        return jsonify({"message": "Password reset email sent"}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@bp.route('/verify_token', methods=['POST'])
def verify_token():
    data = request.json or {}
    id_token = data.get('idToken')
    try:
        # For now, we'll just use the id_token as the uid
        # In a production app, you would verify the Firebase token
        uid = id_token
        email = data.get('email', '')
        # ensure user exists in local DB
        conn = get_conn()
        cur = conn.execute("SELECT * FROM users WHERE firebase_uid = ?", (uid,))
        if cur.fetchone() is None:
            conn.execute("INSERT INTO users (firebase_uid, email) VALUES (?, ?)", (uid, email))
            conn.commit()
        conn.close()
        return jsonify({"uid": uid, "email": email}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 401

# Contacts CRUD (protected)
@bp.route('/contacts', methods=['GET'])
@login_required
def list_contacts():
    uid = g.user['uid']
    conn = get_conn()
    rows = conn.execute("SELECT id, name, phone FROM contacts WHERE firebase_uid = ?", (uid,)).fetchall()
    conn.close()
    return jsonify([dict(r) for r in rows])

@bp.route('/contacts', methods=['POST'])
@login_required
def add_contact():
    uid = g.user['uid']
    data = request.json or {}
    name = data.get('name')
    phone = data.get('phone')
    if not phone:
        return jsonify({"error":"phone required"}), 400
    conn = get_conn()
    try:
        conn.execute("INSERT INTO contacts (firebase_uid, name, phone) VALUES (?, ?, ?)", (uid, name, phone))
        conn.commit()
        return jsonify({"ok": True}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 400
    finally:
        conn.close()

@bp.route('/contacts/<int:cid>', methods=['DELETE'])
@login_required
def delete_contact(cid):
    uid = g.user['uid']
    conn = get_conn()
    conn.execute("DELETE FROM contacts WHERE id = ? AND firebase_uid = ?", (cid, uid))
    conn.commit()
    conn.close()
    return jsonify({"ok": True}), 200

@bp.route('/trigger_alert', methods=['POST'])
def trigger_alert():
    try:
        data = request.json or {}
        firebase_uid = data.get('firebase_uid')
        
        # For now, we'll just return a success response
        # In a production app, you would trigger the alert logic here
        return jsonify({
            "success": True,
            "message": "Alert triggered successfully"
        }), 200
    except Exception as e:
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500
