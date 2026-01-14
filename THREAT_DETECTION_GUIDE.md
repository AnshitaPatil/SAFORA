# Threat Detection System - Complete Guide

## 🎯 Overview

The Draupadi AI threat detection system uses a **two-stage detection process** with **4 parameters**. A threat is triggered when **ANY 2 of the 4 parameters** become true (across both stages).

---

## 📊 Detection Parameters

The system monitors 4 parameters simultaneously:

### 1. **Keyword Detection** (Speech Recognition)
- **What it detects:** Specific keywords/phrases (e.g., "help", "save me")
- **How it works:** Uses Google Speech Recognition API to listen for configured keywords
- **Technology:** Speech recognition with keyword verification

### 2. **Audio Scream Detection** (Machine Learning)
- **What it detects:** Screams, distress sounds, high-pitched audio
- **How it works:** Records audio and analyzes using Random Forest ML model
- **Technology:** Librosa feature extraction + Scikit-learn model

### 3. **Accelerometer Detection** (Motion Sensors)
- **What it detects:**
  - **Fall:** Sudden drop in acceleration (phone dropped)
  - **Shake:** High acceleration magnitude (phone being shaken)
  - **Struggle:** Irregular, high-frequency variations (struggle patterns)
  - **Motion:** Unusual motion patterns (abnormal movement)
- **How it works:** Monitors X, Y, Z acceleration values and calculates magnitude/patterns
- **Technology:** Device accelerometer sensor data analysis

### 4. **Gyroscope Detection** (Rotation Sensors)
- **What it detects:**
  - **Crush:** Rapid rotation changes (phone being crushed)
  - **Rotation:** High rotation magnitude (phone being rotated violently)
- **How it works:** Monitors X, Y, Z rotation values and calculates change rates
- **Technology:** Device gyroscope sensor data analysis

---

## 🔄 Two-Stage Detection Process

### **STAGE 1: Initial Detection**
Checks all 4 parameters:
1. Keyword detection
2. Scream detection
3. Accelerometer threat (any of: fall, shake, struggle, motion)
4. Gyroscope threat (any of: crush, rotation)

**Result:**
- If **2+ parameters** detected → **Threat detected immediately** ✅
- If **1 parameter** detected → Proceed to Stage 2
- If **0 parameters** detected → Continue monitoring

### **STAGE 2: Confirmation (Only if Stage 1 detected 1 parameter)**
Re-checks all 4 parameters:
1. Keyword detection (if not detected in Stage 1)
2. Scream detection (if not detected in Stage 1)
3. Accelerometer threat (may persist from Stage 1)
4. Gyroscope threat (may persist from Stage 1)

**Result:**
- Count **unique parameters** across **BOTH stages**
- If **2+ unique parameters** detected → **Threat detected** ✅
- Examples:
  - Stage 1: Gyroscope detected (1), Stage 2: Keyword detected (1) = **2 total** → **Threat** ✅
  - Stage 1: Accelerometer detected (1), Stage 2: Scream detected (1) = **2 total** → **Threat** ✅
  - Stage 1: Accelerometer detected (1), Stage 2: Gyroscope detected (1) = **2 total** → **Threat** ✅

---

## 🚨 Alert Process

When a threat is detected:

1. **Threat Detection** → `two_stage_verification()` returns `True`

2. **Alert Initiation** → Backend:
   - Records audio evidence (8 seconds)
   - Uploads audio to Google Drive
   - Gets device location
   - Sets `alert_active = True`

3. **Alert Page Display** → Frontend:
   - Flask detects `alert_active = True`
   - Automatically navigates to `/alert` page
   - Shows countdown timer (6 seconds)

4. **Countdown** → Alert Page:
   - User can **Cancel** within 6 seconds
   - If not cancelled → Auto-sends alert after 6 seconds
   - User can **Send Now** to send immediately

5. **SMS Sending** → Automatic:
   - When countdown reaches 0 (or user clicks "Send Now")
   - Calls `/confirm_alert` endpoint
   - Gets emergency contacts from database
   - Sends alert data to Flutter via JavaScript channel
   - Flutter automatically sends SMS to all emergency contacts

---

## 📱 Automatic SMS Sending

### How It Works:

1. **Flutter receives alert data** via JavaScript channel from WebView
2. **SMS Service** (`sms_service.dart`) uses `flutter_sms` package
3. **Permission check**: Requests SMS permission if not granted
4. **Phone number cleaning**: Automatically adds `+91` for Indian numbers
5. **Bulk SMS**: Sends SMS to all emergency contacts automatically
6. **No user interaction needed**: SMS is sent programmatically

### SMS Message Format:
```
EMERGENCY ALERT - Help needed!

Time: [timestamp]
Location: [latitude,longitude]
Map: [Google Maps link]
Audio: [Audio stream link]
Video: [Video stream link]

Respond immediately!
SAFORA Alert System
```

---

## 🔧 Technical Implementation

### Flask Backend (`app.py`):

- **`two_stage_verification()`**: Main detection function
  - Stage 1: Checks all 4 parameters
  - Stage 2: Re-checks if Stage 1 had 1 detection
  - Returns `True` if 2+ unique parameters detected
  
- **`main_audio_monitoring()`**: Background thread
  - Continuously monitors audio
  - Calls `two_stage_verification()` when detection enabled
  - Triggers alert process when threat detected

- **`/api/sensor_data`**: Receives sensor data from Flutter
  - Processes accelerometer and gyroscope data
  - Updates sensor detector state

- **`/confirm_alert`**: Prepares alert data
  - Gets emergency contacts from database
  - Returns phone numbers, location, links to frontend

### Flutter Frontend:

- **`SensorService`**: Monitors device sensors
  - Streams accelerometer data every 500ms
  - Streams gyroscope data every 500ms
  - Sends data to Flask backend continuously

- **`SmsService`**: Handles SMS sending
  - Uses `flutter_sms` for automatic sending
  - Requests SMS permission
  - Sends SMS to all emergency contacts

- **`FlaskWebPage`**: WebView integration
  - JavaScript channel `FlutterChannel` for communication
  - Receives alert data from Flask
  - Triggers SMS sending automatically

---

## 📋 Detection Logic Examples

### Example 1: Keyword + Gyroscope
- **Stage 1:** Keyword detected ✅ (1), Gyroscope detected ✅ (1) = **2 total** → **Threat triggered immediately**

### Example 2: Accelerometer + Scream (across stages)
- **Stage 1:** Accelerometer detected ✅ (1), No keyword/scream
- **Stage 2:** Scream detected ✅ (1)
- **Total unique:** Accelerometer (1) + Scream (1) = **2 total** → **Threat triggered**

### Example 3: Gyroscope + Accelerometer (across stages)
- **Stage 1:** Gyroscope detected ✅ (1)
- **Stage 2:** Accelerometer detected ✅ (1)
- **Total unique:** Gyroscope (1) + Accelerometer (1) = **2 total** → **Threat triggered**

### Example 4: Single parameter
- **Stage 1:** Keyword detected ✅ (1)
- **Stage 2:** No other parameters detected
- **Total unique:** Keyword (1) only = **1 total** → **No threat** (need 2+)

---

## ⚙️ How to Test Threat Detection

### Test Scenario 1: Keyword + Gyroscope
1. Enable AI Detection toggle in Flask UI
2. Say the configured keyword (e.g., "help")
3. Rotate phone rapidly at the same time
4. **Expected:** Threat detected immediately (2 parameters in Stage 1)

### Test Scenario 2: Accelerometer + Scream (across stages)
1. Enable AI Detection toggle
2. Shake phone vigorously (Stage 1: Accelerometer detected)
3. Scream loudly (Stage 2: Scream detected)
4. **Expected:** Threat detected in Stage 2 (2 unique parameters)

### Test Scenario 3: Gyroscope + Accelerometer
1. Enable AI Detection toggle
2. Rotate phone (Stage 1: Gyroscope detected)
3. Drop or shake phone (Stage 2: Accelerometer detected)
4. **Expected:** Threat detected in Stage 2 (2 unique parameters)

---

## 🛠️ Configuration

### Threshold Values:

**Accelerometer:**
- Fall threshold: 9.5 m/s² (sudden drop)
- Shake threshold: 15.0 m/s² (high acceleration)
- Struggle threshold: 12.0 (variance)
- Motion threshold: 8.0 m/s² (unusual motion)

**Gyroscope:**
- Crush threshold: 10.0 rad/s (rapid rotation change)
- Rotation threshold: 8.0 rad/s (high rotation)

**Timing:**
- Stage 1 timeout: 3 seconds per parameter check
- Stage 2 duration: 10 seconds (checks every 1 second)
- Alert countdown: 6 seconds (auto-send if not cancelled)

---

## 📝 Important Notes

1. **Sensor data is sent continuously**: Flutter sends sensor data to Flask every 500ms
2. **Detection flags persist**: Sensor detections persist across stages for proper counting
3. **Automatic SMS**: SMS is sent automatically after 6-second countdown (no user tap needed)
4. **User can cancel**: User has 6 seconds to cancel alert before SMS is sent
5. **Multiple contacts**: SMS is sent to all emergency contacts in the database

---

## ✅ Summary

- **4 Parameters**: Keyword, Scream, Accelerometer, Gyroscope
- **2 Stages**: Initial detection + Confirmation
- **2+ Parameters Required**: Any 2 parameters true = Threat detected
- **Automatic SMS**: Sent automatically after 6 seconds if not cancelled
- **No User Interaction**: SMS is sent programmatically (after permission granted)

---

## 🚀 Next Steps

1. Enable AI Detection toggle in Flask UI
2. Add emergency contacts in Emergency Contacts page
3. Test with various scenarios (shake, rotate, say keyword, scream)
4. Check logs for detailed detection information
5. Verify SMS is sent automatically to all emergency contacts

