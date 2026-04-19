import 'package:sensors_plus/sensors_plus.dart';
import 'dart:async';
import 'dart:math';

class SensorService {
  static StreamSubscription<AccelerometerEvent>? _accelerometerSubscription;
  static StreamSubscription<GyroscopeEvent>? _gyroscopeSubscription;

  // ✅ Adjusted thresholds (same as your original)
  static const double SHAKE_THRESHOLD = 18.0;
  static const double MOTION_THRESHOLD = 6.0;
  static const double GYRO_ROTATION_THRESHOLD = 1.8;
  static const int STABLE_COUNT_REQUIRED = 4;
  static const int BUFFER_SIZE = 20;

  static final List<double> _accelMagnitudes = [];
  static final List<double> _gyroMagnitudes = [];

  static int _accelAbnormalCount = 0;
  static int _gyroAbnormalCount = 0;

  static bool _accelerometerThreat = false;
  static bool _gyroscopeThreat = false;

  static const double _alphaLow = 0.8;
  static const double _alphaSmooth = 0.2;

  static double _gravityX = 0.0;
  static double _gravityY = 0.0;
  static double _gravityZ = 0.0;

  static double _filteredGyroX = 0.0;
  static double _filteredGyroY = 0.0;
  static double _filteredGyroZ = 0.0;

  static double _currentAccelX = 0.0;
  static double _currentAccelY = 0.0;
  static double _currentAccelZ = 0.0;
  static double _currentGyroX = 0.0;
  static double _currentGyroY = 0.0;
  static double _currentGyroZ = 0.0;

  static void resetDetections() {
    _accelerometerThreat = false;
    _gyroscopeThreat = false;
    _accelAbnormalCount = 0;
    _gyroAbnormalCount = 0;
    _accelMagnitudes.clear();
    _gyroMagnitudes.clear();
  }

  static Future<void> startMonitoring() async {
    resetDetections();

    _accelerometerSubscription = accelerometerEventStream().listen(
      (event) => _processAccelerometer(event.x, event.y, event.z),
    );

    _gyroscopeSubscription = gyroscopeEventStream().listen(
      (event) => _processGyroscope(event.x, event.y, event.z),
    );
  }

  static void stopMonitoring() {
    _accelerometerSubscription?.cancel();
    _gyroscopeSubscription?.cancel();
  }

  /// ✅ FIXED ACCELEROMETER (noise filtered + proper decay)
  static void _processAccelerometer(double x, double y, double z) {
    _gravityX = _alphaLow * _gravityX + (1 - _alphaLow) * x;
    _gravityY = _alphaLow * _gravityY + (1 - _alphaLow) * y;
    _gravityZ = _alphaLow * _gravityZ + (1 - _alphaLow) * z;

    double linearX = x - _gravityX;
    double linearY = y - _gravityY;
    double linearZ = z - _gravityZ;

    _currentAccelX = linearX;
    _currentAccelY = linearY;
    _currentAccelZ = linearZ;

    double magnitude = sqrt(
      linearX * linearX +
      linearY * linearY +
      linearZ * linearZ
    );

    // ✅ Ignore tiny noise
    if (magnitude < 2.5) return;

    if (magnitude > SHAKE_THRESHOLD) {
      _accelAbnormalCount++;
    } else {
      // ✅ Faster decay when stable
      _accelAbnormalCount = max(0, _accelAbnormalCount - 2);
    }

    _accelerometerThreat = _accelAbnormalCount >= STABLE_COUNT_REQUIRED;
  }

  /// ✅ FIXED GYROSCOPE (noise filtered + proper decay)
  static void _processGyroscope(double x, double y, double z) {
    _filteredGyroX = _alphaSmooth * x + (1 - _alphaSmooth) * _filteredGyroX;
    _filteredGyroY = _alphaSmooth * y + (1 - _alphaSmooth) * _filteredGyroY;
    _filteredGyroZ = _alphaSmooth * z + (1 - _alphaSmooth) * _filteredGyroZ;

    _currentGyroX = _filteredGyroX;
    _currentGyroY = _filteredGyroY;
    _currentGyroZ = _filteredGyroZ;

    double magnitude = sqrt(
      _filteredGyroX * _filteredGyroX +
      _filteredGyroY * _filteredGyroY +
      _filteredGyroZ * _filteredGyroZ
    );

    // ✅ Ignore micro rotation noise
    if (magnitude < 0.5) return;

    if (magnitude > GYRO_ROTATION_THRESHOLD) {
      _gyroAbnormalCount++;
    } else {
      _gyroAbnormalCount = max(0, _gyroAbnormalCount - 2);
    }

    _gyroscopeThreat = _gyroAbnormalCount >= STABLE_COUNT_REQUIRED;
  }

  static Map<String, dynamic> getDetectionResults() {
    return {
      'accelerometer': _accelerometerThreat,
      'gyroscope': _gyroscopeThreat,
      'accelX': _currentAccelX,
      'accelY': _currentAccelY,
      'accelZ': _currentAccelZ,
      'gyroX': _currentGyroX,
      'gyroY': _currentGyroY,
      'gyroZ': _currentGyroZ,
    };
  }

  static bool isAccelerometerThreat() => _accelerometerThreat;
  static bool isGyroscopeThreat() => _gyroscopeThreat;
}