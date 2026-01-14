import 'package:flutter/material.dart';
import 'package:cloud_firestore/cloud_firestore.dart';
import 'package:firebase_auth/firebase_auth.dart';
import 'package:uuid/uuid.dart';

class ContactsPage extends StatefulWidget {
  const ContactsPage({super.key});

  @override
  State<ContactsPage> createState() => _ContactsPageState();
}

class _ContactsPageState extends State<ContactsPage> {
  final _nameCtrl = TextEditingController();
  final _phoneCtrl = TextEditingController();
  final user = FirebaseAuth.instance.currentUser;
  final uuid = const Uuid();

  Future<void> _addContact() async {
    if (_nameCtrl.text.isEmpty || _phoneCtrl.text.isEmpty) return;

    final uid = user?.uid;
    if (uid == null) return;

    final contact = {
      "id": uuid.v4(),
      "name": _nameCtrl.text.trim(),
      "phone": _phoneCtrl.text.trim(),
    };

    await FirebaseFirestore.instance
        .collection("users")
        .doc(uid)
        .set({
      "emergencyContacts": FieldValue.arrayUnion([contact])
    }, SetOptions(merge: true));

    _nameCtrl.clear();
    _phoneCtrl.clear();
  }

  Future<void> _deleteContact(String contactId) async {
    final uid = user?.uid;
    if (uid == null) return;

    final doc =
        FirebaseFirestore.instance.collection("users").doc(uid);
    final snapshot = await doc.get();

    if (!snapshot.exists) return;

    final contacts =
        List<Map<String, dynamic>>.from(snapshot["emergencyContacts"]);

    final updated =
        contacts.where((c) => c["id"] != contactId).toList();

    await doc.update({"emergencyContacts": updated});
  }

  @override
  Widget build(BuildContext context) {
    final uid = user?.uid;

    return Scaffold(
      appBar: AppBar(
        title: const Text("Emergency Contacts"),
        backgroundColor: Colors.pinkAccent,
      ),
      body: uid == null
          ? const Center(child: Text("User not logged in"))
          : Column(
              children: [
                Padding(
                  padding: const EdgeInsets.all(12),
                  child: Column(
                    children: [
                      TextField(
                        controller: _nameCtrl,
                        decoration: const InputDecoration(
                          labelText: "Name",
                        ),
                      ),
                      const SizedBox(height: 8),
                      TextField(
                        controller: _phoneCtrl,
                        decoration: const InputDecoration(
                          labelText: "Phone",
                        ),
                        keyboardType: TextInputType.phone,
                      ),
                      const SizedBox(height: 10),
                      ElevatedButton(
                        onPressed: _addContact,
                        child: const Text("Add Contact"),
                      ),
                    ],
                  ),
                ),
                const Divider(),
                Expanded(
                  child: StreamBuilder<DocumentSnapshot>(
                    stream: FirebaseFirestore.instance
                        .collection("users")
                        .doc(uid)
                        .snapshots(),
                    builder: (context, snapshot) {
                      if (!snapshot.hasData ||
                          !snapshot.data!.exists) {
                        return const Center(
                          child: Text("No contacts yet"),
                        );
                      }

                      final contacts =
                          List<Map<String, dynamic>>.from(
                        snapshot.data!["emergencyContacts"] ?? [],
                      );

                      if (contacts.isEmpty) {
                        return const Center(
                          child: Text("No emergency contacts"),
                        );
                      }

                      return ListView.builder(
                        itemCount: contacts.length,
                        itemBuilder: (context, index) {
                          final c = contacts[index];
                          return ListTile(
                            leading: const Icon(Icons.person),
                            title: Text(c["name"]),
                            subtitle: Text(c["phone"]),
                            trailing: IconButton(
                              icon: const Icon(Icons.delete,
                                  color: Colors.red),
                              onPressed: () =>
                                  _deleteContact(c["id"]),
                            ),
                          );
                        },
                      );
                    },
                  ),
                )
              ],
            ),
    );
  }
}
