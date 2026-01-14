import 'package:flutter/material.dart';
import 'package:firebase_auth/firebase_auth.dart';
import 'registration_page.dart';
import 'forgot_password_page.dart';
import 'flask_webview_page.dart';
import '../services/api_service.dart';
import 'package:permission_handler/permission_handler.dart';

class LoginPage extends StatefulWidget {
  const LoginPage({super.key});

  @override
  State<LoginPage> createState() => _LoginPageState();
}

class _LoginPageState extends State<LoginPage> {
  final TextEditingController _emailController = TextEditingController();
  final TextEditingController _passwordController = TextEditingController();
  bool _loading = false;

  // ✅ Request necessary permissions before login
  Future<void> requestAllPermissions() async {
    await [
      Permission.camera,
      Permission.microphone,
      Permission.location,
      Permission.sms,
      Permission.phone,
    ].request();
  }

  Future<void> _login() async {
    setState(() => _loading = true);
    try {
      // Request permissions
      await requestAllPermissions();

      // Check Flask
      final isFlaskRunning = await ApiService.checkHealth();
      if (!isFlaskRunning && mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(
            content: Text(
              'Warning: Flask backend not detected. Some features may not work.',
            ),
            backgroundColor: Colors.orange,
          ),
        );
      }

      // 🔐 Firebase Authentication
      final userCredential =
          await FirebaseAuth.instance.signInWithEmailAndPassword(
        email: _emailController.text.trim(),
        password: _passwordController.text.trim(),
      );

      // 🔑 Print Firebase ID token (for backend testing)
      final idToken =
          await FirebaseAuth.instance.currentUser?.getIdToken(true);
      print("\n========== FIREBASE ID TOKEN ==========\n");
      print(idToken);
      print("\n======================================\n");

      // Call Flask backend
      await ApiService.login(
        _emailController.text.trim(),
        _passwordController.text.trim(),
      );

      // Navigate to dashboard
      final flaskUrl = await ApiService.getFlaskUrl();
      if (mounted) {
        Navigator.pushReplacement(
          context,
          MaterialPageRoute(
            builder: (_) => FlaskWebPage(url: flaskUrl),
          ),
        );
      }
    } catch (e) {
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(content: Text('Login error: $e')),
      );
    } finally {
      setState(() => _loading = false);
    }
  }

  @override
  void dispose() {
    _emailController.dispose();
    _passwordController.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: Colors.pink[50],
      body: Center(
        child: Padding(
          padding: const EdgeInsets.all(24.0),
          child: SingleChildScrollView(
            child: Column(
              mainAxisAlignment: MainAxisAlignment.center,
              children: [
                Image.asset(
                  'assets/images/logo.jpg',
                  height: 120,
                  fit: BoxFit.contain,
                ),
                const SizedBox(height: 8),
                const Text(
                  'SAFORA',
                  style: TextStyle(
                    fontSize: 30,
                    fontWeight: FontWeight.bold,
                    color: Color.fromARGB(255, 19, 15, 17),
                    letterSpacing: 1.5,
                  ),
                ),
                const SizedBox(height: 24),

                TextField(
                  controller: _emailController,
                  decoration: const InputDecoration(
                    labelText: 'Email',
                    border: OutlineInputBorder(),
                  ),
                  keyboardType: TextInputType.emailAddress,
                ),
                const SizedBox(height: 12),

                TextField(
                  controller: _passwordController,
                  decoration: const InputDecoration(
                    labelText: 'Password',
                    border: OutlineInputBorder(),
                  ),
                  obscureText: true,
                ),
                const SizedBox(height: 16),

                ElevatedButton(
                  onPressed: _loading ? null : _login,
                  style: ElevatedButton.styleFrom(
                    backgroundColor: Colors.pinkAccent,
                    padding: const EdgeInsets.symmetric(
                      horizontal: 60,
                      vertical: 14,
                    ),
                    shape: RoundedRectangleBorder(
                      borderRadius: BorderRadius.circular(24),
                    ),
                  ),
                  child: _loading
                      ? const SizedBox(
                          width: 20,
                          height: 20,
                          child: CircularProgressIndicator(
                            color: Colors.white,
                            strokeWidth: 2,
                          ),
                        )
                      : const Text(
                          'Login',
                          style: TextStyle(fontSize: 16),
                        ),
                ),

                const SizedBox(height: 8),

                TextButton(
                  onPressed: () {
                    Navigator.push(
                      context,
                      MaterialPageRoute(
                        builder: (_) => const ForgotPasswordPage(),
                      ),
                    );
                  },
                  child: const Text(
                    'Forgot Password?',
                    style: TextStyle(color: Colors.pinkAccent),
                  ),
                ),

                TextButton(
                  onPressed: () {
                    Navigator.push(
                      context,
                      MaterialPageRoute(
                        builder: (_) => const RegisterPage(),
                      ),
                    );
                  },
                  child: const Text("Don’t have an account? Register"),
                ),
              ],
            ),
          ),
        ),
      ),
    );
  }
}
