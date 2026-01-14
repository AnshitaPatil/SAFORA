// lib/services/api_service.dart
import 'dart:convert';
import 'dart:io';
import 'package:http/http.dart' as http;

class ApiService {
  // ✅ Use your actual network IP (from Flask logs)
  static const String _defaultLocalIp = "http://192.168.1.9:5000";

  /// ✅ Automatically detects Flask server URL
  static Future<String> detectFlaskUrl() async {
    final testUrls = [
      if (Platform.isAndroid) "http://192.168.1.9:5000", // Android emulator
      if (Platform.isIOS) "http://localhost:5000", // iOS simulator
      _defaultLocalIp,
    ];

    for (String url in testUrls) {
      try {
        final response = await http
            .get(Uri.parse("$url/health"))
            .timeout(const Duration(seconds: 2));
        if (response.statusCode == 200) {
          print("✅ Connected to Flask at $url");
          return url;
        }
      } catch (_) {
        continue;
      }
    }

    print("⚠️ Falling back to default IP: $_defaultLocalIp");
    return _defaultLocalIp;
  }

  /// ✅ Health check to verify Flask is running
  static Future<bool> checkHealth() async {
    try {
      final flaskUrl = await detectFlaskUrl();
      final response = await http
          .get(Uri.parse("$flaskUrl/health"))
          .timeout(const Duration(seconds: 3));
      return response.statusCode == 200;
    } catch (e) {
      print("⚠️ Flask health check failed: $e");
      return false;
    }
  }

  /// ✅ Login API
  static Future<Map<String, dynamic>?> login(String email, String password) async {
    final flaskUrl = await detectFlaskUrl();
    final url = Uri.parse("$flaskUrl/api/login"); // ✅ matches Flask endpoint now
    try {
      final response = await http.post(
        url,
        headers: {"Content-Type": "application/json"},
        body: jsonEncode({"email": email, "password": password}),
      );

      if (response.statusCode == 200) {
        return jsonDecode(response.body);
      } else {
        print("Login Error: ${response.body}");
        return null;
      }
    } catch (e) {
      print("Error connecting to Flask: $e");
      return null;
    }
  }

  /// ✅ Register API
  static Future<Map<String, dynamic>?> register(String email, String password) async {
    final flaskUrl = await detectFlaskUrl();
    final url = Uri.parse("$flaskUrl/api/register");
    try {
      final response = await http.post(
        url,
        headers: {"Content-Type": "application/json"},
        body: jsonEncode({"email": email, "password": password}),
      );

      if (response.statusCode == 200) {
        return jsonDecode(response.body);
      } else {
        print("Register Error: ${response.body}");
        return null;
      }
    } catch (e) {
      print("Error connecting to Flask: $e");
      return null;
    }
  }

  /// ✅ Forgot Password API
  static Future<Map<String, dynamic>?> forgotPassword(String email) async {
    final flaskUrl = await detectFlaskUrl();
    final url = Uri.parse("$flaskUrl/api/forgot-password");
    try {
      final response = await http.post(
        url,
        headers: {"Content-Type": "application/json"},
        body: jsonEncode({"email": email}),
      );

      if (response.statusCode == 200) {
        return jsonDecode(response.body);
      } else {
        print("Forgot Password Error: ${response.body}");
        return null;
      }
    } catch (e) {
      print("Error connecting to Flask: $e");
      return null;
    }
  }

  /// ✅ Trigger alert manually (used in threat detection)
  static Future<void> triggerAlert(Map<String, dynamic> alertData) async {
    try {
      final flaskUrl = await detectFlaskUrl();
      final response = await http.post(
        Uri.parse("$flaskUrl/api/trigger_alert"),
        headers: {'Content-Type': 'application/json'},
        body: jsonEncode(alertData),
      );
      if (response.statusCode != 200) {
        print("⚠️ Flask trigger_alert response: ${response.body}");
      } else {
        print("🚨 Alert successfully sent to Flask backend!");
      }
    } catch (e) {
      print("Error triggering alert: $e");
    }
  }

  /// ✅ Get Flask URL for WebView
  static Future<String> getFlaskUrl() async {
    return await detectFlaskUrl();
  }
}
