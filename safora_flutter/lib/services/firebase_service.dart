// lib/services/firebase_service.dart
import 'package:firebase_core/firebase_core.dart';
import 'package:flutter/material.dart';

class FirebaseService {
  static Future<void> initializeFirebase() async {
    try {
      WidgetsFlutterBinding.ensureInitialized();
      await Firebase.initializeApp();
    } catch (e) {
      debugPrint("Firebase initialization error: $e");
    }
  }
}
