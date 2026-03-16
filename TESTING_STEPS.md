# CampusHub Mobile Testing Steps

## Before You Start
- Install `Expo Go` from the App Store or Play Store.
- Ask the developer to confirm the backend and Expo dev server are already running.
- If the developer is sharing over Wi-Fi, keep your phone on the same network.

## Open the App
1. Open `Expo Go` on your phone.
2. Scan the QR code shared by the developer.
3. Wait for the CampusHub app to load inside Expo Go.

## If the Backend Uses localtunnel
- You may see a `loca.lt` warning page the first time the backend URL opens.
- If that happens, open the shared tunnel URL in your phone browser once and tap `Click to Continue`, then go back to Expo Go.

## Login Credentials
Use one of these local testing accounts:

- Admin
  - Email: `admin@campushub.com`
  - Password: `Admin@12345`
- Student 1
  - Email: `student1@campushub.com`
  - Password: `Student@12345`
- Student 2
  - Email: `student2@campushub.com`
  - Password: `Student@12345`
- Student 3
  - Email: `student3@campushub.com`
  - Password: `Student@12345`

## What to Test
- Log in and log out.
- Check the dashboard and announcements.
- Browse resources and open a resource detail page.
- Check bookmarks, favorites, library, and notifications.
- Open profile/settings screens and confirm they load correctly.

## Troubleshooting
- If the app opens but data does not load, ask the developer to verify `mobile/.env` is using a reachable backend URL, not `localhost`.
- If the QR code does not open the app, ask the developer to restart Expo and share a fresh QR code.
- If login fails, re-enter the credentials exactly as shown above.
- If nothing loads, make sure the developer's computer, backend server, and Expo server are still running.
