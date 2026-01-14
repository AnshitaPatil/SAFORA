# Migrate Contacts to User-Specific Database

## What Changed

Emergency contacts are now stored **per user** in the database instead of a shared JSON file.

## For Existing Users

If you already have contacts in `emergency_contacts.json`, they need to be migrated to the database:

1. **First time you login** with a user account, the system will:
   - Check if you have contacts in the database
   - If not, it will try to load from JSON file (backward compatibility)
   - Once you save contacts, they'll be stored in the database for that user

2. **To migrate existing contacts:**
   - Login with your account
   - Go to Emergency Contacts page
   - Your contacts should load (from JSON or database)
   - Re-save them (they'll be saved to database)
   - Each user's contacts are now separate!

## How It Works Now

1. **User logs in** → Firebase token is stored in WebView localStorage
2. **Emergency Contacts page loads** → Sends Firebase token in request
3. **Backend gets token** → Extracts user ID
4. **Loads contacts** → Gets user-specific contacts from database
5. **Saves contacts** → Stores in database for that specific user

## Benefits

- ✅ Each user has their own contacts
- ✅ No more shared contacts between users
- ✅ Contacts are isolated per account
- ✅ More secure (user can only see their own contacts)

## Testing

1. **Login with User 1:**
   - Add contacts
   - Logout

2. **Login with User 2:**
   - Should see NO contacts (empty list)
   - Add different contacts
   - Logout

3. **Login again with User 1:**
   - Should see User 1's contacts (not User 2's)
   - Each user has separate contacts!

## Troubleshooting

### "Still seeing other user's contacts"

**Check:**
1. Are you sending Firebase token in requests?
2. Check Flask console logs for user ID
3. Verify token is being extracted correctly

**Fix:**
- Make sure Flutter app injects Firebase token
- Check browser console for token injection
- Verify Authorization header in network requests

### "No contacts showing"

**Check:**
1. Do you have contacts saved?
2. Are you logged in with the correct account?
3. Check database for your user's contacts

**Fix:**
- Login and add contacts again
- Check Flask console for errors
- Verify database connection

