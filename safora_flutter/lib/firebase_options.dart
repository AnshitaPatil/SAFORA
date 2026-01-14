
// ignore_for_file: type=lint
import 'package:firebase_core/firebase_core.dart' show FirebaseOptions;
import 'package:flutter/foundation.dart'
    show defaultTargetPlatform, kIsWeb, TargetPlatform;

/// Default [FirebaseOptions] for use with your Firebase apps.
///
/// Example:
/// ```dart
/// import 'firebase_options.dart';
/// // ...
/// await Firebase.initializeApp(
///   options: DefaultFirebaseOptions.currentPlatform,
/// );
/// ```
class DefaultFirebaseOptions {
  static FirebaseOptions get currentPlatform {
    if (kIsWeb) {
      return web;
    }
    switch (defaultTargetPlatform) {
      case TargetPlatform.android:
        return android;
      case TargetPlatform.iOS:
        return ios;
      case TargetPlatform.macOS:
        return macos;
      case TargetPlatform.windows:
        return windows;
      case TargetPlatform.linux:
        throw UnsupportedError(
          'DefaultFirebaseOptions have not been configured for linux - '
          'you can reconfigure this by running the FlutterFire CLI again.',
        );
      default:
        throw UnsupportedError(
          'DefaultFirebaseOptions are not supported for this platform.',
        );
    }
  }

  static const FirebaseOptions web = FirebaseOptions(
    apiKey: 'AIzaSyDwl1dVX0BFyPmtP9CffujEVe0442MfSHk',
    appId: '1:299324417871:web:0953ea47d4afaf0710073a',
    messagingSenderId: '299324417871',
    projectId: 'safetyai-ae643',
    authDomain: 'safetyai-ae643.firebaseapp.com',
    storageBucket: 'safetyai-ae643.firebasestorage.app',
    measurementId: 'G-VSBS8P1VRF',
  );

  static const FirebaseOptions android = FirebaseOptions(
    apiKey: 'AIzaSyCNt7dc2te0gkQ76maDUEFmlG3bD4bVST4',
    appId: '1:299324417871:android:ad3202c27a6b0f3010073a',
    messagingSenderId: '299324417871',
    projectId: 'safetyai-ae643',
    storageBucket: 'safetyai-ae643.firebasestorage.app',
  );

  static const FirebaseOptions ios = FirebaseOptions(
    apiKey: 'AIzaSyBqD3xl9xP4Cg5e7iZqvpzW97rGmKIqWQU',
    appId: '1:299324417871:ios:d8a7bdc3495e6bef10073a',
    messagingSenderId: '299324417871',
    projectId: 'safetyai-ae643',
    storageBucket: 'safetyai-ae643.firebasestorage.app',
    iosBundleId: 'com.example.saforaFlutter',
  );

  static const FirebaseOptions macos = FirebaseOptions(
    apiKey: 'AIzaSyBqD3xl9xP4Cg5e7iZqvpzW97rGmKIqWQU',
    appId: '1:299324417871:ios:d8a7bdc3495e6bef10073a',
    messagingSenderId: '299324417871',
    projectId: 'safetyai-ae643',
    storageBucket: 'safetyai-ae643.firebasestorage.app',
    iosBundleId: 'com.example.saforaFlutter',
  );

  static const FirebaseOptions windows = FirebaseOptions(
    apiKey: 'AIzaSyDwl1dVX0BFyPmtP9CffujEVe0442MfSHk',
    appId: '1:299324417871:web:25d5b427795e53b310073a',
    messagingSenderId: '299324417871',
    projectId: 'safetyai-ae643',
    authDomain: 'safetyai-ae643.firebaseapp.com',
    storageBucket: 'safetyai-ae643.firebasestorage.app',
    measurementId: 'G-FR7VCPY6W8',
  );

}