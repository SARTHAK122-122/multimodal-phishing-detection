package com.phishingdet.service;

import com.phishingdet.exception.BadRequestException;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.stereotype.Component;
import org.springframework.web.multipart.MultipartFile;

import java.io.IOException;
import java.nio.file.Files;
import java.nio.file.Path;
import java.nio.file.StandardCopyOption;
import java.time.Instant;
import java.util.Locale;

/**
 * Centralised, path-traversal-safe file storage for uploaded and processed
 * datasets. Everything lives under the configured upload directory, which is
 * shared with the Python service.
 */
@Component
public class StorageService {

    private static final long MAX_BYTES = 50L * 1024 * 1024;

    private final Path uploadDir;
    private final Path processedDir;

    public StorageService(@Value("${storage.upload-dir}") String uploadDir,
                          @Value("${storage.processed-dir}") String processedDir) throws IOException {
        this.uploadDir = Path.of(uploadDir).toAbsolutePath().normalize();
        this.processedDir = Path.of(processedDir).toAbsolutePath().normalize();
        Files.createDirectories(this.uploadDir);
        Files.createDirectories(this.processedDir);
    }

    public Path uploadDir() {
        return uploadDir;
    }

    public Path processedDir() {
        return processedDir;
    }

    /** Saves the uploaded file under a generated, unique name. Returns the stored name. */
    public String saveUpload(MultipartFile file) {
        if (file == null || file.isEmpty()) {
            throw new BadRequestException("No file was uploaded.");
        }
        if (file.getSize() > MAX_BYTES) {
            throw new BadRequestException("File exceeds the 50 MB upload limit.");
        }
        String original = sanitize(file.getOriginalFilename());
        if (original == null || original.isBlank()) {
            throw new BadRequestException("The upload has no filename.");
        }
        String ext = extension(original);
        if (!".csv".equals(ext)) {
            throw new BadRequestException("Only CSV files are supported (received: " + ext + ").");
        }
        String stored = "ds-" + Instant.now().toEpochMilli() + "-" + original;
        Path target = uploadDir.resolve(stored).normalize();
        if (!target.startsWith(uploadDir)) {
            throw new BadRequestException("Invalid filename.");
        }
        try {
            Files.copy(file.getInputStream(), target, StandardCopyOption.REPLACE_EXISTING);
        } catch (IOException ex) {
            throw new BadRequestException("Could not store the uploaded file: " + ex.getMessage());
        }
        return stored;
    }

    /** Resolves a stored file name inside the upload directory (traversal-safe). */
    public Path resolveUpload(String storedName) {
        Path resolved = uploadDir.resolve(storedName).normalize();
        if (!resolved.startsWith(uploadDir)) {
            throw new BadRequestException("Invalid file path.");
        }
        return resolved;
    }

    /** Resolves a processed file reference such as {@code processed/x.csv}. */
    public Path resolveProcessed(String relativeName) {
        Path resolved = uploadDir.resolve(relativeName).normalize();
        if (!resolved.startsWith(uploadDir) || !resolved.startsWith(processedDir)) {
            throw new BadRequestException("Invalid processed file path.");
        }
        return resolved;
    }

    private static final java.util.Set<String> IMAGE_EXTENSIONS =
            java.util.Set.of(".png", ".jpg", ".jpeg", ".bmp", ".gif", ".webp");

    /**
     * Saves an uploaded image (QR scans) under a generated, unique name.
     * Only image formats the Python decoder accepts are allowed.
     * Returns the stored name, relative to the upload directory.
     */
    public String saveImage(MultipartFile file) {
        if (file == null || file.isEmpty()) {
            throw new BadRequestException("No file was uploaded.");
        }
        if (file.getSize() > MAX_BYTES) {
            throw new BadRequestException("File exceeds the 50 MB upload limit.");
        }
        String original = sanitize(file.getOriginalFilename());
        if (original == null || original.isBlank()) {
            throw new BadRequestException("The upload has no filename.");
        }
        String ext = extension(original);
        if (!IMAGE_EXTENSIONS.contains(ext)) {
            throw new BadRequestException(
                    "Only image files are supported for QR scans (png, jpg, jpeg, bmp, gif, webp); received: "
                            + (ext.isBlank() ? "no extension" : ext) + ".");
        }
        String stored = "img-" + Instant.now().toEpochMilli() + "-" + original;
        Path target = uploadDir.resolve(stored).normalize();
        if (!target.startsWith(uploadDir)) {
            throw new BadRequestException("Invalid filename.");
        }
        try {
            Files.copy(file.getInputStream(), target, StandardCopyOption.REPLACE_EXISTING);
        } catch (IOException ex) {
            throw new BadRequestException("Could not store the uploaded file: " + ex.getMessage());
        }
        return stored;
    }

    /**
     * Normalises a screenshot reference produced by the AI service (an absolute
     * path inside the shared uploads directory) into an upload-relative path
     * such as {@code screenshots/scan_123.png}. Returns null when the reference
     * is missing, points outside the uploads directory, or is not a plain image
     * reference - so a hostile value can never be persisted or served.
     */
    public String storedImageRef(String engineReference) {
        if (engineReference == null || engineReference.isBlank()) {
            return null;
        }
        final Path candidate;
        try {
            candidate = Path.of(engineReference.trim()).normalize();
        } catch (RuntimeException ex) {
            return null;
        }
        Path absolute = candidate.isAbsolute() ? candidate : uploadDir.resolve(candidate).normalize();
        if (!absolute.startsWith(uploadDir)) {
            return null;
        }
        String relative = uploadDir.relativize(absolute).toString().replace('\\', '/');
        if (relative.matches("^[A-Za-z0-9._-]+(?:/[A-Za-z0-9._-]+)*\\.(?:png|jpg|jpeg|bmp|gif|webp)$")) {
            return relative;
        }
        return null;
    }

    public static String sanitize(String name) {
        if (name == null) {
            return null;
        }
        String base = name.replace('\\', '/');
        int slash = base.lastIndexOf('/');
        base = slash >= 0 ? base.substring(slash + 1) : base;
        base = base.replaceAll("[^A-Za-z0-9._-]", "_");
        return base.length() > 120 ? base.substring(base.length() - 120) : base;
    }

    private static String extension(String name) {
        int dot = name.lastIndexOf('.');
        return dot >= 0 ? name.substring(dot).toLowerCase(Locale.ROOT) : "";
    }
}
