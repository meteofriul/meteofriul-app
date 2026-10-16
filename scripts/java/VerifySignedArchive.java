import java.io.InputStream;
import java.nio.file.Path;
import java.security.CodeSigner;
import java.security.MessageDigest;
import java.security.cert.Certificate;
import java.util.Arrays;
import java.util.Enumeration;
import java.util.Locale;
import java.util.jar.JarEntry;
import java.util.jar.JarFile;

public final class VerifySignedArchive {
    private VerifySignedArchive() {}

    private static String sha256(Certificate certificate) throws Exception {
        byte[] digest = MessageDigest.getInstance("SHA-256").digest(certificate.getEncoded());
        StringBuilder result = new StringBuilder(digest.length * 2);
        for (byte value : digest) {
            result.append(String.format(Locale.ROOT, "%02x", value & 0xff));
        }
        return result.toString();
    }

    private static boolean isPayload(JarEntry entry) {
        return !entry.isDirectory()
                && !entry.getName().toUpperCase(Locale.ROOT).startsWith("META-INF/");
    }

    public static void main(String[] args) throws Exception {
        if (args.length != 1) {
            throw new IllegalArgumentException("usage: VerifySignedArchive <archive.aab>");
        }
        String archiveFingerprint = null;
        int payloadEntries = 0;
        byte[] buffer = new byte[64 * 1024];
        try (JarFile archive = new JarFile(Path.of(args[0]).toFile(), true)) {
            Enumeration<JarEntry> entries = archive.entries();
            while (entries.hasMoreElements()) {
                JarEntry entry = entries.nextElement();
                if (!isPayload(entry)) {
                    continue;
                }
                payloadEntries++;
                try (InputStream stream = archive.getInputStream(entry)) {
                    while (stream.read(buffer) != -1) {
                        // Reading every byte is what triggers JarVerifier digest checks.
                    }
                }
                CodeSigner[] signers = entry.getCodeSigners();
                if (signers == null || signers.length != 1) {
                    throw new SecurityException(
                            "entry must have exactly one signer: " + entry.getName());
                }
                Certificate[] certificates = signers[0].getSignerCertPath()
                        .getCertificates().toArray(Certificate[]::new);
                if (certificates.length == 0) {
                    throw new SecurityException("signer certificate missing: " + entry.getName());
                }
                String entryFingerprint = sha256(certificates[0]);
                if (archiveFingerprint == null) {
                    archiveFingerprint = entryFingerprint;
                } else if (!archiveFingerprint.equals(entryFingerprint)) {
                    throw new SecurityException("multiple signer fingerprints detected");
                }
                if (!Arrays.equals(
                        certificates[0].getEncoded(),
                        signers[0].getSignerCertPath().getCertificates().get(0).getEncoded())) {
                    throw new SecurityException("signer certificate changed while reading archive");
                }
            }
        }
        if (payloadEntries == 0 || archiveFingerprint == null) {
            throw new SecurityException("archive contains no signed payload entries");
        }
        System.out.println(archiveFingerprint);
    }
}
