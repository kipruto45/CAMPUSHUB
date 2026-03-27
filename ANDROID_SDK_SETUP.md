# Android SDK Setup for CampusHub

## Prerequisites
- Java 17+ (already installed: `java -version`)

## Step 1: Install Android SDK Command Line Tools

```bash
mkdir -p ~/android-sdk/cmdline-tools
cd ~/android-sdk/cmdline-tools

# Download command line tools
curl -L -o cmdline-tools.zip https://dl.google.com/android/repository/commandlinetools-linux-11076708_latest.zip
unzip cmdline-tools.zip
mv cmdline-tools latest
rm cmdline-tools.zip
```

## Step 2: Set Environment Variables

Add to `~/.bashrc` or `~/.zshrc`:

```bash
export ANDROID_HOME=~/android-sdk
export ANDROID_SDK_ROOT=~/android-sdk
export PATH=$PATH:$ANDROID_HOME/cmdline-tools/latest/bin:$ANDROID_HOME/platform-tools
```

Then run:
```bash
source ~/.bashrc
```

CampusHub can also auto-detect these common SDK locations when generating `mobile/android/local.properties`:

- `ANDROID_SDK_ROOT`
- `ANDROID_HOME`
- `~/Android/Sdk`
- `~/android-sdk`

## Step 3: Accept Licenses and Install SDK Components

```bash
yes | sdkmanager --licenses
sdkmanager "platform-tools" "platforms;android-34" "build-tools;34.0.0"
```

## Step 4: Configure Local Properties

```bash
cd /home/kipruto/Desktop/CampusHub/mobile
npm run android:configure-sdk
```

## Step 5: Build APK

```bash
cd /home/kipruto/Desktop/CampusHub/mobile
npx expo prebuild --platform android
cd android
./gradlew assembleDebug
```

The APK will be at: `android/app/build/outputs/apk/debug/app-debug.apk`
