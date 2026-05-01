import os
import wave
import pyaudio
import speech_recognition as sr
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
from geocoder import ip
import joblib
import numpy as np
import librosa
from librosa.feature import spectral_contrast
import logging
import time
from flask import Flask, render_template, request, jsonify, redirect, url_for
from flask_cors import CORS
import threading
from threading import Event, Thread, Lock
from langchain_ollama import ChatOllama
import re
import pandas as pd
from math import radians, sin, cos, sqrt, atan2
from Main import upload_to_drive
import geocoder
import json
from flask import Flask, request, jsonify
import firebase_admin
from firebase_admin import credentials, firestore
import uuid
from supabase import create_client
from dotenv import load_dotenv
from flask import make_response

load_dotenv()

# ================= SUPABASE SETUP =================
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_SERVICE_ROLE_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY")
SUPABASE_BUCKET = os.getenv("SUPABASE_BUCKET")

if not SUPABASE_URL or not SUPABASE_SERVICE_ROLE_KEY or not SUPABASE_BUCKET:
    raise RuntimeError("❌ Supabase environment variables not set")

supabase = create_client(SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY)
# =================================================

cred = credentials.Certificate("serviceAccountKey.json")
firebase_admin.initialize_app(cred)
db = firestore.client()

current_alert_id = None
current_firebase_uid = None
pending_video_link = None


def load_emergency_contacts(firebase_uid=None):
    if not firebase_uid:
        return {"phone_numbers": [], "contact_names": []}
    try:
        doc = db.collection("users").document(firebase_uid).get()
        if not doc.exists:
            return {"phone_numbers": [], "contact_names": []}
        contacts = doc.to_dict().get("emergencyContacts", [])
        phone_numbers = []
        contact_names = []
        for c in contacts:
            phone = c.get("phone")
            name = c.get("name", "Emergency Contact")
            if phone:
                phone_numbers.append(phone)
                contact_names.append(name)
        return {"phone_numbers": phone_numbers, "contact_names": contact_names}
    except Exception as e:
        logging.error(f"❌ Firestore contact load failed: {e}")
        return {"phone_numbers": [], "contact_names": []}


# Initialize Flask app
app = Flask(__name__, static_folder='static', template_folder='templates')
CORS(app, resources={r"/*": {"origins": "*"}})

try:
    model_chat = ChatOllama(model="llama3.2:1b", base_url="http://localhost:11434/")
except Exception as e:
    print(f"Warning: Could not initialize ChatOllama model: {e}")
    model_chat = None

from dotenv import load_dotenv
import os
from notification_service import load_emergency_contacts
from auth_helpers import verify_firebase_token, login_required
from sensor_detection import SensorDetector
import sqlite3
from auth_routes import bp as auth_bp

load_dotenv()

from auth_db import init_db
init_db()

app.register_blueprint(auth_bp)

try:
    model_audio = joblib.load('models/final_random_forest_model.pkl')
    logging.info("Audio model loaded successfully")
except Exception as e:
    logging.error(f"Error loading audio model: {e}")
    model_audio = None


def load_crime_data():
    try:
        csv_files = [f for f in os.listdir('datasets') if f.endswith('.csv') and 'crime' in f.lower()]
        if not csv_files:
            return pd.DataFrame()
        df = pd.read_csv(f'datasets/{csv_files[0]}')
        return df
    except Exception as e:
        logging.error(f"Error loading crime data: {e}")
        return pd.DataFrame()


def get_crime_data_for_map():
    try:
        df = load_crime_data()
        if df.empty:
            return []
        crime_data = []
        intensity_colors = {'High': 'red', 'Medium': 'yellow', 'Low': 'green'}
        for _, row in df.iterrows():
            crime_data.append({
                'lat': row['Latitude'],
                'lng': row['Longitude'],
                'type': row['Incident_Type'],
                'date': row['Date'],
                'time': row['Time'],
                'intensity': row['Intensity'],
                'color': intensity_colors.get(str(row['Intensity']), 'green')
            })
        return crime_data
    except Exception as e:
        print(f"Warning: Could not load crime data: {e}")
        return []


crime_data = load_crime_data()
KEYWORD_FILE = 'keyword.json'


def load_keyword():
    try:
        if os.path.exists(KEYWORD_FILE):
            with open(KEYWORD_FILE, 'r') as f:
                data = json.load(f)
                return data.get('keyword', 'help')
        return 'help'
    except:
        return 'help'


def save_keyword(keyword):
    with open(KEYWORD_FILE, 'w') as f:
        json.dump({'keyword': keyword}, f)


def get_firebase_uid_from_request():
    auth_header = request.headers.get('Authorization')
    if not auth_header:
        return None
    try:
        parts = auth_header.split()
        if len(parts) == 2 and parts[0].lower() == 'bearer':
            decoded = verify_firebase_token(parts[1])
            return decoded.get('uid') if decoded else None
    except Exception:
        return None
    return None


@app.route('/add_emergency_contact', methods=['POST'])
def add_emergency_contact():
    firebase_uid = get_firebase_uid_from_request()
    if not firebase_uid:
        return jsonify({"success": False, "error": "Unauthorized"}), 401
    data = request.get_json(force=True)
    name = data.get("name")
    phone = data.get("phone")
    if not name or not phone:
        return jsonify({"success": False, "error": "Invalid data"}), 400
    doc_ref = db.collection("users").document(firebase_uid)
    doc = doc_ref.get()
    contacts = []
    if doc.exists:
        contacts = doc.to_dict().get("emergencyContacts", [])
    for c in contacts:
        if c.get("phone") == phone:
            return jsonify({"success": False, "error": "Contact already exists"}), 409
    new_contact = {"id": str(int(time.time() * 1000)), "name": name, "phone": phone}
    contacts.append(new_contact)
    doc_ref.set({"emergencyContacts": contacts}, merge=True)
    return jsonify({"success": True, "contact": new_contact})


@app.route('/update_keyword', methods=['POST'])
def update_keyword():
    try:
        data = request.get_json()
        keyword = data.get('keyword', 'help').lower()
        save_keyword(keyword)
        return jsonify({'success': True}), 200
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


# PyAudio configuration
FORMAT = pyaudio.paInt16
CHANNELS = 1
RATE = 22050
CHUNK = RATE * 3
SILENCE_THRESHOLD = 0.6
FEATURES_LENGTH = 77

OUTPUT_DIR = 'audio_chunks1'
if not os.path.exists(OUTPUT_DIR):
    os.makedirs(OUTPUT_DIR)

logging.basicConfig(level=logging.INFO)

alert_cancelled = Event()
alert_id_ready = Event()
alert_active = False
alert_payload = {}
alert_lock = Lock()
pending_evidence = {}
pending_evidence_lock = Lock()


def calculate_distance(lat1, lon1, lat2, lon2):
    R = 6371
    lat1, lon1, lat2, lon2 = map(radians, [lat1, lon1, lat2, lon2])
    dlat = lat2 - lat1
    dlon = lon2 - lon1
    a = sin(dlat/2)*2 + cos(lat1) * cos(lat2) * sin(dlon/2)*2
    c = 2 * atan2(sqrt(a), sqrt(1-a))
    return R * c


def check_nearby_crimes(user_lat, user_lon, radius_km=2):
    if crime_data.empty:
        return True, []
    nearby_crimes = []
    for _, crime in crime_data.iterrows():
        distance = calculate_distance(user_lat, user_lon, crime['Latitude'], crime['Longitude'])
        if distance <= radius_km:
            nearby_crimes.append({
                'type': crime['Incident_Type'],
                'distance': round(distance, 2),
                'intensity': crime['Intensity']
            })
    return len(nearby_crimes) == 0, nearby_crimes


def initialize_audio():
    try:
        audio = pyaudio.PyAudio()
        try:
            device_count = audio.get_host_api_info_by_index(0).get('deviceCount', 0)
        except Exception:
            device_count = 1
        if int(device_count) <= 0:
            logging.error("No audio input devices found")
            return False
        with sr.Microphone() as source:
            recognizer = sr.Recognizer()
            recognizer.adjust_for_ambient_noise(source, duration=1)
        logging.info("Audio system initialized successfully")
        return True
    except Exception as e:
        logging.error(f"Failed to initialize audio system: {e}")
        return False


def record_audio(file_path="output.wav", record_seconds=8):
    audio = pyaudio.PyAudio()
    stream = audio.open(format=FORMAT, channels=CHANNELS, rate=RATE, input=True, frames_per_buffer=CHUNK)
    print(f"Recording for {record_seconds} seconds...")
    frames = []
    for _ in range(0, int(RATE / CHUNK * record_seconds)):
        data = stream.read(CHUNK)
        frames.append(data)
    stream.stop_stream()
    stream.close()
    audio.terminate()
    with wave.open(file_path, 'wb') as wf:
        wf.setnchannels(CHANNELS)
        wf.setsampwidth(audio.get_sample_size(FORMAT))
        wf.setframerate(RATE)
        wf.writeframes(b''.join(frames))
    print("Recording finished.")
    return file_path


def extract_features(file_path):
    try:
        audio_np, _ = librosa.load(file_path, sr=RATE, mono=True)
        if np.max(np.abs(audio_np)) < SILENCE_THRESHOLD:
            logging.info("Silence detected, skipping feature extraction.")
            return None
        rms = librosa.feature.rms(y=audio_np)
        mfccs = librosa.feature.mfcc(y=audio_np, sr=RATE, n_mfcc=13)
        spectral_centroid = librosa.feature.spectral_centroid(y=audio_np, sr=RATE)
        spectral_bandwidth = librosa.feature.spectral_bandwidth(y=audio_np, sr=RATE)
        spectral_flatness = librosa.feature.spectral_flatness(y=audio_np)
        zero_crossing_rate = librosa.feature.zero_crossing_rate(y=audio_np)
        chroma = librosa.feature.chroma_stft(y=audio_np, sr=RATE)
        spectral_contrasts = spectral_contrast(y=audio_np, sr=RATE)
        mel_spectrogram = librosa.feature.melspectrogram(y=audio_np, sr=RATE, n_mels=40)
        features = np.concatenate((
            [np.mean(rms), np.mean(spectral_centroid), np.mean(spectral_bandwidth),
             np.mean(spectral_flatness), np.mean(zero_crossing_rate)],
            np.mean(mfccs, axis=1),
            np.mean(chroma, axis=1),
            np.mean(spectral_contrasts, axis=1),
            np.mean(mel_spectrogram, axis=1)
        ))
        if len(features) != FEATURES_LENGTH:
            logging.error(f"Feature length mismatch: Expected {FEATURES_LENGTH}, got {len(features)}")
            return None
        return features
    except Exception as e:
        logging.error(f"Error extracting features: {e}")
        return None


sleep_timer = None
keyword = None
keyword_lock = Lock()
sleep_until = 0
sleep_lock = Lock()

detection_enabled = False
detection_lock = Lock()
audio_thread = None

sensor_detector = SensorDetector()


def announce_sleep_mode():
    wake_time = time.strftime('%H:%M:%S', time.localtime(sleep_until))
    announcement = f"""
    ============================
    SYSTEM ENTERING SLEEP MODE
    Time: {time.strftime('%H:%M:%S')}
    Will wake at: {wake_time}
    Duration: 30 minutes
    ============================
    """
    logging.info(announcement)
    return announcement


def is_system_sleeping():
    global sleep_until
    with sleep_lock:
        return time.time() < sleep_until


def toggle_sleep_mode(is_sleeping):
    global sleep_until
    with sleep_lock:
        if is_sleeping:
            sleep_duration = 30 * 60
            sleep_until = time.time() + sleep_duration
            logging.info("SLEEP MODE ACTIVATED - System will resume in 30 minutes")
        else:
            sleep_until = 0
            logging.info("SLEEP MODE DEACTIVATED - System resuming normal operation")


@app.route("/test_supabase_upload", methods=["GET"])
def test_supabase_upload():
    try:
        url = upload_video_to_supabase(firebase_uid="test_user", alert_id="test_alert", file_path="demo_video.mp4")
        return jsonify({"success": True, "signed_url": url})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@app.route('/sleep_status', methods=['GET'])
def get_sleep_status():
    with sleep_lock:
        is_sleeping = time.time() < sleep_until
        remaining_time = max(0, sleep_until - time.time()) if is_sleeping else 0
        return jsonify({
            "sleeping": is_sleeping,
            "remaining_minutes": round(remaining_time / 60, 1),
            "wake_time": time.strftime('%H:%M:%S', time.localtime(sleep_until)) if is_sleeping else None,
            "status_message": "System is in sleep mode" if is_sleeping else "System is active"
        })


@app.route('/toggle_sleep', methods=['POST'])
def toggle_sleep():
    try:
        data = request.json
        is_sleeping = data.get('sleeping', False) if data else False
        toggle_sleep_mode(is_sleeping)
        return jsonify({"success": True, "sleeping": is_system_sleeping(), "message": "Sleep mode toggled successfully"})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@app.route('/detection_status', methods=['GET'])
def get_detection_status():
    global detection_enabled
    with detection_lock:
        enabled = detection_enabled
    return jsonify({
        "enabled": enabled,
        "status_message": "AI Detection is active" if enabled else "AI Detection is disabled"
    })


@app.route('/toggle_detection', methods=['POST'])
def toggle_detection():
    global detection_enabled, audio_thread
    try:
        data = request.json
        should_enable = data.get('enabled', False) if data else False
        with detection_lock:
            detection_enabled = should_enable
        if should_enable:
            logging.info("AI DETECTION ACTIVATED")
        else:
            logging.info("AI DETECTION DEACTIVATED")
        return jsonify({"success": True, "enabled": detection_enabled, "message": "AI Detection toggled successfully"})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@app.route('/api/sensor_data', methods=['POST'])
def receive_sensor_data():
    global sensor_detector
    try:
        data = request.get_json(force=True)
        accel_x = data.get('accelX', 0.0)
        accel_y = data.get('accelY', 0.0)
        accel_z = data.get('accelZ', 0.0)
        gyro_x = data.get('gyroX', 0.0)
        gyro_y = data.get('gyroY', 0.0)
        gyro_z = data.get('gyroZ', 0.0)
        if accel_x != 0.0 or accel_y != 0.0 or accel_z != 0.0:
            sensor_detector.process_accelerometer(accel_x, accel_y, accel_z)
        if gyro_x != 0.0 or gyro_y != 0.0 or gyro_z != 0.0:
            sensor_detector.process_gyroscope(gyro_x, gyro_y, gyro_z)
        detections = sensor_detector.get_all_detections()
        logging.info(f"📡 Sensor data received: {data}")
        return jsonify({"success": True, "detections": detections}), 200
    except Exception as e:
        logging.error(f"Error processing sensor data: {e}")
        return jsonify({"success": False, "error": str(e)}), 500


@app.route('/api/get_sensor_status', methods=['GET'])
def get_sensor_status():
    global sensor_detector
    detections = sensor_detector.get_all_detections()
    return jsonify({
        "success": True,
        "detections": detections,
        "accelerometer_threat": sensor_detector.get_accelerometer_threat(),
        "gyroscope_threat": sensor_detector.get_gyroscope_threat()
    })


def verify_keyword(text):
    current_keyword = load_keyword().lower()
    return current_keyword in text.lower()


def print_detection_table(window_name, detected):
    logging.info(f"\n{'='*35}")
    logging.info(f"  {window_name}")
    logging.info(f"{'='*35}")
    logging.info(f"  {'Parameter':<15} {'Status':<10}")
    logging.info(f"  {'-'*25}")
    logging.info(f"  {'Keyword':<15} {'✅ TRUE' if detected['keyword'] else '❌ false'}")
    logging.info(f"  {'Scream':<15} {'✅ TRUE' if detected['scream'] else '❌ false'}")
    logging.info(f"  {'Accelerometer':<15} {'✅ TRUE' if detected['accel'] else '❌ false'}")
    logging.info(f"  {'Gyroscope':<15} {'✅ TRUE' if detected['gyro'] else '❌ false'}")
    logging.info(f"  {'-'*25}")
    logging.info(f"  {'Total':<15} {sum(detected.values())}/4")
    logging.info(f"{'='*35}\n")


def two_stage_verification(recognizer, source):
    if is_system_sleeping():
        logging.info("🟡 System is in sleep mode, skipping verification.")
        return False

    global sensor_detector

    detected = {"keyword": False, "scream": False, "accel": False, "gyro": False}
    detected_lock = Lock()
    alert_triggered = Event()
    stop_threads = Event()

    def check_alert():
        while not stop_threads.is_set():
            with detected_lock:
                keyword_true = detected["keyword"]
                others = detected["scream"] or detected["accel"] or detected["gyro"]
                total = sum(detected.values())

            print_detection_table("CURRENT STATE", detected)

            if keyword_true and others:
                logging.info("🚨 Keyword + secondary signal → ALERT!")
                alert_triggered.set()
                return

            if total >= 2:
                logging.info("🚨 2+ signals detected → ALERT!")
                alert_triggered.set()
                return

            time.sleep(1)

    def keyword_thread_fn():
        logging.info("🎙️ Keyword thread started")
        local_recognizer = sr.Recognizer()
        while not stop_threads.is_set() and not alert_triggered.is_set():
            try:
                with sr.Microphone() as mic:
                    local_recognizer.adjust_for_ambient_noise(mic, duration=0.3)
                    audio = local_recognizer.listen(mic, timeout=3, phrase_time_limit=3)
                    text = local_recognizer.recognize_google(audio)
                    logging.info(f"🎙️ Heard: '{text}'")
                    if load_keyword().lower() in text.lower():
                        with detected_lock:
                            detected["keyword"] = True
                        logging.info(f"✅ KEYWORD DETECTED: '{text}'")
            except sr.WaitTimeoutError:
                pass
            except sr.UnknownValueError:
                pass
            except Exception as e:
                logging.error(f"❌ Keyword thread error: {e}")
                time.sleep(1)

    def scream_thread_fn():
        logging.info("😱 Scream thread started")
        while not stop_threads.is_set() and not alert_triggered.is_set():
            try:
                audio_path = record_audio(record_seconds=3)
                if predict_audio(audio_path):
                    with detected_lock:
                        detected["scream"] = True
                    logging.info("✅ SCREAM DETECTED")
            except Exception as e:
                logging.error(f"❌ Scream thread error: {e}")
                time.sleep(1)

    def sensor_thread_fn():
        logging.info("📡 Sensor thread started")
        while not stop_threads.is_set() and not alert_triggered.is_set():
            try:
                if sensor_detector.get_accelerometer_threat():
                    with detected_lock:
                        detected["accel"] = True
                    logging.info("✅ ACCELEROMETER THREAT")
                if sensor_detector.get_gyroscope_threat():
                    with detected_lock:
                        detected["gyro"] = True
                    logging.info("✅ GYROSCOPE THREAT")
                time.sleep(0.5)
            except Exception as e:
                logging.error(f"❌ Sensor thread error: {e}")
                time.sleep(1)

    threads = [
        Thread(target=keyword_thread_fn, daemon=True),
        Thread(target=scream_thread_fn, daemon=True),
        Thread(target=sensor_thread_fn, daemon=True),
        Thread(target=check_alert, daemon=True),
    ]

    for t in threads:
        t.start()

    logging.info("🔍 All detection threads running in parallel...")

    while not alert_triggered.is_set():
        with detection_lock:
            if not detection_enabled:
                logging.info("🛑 Detection disabled — stopping all threads")
                stop_threads.set()
                return False
        time.sleep(0.5)

    stop_threads.set()
    return True


def predict_audio(file_path):
    try:
        features = extract_features(file_path)
        if features is None:
            logging.info("No features extracted from audio - likely silence")
            return False
        if model_audio is None:
            logging.error("Audio model not loaded")
            return False
        prediction = model_audio.predict([features])
        logging.info(f"Audio prediction result: {prediction[0]}")
        return int(prediction[0]) == 1
    except Exception as e:
        logging.error(f"Error in predict_audio: {e}")
        return False


def handle_alert_process(location, map_link, shareable_link, firebase_uid=None):
    global alert_active, alert_payload
    with alert_lock:
        alert_payload = {
            "video": shareable_link,
            "location": location,
            "mapLink": map_link,
            "firebase_uid": firebase_uid,
            "timestamp": time.time()
        }
    alert_active = True
    alert_cancelled.clear()


def ensure_active_alert(firebase_uid):
    global current_alert_id, current_firebase_uid
    if current_alert_id and current_firebase_uid:
        return current_alert_id
    alert_id = str(uuid.uuid4())
    db.collection("alerts").document(alert_id).set({
        "userId": firebase_uid,
        "isActive": True,
        "createdAt": firestore.SERVER_TIMESTAMP,
        "lastUpdated": firestore.SERVER_TIMESTAMP,
        "latestVideoUrl": None,
        "location": {"lat": None, "lng": None}
    })
    current_alert_id = alert_id
    current_firebase_uid = firebase_uid
    logging.info(f"🆕 Alert context created by audio thread: {alert_id}")
    return alert_id


@app.route('/')
def index():
    return render_template('index.html')


@app.route('/health', methods=['GET'])
def health():
    return jsonify({
        "status": "healthy",
        "service": "Safora AI Flask Backend",
        "detection_enabled": detection_enabled
    }), 200


@app.route('/alert')
def alert():
    global alert_active
    alert_active = True
    return render_template('alert.html')


@app.route('/alert_status', methods=['GET'])
def alert_status():
    global alert_active
    return jsonify({"alert_active": alert_active, "show_alert": alert_active})


@app.route('/cancel', methods=['POST'])
def cancel_alert():
    global alert_active
    alert_active = False
    alert_cancelled.set()
    logging.info("Alert cancelled by user")
    return jsonify({"success": True, "message": "Alert cancelled"})


@app.route("/confirm_alert", methods=["POST"])
def confirm_alert():
    global alert_active
    try:
        firebase_uid = None
        auth_header = request.headers.get('Authorization', None)

        if auth_header:
            parts = auth_header.split()
            if len(parts) == 2 and parts[0].lower() == 'bearer':
                decoded = verify_firebase_token(parts[1])
                if decoded:
                    firebase_uid = decoded.get('uid')
                    logging.info(f"👤 User identified for alert: {firebase_uid}")

        if not firebase_uid:
            return jsonify({"success": False, "error": "User not authenticated."}), 401

        if auth_header:
            try:
                parts = auth_header.split()
                if len(parts) == 2 and parts[0].lower() == 'bearer':
                    token = parts[1]
                    decoded = verify_firebase_token(token)
                    if decoded:
                        firebase_uid = decoded.get('uid')
                        global current_firebase_uid
                        current_firebase_uid = firebase_uid
            except Exception as e:
                logging.warning(f"⚠️ Could not get user from token: {e}")

        try:
            g = geocoder.ip('me')
            location = f"{g.latlng[0]},{g.latlng[1]}" if g and g.latlng else "Location unavailable"
        except Exception as e:
            logging.error(f"❌ Failed to get location: {e}")
            location = "Location unavailable"

        map_link = f"https://www.google.com/maps/place/{location}" if location != "Location unavailable" else "Map link unavailable"
        contacts = load_emergency_contacts(firebase_uid=firebase_uid)
        phone_numbers = contacts.get("phone_numbers", [])

        logging.info("🚨 EMERGENCY ALERT TRIGGERED - PREPARING DATA")
        logging.info(f"📍 Location: {location}")
        logging.info(f"📞 Emergency Contacts Found: {len(phone_numbers)}")

        results = {
            "success": True,
            "message": "✅ Alert data prepared.",
            "phoneNumbers": phone_numbers,
            "location": location,
            "mapLink": map_link,
        }

        try:
            return jsonify(results)
        except Exception as e:
            return jsonify({"success": True, "message": "Alert prepared locally.", "data": results}), 200

    except Exception as e:
        logging.error(f"❌ Error in confirm_alert: {str(e)}")
        return jsonify({"message": "Error processing alert.", "success": False, "error": str(e)}), 500


@app.route('/get_crime_data', methods=['GET'])
def get_crime_data():
    return jsonify(get_crime_data_for_map())


@app.route('/emergency')
def emergency():
    return render_template('emergency.html')


@app.route('/hotspot')
def hotspot():
    return render_template('hotspot.html')


@app.route('/news')
def news():
    return render_template('news.html')


@app.route('/chatbot')
def chatbot():
    return render_template('chatbot.html')


@app.route('/get_emergency_contacts', methods=['GET'])
def get_emergency_contacts():
    try:
        firebase_uid = None
        auth_header = request.headers.get('Authorization', None)
        if auth_header:
            try:
                parts = auth_header.split()
                if len(parts) == 2 and parts[0].lower() == 'bearer':
                    decoded = verify_firebase_token(parts[1])
                    if decoded:
                        firebase_uid = decoded.get('uid')
            except Exception as e:
                logging.warning(f"Could not get user from token: {e}")
        contacts = load_emergency_contacts(firebase_uid=firebase_uid)
        return jsonify(contacts)
    except Exception as e:
        logging.error(f"Error getting emergency contacts: {e}")
        return jsonify({"phone_numbers": [], "contact_names": []}), 500


@app.route('/save_emergency_contacts', methods=['POST'])
def save_emergency_contacts():
    try:
        firebase_uid = None
        auth_header = request.headers.get('Authorization')
        if auth_header:
            try:
                parts = auth_header.split()
                if len(parts) == 2 and parts[0].lower() == 'bearer':
                    decoded = verify_firebase_token(parts[1])
                    if decoded:
                        firebase_uid = decoded.get('uid')
            except Exception as e:
                logging.warning(f"⚠️ Token verification failed: {e}")

        if not firebase_uid:
            return jsonify({"success": False, "error": "User not authenticated"}), 401

        data = request.get_json(force=True)
        phone_numbers = data.get("phone_numbers", [])
        contact_names = data.get("contact_names", [])
        emergency_contacts = []
        for name, phone in zip(contact_names, phone_numbers):
            emergency_contacts.append({"id": f"{name}_{phone}", "name": name, "phone": phone})

        db.collection("users").document(firebase_uid).set({"emergencyContacts": emergency_contacts}, merge=True)
        logging.info(f"✅ Saved {len(emergency_contacts)} emergency contacts for {firebase_uid}")
        return jsonify({"success": True})

    except Exception as e:
        logging.error(f"❌ Error saving emergency contacts: {e}")
        return jsonify({"success": False, "error": str(e)}), 500


@app.route('/set_keyword', methods=['POST'])
def set_keyword():
    global keyword
    data = request.json
    with keyword_lock:
        keyword = data.get('keyword') if data else None
    return jsonify({"success": True, "message": "Keyword set successfully"})


@app.route("/generate_response", methods=["POST"])
def generate_response():
    if model_chat is None:
        return jsonify({"error": "Chat model not initialized"}), 500
    input_text = request.json.get("input_text", "") if request.json else ""
    if not input_text:
        return jsonify({"error": "No input text provided"}), 400
    try:
        response = model_chat.invoke(input_text)
        return jsonify({"response": response.content})
    except Exception as e:
        logging.error(f"Error generating response: {e}")
        return jsonify({"error": str(e)}), 500


@app.route('/api/upload_clip', methods=['POST'])
def upload_clip():
    global current_alert_id, current_firebase_uid
    try:
        alert_id = request.form.get('alert_id')
        firebase_uid = request.form.get('firebase_uid')
        clip_index = request.form.get('clip_index', '0')

        if not alert_id or not firebase_uid:
            return jsonify({"success": False, "error": "alert_id and firebase_uid are required"}), 400
        if 'clip' not in request.files:
            return jsonify({"success": False, "error": "No clip file in request"}), 400

        clip_file = request.files['clip']
        file_bytes = clip_file.read()
        object_path = f"{firebase_uid}/{alert_id}_clip{clip_index}.mp4"

        supabase.storage.from_(SUPABASE_BUCKET).upload(object_path, file_bytes, {"content-type": "video/mp4"})
        signed = supabase.storage.from_(SUPABASE_BUCKET).create_signed_url(object_path, 86400)
        clip_url = signed["signedURL"]

        db.collection("alerts").document(alert_id).update({
            "latestVideoUrl": clip_url,
            f"clips.clip{clip_index}": clip_url,
            "videoReady": True,
            "lastUpdated": firestore.SERVER_TIMESTAMP
        })

        logging.info(f"✅ Clip {clip_index} uploaded: {clip_url}")
        return jsonify({"success": True, "clip_index": clip_index, "url": clip_url}), 200

    except Exception as e:
        logging.error(f"❌ upload_clip failed: {e}")
        return jsonify({"success": False, "error": str(e)}), 500


@app.route('/api/trigger_alert', methods=['POST'])
def trigger_alert():
    global alert_active, current_alert_id, current_firebase_uid, pending_video_link
    try:
        data = request.get_json(force=True)
        logging.info(f"🚨 AUTO ALERT RECEIVED FROM FLUTTER: {data}")

        firebase_uid = data.get("firebaseUid") or data.get("firebase_uid")
        if not firebase_uid:
            return jsonify({"success": False, "error": "firebaseUid missing in request"}), 400

        if current_alert_id:
            alert_id = current_alert_id
            logging.info(f"♻️ Reusing audio-thread alert: {alert_id}")
            db.collection("alerts").document(alert_id).update({
                "userId": firebase_uid,
                "lastUpdated": firestore.SERVER_TIMESTAMP,
            })
        else:
            alert_id = str(uuid.uuid4())
            db.collection("alerts").document(alert_id).set({
                "userId": firebase_uid,
                "isActive": True,
                "createdAt": firestore.SERVER_TIMESTAMP,
                "lastUpdated": firestore.SERVER_TIMESTAMP,
                "latestVideoUrl": None,
                "location": {"lat": None, "lng": None}
            })

        current_alert_id = alert_id
        current_firebase_uid = firebase_uid
        alert_id_ready.set()

        logging.info(f"📌 MASTER alert ID set to: {alert_id} — all clips will go here")

        alert_active = True

        if pending_video_link:
            try:
                db.collection("alerts").document(alert_id).update({
                    "latestVideoUrl": pending_video_link,
                    "lastUpdated": firestore.SERVER_TIMESTAMP
                })
                logging.info("🔗 Stored video evidence linked to new alert")
                pending_video_link = None
            except Exception as e:
                logging.error(f"❌ Failed to attach stored video evidence: {e}")

        try:
            g = geocoder.ip('me')
            location = f"{g.latlng[0]},{g.latlng[1]}" if g and g.latlng else "Location unavailable"
        except Exception:
            location = "Location unavailable"

        map_link = f"https://www.google.com/maps/place/{location}" if location != "Location unavailable" else "Map link unavailable"
        base_url = request.url_root.rstrip('/')

        # ✅ Live video page link — sent in SMS 2
        viewer_link = f"{base_url}/live/{alert_id}"

        contacts = load_emergency_contacts(firebase_uid=firebase_uid)
        phone_numbers = contacts.get("phone_numbers", [])

        logging.info("🚨 AUTO EMERGENCY ALERT (NO CONFIRMATION)")
        logging.info(f"📍 Location: {location}")
        logging.info(f"📞 Emergency Contacts Found: {len(phone_numbers)}")
        logging.info(f"DEBUG UID RECEIVED: {firebase_uid}")

        alert_cancelled.set()

        return jsonify({
            "success": True,
            "auto": True,
            "alertId": alert_id,
            "viewerLink": viewer_link,
            "phoneNumbers": phone_numbers,
            "message": "Auto alert created. Send SMS with viewerLink."
        }), 200

    except Exception as e:
        logging.error(f"❌ Error in auto trigger_alert: {e}")
        return jsonify({"success": False, "error": str(e)}), 500


# ✅ Live video page
@app.route('/live/<alert_id>')
def live_video(alert_id):
    return render_template('live_video.html', alert_id=alert_id)


# ✅ Returns all clips in order for history and catchup
@app.route('/api/all_clips/<alert_id>', methods=['GET'])
def all_clips(alert_id):
    try:
        doc = db.collection('alerts').document(alert_id).get()
        if not doc.exists:
            return jsonify({"success": False, "error": "Alert not found"}), 404

        data = doc.to_dict()
        clips_dict = data.get('clips', {})

        sorted_clips = []
        index = 0
        while True:
            key = f"clip{index}"
            if key in clips_dict:
                sorted_clips.append({"index": index, "url": clips_dict[key]})
                index += 1
            else:
                found_next = False
                for skip in range(1, 4):
                    if f"clip{index + skip}" in clips_dict:
                        index += skip
                        found_next = True
                        break
                if not found_next:
                    break

        latest_url = data.get('latestVideoUrl')

        response = make_response(jsonify({
            "success": True,
            "clips": sorted_clips,
            "latestUrl": latest_url,
            "totalClips": len(sorted_clips)
        }))
        response.headers['Cache-Control'] = 'no-store'
        return response, 200

    except Exception as e:
        logging.error(f"❌ all_clips error: {e}")
        return jsonify({"success": False, "error": str(e)}), 500


# ✅ Returns latest clip URL only
@app.route('/api/latest_clip/<alert_id>', methods=['GET'])
def latest_clip(alert_id):
    try:
        doc = db.collection('alerts').document(alert_id).get()
        if not doc.exists:
            return jsonify({"success": False, "error": "Alert not found"}), 404
        data = doc.to_dict()
        url = data.get('latestVideoUrl')
        logging.info(f"📡 latest_clip called — returning URL ending: ...{url[-30:] if url else 'NONE'}")
        if not url:
            return jsonify({"success": False, "error": "No clip yet"}), 404
        response = make_response(jsonify({"success": True, "url": url}))
        response.headers['Cache-Control'] = 'no-store'
        return response, 200
    except Exception as e:
        logging.error(f"❌ latest_clip error: {e}")
        return jsonify({"success": False, "error": str(e)}), 500


def main_audio_monitoring():
    global alert_active, detection_enabled, current_alert_id, current_firebase_uid

    try:
        if not initialize_audio():
            logging.error("❌ Audio monitoring could not start")
            return

        recognizer = sr.Recognizer()
        logging.info("🎧 Audio monitoring initialized")

        while True:
            with detection_lock:
                if not detection_enabled:
                    time.sleep(2)
                    continue

            try:
                with sr.Microphone() as source:
                    time.sleep(0.1)
                    recognizer.adjust_for_ambient_noise(source, duration=0.5)

                    verified = two_stage_verification(recognizer, source)
                    if not verified:
                        continue

                    logging.info("🚨 AUDIO THREAT CONFIRMED — SIGNALING FLUTTER VIA FIRESTORE")

                    alert_active = True
                    alert_cancelled.clear()

                    try:
                        db.collection("alert_triggers").document("current").set({
                            "active": True,
                            "triggeredAt": firestore.SERVER_TIMESTAMP,
                            "source": "audio"
                        })
                        logging.info("✅ Firestore trigger doc written")
                    except Exception as e:
                        logging.error(f"❌ Firestore trigger write failed: {e}")

                    # ⏳ Wait for Flutter to call /api/trigger_alert
                    alert_id_ready.wait(timeout=45)
                    alert_id_ready.clear()

                    try:
                        if not current_alert_id:
                            logging.warning("⚠️ Flutter did not respond in time — resetting")
                            current_alert_id = None
                            current_firebase_uid = None
                            alert_active = False
                            time.sleep(5)
                            continue

                        # ✅ Flutter owns video recording and uploading via VideoRecordingService
                        # Flask just signals Flutter and waits — clips arrive via /api/upload_clip
                        logging.info(f"✅ Alert active — Flutter recording video for alert: {current_alert_id}")

                    except Exception as e:
                        logging.error(f"❌ Alert setup error: {e}")

                    try:
                        g = ip('me')
                        location = f"{g.latlng[0]},{g.latlng[1]}" if g and g.latlng else "Location unavailable"
                    except Exception as e:
                        logging.error(f"❌ Location error: {e}")
                        location = "Location unavailable"

                    map_link = f"https://www.google.com/maps/place/{location}" if location != "Location unavailable" else "Map link unavailable"

                    handle_alert_process(location, map_link, None)

                    logging.info("✅ ALERT PREPARED — Flutter sending SMS with live video link")

                    # ✅ Disable detection after alert fires
                    with detection_lock:
                        detection_enabled = False
                        logging.info("🛑 Detection automatically disabled after alert")

                    # ✅ Reset alert context
                    current_alert_id = None
                    current_firebase_uid = None

                    # ✅ Sync disabled state to frontend
                    try:
                        db.collection("alert_triggers").document("current").set({
                            "active": False,
                            "source": "init"
                        }, merge=True)
                        logging.info("✅ Firestore trigger reset after alert")
                    except Exception as e:
                        logging.error(f"❌ Firestore reset failed: {e}")

            except sr.UnknownValueError:
                continue
            except sr.RequestError as e:
                logging.error(f"❌ Speech recognition service error: {e}")
                time.sleep(2)
            except Exception as e:
                logging.error(f"❌ Audio monitoring error: {e}")
                time.sleep(2)

    except Exception as e:
        logging.error(f"❌ Fatal error in audio monitoring thread: {e}")


if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
    required_modules = ['pyaudio', 'speech_recognition', 'wave']
    missing_modules = []
    for module in required_modules:
        try:
            __import__(module)
        except ImportError:
            missing_modules.append(module)
    if missing_modules:
        logging.error(f"Missing required modules: {', '.join(missing_modules)}")
        exit(1)
    try:
        audio_thread = Thread(target=main_audio_monitoring)
        audio_thread.daemon = True
        audio_thread.start()
        logging.info("Audio monitoring thread started (waiting for activation)")
        logging.info("Sensor monitoring activated")
        logging.info("AI Detection is DISABLED by default. Use the toggle in the UI to enable it.")
        app.run(debug=True, use_reloader=False, threaded=True, host="0.0.0.0", port=5000)
    except Exception as e:
        logging.error(f"Failed to start application: {e}")