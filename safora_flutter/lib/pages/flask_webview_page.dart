import 'package:flutter/material.dart';
import 'package:webview_flutter/webview_flutter.dart';
import 'package:webview_flutter_android/webview_flutter_android.dart';
import 'dart:io';
import 'package:firebase_auth/firebase_auth.dart';
import 'dart:convert';
import 'package:http/http.dart' as http;
import 'dart:async';
import '../services/api_service.dart';
import '../services/sensor_service.dart';
import '../services/alert_service.dart';
import 'package:fluttertoast/fluttertoast.dart';
import 'package:cloud_firestore/cloud_firestore.dart';
import 'alert_page.dart'; // Add this import

class FlaskWebPage extends StatefulWidget {
  final String url;

  const FlaskWebPage({super.key, required this.url});

  @override
  State<FlaskWebPage> createState() => _FlaskWebPageState();
}

class _FlaskWebPageState extends State<FlaskWebPage> {
  late final WebViewController _controller;
  final TextEditingController nameController = TextEditingController();
  final TextEditingController phoneController = TextEditingController();
  bool _isLoading = true;
  bool _hasError = false;
  bool _alertInProgress = false;
  String? _errorMessage;
  Timer? _sensorTimer;

  void _stopSensorTimer() {
  _sensorTimer?.cancel();
  _sensorTimer = null;
}

  // ⚙️ Alert control
  bool _previousThreat = false;
  DateTime? _lastAlertTime=DateTime.now();
  final Duration _alertCooldown = const Duration(seconds: 60); // prevent spam

  @override
  void initState() {
    super.initState();
    _initializeWebView();
    SensorService.startMonitoring();
    _startSensorDataStream();
  }

  @override
  void dispose() {
    _sensorTimer?.cancel();
    SensorService.stopMonitoring();
    super.dispose();
  }

  /// ✅ Manual test alert trigger
  Future<void> _testAlert() async {
    print("🧪 Manual test alert triggered");
    
    // Navigate to alert page
    if (mounted) {
      await Navigator.push(
        context,
        MaterialPageRoute(
          builder: (context) => AlertPage(
            onAlertSent: () {
              // Reset detections after alert is sent
              SensorService.resetDetections();
              Navigator.pop(context);
            },
          ),
        ),
      );
    }
  }
 
 Future<void> _saveContactToFirestore(String name, String number) async {
  final uid = FirebaseAuth.instance.currentUser?.uid;
  if (uid == null) return;

  final doc = FirebaseFirestore.instance.collection('users').doc(uid);
  final contact = {'name': name, 'phone': number};

  final snap = await doc.get();

  if (snap.exists) {
    await doc.update({
      'emergencyContacts': FieldValue.arrayUnion([contact])
    });
  } else {
    await doc.set({
      'emergencyContacts': [contact]
    });
  }
}
  /// ✅ Debug function to check user documents
  Future<void> _debugUserDocuments() async {
    try {
      // Show immediate feedback
      Fluttertoast.showToast(
        msg: "Debugging user documents...",
        toastLength: Toast.LENGTH_SHORT,
        gravity: ToastGravity.BOTTOM,
        backgroundColor: Colors.blue,
        textColor: Colors.white,
      );
      
      final currentUser = FirebaseAuth.instance.currentUser;
      if (currentUser == null) {
        print("❌ No current user");
        Fluttertoast.showToast(
          msg: "No current user logged in",
          toastLength: Toast.LENGTH_LONG,
          gravity: ToastGravity.BOTTOM,
          backgroundColor: Colors.red,
          textColor: Colors.white,
        );
        return;
      }
      
      print("🔍 Debug - Current user ID: ${currentUser.uid}");
      
      // Check what documents exist in the users collection
      final usersCollection = await FirebaseFirestore.instance.collection('users').limit(10).get();
      print("📄 Debug - Found ${usersCollection.docs.length} user documents:");
      
      for (var doc in usersCollection.docs) {
        print("   - Document ID: ${doc.id}");
        print("   - Document data: ${doc.data()}");
      }
      
      // Check the specific user document
      final userDoc = await FirebaseFirestore.instance.collection('users').doc(currentUser.uid).get();
      print("📄 Debug - Specific user document exists: ${userDoc.exists}");
      if (userDoc.exists) {
        print("📄 Debug - Specific user document data: ${userDoc.data()}");
        Fluttertoast.showToast(
          msg: "User document found! Check console for details.",
          toastLength: Toast.LENGTH_LONG,
          gravity: ToastGravity.BOTTOM,
          backgroundColor: Colors.green,
          textColor: Colors.white,
        );
      } else {
        print("❌ Debug - User document does not exist for UID: ${currentUser.uid}");
        Fluttertoast.showToast(
          msg: "User document not found! Check console for details.",
          toastLength: Toast.LENGTH_LONG,
          gravity: ToastGravity.BOTTOM,
          backgroundColor: Colors.red,
          textColor: Colors.white,
        );
      }
      
      // Also test getting contacts directly
      
      
    } catch (e) {
      print("❌ Debug error: $e");
      Fluttertoast.showToast(
        msg: "Debug error: $e",
        toastLength: Toast.LENGTH_LONG,
        gravity: ToastGravity.BOTTOM,
        backgroundColor: Colors.red,
        textColor: Colors.white,
      );
    }
  }

  /// ✅ Navigate back to login page
  Future<void> _goBack() async {
    // Stop sensor monitoring
    SensorService.stopMonitoring();
    
    // Sign out user
    await FirebaseAuth.instance.signOut();
    
    // Navigate back to login
    if (mounted) {
      Navigator.pushNamedAndRemoveUntil(context, '/login', (route) => false);
    }
  }

  /// ✅ Continuous sensor data stream and one-time alert per event
  void _startSensorDataStream() {
  print("🔄 Starting sensor data stream");

  _sensorTimer?.cancel(); // safety: avoid multiple timers

  _sensorTimer = Timer.periodic(const Duration(seconds: 1), (timer) async {
    if (!mounted) {
      timer.cancel();
      return;
    }

    // 🔒 Do nothing if an alert is already in progress
    if (_alertInProgress) return;

    try {
      final detections = SensorService.getDetectionResults();
      final bool accelThreat = detections['accelerometer'] == true;
      final bool gyroThreat = detections['gyroscope'] == true;
      final bool currentThreat = accelThreat || gyroThreat;

      print(
        "📊 Sensor data - Accel: $accelThreat, Gyro: $gyroThreat, Current: $currentThreat",
      );

      final flaskUrl = await ApiService.getFlaskUrl();

      // 📡 Send live telemetry (non-blocking)
      try {
        await http.post(
          Uri.parse('$flaskUrl/api/sensor_data'),
          headers: {'Content-Type': 'application/json'},
          body: jsonEncode({
            'accelX': detections['accelX'],
            'accelY': detections['accelY'],
            'accelZ': detections['accelZ'],
            'gyroX': detections['gyroX'],
            'gyroY': detections['gyroY'],
            'gyroZ': detections['gyroZ'],
            'accelerometerThreat': accelThreat,
            'gyroscopeThreat': gyroThreat,
          }),
        ).timeout(const Duration(seconds: 2));
      } catch (_) {
        // telemetry failures are non-fatal
      }

      final now = DateTime.now();
      final bool cooldownPassed =
          _lastAlertTime == null ||
          now.difference(_lastAlertTime!) >= _alertCooldown;

      // 🔔 AUDIO-TRIGGERED ALERT FROM FLASK (AUTOMATED)
try {
  final alertStatusRes = await http
      .get(Uri.parse('$flaskUrl/alert_status'))
      .timeout(const Duration(seconds: 2));

  if (alertStatusRes.statusCode == 200) {
    final data = jsonDecode(alertStatusRes.body);

    // 🚨 THIS IS THE AUTOMATION DECISION
    if (data['alert_active'] == true && !_alertInProgress) {
      print("🚨 AUTOMATION: Flask audio alert detected → sending SMS");

      // 🔒 Lock so it happens ONCE
      _alertInProgress = true;
      _lastAlertTime = DateTime.now();

      // 🛑 Stop sensor loop to avoid re-entry
      _sensorTimer?.cancel();
      _sensorTimer = null;

      try {
        // 🚀 THIS IS THE ACTUAL AUTOMATION
        await AlertService.triggerAutomaticAlert();
        print("✅ AUTOMATION COMPLETE: SMS sent by Flutter");
      } catch (e) {
        print("❌ AUTOMATION FAILED: $e");
      } finally {
        // 🔓 Reset local guards
        _alertInProgress = false;
        _previousThreat = false;

        if (mounted) {
          _startSensorDataStream();
        }
      }

      // ⛔ Do NOT process sensor logic this tick
      return;
    }
  }
} catch (e) {
  debugPrint("Audio alert status check failed: $e");
}

      // 🚨 SINGLE, CLEAN AUTO-ALERT PATH
      if (currentThreat &&
          !_previousThreat &&
          cooldownPassed &&
          !_alertInProgress) {
        print("🚨 THREAT DETECTED! Triggering alert...");

        // 🔒 Lock immediately
        _alertInProgress = true;
        _previousThreat = true;
        _lastAlertTime = now;

        final String source = accelThreat && gyroThreat
            ? "Accelerometer + Gyroscope"
            : accelThreat
                ? "Accelerometer"
                : "Gyroscope";

        Fluttertoast.showToast(
          msg: "⚠️ Threat detected from $source! Sending alert...",
          toastLength: Toast.LENGTH_LONG,
          gravity: ToastGravity.BOTTOM,
          backgroundColor: Colors.redAccent,
          textColor: Colors.white,
        );

        // 🚨 Notify backend (best effort)
        try {
          await http.post(
            Uri.parse('$flaskUrl/api/trigger_alert'),
            headers: {'Content-Type': 'application/json'},
            body: jsonEncode({
              'accelerometer': accelThreat,
              'gyroscope': gyroThreat,
              'timestamp': now.toIso8601String(),
              'firebaseUid': FirebaseAuth.instance.currentUser?.uid,
            }),
          ).timeout(const Duration(seconds: 3));
        } catch (_) {}

        // 🛑 Stop sensor loop BEFORE navigation
        _sensorTimer?.cancel();
        _sensorTimer = null;

        try {
          if (mounted) {
            print("📤 Triggering automatic alert directly (no UI)...");

            await AlertService.triggerAutomaticAlert();

            print("✅ Automatic alert sent via Flutter");
          }
        } finally {
          // 🔓 ALWAYS reset state after alert
          _alertInProgress = false;
          _previousThreat = false;
          _lastAlertTime = DateTime.now();

          if (mounted) {
            _startSensorDataStream(); // resume monitoring
          }
        }
      }

      // 🟢 Calm state reset
      if (!currentThreat) {
        _previousThreat = false;
      }
    } catch (e) {
      print("❌ Sensor data processing error: $e");
    }
  });
}
  /// ✅ WebView setup
  Future<void> _initializeWebView() async {
    print("🌐 Initializing WebView");
    if (Platform.isAndroid) {
      WebViewPlatform.instance = AndroidWebViewPlatform();
    }

    String? firebaseToken;
    try {
      final user = FirebaseAuth.instance.currentUser;
      if (user != null) {
        firebaseToken = await user.getIdToken();
      }
    } catch (e) {
      debugPrint("Error getting Firebase token: $e");
    }

    final params = PlatformWebViewControllerCreationParams();
    _controller = WebViewController.fromPlatformCreationParams(params)
       ..addJavaScriptChannel(
  'ContactChannel',
  onMessageReceived: (JavaScriptMessage msg) async {
    try {
      final data = jsonDecode(msg.message);
      final name = data['name'];
      final number = data['number'];

      print("🔥 Contact from WebView → $name / $number");

      await _saveContactToFirestore(name, number);

      final doc = await FirebaseFirestore.instance
          .collection('users')
          .doc(FirebaseAuth.instance.currentUser!.uid)
          .get();

      final contacts = doc.data()?['emergencyContacts'];

      Fluttertoast.showToast(
        msg: "Saved contacts → $contacts",
        toastLength: Toast.LENGTH_LONG,
        backgroundColor: Colors.green,
        textColor: Colors.white,
      );

    } catch (e) {
      print("❌ Error saving contact: $e");
      Fluttertoast.showToast(
        msg: "Failed to save contact",
        backgroundColor: Colors.red,
        textColor: Colors.white,
      );
    }
  },
)
      ..setJavaScriptMode(JavaScriptMode.unrestricted)
      ..setNavigationDelegate(
        NavigationDelegate(
          onPageStarted: (_) {
            if (!mounted) return;
            setState(() {
              _isLoading = true;
              _hasError = false;
            });
          },
          onPageFinished: (_) async {
            if (!mounted) return;
            // Inject Firebase token into the web page
            if (firebaseToken != null) {
              try {
                await _controller.runJavaScript('''
                  localStorage.setItem('firebaseToken', '$firebaseToken');
                  sessionStorage.setItem('firebaseToken', '$firebaseToken');
                  // Notify the web page that the token is ready
                  if (typeof window.flutterReady === 'function') {
                    window.flutterReady();
                  }
                ''');
              } catch (e) {
                debugPrint("Error injecting Firebase token: $e");
              }
            }
            setState(() {
              _isLoading = false;
            });
          },
          onWebResourceError: (error) {
            if (!mounted) return;
            setState(() {
              _isLoading = false;
              _hasError = true;
              _errorMessage = error.description;
            });
          },
        ),
      )
      ..loadRequest(Uri.parse(widget.url));
  }

  Future<void> _retryConnection() async {
    print("🔄 Retrying connection...");
    final isHealthy = await ApiService.checkHealth();
    if (isHealthy) {
      final flaskUrl = await ApiService.getFlaskUrl();
      _controller.loadRequest(Uri.parse(flaskUrl));
      if (mounted) {
        setState(() {
          _hasError = false;
          _errorMessage = null;
        });
      }
    } else {
      if (mounted) {
        setState(() {
          _errorMessage =
              "Flask backend is not running. Please start Flask server on port 5000.";
        });
      }
    }
  }

  @override
  Widget build(BuildContext context) {
    return WillPopScope(
      onWillPop: () async {
        // Handle back button press
        _goBack();
        return false; // Prevent default back behavior
      },
      child: Scaffold(
        appBar: AppBar(
          title: const Text('Safora Dashboard'),
          backgroundColor: Colors.pinkAccent,
          leading: IconButton(
            icon: const Icon(Icons.arrow_back),
            onPressed: _goBack,
          ),
          actions: [
            IconButton(
              icon: const Icon(Icons.bug_report),
              onPressed: _debugUserDocuments, // Debug button
            ),
            IconButton(
              icon: const Icon(Icons.sms),
              onPressed: _testAlert, // Test alert button
            ),
            IconButton(
              icon: const Icon(Icons.refresh),
              onPressed: _retryConnection,
            ),
                  // ⭐ TEST FIRESTORE WRITE BUTTON
            IconButton(
              icon: const Icon(Icons.check_circle),
              color: Colors.green,
              tooltip: "Test Firestore Write",
              onPressed: () {
                // Give manual test values
                nameController.text = "Test User";
                phoneController.text = "919175397501";

                print("🔥 TEST: Writing Test User + Number to Firestore...");
                _debugUserDocuments(); // ← will save into Firestore
              },
            ),
          ],
        ),
        body: _hasError
            ? Center(
                child: Column(
                  mainAxisAlignment: MainAxisAlignment.center,
                  children: [
                    Text(_errorMessage ?? 'Failed to connect'),
                    const SizedBox(height: 16),
                    ElevatedButton(
                      onPressed: _retryConnection,
                      child: const Text('Retry'),
                    ),
                  ],
                ),
              )
            : Stack(
                children: [
                  WebViewWidget(controller: _controller),
                  if (_isLoading)
                    const Center(
                      child: CircularProgressIndicator(color: Colors.pinkAccent),
                    ),
                ],
              ),
      ),
    );
  }
}