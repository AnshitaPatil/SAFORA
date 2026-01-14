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

cred = credentials.Certificate("serviceAccountKey.json")
firebase_admin.initialize_app(cred)
db = firestore.client()

def load_emergency_contacts(firebase_uid=None):
    """
    Loads ALL emergency contacts for a user from Firestore
    Returns:
    {
        "phone_numbers": [...],
        "contact_names": [...]
    }
    """
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

        return {
            "phone_numbers": phone_numbers,
            "contact_names": contact_names
        }

    except Exception as e:
        logging.error(f"❌ Firestore contact load failed: {e}")
        return {"phone_numbers": [], "contact_names": []}




# Initialize Flask app
app = Flask(__name__, static_folder='static', template_folder='templates')
# Enable CORS for mobile app connections
CORS(app, resources={r"/*": {"origins": "*"}})

# Initialize the ChatOllama model
try:
    model_chat = ChatOllama(model="llama3.2:1b", base_url="http://localhost:11434/")
except Exception as e:
    print(f"Warning: Could not initialize ChatOllama model: {e}")
    model_chat = None



from dotenv import load_dotenv
import os
from notification_service import load_emergency_contacts   # keep only load_emergency_contacts
from auth_helpers import verify_firebase_token, login_required
from sensor_detection import SensorDetector
import sqlite3
from auth_routes import bp as auth_bp

# Load env
load_dotenv()

# Initialize database
from auth_db import init_db
init_db()

# Register blueprints
app.register_blueprint(auth_bp)

# Load the audio model
try:
    model_audio = joblib.load('models/final_random_forest_model.pkl')
    logging.info("Audio model loaded successfully")
except Exception as e:
    logging.error(f"Error loading audio model: {e}")
    model_audio = None

# Load crime data
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
        intensity_colors = {
            'High': 'red',
            'Medium': 'yellow',
            'Low': 'green'
        }
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

# Load initial crime data
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

# Directory to save audio chunks
OUTPUT_DIR = 'audio_chunks1'
if not os.path.exists(OUTPUT_DIR):
    os.makedirs(OUTPUT_DIR)

# Setup logging
logging.basicConfig(level=logging.INFO)

# Create events for alert handling
alert_cancelled = Event()
alert_active = False

# Helper Functions
def calculate_distance(lat1, lon1, lat2, lon2):
    R = 6371
    lat1, lon1, lat2, lon2 = map(radians, [lat1, lon1, lat2, lon2])
    dlat = lat2 - lat1
    dlon = lon2 - lon1
    a = sin(dlat/2)*2 + cos(lat1) * cos(lat2) * sin(dlon/2)*2
    c = 2 * atan2(sqrt(a), sqrt(1-a))
    return R * c

def check_nearby_crimes(user_lat, user_lon, radius_km=2):
    """
    Check if there are any crimes within the specified radius
    Returns tuple (is_safe, nearby_crimes)
    """
    if crime_data.empty:
        return True, []
    nearby_crimes = []
    for _, crime in crime_data.iterrows():
        distance = calculate_distance(
            user_lat, user_lon,
            crime['Latitude'], crime['Longitude']
        )
        if distance <= radius_km:
            nearby_crimes.append({
                'type': crime['Incident_Type'],
                'distance': round(distance, 2),
                'intensity': crime['Intensity']
            })
    return len(nearby_crimes) == 0, nearby_crimes

def initialize_audio():
    """Initialize and verify audio setup"""
    try:
        audio = pyaudio.PyAudio()
        # If deviceCount can't be retrieved gracefully catch and continue
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

# Sleep mode variables and functions
sleep_timer = None
keyword = None
keyword_lock = Lock()
sleep_until = 0
sleep_lock = Lock()

# AI Detection control variables
detection_enabled = False
detection_lock = Lock()
audio_thread = None

# Sensor detector instance
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




@app.route('/sleep_status', methods=['GET'])
def get_sleep_status():
    with sleep_lock:
        is_sleeping = time.time() < sleep_until
        remaining_time = max(0, sleep_until - time.time()) if is_sleeping else 0
        status_info = {
            "sleeping": is_sleeping,
            "remaining_minutes": round(remaining_time / 60, 1),
            "wake_time": time.strftime('%H:%M:%S', time.localtime(sleep_until)) if is_sleeping else None,
            "status_message": "System is in sleep mode" if is_sleeping else "System is active"
        }
        return jsonify(status_info)

@app.route('/toggle_sleep', methods=['POST'])
def toggle_sleep():
    try:
        data = request.json
        is_sleeping = data.get('sleeping', False) if data else False
        toggle_sleep_mode(is_sleeping)
        return jsonify({
            "success": True,
            "sleeping": is_system_sleeping(),
            "message": "Sleep mode toggled successfully"
        })
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

@app.route('/detection_status', methods=['GET'])
def get_detection_status():
    global detection_enabled
    with detection_lock:
        enabled = detection_enabled
    status_info = {
        "enabled": enabled,
        "status_message": "AI Detection is active" if enabled else "AI Detection is disabled"
    }
    return jsonify(status_info)

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
    """Receive sensor data from Flutter and process for threat detection."""
    global sensor_detector
    try:
        data = request.get_json(force=True)
        # Expected keys accelX, accelY, accelZ, gyroX, gyroY, gyroZ
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

def two_stage_verification(recognizer, source):
    """
    Two-stage AI threat detection using:
      1. Keyword (voice)
      2. Scream (audio)
      3. Accelerometer (movement)
      4. Gyroscope (rotation)
    If ANY 2 parameters across BOTH stages are True → Trigger Alert 🚨
    """
    if is_system_sleeping():
        logging.info("🟡 System is in sleep mode, skipping verification.")
        return False

    global sensor_detector

    # Track Stage 1 + Stage 2 flags
    stage1 = {"keyword": False, "scream": False, "accel": False, "gyro": False}
    stage2 = {"keyword": False, "scream": False, "accel": False, "gyro": False}

    def print_stage_result(stage_name, data):
        """Neatly print results for each stage"""
        logging.info("\n───────────────────────────────")
        logging.info(f"🔎 {stage_name} RESULTS")
        logging.info("───────────────────────────────")
        for k, v in data.items():
            logging.info(f"{k.capitalize():<15}: {'✅ True' if v else '❌ False'}")
        total = sum(data.values())
        logging.info("───────────────────────────────")
        logging.info(f"Total Detected: {total}/4\n")
        return total

    # ========== 🧠 STAGE 1 ==========
    try:
        logging.info("\n===============================")
        logging.info("🧠 STAGE 1: Checking all 4 parameters")
        logging.info("===============================")

        # Keyword detection
        try:
            audio = recognizer.listen(source, timeout=3, phrase_time_limit=3)
            text = recognizer.recognize_google(audio)
            kw = load_keyword().lower()
            stage1["keyword"] = kw in text.lower()
        except Exception:
            pass

        # Scream detection
        try:
            audio_path = record_audio(record_seconds=3)
            stage1["scream"] = predict_audio(audio_path)
        except Exception:
            pass

        # Sensor data
        stage1["accel"] = sensor_detector.get_accelerometer_threat()
        stage1["gyro"] = sensor_detector.get_gyroscope_threat()

        print_stage_result("STAGE 1", stage1)

    except Exception as e:
        logging.error(f"Error in Stage 1: {e}")

    # If 2 or more parameters detected → immediate threat
    if sum(stage1.values()) >= 2:
        logging.info("🚨 Threat detected in Stage 1! Triggering alert immediately.")
        return True

    # ========== 🧠 STAGE 2 ==========
    try:
        logging.info("\n===============================")
        logging.info("🧠 STAGE 2: Re-checking all 4 parameters")
        logging.info("===============================")

        end_time = time.time() + 10
        while time.time() < end_time:
            try:
                # Keyword
                try:
                    audio = recognizer.listen(source, timeout=3, phrase_time_limit=3)
                    text = recognizer.recognize_google(audio)
                    kw = load_keyword().lower()
                    if kw in text.lower():
                        stage2["keyword"] = True
                except Exception:
                    pass

                # Scream
                try:
                    audio_path = record_audio(record_seconds=3)
                    if predict_audio(audio_path):
                        stage2["scream"] = True
                except Exception:
                    pass

                # Sensors
                if sensor_detector.get_accelerometer_threat():
                    stage2["accel"] = True
                if sensor_detector.get_gyroscope_threat():
                    stage2["gyro"] = True

                print_stage_result("STAGE 2 (intermediate)", stage2)

                # Combine both stages
                total_true = sum([
                    stage1["keyword"] or stage2["keyword"],
                    stage1["scream"] or stage2["scream"],
                    stage1["accel"] or stage2["accel"],
                    stage1["gyro"] or stage2["gyro"],
                ])

                logging.info(f"✅ Total True (cross-stage): {total_true}/4\n")

                if total_true >= 2:
                    logging.info("🚨 Threat confirmed across stages → Triggering alert.")
                    return True

                time.sleep(1)

            except Exception as e:
                logging.error(f"Error in Stage 2 loop: {e}")
                time.sleep(1)

    except Exception as e:
        logging.error(f"Stage 2 failed: {e}")

    # Final Summary
    logging.info("\n===============================")
    logging.info("🧾 FINAL SUMMARY")
    logging.info("===============================")
    total_true = sum([
        stage1["keyword"] or stage2["keyword"],
        stage1["scream"] or stage2["scream"],
        stage1["accel"] or stage2["accel"],
        stage1["gyro"] or stage2["gyro"],
    ])
    logging.info(f"✅ Total True (combined): {total_true}/4")
    logging.info("===============================\n")

    if total_true >= 2:
        logging.info("🚨 Threat detected: 2 or more parameters true across stages.")
        return True

    logging.info("❌ No threat detected (less than 2 parameters true).")
    return False


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

def handle_alert_process(audio_file_path, location, map_link, shareable_link, firebase_uid=None):
    """Handle the alert process - set flag and prepare alert data for frontend/Flutter"""
    global alert_active
    alert_active = True
    alert_cancelled.clear()
    logging.info(f"Alert process started. Location: {location}, Map: {map_link}, audio: {shareable_link}")

@app.route('/')
def index():
    # Ensure your templates folder still contains index.html
    return render_template('index.html')

@app.route('/health', methods=['GET'])
def health():
    """Health check endpoint for Flutter app"""
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
    return jsonify({
        "alert_active": alert_active,
        "show_alert": alert_active
    })

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
            try:
                parts = auth_header.split()
                if len(parts) == 2 and parts[0].lower() == 'bearer':
                    token = parts[1]
                    decoded = verify_firebase_token(token)
                    if decoded:
                        firebase_uid = decoded.get('uid')
                        logging.info(f"👤 User identified for alert: {firebase_uid}")
            except Exception as e:
                logging.warning(f"⚠️ Could not get user from token: {e}")

        # 🌍 Use IP geolocation (best-effort)
        try:
            g = geocoder.ip('me')
            if g and g.latlng:
                location = f"{g.latlng[0]},{g.latlng[1]}"
            else:
                location = "Location unavailable"
        except Exception as e:
            logging.error(f"❌ Failed to get location: {e}")
            location = "Location unavailable"

        # 📍 Prepare map and media links
        map_link = (
            f"https://www.google.com/maps/place/{location}"
            if location != "Location unavailable"
            else "Map link unavailable"
        )
        base_url = request.url_root.rstrip('/')
        audio_link = f"{base_url}/audio_stream"
        video_link = f"{base_url}/video_stream"

        # 📱 Load user’s emergency contacts from Firebase DB
        contacts = load_emergency_contacts(firebase_uid=firebase_uid)
        phone_numbers = contacts.get("phone_numbers", [])

        logging.info("\n======================================")
        logging.info("🚨 EMERGENCY ALERT TRIGGERED - PREPARING DATA")
        logging.info("======================================")
        logging.info(f"📍 Location: {location}")
        logging.info(f"🗺️ Map Link: {map_link}")
        logging.info(f"📞 Emergency Contacts Found: {len(phone_numbers)}")
        logging.info("======================================")

        results = {
            "success": True,
            "message": "✅ Alert data prepared. Flutter (Telephony) should now send SMS automatically.",
            "phoneNumbers": phone_numbers,
            "location": location,
            "mapLink": map_link,
            "audioLink": audio_link,
            "videoLink": video_link
        }

        alert_active = False
        alert_cancelled.set()

        # ✅ Safe return to Flutter — avoids connection crash
        try:
            return jsonify(results)
        except Exception as e:
            logging.warning(f"⚠️ Flutter not connected — sending fallback response: {e}")
            return jsonify({
                "success": True,
                "message": "Alert prepared locally (Flutter not reachable).",
                "data": results
            }), 200

    except Exception as e:
        logging.error(f"❌ Error in confirm_alert: {str(e)}")
        return jsonify({
            "message": "Error processing alert.",
            "success": False,
            "error": str(e)
        }), 500


@app.route('/get_crime_data', methods=['GET'])
def get_crime_data():
    crime_data_list = get_crime_data_for_map()
    return jsonify(crime_data_list)

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
                    token = parts[1]
                    decoded = verify_firebase_token(token)
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

        # 🔐 Verify Firebase token
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
            emergency_contacts.append({
                "id": f"{name}_{phone}",   # required for delete
                "name": name,
                "phone": phone
            })

        # 🔥 SAVE TO FIRESTORE (single source of truth)
        db.collection("users").document(firebase_uid).set(
            {"emergencyContacts": emergency_contacts},
            merge=True
        )

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

@app.route('/api/trigger_alert', methods=['POST'])
def trigger_alert():
    """
    🔥 AUTOMATIC ALERT ENDPOINT (NO CONFIRMATION, NO COUNTDOWN)
    Called directly by Flutter when sensors detect danger.
    """
    global alert_active

    try:
        data = request.get_json(force=True)
        logging.info(f"🚨 AUTO ALERT RECEIVED FROM FLUTTER: {data}")

        firebase_uid = data.get("firebaseUid") or data.get("firebase_uid")

        # 🌍 Location (best-effort)
        try:
            g = geocoder.ip('me')
            if g and g.latlng:
                location = f"{g.latlng[0]},{g.latlng[1]}"
            else:
                location = "Location unavailable"
        except Exception:
            location = "Location unavailable"

        map_link = (
            f"https://www.google.com/maps/place/{location}"
            if location != "Location unavailable"
            else "Map link unavailable"
        )

        base_url = request.url_root.rstrip('/')
        audio_link = f"{base_url}/audio_stream"
        video_link = f"{base_url}/video_stream"

        # 📱 Load emergency contacts
        contacts = load_emergency_contacts(firebase_uid=firebase_uid)
        phone_numbers = contacts.get("phone_numbers", [])

        logging.info("\n======================================")
        logging.info("🚨 AUTO EMERGENCY ALERT (NO CONFIRMATION)")
        logging.info("======================================")
        logging.info(f"📍 Location: {location}")
        logging.info(f"📞 Emergency Contacts Found: {len(phone_numbers)}")
        logging.info("======================================")

        # 🔴 IMPORTANT: kill web countdown flow
        alert_active = False
        alert_cancelled.set()

        return jsonify({
            "success": True,
            "auto": True,
            "phoneNumbers": phone_numbers,
            "location": location,
            "mapLink": map_link,
            "audioLink": audio_link,
            "videoLink": video_link,
            "message": "Auto alert prepared. Flutter should send SMS immediately."
        }), 200

    except Exception as e:
        logging.error(f"❌ Error in auto trigger_alert: {e}")
        return jsonify({"success": False, "error": str(e)}), 500

def main_audio_monitoring():
    """
    Audio monitoring thread — FULLY AUTOMATIC.
    If audio threat is verified → signals Flutter via alert_active.
    NO countdown, NO manual confirmation, NO UI dependency.
    """
    global alert_active, detection_enabled

    try:
        if not initialize_audio():
            logging.error("❌ Audio monitoring could not start")
            return

        recognizer = sr.Recognizer()
        logging.info("🎧 Audio monitoring initialized")

        while True:
            # 🔒 Respect detection toggle
            with detection_lock:
                if not detection_enabled:
                    time.sleep(2)
                    continue

            try:
                with sr.Microphone() as source:
                    time.sleep(0.1)
                    recognizer.adjust_for_ambient_noise(source)

                    # 🧠 Two-stage verification
                    verified = two_stage_verification(recognizer, source)
                    if not verified:
                        continue

                    # 🚨 AUDIO THREAT CONFIRMED
                    logging.info("🚨 AUDIO THREAT CONFIRMED — SIGNALING FLUTTER")

                    # 🔔 SIGNAL FLUTTER (THIS WAS MISSING)
                    alert_active = True
                    alert_cancelled.clear()

                    # 🎙️ Record evidence
                    audio_file_path = record_audio(record_seconds=8)

                    try:
                        shareable_link = upload_to_drive(audio_file_path)
                    except Exception as e:
                        logging.error(f"❌ Audio upload failed: {e}")
                        shareable_link = "Audio upload failed"

                    # 🌍 Get location (best-effort)
                    try:
                        g = ip('me')
                        if g and g.latlng:
                            location = f"{g.latlng[0]},{g.latlng[1]}"
                        else:
                            location = "Location unavailable"
                    except Exception as e:
                        logging.error(f"❌ Location error: {e}")
                        location = "Location unavailable"

                    map_link = (
                        f"https://www.google.com/maps/place/{location}"
                        if location != "Location unavailable"
                        else "Map link unavailable"
                    )

                    # 🧾 Prepare alert data (Flask side only)
                    handle_alert_process(
                        audio_file_path,
                        location,
                        map_link,
                        shareable_link
                    )

                    logging.info(
                        "✅ AUDIO ALERT PREPARED — waiting for Flutter to send SMS"
                    )

                    # ⏸️ Cooldown to avoid repeated triggers
                    time.sleep(5)

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
    # Initialize logging
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
        # Start audio monitoring thread
        audio_thread = Thread(target=main_audio_monitoring)
        audio_thread.daemon = True
        audio_thread.start()
        logging.info("Audio monitoring thread started (waiting for activation)")
        logging.info("Sensor monitoring activated")
        logging.info("AI Detection is DISABLED by default. Use the toggle in the UI to enable it.")
        app.run(debug=True, use_reloader=False, threaded=True, host="0.0.0.0", port=5000)
    except Exception as e:
        logging.error(f"Failed to start application: {e}")


