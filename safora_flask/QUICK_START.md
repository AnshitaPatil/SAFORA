# SMS Quick Start Guide

Get SMS working in 3 simple steps!

## Step 1: Set Up Gmail Credentials (2 minutes)

### Option A: Use Setup Script (Easiest)

```bash
cd safora_flask
python setup_sms.py
```

The script will guide you through creating the `.env` file.

### Option B: Create .env File Manually

1. Create a file named `.env` in `safora_flask/` folder
2. Add these lines:

```
ALERT_EMAIL=your-email@gmail.com
ALERT_EMAIL_PASSWORD=your-16-character-app-password
SMTP_SERVER=smtp.gmail.com
SMTP_PORT=587
```

3. Replace with your actual Gmail credentials

### Get Gmail App Password

1. Go to: https://myaccount.google.com/apppasswords
2. Enable 2-Step Verification (if not enabled)
3. Create app password for "Mail"
4. Copy the 16-character password
5. Paste in `.env` file (remove spaces)

## Step 2: Add Emergency Contacts (1 minute)

1. Start Flask app: `python app.py`
2. Open the app in browser or Flutter app
3. Go to **Emergency Contacts** page
4. Click **Add Contact**
5. Enter:
   - **Name**: e.g., "Mom", "Dad"
   - **Phone**: Enter 10 digits (e.g., `753975010`)
6. Click **Save**
7. System automatically:
   - Adds `91` country code
   - Sends SMS to ALL Indian carriers

## Step 3: Test SMS (1 minute)

### Option A: Use Test Script

```bash
cd safora_flask
python test_sms_sending.py
```

### Option B: Test via App

1. Start Flask app: `python app.py`
2. Login to app
3. Trigger an emergency alert (test)
4. Check your phone in 1-2 minutes

### Option C: Use Diagnostic Tool

```bash
cd safora_flask
python comprehensive_sms_test.py
```

## Verify Everything Works

Run diagnostic:

```bash
cd safora_flask
python comprehensive_sms_test.py
```

**Expected output:**
- ✓ ALERT_EMAIL: your-email@gmail.com
- ✓ ALERT_EMAIL_PASSWORD: ******** (16 chars)
- ✓ SMTP connection test PASSED
- ✓ Emergency contacts found

## Troubleshooting

### "EMAIL CREDENTIALS NOT SET"
→ Run `python setup_sms.py` to create `.env` file

### "AUTHENTICATION FAILED"
→ Check if using Gmail App Password (not regular password)
→ Enable 2-Step Verification
→ Regenerate App Password

### "NO EMERGENCY CONTACTS"
→ Add contacts via Emergency Contacts page

### SMS sent but not received
→ Wait 1-2 minutes (SMS can be delayed)
→ Check phone number format (must be 12 digits with 91)
→ System sends to ALL carriers, so check all carrier SMS folders

## Files Created

- `.env` - Your Gmail credentials (keep secure!)
- `emergency_contacts.json` - Your emergency contacts
- All diagnostic and test scripts

## That's It!

✅ Gmail credentials configured  
✅ Emergency contacts added  
✅ SMS tested and working  

Your SMS system is now ready! 🎉

## Need Help?

- See `SMS_FIX_GUIDE.md` for detailed troubleshooting
- See `HOW_SMS_WORKS.md` for how email-to-SMS works
- Check Flask console logs for detailed error messages

