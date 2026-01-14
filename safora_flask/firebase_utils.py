# firebase_utils.py
import os
import firebase_admin
from firebase_admin import credentials, auth

KEY_PATH = os.getenv("FIREBASE_SERVICE_ACCOUNT") or "serviceAccountKey.json"

if not firebase_admin._apps:
    cred = credentials.Certificate(KEY_PATH)
    firebase_admin.initialize_app(cred)
