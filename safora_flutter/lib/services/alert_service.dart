import 'package:flutter/services.dart';
import 'package:firebase_auth/firebase_auth.dart';
import 'package:cloud_firestore/cloud_firestore.dart';
import 'package:firebase_storage/firebase_storage.dart';
import 'package:geolocator/geolocator.dart';
import 'package:record/record.dart';
import 'package:camera/camera.dart';
import 'package:intl/intl.dart';
import 'package:path_provider/path_provider.dart';
import 'package:permission_handler/permission_handler.dart';
import 'package:url_launcher/url_launcher.dart';
import 'package:fluttertoast/fluttertoast.dart';
import 'package:flutter/material.dart';
import 'dart:io';
import 'dart:async';

class AlertService {
  static final FirebaseAuth _auth = FirebaseAuth.instance;
  static final FirebaseFirestore _firestore = FirebaseFirestore.instance;
  static final FirebaseStorage _storage = FirebaseStorage.instance;
  static final Record _recorder = Record();

  static bool _isAlertRunning = false;

  // Test function to verify contacts can be saved
  static Future<bool> testSaveContact(String name, String phone) async {
    try {
      final uid = _auth.currentUser?.uid;
      if (uid == null) {
        print("❌ No logged-in user.");
        return false;
      }

      final doc = _firestore.collection('users').doc(uid);  // Correct collection name
      final contactData = {
        'name': name,
        'phone': phone,
      };

      await doc.update({
        'emergencyContacts': FieldValue.arrayUnion([contactData])
      }).catchError((error) {
        // If document doesn't exist, create it
        return doc.set({
          'emergencyContacts': [contactData]
        });
      });

      print("✅ Test contact saved successfully!");
      return true;
    } catch (e) {
      print("❌ Error saving test contact: $e");
      return false;
    }
  }

  // Test function to verify contacts can be retrieved
  static Future<List<Map<String, dynamic>>> testGetContacts() async {
    try {
      final uid = _auth.currentUser?.uid;
      if (uid == null) {
        print("❌ No logged-in user.");
        return [];
      }

      print("🔍 testGetContacts - User ID: $uid");
      final doc = await _firestore.collection('users').doc(uid).get();  // Correct collection name
      
      print("📄 testGetContacts - Document exists: ${doc.exists}");
      if (doc.exists) {
        print("📄 testGetContacts - Document data: ${doc.data()}");
        final contactsData = doc.data()?['emergencyContacts'];
        print("📱 testGetContacts - Contacts data: $contactsData");
        if (contactsData != null && contactsData is List) {
          return List<Map<String, dynamic>>.from(contactsData);
        }
      }
      
      print("ℹ️ testGetContacts - No contacts found or document doesn't exist");
      return [];
    } catch (e) {
      print("❌ testGetContacts - Error retrieving test contacts: $e");
      return [];
    }
  }

  static Future<bool> sendTestSms() async {
    print("📱 sendTestSms called");
    
    // Request permissions
    final sms = await Permission.sms.request();
    final phone = await Permission.phone.request();

    if (!sms.isGranted || !phone.isGranted) {
      print("❌ SMS or Phone permission not granted");
      return false;
    }

    final platform = MethodChannel("sms_sender_channel");

    try {
      const testNumber = "9175397501";  // <<< PUT YOUR NUMBER HERE

      print("📤 Sending test SMS to: $testNumber");
      final result = await platform.invokeMethod(
        "sendSms",
        {
          "number": testNumber,
          "message": "Test 123",
        },
      );

      if (result == true) {
        print("✅ Native SMS send request sent!");
        return true;
      } else {
        print("❌ Native SMS send failed");
        return false;
      }
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
      print("📤 Attempting to send SMS to: $number");
      print("📝 Message: $message");
      
      // Add a timeout to prevent hanging
      final result = await platform.invokeMethod(
        "sendSms",
        {
          "number": number,
          "message": message,
        },
      ).timeout(const Duration(seconds: 10)); // Add timeout

      print("📱 SMS send result for $number: $result");
      return result == true;
    } on PlatformException catch (e) {
      print("❌ Platform exception sending SMS to $number: ${e.message}");
      print("📜 Platform exception details: ${e.details}");
      return false;
    } on TimeoutException catch (e) {
      print("❌ Timeout sending SMS to $number: $e");
      return false;
    } catch (e) {
      print("❌ Error sending SMS to $number: $e");
      return false;
    }
  }

  /// 🚨 MAIN METHOD - trigger automatic alert
  static Future<void> triggerAutomaticAlert() async {
    print("🚨 Starting automatic alert process...");
    
    if (_isAlertRunning) {
      print("⚠️ Alert already running, skipping...");
      return;
    }
    _isAlertRunning = true;

    try {
      final user = _auth.currentUser;
      print("👤 Current user: $user");
      
      if (user == null) {
        print("❌ No logged-in user. Cannot send alert.");
        Fluttertoast.showToast(
          msg: "No user logged in. Cannot send alert.",
          toastLength: Toast.LENGTH_LONG,
          gravity: ToastGravity.BOTTOM,
          backgroundColor: Colors.red,
          textColor: Colors.white,
        );
        return;
      }
      
      final uid = user.uid;
      print("👤 Current user ID: $uid");
      print("📧 Current user email: ${user.email}");

      // ✅ Request SMS permission explicitly
      final smsStatus = await Permission.sms.request();
      if (!smsStatus.isGranted) {
        print("❌ SMS permission not granted. Cannot send alert.");
        Fluttertoast.showToast(
          msg: "SMS permission not granted. Cannot send alert.",
          toastLength: Toast.LENGTH_LONG,
          gravity: ToastGravity.BOTTOM,
          backgroundColor: Colors.red,
          textColor: Colors.white,
        );
        return;
      }

      // ✅ Step 1: Fetch emergency contacts - IMPROVED IMPLEMENTATION
      List<String> phoneNumbers = [];
      
      try {
        print("🔍 Attempting to fetch emergency contacts for user: $uid");
        
        // Fetch from the user document's emergencyContacts field
        final userDoc = await _firestore.collection('users').doc(uid).get();  // Correct collection name
        
        print("📄 User document exists: ${userDoc.exists}");
        
        if (userDoc.exists) {
          // Print the entire document data for debugging
          print("📄 User document data: ${userDoc.data()}");
          
          // Check if emergencyContacts field exists in the user document
          final contactsData = userDoc.data()?['emergencyContacts'];
          print("📱 Contacts data: $contactsData");
          print("📱 Contacts data type: ${contactsData.runtimeType}");
          
          if (contactsData != null && contactsData is List) {
            print("✅ Found ${contactsData.length} contacts");
            
            // Process each contact
            for (int i = 0; i < contactsData.length; i++) {
              final contact = contactsData[i];
              print("📱 Contact $i: $contact (type: ${contact.runtimeType})");
              
              if (contact is Map<String, dynamic>) {
                final phone = contact['phone']?.toString();
                if (phone != null && phone.isNotEmpty) {
                  phoneNumbers.add(phone);
                  print("✅ Added phone number: $phone");
                } else {
                  print("⚠️ Invalid phone for contact $i: $contact");
                }
              } else {
                print("⚠️ Contact $i is not a Map: $contact");
              }
            }
            
            print("✅ Emergency contacts fetched from user document: $phoneNumbers");
          } else {
            print("⚠️ No emergencyContacts field found in user document or it's not a List");
            print("📱 Actual contactsData: $contactsData");
          }
        } else {
          print("⚠️ User document does not exist");
          
          // Let's try to see what documents actually exist
          print("🔍 Checking what user documents exist...");
          final usersCollection = await _firestore.collection('users').limit(10).get();
          print("📄 Found ${usersCollection.docs.length} user documents:");
          for (var doc in usersCollection.docs) {
            print("   - Document ID: ${doc.id}");
            print("   - Document data: ${doc.data()}");
          }
        }
      } catch (e) {
        print("⚠️ Error fetching emergency contacts: $e");
        // Print stack trace for better debugging
        print("⚠️ Stack trace: ${e.toString()}");
        Fluttertoast.showToast(
          msg: "Error fetching contacts: ${e.toString()}",
          toastLength: Toast.LENGTH_LONG,
          gravity: ToastGravity.BOTTOM,
          backgroundColor: Colors.red,
          textColor: Colors.white,
        );
      }

      if (phoneNumbers.isEmpty) {
        print("⚠️ No emergency contacts found.");
        Fluttertoast.showToast(
          msg: "No emergency contacts found.",
          toastLength: Toast.LENGTH_LONG,
          gravity: ToastGravity.BOTTOM,
          backgroundColor: Colors.red,
          textColor: Colors.white,
        );
        return;
      }

      print("📞 Found ${phoneNumbers.length} emergency contacts: $phoneNumbers");

      // ✅ Step 2: Get live location
      print("📍 Getting live location...");
      final position = await Geolocator.getCurrentPosition(
          desiredAccuracy: LocationAccuracy.high);
      final locationUrl =
          "https://www.google.com/maps?q=${position.latitude},${position.longitude}";
      print("📍 Location URL: $locationUrl");

      // ✅ Step 3: Record short audio
      print("🎤 Recording audio...");
      final audioPath = await _recordAudio();
      print("🎤 Audio recorded to: $audioPath");
      final audioUrl = await _uploadFile(audioPath, 'audio');
      print("🎤 Audio uploaded to: $audioUrl");

      // ✅ Step 4: Record short video
      print("🎥 Recording video...");
      final videoPath = await _recordVideo();
      print("🎥 Video recorded to: $videoPath");
      final videoUrl = await _uploadFile(videoPath, 'video');
      print("🎥 Video uploaded to: $videoUrl");

      // ✅ Step 5: Send SMS to all contacts
      final message =
          "🚨 SAFORA ALERT!\nPossible threat detected.\nLive Location: $locationUrl\n"
          "Audio: $audioUrl\nVideo: $videoUrl\nStay safe!";

      print("📱 Sending SMS to ${phoneNumbers.length} contacts...");
      print("📝 Message content:\n$message");

      int successCount = 0;
      for (String number in phoneNumbers) {
        print("📱 Sending SMS to: $number");
        bool ok = await sendRealSms(number, message);

        if (ok) {
          print("✅ SMS sent to $number");
          successCount++;
        } else {
          print("❌ Failed to send SMS to $number");
        }
      }

      // Show success or partial success message
      if (successCount > 0) {
        Fluttertoast.showToast(
          msg: "Alert sent successfully to $successCount/${phoneNumbers.length} contacts!",
          toastLength: Toast.LENGTH_LONG,
          gravity: ToastGravity.BOTTOM,
          backgroundColor: Colors.green,
          textColor: Colors.white,
        );
        print("✅ Alert process completed. Sent to $successCount/${phoneNumbers.length} contacts: $phoneNumbers");
      } else {
        Fluttertoast.showToast(
          msg: "Failed to send alert to any contacts.",
          toastLength: Toast.LENGTH_LONG,
          gravity: ToastGravity.BOTTOM,
          backgroundColor: Colors.red,
          textColor: Colors.white,
        );
        print("❌ Alert process failed. Sent to $successCount/${phoneNumbers.length} contacts: $phoneNumbers");
      }
    } catch (e) {
      print("❌ Error sending alert: $e");
      print("❌ Stack trace: ${e.toString()}");
      Fluttertoast.showToast(
        msg: "Error sending alert: ${e.toString()}",
        toastLength: Toast.LENGTH_LONG,
        gravity: ToastGravity.BOTTOM,
        backgroundColor: Colors.red,
        textColor: Colors.white,
      );
    } finally {
      _isAlertRunning = false;
    }
  }

  /// 🎙️ Record short 5-second audio (for record: ^4.4.4)
  static Future<String> _recordAudio() async {
    try {
      final dir = await getTemporaryDirectory();
      final filePath =
          '${dir.path}/audio_${DateFormat('yyyyMMdd_HHmmss').format(DateTime.now())}.m4a';

      if (await _recorder.hasPermission()) {
        await _recorder.start(
          path: filePath,
          encoder: AudioEncoder.aacLc,
          bitRate: 128000,
          samplingRate: 44100,
        );

        await Future.delayed(const Duration(seconds: 5));
        await _recorder.stop();
        return filePath;
      } else {
        throw Exception("No microphone permission");
      }
    } catch (e) {
      print("Audio recording error: $e");
      rethrow;
    }
  }

  /// 🎥 Record short 5-second video
  static Future<String> _recordVideo() async {
    try {
      final cameras = await availableCameras();
      final controller =
          CameraController(cameras.first, ResolutionPreset.medium);
      await controller.initialize();

      final dir = await getTemporaryDirectory();
      final filePath =
          '${dir.path}/video_${DateFormat('yyyyMMdd_HHmmss').format(DateTime.now())}.mp4';

      await controller.startVideoRecording();
      await Future.delayed(const Duration(seconds: 5));
      final file = await controller.stopVideoRecording();
      await controller.dispose();

      await file.saveTo(filePath);
      return filePath;
    } catch (e) {
      print("Video recording error: $e");
      rethrow;
    }
  }

  /// ☁️ Upload file to Firebase Storage
  static Future<String> _uploadFile(String filePath, String type) async {
    try {
      final file = File(filePath);
      final ref = _storage.ref().child(
          'alerts/${_auth.currentUser?.uid}/${type}_${DateFormat('yyyyMMdd_HHmmss').format(DateTime.now())}.${type == 'audio' ? 'm4a' : 'mp4'}');
      await ref.putFile(file);
      return await ref.getDownloadURL();
    } catch (e) {
      print("File upload error: $e");
      return "Upload failed";
    }
  }
}