"""
Notification Service - Simplified for Native SMS
Only provides contact loading functionality
SMS is sent directly from Flutter app using device's SMS app
"""
import os
import logging
import json

logging.basicConfig(level=logging.INFO)

# Configuration file for emergency contacts
CONTACTS_FILE = 'emergency_contacts.json'

def load_emergency_contacts(firebase_uid=None):
    """
    Load emergency contacts from database (if firebase_uid provided) or JSON file (legacy).
    
    Args:
        firebase_uid: Firebase user ID to get user-specific contacts. If None, uses legacy JSON file.
    
    Returns:
        Dict with 'phone_numbers' and 'contact_names' lists
    """
    # If firebase_uid provided, get from database
    if firebase_uid:
        try:
            from auth_db import get_conn
            conn = get_conn()
            
            rows = conn.execute("""
                SELECT name, phone_number 
                FROM emergency_contacts 
                WHERE firebase_uid = ?
                ORDER BY created_at ASC
            """, (firebase_uid,)).fetchall()
            conn.close()
            
            phone_numbers = []
            contact_names = []
            
            for row in rows:
                contact_names.append(row['name'])
                phone_numbers.append(row['phone_number'])
            
            logging.info(f"Loaded {len(phone_numbers)} contacts from database for user: {firebase_uid}")
            
            return {
                "phone_numbers": phone_numbers,
                "contact_names": contact_names
            }
        except Exception as e:
            logging.error(f"Error loading contacts from database: {e}")
            # Fallback to JSON file
            pass
    
    # Legacy: Load from JSON file
    if os.path.exists(CONTACTS_FILE):
        try:
            with open(CONTACTS_FILE, 'r') as f:
                return json.load(f)
        except Exception as e:
            logging.error(f"Error loading contacts: {e}")
            return get_default_contacts()
    return get_default_contacts()

def get_default_contacts():
    """Get default emergency contacts."""
    return {
        "phone_numbers": [],
        "contact_names": []
    }

def save_emergency_contacts(contacts):
    """Save emergency contacts to JSON file (legacy method)."""
    try:
        with open(CONTACTS_FILE, 'w') as f:
            json.dump(contacts, f, indent=2)
        return True
    except Exception as e:
        logging.error(f"Error saving contacts: {e}")
        return False
