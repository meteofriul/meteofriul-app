$ErrorActionPreference='Stop'
$sdk='C:/Users/LOCAL_USER/AppData/Local/Android/Sdk'
$bt=Join-Path $sdk 'build-tools/36.0.0'
$jbr='C:/Program Files/Android/Android Studio/jbr/bin'
$androidJar=Join-Path $sdk 'platforms/android-36/android.jar'
$env:JAVA_HOME='C:/Program Files/Android/Android Studio/jbr'
Set-Location $PSScriptRoot
New-Item -ItemType Directory -Force classes,dex | Out-Null
& "$bt/aapt.exe" package -f -M AndroidManifest.xml -I $androidJar -F unsigned.apk
if ($LASTEXITCODE) { throw 'aapt failed' }
& "$jbr/javac.exe" -source 8 -target 8 -classpath $androidJar -d classes BarProbe.java
if ($LASTEXITCODE) { throw 'javac failed' }
& "$bt/d8.bat" --lib $androidJar --min-api 30 --output dex classes/com/meteofriul/test/barprobe/BarProbe.class
if ($LASTEXITCODE) { throw 'd8 failed' }
Copy-Item dex/classes.dex classes.dex
& "$bt/aapt.exe" add unsigned.apk classes.dex
& "$bt/zipalign.exe" -f 4 unsigned.apk aligned.apk
if (!(Test-Path probe.jks)) {
  & "$jbr/keytool.exe" -genkeypair -keystore probe.jks -storepass diagnostic -keypass diagnostic -alias probe -dname 'CN=Local emulator diagnostic' -keyalg RSA -validity 2
}
& "$bt/apksigner.bat" sign --ks probe.jks --ks-pass pass:diagnostic --key-pass pass:diagnostic --out probe.apk aligned.apk
if ($LASTEXITCODE) { throw 'signing failed' }
