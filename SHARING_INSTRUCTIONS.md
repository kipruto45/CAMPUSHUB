# How to Share the CampusHub Mobile App for Testing

## 1. Start the Backend
From the project root, run:

```bash
venv/bin/python manage.py runserver 0.0.0.0:8000
```

`0.0.0.0` is important because it lets physical devices reach the backend.

## 2. Point the Mobile App to a Reachable Backend

### Option A: Same Wi-Fi Network (recommended)
Use this when your phone and laptop are on the same network.

1. Find your laptop's LAN IP address.
2. Set `mobile/.env` to:

```env
EXPO_PUBLIC_API_URL=http://<your-lan-ip>:8000/api
```

3. Restart Expo after saving the file.

### Option B: localtunnel
Use this when testers are not on the same Wi-Fi or you need a public backend URL.

1. In a new terminal, run:

```bash
npx localtunnel --port 8000
```

2. Copy the URL that localtunnel prints, for example:

```text
https://your-subdomain.loca.lt
```

3. Set `mobile/.env` to:

```env
EXPO_PUBLIC_API_URL=https://your-subdomain.loca.lt/api
```

4. Keep the localtunnel terminal open for the whole test session.
5. If the device shows a `loca.lt` warning page, open the tunnel URL in the device browser once and tap `Click to Continue`.

## 3. Start the Expo App
From the `mobile` directory, run:

```bash
npm install
npx expo start
```

If the tester cannot reach the Expo dev server over LAN, restart Expo with:

```bash
npx expo start --tunnel
```

## 4. Share with Testers
- Ask testers to install `Expo Go`.
- Share the QR code from the Expo terminal or browser window.
- Give them one of the local test accounts:
  - `admin@campushub.com` / `Admin@12345`
  - `student1@campushub.com` / `Student@12345`
  - `student2@campushub.com` / `Student@12345`
  - `student3@campushub.com` / `Student@12345`

## 5. Quick Check Before You Hand It Off
- Confirm the backend responds at `http://127.0.0.1:8000/health/`.
- Open the app on a phone and verify login works.
- Make sure the dashboard and resource list both load.

## Important Notes
- Do not use `localhost` or `127.0.0.1` in `mobile/.env` when testing on a physical phone.
- Restart Expo every time you change `mobile/.env`.
- Keep the backend server, Expo server, and localtunnel process running during testing.
- For permanent access, deploy the backend instead of relying on localtunnel.
