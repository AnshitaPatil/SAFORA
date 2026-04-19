import 'api_service.dart';
import 'package:flutter/services.dart';
import 'package:firebase_auth/firebase_auth.dart';
import 'package:cloud_firestore/cloud_firestore.dart';
import 'package:geolocator/geolocator.dart';
import 'package:permission_handler/permission_handler.dart';
import 'package:fluttertoast/fluttertoast.dart';
import 'package:flutter/material.dart';
import 'dart:async';
import 'audio_recording_service.dart';
import 'dart:convert';
import 'package:http/http.dart' as http;

class AlertService {
  static final FirebaseAuth _auth = FirebaseAuth.instance;
  static final FirebaseFirestore _firestore = FirebaseFirestore.instance;

  static bool _isAlertRunning = false;
  static DateTime? _lastAlertTime;
  static const Duration _alertCooldown = Duration(minutes: 3);

  // ─── Contact helpers ─────────────────────────────────────────────────────────

  static Future<bool> testSaveContact(String name, String phone) async {
    try {
      final uid = _auth.currentUser?.uid;
      if (uid == null) {
        print("❌ No logged-in user.");
        return false;
      }
      final doc = _firestore.collection('users').doc(uid);
      final contactData = {'name': name, 'phone': phone};
      await doc.update({
        'emergencyContacts': FieldValue.arrayUnion([contactData])
      }).catchError((error) {
        return doc.set({'emergencyContacts': [contactData]});
      });
      print("✅ Test contact saved successfully!");
      return true;
    } catch (e) {
      print("❌ Error saving test contact: $e");
      return false;
    }
  }

  static Future<List<Map<String, dynamic>>> testGetContacts() async {
    try {
      final uid = _auth.currentUser?.uid;
      if (uid == null) {
        print("❌ No logged-in user.");
        return [];
      }
      final doc = await _firestore.collection('users').doc(uid).get();
      if (doc.exists) {
        final contactsData = doc.data()?['emergencyContacts'];
        if (contactsData != null && contactsData is List) {
          return List<Map<String, dynamic>>.from(contactsData);
        }
      }
      return [];
    } catch (e) {
      print("❌ testGetContacts - Error: $e");
      return [];
    }
  }

  // ─── SMS helpers ─────────────────────────────────────────────────────────────

  static Future<bool> sendTestSms() async {
    print("📱 sendTestSms called");
    final sms = await Permission.sms.request();
    final phone = await Permission.phone.request();
    if (!sms.isGranted || !phone.isGranted) {
      print("❌ SMS or Phone permission not granted");
      return false;
    }
    final platform = MethodChannel("sms_sender_channel");
    try {
      const testNumber = "9175397501";
      final result = await platform.invokeMethod("sendSms", {
        "number": testNumber,
        "message": "Test 123",
      });
      return result == true;
    } catch (e) {
      print("❌ Error sending SMS: $e");
      return false;
    }
  }

  static Future<bool> sendRealSms(String number, String message) async {
    print("📱 sendRealSms called with number: $number");
    final sms = await Permission.sms.request();
    final phone = await Permission.phone.request();
    if (!sms.isGranted || !phone.isGranted) {
      print("❌ SMS or Phone permission not granted");
      return false;
    }
    final platform = MethodChannel("sms_sender_channel");
    try {
      final result = await platform.invokeMethod("sendSms", {
        "number": number,
        "message": message,
      }).timeout(const Duration(seconds: 10));
      print("📱 SMS send result for $number: $result");
      return result == true;
    } on PlatformException catch (e) {
      print("❌ Platform exception sending SMS to $number: ${e.message}");
      return false;
    } on TimeoutException catch (e) {
      print("❌ Timeout sending SMS to $number: $e");
      return false;
    } catch (e) {
      print("❌ Error sending SMS to $number: $e");
      return false;
    }
  }

  // ─── MAIN ALERT METHOD ───────────────────────────────────────────────────────

  static Future<void> triggerAutomaticAlert() async {
    print("🚨 Starting automatic alert process...");

    if (_isAlertRunning) {
      print("⚠️ Alert already running, skipping...");
      return;
    }
    _isAlertRunning = true;

    // ✅ BUG 1 FIX — reset _isAlertRunning before returning on cooldown
    final now = DateTime.now();
    if (_lastAlertTime != null &&
        now.difference(_lastAlertTime!) < _alertCooldown) {
      print("⏱ Alert suppressed due to cooldown");
      _isAlertRunning = false;
      return;
    }
    _lastAlertTime = now;

    try {
      final user = _auth.currentUser;
      if (user == null) {
        Fluttertoast.showToast(
          msg: "No user logged in. Cannot send alert.",
          backgroundColor: Colors.red,
          textColor: Colors.white,
        );
        return;
      }

      final uid = user.uid;
      print("👤 User ID: $uid");

      // ✅ Request permissions first
      final statuses = await [
        Permission.sms,
        Permission.microphone,
      ].request();

      if (!statuses[Permission.sms]!.isGranted) {
        Fluttertoast.showToast(
          msg: "SMS permission not granted.",
          backgroundColor: Colors.red,
          textColor: Colors.white,
        );
        return;
      }

      if (!statuses[Permission.microphone]!.isGranted) {
        Fluttertoast.showToast(
          msg: "Microphone permission not granted. Audio evidence won't be captured.",
          backgroundColor: Colors.orange,
          textColor: Colors.white,
        );
      }

      // ✅ Call Flask and use its alertId
      String? alertId;
      try {
        final flaskUrl = await ApiService.detectFlaskUrl();
        final response = await http.post(
          Uri.parse('$flaskUrl/api/trigger_alert'),
          headers: {'Content-Type': 'application/json'},
          body: jsonEncode({'firebaseUid': uid}),
        ).timeout(const Duration(seconds: 5));

        if (response.statusCode == 200) {
          final responseData = jsonDecode(response.body);
          alertId = responseData['alertId'];
          print("✅ Flask alert created — alertId: $alertId");
        } else {
          print("⚠️ Flask returned ${response.statusCode} — will create alert locally");
        }
      } catch (e) {
        print("⚠️ Flask call failed (non-fatal): $e");
      }

      // ✅ Fallback — create alert locally if Flask didn't respond
      if (alertId == null) {
        print("📵 Flask unreachable — Flutter creating fallback alert");
        final docRef = _firestore.collection('alerts').doc();
        alertId = docRef.id;
        await docRef.set({
          'userId': uid,
          'isActive': true,
          'createdAt': FieldValue.serverTimestamp(),
          'lastUpdated': FieldValue.serverTimestamp(),
          'latestVideoUrl': null,
          'location': {'lat': null, 'lng': null},
        });
        print("🧾 Fallback alert created in Firestore: $alertId");
      }

      // ✅ Fetch emergency contacts early so they're ready for both SMS sends
      final userDoc = await _firestore.collection('users').doc(uid).get();
      final contactsData = userDoc.data()?['emergencyContacts'];

      if (contactsData == null ||
          contactsData is! List ||
          contactsData.isEmpty) {
        Fluttertoast.showToast(
          msg: "No emergency contacts found.",
          backgroundColor: Colors.red,
          textColor: Colors.white,
        );
        return;
      }

      // ✅ FIX — extract phone numbers into a plain List<String>
      // so it can be safely passed into the background Future closure
      final List<String> phoneNumbers = (contactsData as List)
          .whereType<Map<String, dynamic>>()
          .map((c) => c['phone']?.toString() ?? '')
          .where((p) => p.isNotEmpty)
          .toList();

      if (phoneNumbers.isEmpty) {
        Fluttertoast.showToast(
          msg: "No valid emergency contacts.",
          backgroundColor: Colors.red,
          textColor: Colors.white,
        );
        return;
      }

      // ✅ Get location and patch onto alert doc
      try {
        final position = await Geolocator.getCurrentPosition(
          desiredAccuracy: LocationAccuracy.high,
        );

        await _firestore.collection('alerts').doc(alertId).update({
          'location': {
            'lat': position.latitude,
            'lng': position.longitude,
          },
          'lastUpdated': FieldValue.serverTimestamp(),
        });
        print("📍 Location patched onto alert $alertId");

        final locationUrl =
            "https://www.google.com/maps?q=${position.latitude},${position.longitude}";

        // ✅ SMS 1 — Send location immediately, don't wait for video
        final locationMessage =
            "🚨 SAFORA ALERT\n"
            "Live Location: $locationUrl\n"
            "Help is needed immediately!";

        print("📤 Sending location SMS immediately...");
        int successCount = 0;
        for (final number in phoneNumbers) {
          final ok = await sendRealSms(number, locationMessage);
          if (ok) successCount++;
        }

        if (successCount > 0) {
          Fluttertoast.showToast(
            msg: "📍 Location alert sent to $successCount contact(s).",
            backgroundColor: Colors.orange,
            textColor: Colors.white,
          );
          print("✅ Location SMS sent to $successCount contact(s)");
        } else {
          Fluttertoast.showToast(
            msg: "Failed to send location SMS.",
            backgroundColor: Colors.red,
            textColor: Colors.white,
          );
        }

        // ✅ SMS 2 — Poll for video URL in background, send when ready
        // Captured variables passed into closure safely as plain types
        final String capturedAlertId = alertId;
        final List<String> capturedPhoneNumbers = List.from(phoneNumbers);

        Future(() async {
          print("⏳ Background: waiting for video URL...");
          String? videoUrl;

          // Initial buffer — give Flask time to finish recording and uploading
          await Future.delayed(const Duration(seconds: 20));

          for (int i = 0; i < 24; i++) { // 24 × 5s = 2 minutes
            await Future.delayed(const Duration(seconds: 5));

            try {
              final alertDoc = await _firestore
                  .collection('alerts')
                  .doc(capturedAlertId)
                  .get();

              final data = alertDoc.data();
              final bool videoReady = data?['videoReady'] == true;
              videoUrl = data?['latestVideoUrl']?.toString();

              if ((videoReady || (videoUrl != null && videoUrl!.isNotEmpty))) {
                print("✅ Video URL confirmed at attempt ${i + 1}: $videoUrl");
                break;
              }

              print("⏳ Video not ready yet... attempt ${i + 1}/24");
            } catch (e) {
              print("❌ Error polling for video URL: $e");
            }
          }

          if (videoUrl != null && videoUrl!.isNotEmpty) {
            final videoMessage =
                "🎥 SAFORA VIDEO EVIDENCE\n"
                "Tap to play: $videoUrl";

            print("📤 Sending video SMS to ${capturedPhoneNumbers.length} contact(s)...");
            int videoSmsCount = 0;
            for (final number in capturedPhoneNumbers) {
              final ok = await sendRealSms(number, videoMessage);
              if (ok) videoSmsCount++;
            }

            Fluttertoast.showToast(
              msg: "🎥 Video evidence sent to $videoSmsCount contact(s).",
              backgroundColor: Colors.green,
              textColor: Colors.white,
            );
            print("✅ Video SMS sent to $videoSmsCount contact(s)");
          } else {
            print("⚠️ Video URL never appeared after 2 minutes — skipping video SMS");
          }
        });

      } catch (e) {
        print("❌ Location/SMS step failed: $e");
      }

      // ✅ Start audio recording and location updates
      AudioRecordingService.start(alertId, uid);
      startLocationUpdates(alertId);

      Future.delayed(const Duration(minutes: 2), () {
        AudioRecordingService.stop();
      });

    } catch (e) {
      print("❌ Error in triggerAutomaticAlert: $e");
      Fluttertoast.showToast(
        msg: "Error sending alert.",
        backgroundColor: Colors.red,
        textColor: Colors.white,
      );
    } finally {
      _isAlertRunning = false;
    }
  }

  // ─── Location updates ────────────────────────────────────────────────────────

  static Timer? _locationTimer;

  static void startLocationUpdates(String alertId) {
    int ticks = 0;
    _locationTimer = Timer.periodic(
      const Duration(seconds: 10),
      (timer) async {
        ticks++;
        if (ticks > 12) {
          timer.cancel();
          print("🛑 Location updates stopped");
          return;
        }
        try {
          final position = await Geolocator.getCurrentPosition(
            desiredAccuracy: LocationAccuracy.high,
          );
          await _firestore.collection('alerts').doc(alertId).update({
            'location': {
              'lat': position.latitude,
              'lng': position.longitude,
            },
            'lastUpdated': FieldValue.serverTimestamp(),
          });
          print("📍 Location updated for alert $alertId");
        } catch (e) {
          print("❌ Location update failed: $e");
        }
      },
    );
  }

  // ─── Firestore trigger listener ──────────────────────────────────────────────

  static StreamSubscription<DocumentSnapshot>? _triggerListener;

  static void startAlertTriggerListener() {
    print("👂 Starting Firestore alert trigger listener");

    // ✅ Pre-create doc so listener never misses the first write
    _firestore
        .collection('alert_triggers')
        .doc('current')
        .set(
          {'active': false, 'triggeredAt': null, 'source': 'init'},
          SetOptions(merge: true),
        );

    _triggerListener = _firestore
        .collection('alert_triggers')
        .doc('current')
        .snapshots()
        .listen((snapshot) async {
      if (!snapshot.exists) return;
      final data = snapshot.data() as Map<String, dynamic>?;
      if (data == null) return;
      if (data['active'] != true) return;
      if (_isAlertRunning) return;

      // ✅ BUG 4 FIX — source tag system
      // 'audio' → Firestore listener handles it (Flask audio thread)
      // 'sensor' → sensor loop in flask_webview_page handles it
      // 'init'   → ignored by both
      final source = data['source']?.toString() ?? '';
      if (source == 'sensor') {
        print("⏭ Source is sensor — sensor loop owns this, skipping");
        await _firestore
            .collection('alert_triggers')
            .doc('current')
            .update({'active': false});
        return;
      }

      print("🔔 Firestore bell rang from Flask (source: $source) — firing alert");

      // Silence the bell before firing to prevent re-entry
      await _firestore
          .collection('alert_triggers')
          .doc('current')
          .update({'active': false});

      await triggerAutomaticAlert();
    }, onError: (e) {
      print("❌ Firestore trigger listener error: $e");
    });
  }

  static void stopAlertTriggerListener() {
    print("🛑 Stopping Firestore alert trigger listener");
    _triggerListener?.cancel();
    _triggerListener = null;
  }
}