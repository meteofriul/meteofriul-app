# Add project specific ProGuard rules here.
# You can control the set of applied configuration files using the
# proguardFiles setting in build.gradle.
#
# For more details, see
#   http://developer.android.com/guide/developing/tools/proguard.html

# If your project uses WebView with JS, uncomment the following
# and specify the fully qualified class name to the JavaScript interface
# class:
#-keepclassmembers class fqcn.of.javascript.interface.for.webview {
#   public *;
#}

# Keep source and line metadata so de-obfuscated production stack traces remain
# actionable when interpreted with the archived mapping.txt. Class and method
# names may still be obfuscated by R8.
-keepattributes SourceFile,LineNumberTable
-renamesourcefileattribute SourceFile

# Capacitor reads this cached runtime annotation when resolving plugin
# permissions. R8 bundled with AGP 8.13 can otherwise remove the field/getter
# and replace the permission path with a null throw, even though the plugin
# classes themselves are covered by Capacitor's consumer rules. Keep only this
# metadata edge; unrelated members remain eligible for shrinking/obfuscation.
-keepclassmembers,allowobfuscation class com.getcapacitor.PluginHandle {
    private com.getcapacitor.annotation.CapacitorPlugin pluginAnnotation;
    public com.getcapacitor.annotation.CapacitorPlugin getPluginAnnotation();
}
