"""
Sensor-based threat detection
Detects threats from accelerometer and gyroscope data
"""
import logging
import math
from collections import deque

# Detection thresholds
FALL_THRESHOLD = 9.5  # m/s² - sudden drop
SHAKE_THRESHOLD = 15.0  # m/s² - high acceleration
CRUSH_THRESHOLD = 10.0  # rad/s - rapid rotation
MOTION_THRESHOLD = 8.0  # m/s² - unusual motion
STRUGGLE_THRESHOLD = 12.0  # m/s² - irregular patterns

class SensorDetector:
    def __init__(self, buffer_size=10):
        self.buffer_size = buffer_size
        self.accel_x_buffer = deque(maxlen=buffer_size)
        self.accel_y_buffer = deque(maxlen=buffer_size)
        self.accel_z_buffer = deque(maxlen=buffer_size)
        self.gyro_x_buffer = deque(maxlen=buffer_size)
        self.gyro_y_buffer = deque(maxlen=buffer_size)
        self.gyro_z_buffer = deque(maxlen=buffer_size)
        
        # Detection flags
        self.fall_detected = False
        self.shake_detected = False
        self.struggle_detected = False
        self.motion_detected = False
        self.crush_detected = False
        self.rotation_detected = False
        
    def reset(self):
        """Reset all detection flags"""
        self.fall_detected = False
        self.shake_detected = False
        self.struggle_detected = False
        self.motion_detected = False
        self.crush_detected = False
        self.rotation_detected = False
        self.accel_x_buffer.clear()
        self.accel_y_buffer.clear()
        self.accel_z_buffer.clear()
        self.gyro_x_buffer.clear()
        self.gyro_y_buffer.clear()
        self.gyro_z_buffer.clear()
    
    def process_accelerometer(self, x, y, z):
        """Process accelerometer data and detect threats"""
        # Add to buffers
        self.accel_x_buffer.append(x)
        self.accel_y_buffer.append(y)
        self.accel_z_buffer.append(z)
        
        # Calculate magnitude
        magnitude = math.sqrt(x*x + y*y + z*z)
        
        # Detect fall (sudden drop in magnitude)
        if len(self.accel_z_buffer) >= 3:
            prev_idx = len(self.accel_z_buffer) - 3
            prev_mag = math.sqrt(
                self.accel_x_buffer[prev_idx]**2 +
                self.accel_y_buffer[prev_idx]**2 +
                self.accel_z_buffer[prev_idx]**2
            )
            
            if prev_mag > FALL_THRESHOLD and magnitude < 5.0:
                self.fall_detected = True
                logging.info(f"🚨 FALL DETECTED: {prev_mag:.2f} -> {magnitude:.2f} m/s²")
        
        # Detect shake (high acceleration)
        if magnitude > SHAKE_THRESHOLD:
            self.shake_detected = True
            logging.info(f"🚨 SHAKE DETECTED: {magnitude:.2f} m/s²")
        
        # Detect struggle (irregular patterns)
        if len(self.accel_x_buffer) >= self.buffer_size:
            variance = self._calculate_variance(list(self.accel_x_buffer)) + \
                      self._calculate_variance(list(self.accel_y_buffer)) + \
                      self._calculate_variance(list(self.accel_z_buffer))
            
            if variance > STRUGGLE_THRESHOLD and magnitude > MOTION_THRESHOLD:
                self.struggle_detected = True
                logging.info(f"🚨 STRUGGLE DETECTED: variance={variance:.2f}, magnitude={magnitude:.2f}")
        
        # Detect unusual motion
        if magnitude > MOTION_THRESHOLD and not self._is_normal_motion(magnitude):
            self.motion_detected = True
            logging.info(f"🚨 UNUSUAL MOTION DETECTED: {magnitude:.2f} m/s²")
    
    def process_gyroscope(self, x, y, z):
        """Process gyroscope data and detect threats"""
        # Add to buffers
        self.gyro_x_buffer.append(x)
        self.gyro_y_buffer.append(y)
        self.gyro_z_buffer.append(z)
        
        # Calculate rotation magnitude
        rotation_magnitude = math.sqrt(x*x + y*y + z*z)
        
        # Detect crushing (rapid rotation changes)
        if len(self.gyro_x_buffer) >= 3:
            prev_idx = len(self.gyro_x_buffer) - 3
            prev_rotation = math.sqrt(
                self.gyro_x_buffer[prev_idx]**2 +
                self.gyro_y_buffer[prev_idx]**2 +
                self.gyro_z_buffer[prev_idx]**2
            )
            
            rotation_change = abs(rotation_magnitude - prev_rotation)
            
            if rotation_change > CRUSH_THRESHOLD:
                self.crush_detected = True
                logging.info(f"🚨 CRUSH DETECTED: rotation change={rotation_change:.2f} rad/s")
        
        # Detect rotation (high rotation magnitude)
        if rotation_magnitude > 8.0:
            self.rotation_detected = True
            logging.info(f"🚨 ROTATION DETECTED: {rotation_magnitude:.2f} rad/s")
    
    def _calculate_variance(self, values):
        """Calculate variance of values"""
        if not values:
            return 0.0
        
        mean = sum(values) / len(values)
        variance = sum((v - mean)**2 for v in values) / len(values)
        return variance
    
    def _is_normal_motion(self, magnitude):
        """Check if motion is normal (gravity + small movements)"""
        # Normal motion is around 9.8 (gravity) ± 2
        return 7.8 <= magnitude <= 11.8
    
    def get_accelerometer_threat(self):
        """Check if any accelerometer-based threat is detected"""
        return self.fall_detected or self.shake_detected or self.struggle_detected or self.motion_detected
    
    def get_gyroscope_threat(self):
        """Check if any gyroscope-based threat is detected"""
        return self.crush_detected or self.rotation_detected
    
    def get_all_detections(self):
        """Get all detection results"""
        return {
            'fall': self.fall_detected,
            'shake': self.shake_detected,
            'struggle': self.struggle_detected,
            'motion': self.motion_detected,
            'crush': self.crush_detected,
            'rotation': self.rotation_detected,
            'accelerometer': self.get_accelerometer_threat(),
            'gyroscope': self.get_gyroscope_threat(),
        }

