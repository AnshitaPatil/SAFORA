import 'dart:async';
import 'dart:io';
import 'package:camera/camera.dart';
import 'package:path_provider/path_provider.dart';
import 'package:firebase_auth/firebase_auth.dart';
import 'package:http/http.dart' as http;
import 'package:intl/intl.dart';
import '../services/api_service.dart';

class VideoRecordingService {
  static CameraController? _controller;
  static Timer? _cadenceTimer;
  static bool _isRecording = false;
  static bool _isActive = false;
  static int _clipIndex = 0;

  static String? _alertId;
  static String? _firebaseUid;

  // ── Tuneable constants ──────────────────────────────────────────
  static const int clipDurationSeconds = 20;
  static const int cadenceSeconds = 90; // gap between clip starts
  // ───────────────────────────────────────────────────────────────

  /// Call this right after alert is created in AlertService
  static Future<void> start(String alertId, String uid) async {
    if (_isActive) {
      print("⚠️ VideoRecordingService already active, skipping start");
      return;
    }

    _alertId = alertId;
    _firebaseUid = uid;
    _clipIndex = 0;
    _isActive = true;

    print("🎥 VideoRecordingService starting for alert: $alertId");

    // Initialise rear camera
    final bool ready = await _initCamera();
    if (!ready) {
      print("❌ Camera init failed — video recording aborted");
      _isActive = false;
      return;
    }

    // Record first clip immediately
    await _recordAndUploadClip();

    // Then repeat every cadenceSeconds
    _cadenceTimer = Timer.periodic(
      Duration(seconds: cadenceSeconds),
      (_) async {
        if (!_isActive) return;
        await _recordAndUploadClip();
      },
    );
  }

  /// Call this when alert is cancelled or resolved
  static Future<void> stop() async {
    print("🛑 VideoRecordingService stopping");
    _isActive = false;

    _cadenceTimer?.cancel();
    _cadenceTimer = null;

    if (_isRecording) {
      try {
        await _controller?.stopVideoRecording();
      } catch (e) {
        print("⚠️ Error stopping recording on service stop: $e");
      }
      _isRecording = false;
    }

    await _disposeCamera();

    _alertId = null;
    _firebaseUid = null;
    _clipIndex = 0;
  }

  // ── Private helpers ─────────────────────────────────────────────

  static Future<bool> _initCamera() async {
    try {
      final cameras = await availableCameras();
      if (cameras.isEmpty) {
        print("❌ No cameras available");
        return false;
      }

      // Rear camera = cameras where lensDirection is back
      final rear = cameras.firstWhere(
        (c) => c.lensDirection == CameraLensDirection.back,
        orElse: () => cameras.first, // fallback to whatever is available
      );

      _controller = CameraController(
        rear,
        ResolutionPreset.medium, // medium = good quality, reasonable file size
        enableAudio: true,       // capture ambient audio too
      );

      await _controller!.initialize();
      print("✅ Rear camera initialised");
      return true;
    } catch (e) {
      print("❌ Camera init error: $e");
      return false;
    }
  }

  static Future<void> _disposeCamera() async {
    try {
      await _controller?.dispose();
      _controller = null;
      print("📷 Camera disposed");
    } catch (e) {
      print("⚠️ Camera dispose error: $e");
    }
  }

  static Future<void> _recordAndUploadClip() async {
    if (!_isActive || _controller == null || !_controller!.value.isInitialized) {
      print("⚠️ Skipping clip — service inactive or camera not ready");
      return;
    }

    if (_isRecording) {
      print("⚠️ Already recording, skipping overlap");
      return;
    }

    final int thisIndex = _clipIndex;
    _clipIndex++;

    try {
      print("🔴 Recording clip $thisIndex...");
      _isRecording = true;
      await _controller!.startVideoRecording();

      // Record for clipDurationSeconds
      await Future.delayed(Duration(seconds: clipDurationSeconds));

      if (!_isRecording) {
        // stop() was called mid-recording, bail out cleanly
        return;
      }

      final XFile videoFile = await _controller!.stopVideoRecording();
      _isRecording = false;
      print("⏹ Clip $thisIndex recorded: ${videoFile.path}");

      // Upload in background — don't await so cadence timer isn't blocked
      _uploadClip(videoFile.path, thisIndex);
    } catch (e) {
      _isRecording = false;
      print("❌ Error recording clip $thisIndex: $e");
    }
  }

  static Future<void> _uploadClip(String filePath, int index) async {
    if (_alertId == null || _firebaseUid == null) {
      print("❌ Missing alertId or uid — cannot upload clip $index");
      return;
    }

    try {
      print("☁️ Uploading clip $index to Flask...");

      final flaskUrl = await ApiService.detectFlaskUrl();
      final uri = Uri.parse("$flaskUrl/api/upload_clip");

      final request = http.MultipartRequest('POST', uri)
        ..fields['alert_id']    = _alertId!
        ..fields['firebase_uid'] = _firebaseUid!
        ..fields['clip_index']  = index.toString()
        ..files.add(
            await http.MultipartFile.fromPath('clip', filePath));

      final streamed = await request.send()
          .timeout(const Duration(seconds: 30));
      final response = await http.Response.fromStream(streamed);

      if (response.statusCode == 200) {
        print("✅ Clip $index uploaded successfully");
      } else {
        print("⚠️ Clip $index upload failed: ${response.body}");
      }

      // Clean up local temp file regardless of upload result
      try {
        await File(filePath).delete();
      } catch (_) {}
    } catch (e) {
      print("❌ Upload error for clip $index: $e");
    }
  }
}