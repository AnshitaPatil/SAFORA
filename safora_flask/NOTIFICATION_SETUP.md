# Free Notification Setup Guide

This guide will help you set up free, unlimited emergency notifications via Email and Telegram.

## Overview

The notification system supports three free channels:
1. **Email** - Completely free via Gmail SMTP
2. **Telegram Bot** - Completely free and unlimited
3. **Email-to-SMS** - Free SMS via carrier email gateways

## Setup Instructions

### 1. Email Setup (Recommended - Easiest)

#### Step 1: Create Gmail App Password
1. Go to your Google Account settings
2. Enable 2-Step Verification if not already enabled
3. Go to "App passwords" section
4. Create a new app password for "Mail"
5. Copy the 16-character password

#### Step 2: Add to .env file
Create or update `.env` file in `safora_flask/` directory:

```env
# Email Configuration
ALERT_EMAIL=your-email@gmail.com
ALERT_EMAIL_PASSWORD=your-16-character-app-password
SMTP_SERVER=smtp.gmail.com
SMTP_PORT=587
```

#### Step 3: Add Emergency Contacts
Edit `emergency_contacts.json`:

```json
{
  "email_contacts": [
    "contact1@example.com",
    "contact2@example.com",
    "emergency@family.com"
  ]
}
```

**Email is ready!** Unlimited emails, completely free.

---

### 2. Telegram Bot Setup (Recommended - Best for Real-time)

#### Step 1: Create Telegram Bot
1. Open Telegram and search for `@BotFather`
2. Send `/newbot` command
3. Follow instructions to name your bot
4. Copy the bot token (looks like: `123456789:ABCdefGHIjklMNOpqrsTUVwxyz`)

#### Step 2: Get Chat IDs
For each contact you want to notify:
1. Search for `@userinfobot` on Telegram
2. Start a chat and it will show your Chat ID
3. Have each emergency contact do the same

#### Step 3: Add to .env file
```env
TELEGRAM_BOT_TOKEN=123456789:ABCdefGHIjklMNOpqrsTUVwxyz
```

#### Step 4: Add Emergency Contacts
Edit `emergency_contacts.json`:

```json
{
  "telegram_contacts": [
    "123456789",
    "987654321",
    "555123456"
  ]
}
```

**Telegram is ready!** Unlimited messages, completely free, instant delivery.

---

### 3. Email-to-SMS Setup (For SMS without paid services)

This uses carrier-specific email gateways to send SMS via email.

#### Carrier Email Gateways

**US Carriers:**
- AT&T: `number@txt.att.net`
- Verizon: `number@vtext.com`
- T-Mobile: `number@tmomail.net`
- Sprint: `number@messaging.sprintpcs.com`

**Indian Carriers:**
- Airtel: `number@airtelmail.com`
- Jio: `number@sms.jio.com`
- Vodafone: `number@vodafone-sms.co.in`

#### Add Phone Numbers
Edit `emergency_contacts.json`:

```json
{
  "phone_numbers": [
    "+919876543210@jio.com",
    "+11234567890@txt.att.net"
  ]
}
```

**Note:** Format: `+countrycode+number@carrier-gateway.com`

If you don't know the carrier, the system will try multiple carriers automatically.

---

## Complete Configuration Example

### .env file:
```env
# Email Configuration (Gmail)
ALERT_EMAIL=yourname@gmail.com
ALERT_EMAIL_PASSWORD=abcd efgh ijkl mnop
SMTP_SERVER=smtp.gmail.com
SMTP_PORT=587

# Telegram Bot
TELEGRAM_BOT_TOKEN=123456789:ABCdefGHIjklMNOpqrsTUVwxyz
```

### emergency_contacts.json:
```json
{
  "email_contacts": [
    "mom@example.com",
    "dad@example.com",
    "emergency@family.com"
  ],
  "telegram_contacts": [
    "123456789",
    "987654321"
  ],
  "phone_numbers": [
    "+919876543210@sms.jio.com",
    "+11234567890@txt.att.net"
  ]
}
```

---

## Testing Your Setup

### Test Email:
```python
from notification_service import send_email_alert

send_email_alert(
    location="19.0760,72.8777",
    map_link="https://www.google.com/maps/place/19.0760,72.8777"
)
```

### Test Telegram:
```python
from notification_service import send_telegram_alert

send_telegram_alert(
    location="19.0760,72.8777",
    map_link="https://www.google.com/maps/place/19.0760,72.8777"
)
```

### Test All Channels:
```python
from notification_service import send_emergency_alerts

results = send_emergency_alerts(
    location="19.0760,72.8777",
    map_link="https://www.google.com/maps/place/19.0760,72.8777"
)
print(results)  # Shows which channels succeeded
```

---

## Alert Message Format

When an emergency is detected, contacts will receive:

**Subject:** 🚨 EMERGENCY ALERT - User in Danger!

**Message includes:**
- ⏰ Timestamp
- 📍 Exact location coordinates
- 🔗 Google Maps link
- 🎵 Link to realtime audio (when implemented)
- 📹 Link to realtime video (when implemented)
- ⚠️ Emergency instructions

---

## Troubleshooting

### Email not working?
- Check Gmail app password is correct (16 characters, no spaces)
- Ensure 2-Step Verification is enabled
- Check spam folder
- Verify SMTP settings in .env

### Telegram not working?
- Verify bot token is correct
- Ensure chat IDs are correct (use @userinfobot)
- Check that emergency contacts have started chat with your bot

### SMS not working?
- Verify phone number format: `+countrycode+number@carrier.com`
- Check carrier email gateway is correct
- Some carriers may block email-to-SMS

---

## Benefits

✅ **Completely Free** - No charges ever  
✅ **Unlimited Messages** - Send as many as needed  
✅ **Multiple Channels** - Email, Telegram, SMS  
✅ **Instant Delivery** - Real-time notifications  
✅ **No API Limits** - No rate limiting or quotas  

---

## Security Notes

- Never commit `.env` file to git
- Keep bot tokens and passwords secure
- Regularly update emergency contacts
- Test your setup regularly

---

For support, check the logs in your Flask console for detailed error messages.

