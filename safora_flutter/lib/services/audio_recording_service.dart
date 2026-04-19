import 'dart:async';
import 'dart:io';
import 'package:record/record.dart';
import 'package:path_provider/path_provider.dart';
import 'package:http/http.dart' as http;
import '../services/api_service.dart';

class AudioRecordingService {
  static final Record _recorder = Record();
  static Timer? _cadenceTimer;
  static bool _isRecording = false;
  static bool _isActive = false;
  static int _clipIndex = 0;

  static String? _alertId;
  static String? _firebaseUid;

  // ── Tuneable constants ──────────────────────────────────────────
  static const int clipDurationSeconds = 20;
  static const int cadenceSeconds = 90;
  // ───────────────────────────────────────────────────────────────

  /// Call this right after alert is created in AlertService
  static Future<void> start(String alertId, String uid) async {
    if (_isActive) {
      print("⚠️ AudioRecordingService already active, skipping start");
      return;
    }

    _alertId = alertId;
    _firebaseUid = uid;
    _clipIndex = 0;
    _isActive = true;

    print("🎙️ AudioRecordingService starting for alert: $alertId");

    // Check mic permission
    final hasPermission = await _recorder.hasPermission();
    if (!hasPermission) {
      print("❌ Microphone permission denied — audio recording aborted");
      _isActive = false;
      return;
    }

    // Record first chunk immediately
    await _recordAndUploadChunk();

    // Then repeat every cadenceSeconds
    _cadenceTimer = Timer.periodic(
      Duration(seconds: cadenceSeconds),
      (_) async {
        if (!_isActive) return;
        await _recordAndUploadChunk();
      },
    );
  }

  /// Call this when alert is cancelled or resolved
  static Future<void> stop() async {
    print("🛑 AudioRecordingService stopping");
    _isActive = false;

    _cadenceTimer?.cancel();
    _cadenceTimer = null;

    if (_isRecording) {
      try {
        await _recorder.stop();
      } catch (e) {
        print("⚠️ Error stopping recorder on service stop: $e");
      }
      _isRecording = false;
    }

    _alertId = null;
    _firebaseUid = null;
    _clipIndex = 0;
  }

  // ── Private helpers ─────────────────────────────────────────────

  static Future<void> _recordAndUploadChunk() async {
    if (!_isActive) {
      print("⚠️ Skipping chunk — service inactive");
      return;
    }

    if (_isRecording) {
      print("⚠️ Already recording, skipping overlap");
      return;
    }

    final int thisIndex = _clipIndex;
    _clipIndex++;

    try {
      final dir = await getTemporaryDirectory();
      final filePath = '${dir.path}/safora_chunk_$thisIndex.m4a';

      print("🔴 Recording audio chunk $thisIndex...");
      _isRecording = true;

      await _recorder.start(
        path: filePath,
        encoder: AudioEncoder.aacLc,
        bitRate: 64000,   // 64kbps — good quality, small file size
        samplingRate: 22050,
      );

      // Record for clipDurationSeconds
      await Future.delayed(Duration(seconds: clipDurationSeconds));

      if (!_isRecording) {
        // stop() was called mid-recording
        return;
      }

      await _recorder.stop();
      _isRecording = false;
      print("⏹ Chunk $thisIndex recorded: $filePath");

      // Upload in background — don't await so cadence timer isn't blocked
      _uploadChunk(filePath, thisIndex);

    } catch (e) {
      _isRecording = false;
      print("❌ Error recording chunk $thisIndex: $e");
    }
  }

  static Future<void> _uploadChunk(String filePath, int index) async {
    if (_alertId == null || _firebaseUid == null) {
      print("❌ Missing alertId or uid — cannot upload chunk $index");
      return;
    }

    try {
      print("☁️ Uploading chunk $index to Flask...");

      final flaskUrl = await ApiService.detectFlaskUrl();
      final uri = Uri.parse("$flaskUrl/api/upload_clip");

      final request = http.MultipartRequest('POST', uri)
        ..fields['alert_id']     = _alertId!
        ..fields['firebase_uid'] = _firebaseUid!
        ..fields['clip_index']   = index.toString()
        ..files.add(
            await http.MultipartFile.fromPath('clip', filePath));

      final streamed = await request.send()
          .timeout(const Duration(seconds: 30));
      final response = await http.Response.fromStream(streamed);

      if (response.statusCode == 200) {
        print("✅ Chunk $index uploaded successfully");
      } else {
        print("⚠️ Chunk $index upload failed: ${response.body}");
      }

      // Clean up local temp file
      try {
        await File(filePath).delete();
      } catch (_) {}

    } catch (e) {
      print("❌ Upload error for chunk $index: $e");
    }
  }
}