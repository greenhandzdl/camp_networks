[app]

# (str) Title of your application
title = Dr.COM WLAN

# (str) Package name (used for import path)
package.name = drcomwlan

# (str) Package domain (needed for android/ios packaging)
package.domain = com.greenhandzdl

# (str) Source directory where the main.py is located
source.dir = ./app

# (list) Source files to include (let empty to include all the files)
source.include_exts = py,png,jpg,kv,atlas,ttf

# (list) List of inclusions using pattern matching
#source.include_patterns = assets/*,images/*.png

# (list) Source files to exclude (let empty to not exclude anything)
# (avoid committing .venv and caches inside the app)
source.exclude_exts = spec,pyc

# (list) List of directory to exclude (let empty to not exclude anything)
source.exclude_dirs = tests,bin,.venv,__pycache__

# (list) List of exclusions using pattern matching
# Do not exclude anything here, we copy drcom_core.py via build_apk.sh

# (str) Application versioning (method 1)
version = 3.0.0

# (int) Application versioning (method 2)
# This is set by CI from module.prop versionCode

# (list) Application requirements
# comma separated e.g. requirements = sqlite3,kivy
requirements = python3,kivy,requests,pyjnius,android

# (str) Presplash of the application
#presplash.filename = %(source.dir)s/data/presplash.png

# (str) Icon of the application
#icon.filename = %(source.dir)s/data/icon.png

# (str) Supported orientation (one of landscape, sensorLandscape, portrait or all)
orientation = portrait

#
# Android specific
#

# (list) Android permissions
android.permissions = INTERNET,ACCESS_NETWORK_STATE,ACCESS_WIFI_STATE

# (int) Target Android API, should be as high as possible.
android.api = 33

# (int) Minimum API your APK / AAB will support.
android.minapi = 21

# (str) Android NDK version to use
android.ndk = 25b

# (bool) Indicate whether the screen should stay on
# Don't forget to add the WAKE_LOCK permission if you set this to True
#android.wakelock = False

# (list) Android application meta-data to set (key=value format)
#android.meta_data =

# (list) Android additional libraries to copy
#android.add_libs_armeabi = libs/android/armeabi/*.so
#android.add_libs_armeabi_v7a = libs/android/armeabi-v7a/*.so
#android.add_libs_arm64_v8a = libs/android/arm64-v8a/*.so
#android.add_libs_x86 = libs/android/x86/*.so
#android.add_libs_x86_64 = libs/android/x86_64/*.so

# (int) selects which android architecture to build for
# 0 = all, 1 = armeabi-v7a, 2 = arm64-v8a, 3 = x86, 4 = x86_64
#android.archs = arm64-v8a, armeabi-v7a

# (str) logcat filter to use
#android.logcat_filters = *:S python:D

# (bool) If True, use AndroidX (instead of old support library)
android.enable_androidx = True

[buildozer]

# (int) Log level (0 = error only, 1 = info, 2 = debug (with command output))
log_level = 2

# (int) Display warning if buildozer is run as root (0 = False, 1 = True)
warn_on_root = 1
