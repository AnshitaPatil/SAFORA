import 'package:flutter/material.dart';
import 'package:firebase_auth/firebase_auth.dart';
import 'package:cloud_firestore/cloud_firestore.dart';
import 'package:fluttertoast/fluttertoast.dart';
import '../services/alert_service.dart';

class AlertPage extends StatefulWidget {
  final VoidCallback onAlertSent;
  
  const AlertPage({super.key, required this.onAlertSent});

  @override
  State<AlertPage> createState() => _AlertPageState();
}

class _AlertPageState extends State<AlertPage> {
  bool _isSending = false;
  String _status = "Sending alert...";
  
  @override
  void initState() {
    super.initState();
    _sendAlert();
  }
  
  Future<void> _sendAlert() async {
    setState(() {
      _isSending = true;
      _status = "Sending alert...";
    });
    
    try {
      await AlertService.triggerAutomaticAlert();
      
      setState(() {
        _status = "Alert sent successfully!";
      });
      
      // Wait a moment to show success message
      await Future.delayed(const Duration(seconds: 2));
      
      // Notify parent that alert was sent
      widget.onAlertSent();
    } catch (e) {
      setState(() {
        _status = "Failed to send alert: $e";
      });
      
      Fluttertoast.showToast(
        msg: "Failed to send alert: $e",
        toastLength: Toast.LENGTH_LONG,
        gravity: ToastGravity.BOTTOM,
        backgroundColor: Colors.red,
        textColor: Colors.white,
      );
    } finally {
      setState(() {
        _isSending = false;
      });
    }
  }
  
  Future<void> _goBack() async {
    // Navigate back to the previous screen
    if (mounted) {
      Navigator.of(context).pop();
    }
  }
  
  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text('Emergency Alert'),
        backgroundColor: Colors.redAccent,
        leading: IconButton(
          icon: const Icon(Icons.arrow_back),
          onPressed: _isSending ? null : _goBack,
        ),
      ),
      body: Center(
        child: Padding(
          padding: const EdgeInsets.all(24.0),
          child: Column(
            mainAxisAlignment: MainAxisAlignment.center,
            children: [
              Icon(
                _isSending ? Icons.warning : (_status.contains("successfully") ? Icons.check_circle : Icons.error),
                size: 80,
                color: _isSending ? Colors.orange : (_status.contains("successfully") ? Colors.green : Colors.red),
              ),
              const SizedBox(height: 24),
              Text(
                _status,
                style: const TextStyle(
                  fontSize: 18,
                  fontWeight: FontWeight.bold,
                ),
                textAlign: TextAlign.center,
              ),
              const SizedBox(height: 24),
              if (_isSending)
                const CircularProgressIndicator(
                  valueColor: AlwaysStoppedAnimation<Color>(Colors.orange),
                ),
              const SizedBox(height: 24),
              if (!_isSending)
                ElevatedButton(
                  onPressed: _goBack,
                  style: ElevatedButton.styleFrom(
                    backgroundColor: Colors.pinkAccent,
                    padding: const EdgeInsets.symmetric(horizontal: 30, vertical: 15),
                    shape: RoundedRectangleBorder(
                      borderRadius: BorderRadius.circular(30),
                    ),
                  ),
                  child: const Text(
                    "Back to Dashboard",
                    style: TextStyle(fontSize: 16, fontWeight: FontWeight.bold),
                  ),
                ),
            ],
          ),
        ),
      ),
    );
  }
}