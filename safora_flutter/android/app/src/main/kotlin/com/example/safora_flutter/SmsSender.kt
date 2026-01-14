package com.example.safora_flutter

import android.Manifest
import android.content.pm.PackageManager
import android.telephony.SmsManager
import android.util.Log
import androidx.core.app.ActivityCompat
import io.flutter.plugin.common.MethodChannel
import io.flutter.plugin.common.BinaryMessenger
import io.flutter.embedding.android.FlutterActivity

class SmsSender(binaryMessenger: BinaryMessenger, private val activity: FlutterActivity) {
    private val CHANNEL = "sms_sender_channel"
    private val TAG = "SmsSender"
    
    private val channel = MethodChannel(binaryMessenger, CHANNEL)

    init {
        channel.setMethodCallHandler { call, result ->
            when (call.method) {
                "sendSms" -> {
                    val number = call.argument<String>("number")
                    val message = call.argument<String>("message")
                    
                    Log.d(TAG, "Received sendSms call with number: $number, message: $message")
                    
                    if (number != null && message != null) {
                        val success = sendSms(number, message)
                        Log.d(TAG, "SMS send result: $success")
                        result.success(success)
                    } else {
                        Log.e(TAG, "Invalid arguments: number or message is null")
                        result.error("INVALID_ARGUMENTS", "Number or message is null", null)
                    }
                }
                else -> {
                    Log.w(TAG, "Unknown method: ${call.method}")
                    result.notImplemented()
                }
            }
        }
    }

    private fun sendSms(number: String, message: String): Boolean {
        return try {
            Log.d(TAG, "Attempting to send SMS to: $number with message: $message")
            
            // Check if we have the necessary permission
            if (ActivityCompat.checkSelfPermission(activity, Manifest.permission.SEND_SMS) != PackageManager.PERMISSION_GRANTED) {
                Log.e(TAG, "SEND_SMS permission not granted")
                return false
            }
            
            val smsManager = SmsManager.getDefault()
            val parts = smsManager.divideMessage(message)
            Log.d(TAG, "Message divided into ${parts.size} parts")
            
            // Send the SMS
            smsManager.sendMultipartTextMessage(number, null, parts, null, null)
            Log.d(TAG, "SMS sent successfully to: $number")
            return true
        } catch (e: SecurityException) {
            Log.e(TAG, "Security exception when sending SMS - permission not granted", e)
            return false
        } catch (e: Exception) {
            Log.e(TAG, "Error sending SMS to $number", e)
            e.printStackTrace()
            return false
        }
    }
}