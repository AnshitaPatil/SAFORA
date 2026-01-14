# Mobile App Setup Guide

This guide explains how to run the Flask backend and Flutter frontend together so everything works within the mobile app.

## Overview

- **Flask Backend**: Runs on your computer as a server (port 5000)
- **Flutter App**: Runs on emulator/device and connects to Flask via HTTP/WebView
- **Connection**: The Flutter app automatically detects the correct URL based on your setup

## Prerequisites

1. Python 3.x installed
2. Flask dependencies installed (`pip install -r requirements.txt`)
3. Flutter SDK installed
4. Android Studio / Xcode for emulators

## Step 1: Start Flask Backend

### Windows:
```bash
cd safora_flask
start_flask.bat
```

### Mac/Linux:
```bash
cd safora_flask
chmod +x start_flask.sh
./start_flask.sh
```

### Manual:
```bash
cd safora_flask
python app.py
```

Flask will start on `http://0.0.0.0:5000`, which accepts connections from:
- Localhost: `http://localhost:5000`
- Android Emulator: `http://10.0.2.2:5000`
- Real devices on same network: `http://YOUR_COMPUTER_IP:5000`

## Step 2: Find Your Computer's IP Address

**For real devices** (not emulator), you need your computer's local network IP:

### Windows:
```cmd
ipconfig
```
Look for "IPv4 Address" under your active network adapter.

### Mac/Linux:
```bash
ifconfig | grep "inet "
```
or
```bash
hostname -I
```

Update `api_service.dart` with your IP if needed (line 31):
```dart
"http://192.168.1.5:5000", // Replace with your IP
```

## Step 3: Run Flutter App

### Android Emulator:
```bash
cd safora_flutter
flutter run
```

The app will automatically use `http://10.0.2.2:5000` to connect to Flask.

### iOS Simulator:
```bash
cd safora_flutter
flutter run
```

The app will automatically use `http://localhost:5000` to connect to Flask.

### Real Device:
1. Ensure your device and computer are on the **same Wi-Fi network**
2. Update the IP address in `api_service.dart` if needed
3. Run:
```bash
flutter run
```

The app will try multiple URLs and auto-detect the working one.

## Troubleshooting

### "Failed to connect to Flask backend"

1. **Check Flask is running**: Open browser and go to `http://localhost:5000/health`
   - Should see: `{"status": "healthy", "message": "Flask backend is running"}`

2. **Check firewall**: Windows/Mac firewall might block port 5000
   - Windows: Allow Python through firewall
   - Mac: System Preferences > Security > Firewall

3. **For real devices**: Ensure both device and computer are on same Wi-Fi

4. **Check URL**: 
   - Emulator: Must use `10.0.2.2:5000`
   - Real device: Must use your computer's IP (not localhost)

### Flask shows "Address already in use"

Port 5000 is already in use. Either:
- Stop the other process using port 5000
- Or change Flask port in `app.py` (line 864) and update Flutter accordingly

### WebView shows blank page

1. Check Flask is running and accessible
2. Use the refresh button in the app
3. Check console for error messages

## Connection Flow

1. Flutter app starts
2. App detects platform (Android/iOS)
3. App tries to connect to Flask at appropriate URL
4. If connection succeeds → Load Flask UI in WebView
5. If connection fails → Show error with retry option

## Architecture

```
┌─────────────────┐
│  Flutter App    │
│  (Mobile)       │
│                 │
│  ┌───────────┐  │
│  │ WebView   │──┼──> HTTP Requests ──┐
│  └───────────┘  │                    │
│                 │                    │
│  ┌───────────┐  │                    │
│  │API Service│──┼──> HTTP Requests ──┤
│  └───────────┘  │                    │
└─────────────────┘                    │
                                       ▼
                              ┌─────────────────┐
                              │  Flask Backend  │
                              │  (Your PC)      │
                              │  Port 5000      │
                              └─────────────────┘
```

## Notes

- Flask must be running before starting the Flutter app
- For production, deploy Flask to a cloud server and update URLs
- WebView loads the full Flask web interface inside the app
- All Flask functionality is accessible within the mobile app

