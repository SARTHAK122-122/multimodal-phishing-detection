package com.phishingdet.controller;

import com.phishingdet.dto.ScanDto;
import com.phishingdet.dto.ScanRequest;
import com.phishingdet.exception.BadRequestException;
import com.phishingdet.service.AiServiceClient;
import com.phishingdet.service.CurrentUserService;
import com.phishingdet.service.ScanService;
import com.phishingdet.service.StorageService;
import jakarta.validation.Valid;
import org.springframework.data.domain.Page;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;
import org.springframework.web.multipart.MultipartFile;

import java.util.LinkedHashMap;
import java.util.List;
import java.util.Locale;
import java.util.Map;

/**
 * Scan API - entry point for the four detectors.
 *
 * <pre>
 * POST /api/scans/website   {url, fetch?, render?}        multimodal webpage scan
 * POST /api/scans/email     {subject, body, sender?, ...} email scan
 * POST /api/scans/sms       {message, sender?, ...}       SMS/message scan
 * POST /api/scans/qr        multipart field "file"        QR image scan
 * POST /api/scans           {inputType, ...}              generic dispatcher
 *
 * GET  /api/scans                 paginated history
 * GET  /api/scans/history         recent scans (dashboard)
 * GET  /api/scans/{id}            full report (modalities + evidence)
 * GET  /api/scans/{id}/evidence   evidence items only
 * </pre>
 *
 * <p>Spring Boot performs no detection itself: every POST forwards the input to
 * the Python AI service, then persists the returned verdict, per-modality
 * outputs and evidence through {@link ScanService#persist}. If the AI service is
 * down the caller gets an honest 503 - never a fabricated score.</p>
 *
 * <p><b>Ownership:</b> POST endpoints accept both signed-in sessions and
 * anonymous callers (the Chrome extension). A scan made while signed in is saved
 * to that account; reads return the caller's scans plus unattributed ones.</p>
 */
@RestController
@RequestMapping("/api")
public class ScanController {

    private final ScanService scanService;
    private final AiServiceClient aiServiceClient;
    private final StorageService storageService;
    private final CurrentUserService currentUserService;

    public ScanController(ScanService scanService,
                          AiServiceClient aiServiceClient,
                          StorageService storageService,
                          CurrentUserService currentUserService) {
        this.scanService = scanService;
        this.aiServiceClient = aiServiceClient;
        this.storageService = storageService;
        this.currentUserService = currentUserService;
    }

    // ---------- reads ----------

    @GetMapping("/scans")
    public Page<ScanDto> list(@RequestParam(defaultValue = "0") int page,
                              @RequestParam(defaultValue = "25") int size) {
        return scanService.list(page, size, currentUserService.currentIdOrNull());
    }

    @GetMapping("/scans/history")
    public List<ScanDto> history(@RequestParam(defaultValue = "10") int limit) {
        return scanService.recent(limit, currentUserService.currentIdOrNull());
    }

    @GetMapping("/scans/{id}")
    public ScanDto get(@PathVariable Long id) {
        return scanService.get(id, currentUserService.currentIdOrNull());
    }

    @GetMapping("/scans/{id}/evidence")
    public List<ScanDto.EvidenceDto> evidence(@PathVariable Long id) {
        return scanService.evidence(id, currentUserService.currentIdOrNull());
    }

    /**
     * Streams the screenshot captured during a website scan (stored in the
     * shared uploads directory). The file name is looked up from the scan row -
     * the client cannot supply a path.
     */
    @GetMapping("/scans/{id}/screenshot")
    public ResponseEntity<byte[]> screenshot(@PathVariable Long id) throws java.io.IOException {
        String name = scanService.screenshotFile(id, currentUserService.currentIdOrNull());
        if (name == null) {
            throw new com.phishingdet.exception.ResourceNotFoundException(
                    "This scan has no stored screenshot.");
        }
        java.nio.file.Path file = storageService.resolveUpload(name);
        if (!java.nio.file.Files.exists(file)) {
            throw new com.phishingdet.exception.ResourceNotFoundException(
                    "The screenshot file is no longer available on disk.");
        }
        String contentType = switch (name.substring(name.lastIndexOf('.') + 1).toLowerCase(Locale.ROOT)) {
            case "jpg", "jpeg" -> "image/jpeg";
            case "gif" -> "image/gif";
            case "webp" -> "image/webp";
            case "bmp" -> "image/bmp";
            default -> "image/png";
        };
        return ResponseEntity.ok()
                .contentType(org.springframework.http.MediaType.parseMediaType(contentType))
                .body(java.nio.file.Files.readAllBytes(file));
    }

    // ---------- analysis (delegate to Python, then persist) ----------

    /** Signed-in owner of a new scan, or null for anonymous (extension) callers. */
    private com.phishingdet.entity.User owner() {
        return currentUserService.current().orElse(null);
    }

    @PostMapping("/scans/website")
    public Map<String, Object> website(@Valid @RequestBody ScanRequest.Website request) {
        Map<String, Object> ai = aiServiceClient.analyzeWebsite(
                websiteBody(request.url(), request.fetch(), request.render()));
        return scanService.persist("WEBSITE", ai, owner());
    }

    @PostMapping("/scans/email")
    public Map<String, Object> email(@Valid @RequestBody ScanRequest.Email request) {
        return scanService.persist("EMAIL", aiServiceClient.analyzeEmail(emailBody(
                request.subject(), request.body(), request.sender(),
                request.spf(), request.dkim(), request.dmarc(), request.analyzeLinks())), owner());
    }

    @PostMapping("/scans/sms")
    public Map<String, Object> sms(@Valid @RequestBody ScanRequest.Sms request) {
        return scanService.persist("SMS", aiServiceClient.analyzeSms(
                smsBody(request.message(), request.sender(), request.analyzeLinks())), owner());
    }

    /**
     * QR scan: the image is stored in the shared upload directory (the Python
     * service decodes it in place - the bytes never round-trip through JSON) and
     * the decoded destination is analysed by the AI service without being visited.
     */
    @PostMapping("/scans/qr")
    public Map<String, Object> qr(@RequestParam("file") MultipartFile file) {
        String stored = storageService.saveImage(file);
        Map<String, Object> ai = aiServiceClient.analyzeQr(Map.of("filePath", stored));
        Map<String, Object> result = scanService.persist("QR", ai, owner());
        result.put("storedFile", stored);
        return result;
    }

    /** Generic dispatcher for clients that post {inputType, ...} in one shape. */
    @PostMapping("/scans")
    public Map<String, Object> create(@Valid @RequestBody ScanRequest.Create request) {
        String type = request.inputType().trim().toUpperCase(Locale.ROOT);
        Map<String, Object> ai = switch (type) {
            case "WEBSITE" -> {
                require(request.url(), "url");
                yield aiServiceClient.analyzeWebsite(
                        websiteBody(request.url(), request.fetch(), request.render()));
            }
            case "EMAIL" -> {
                require(request.body(), "body");
                yield aiServiceClient.analyzeEmail(emailBody(
                        request.subject(), request.body(), request.sender(),
                        request.spf(), request.dkim(), request.dmarc(), request.analyzeLinks()));
            }
            case "SMS" -> {
                require(request.message(), "message");
                yield aiServiceClient.analyzeSms(
                        smsBody(request.message(), request.sender(), request.analyzeLinks()));
            }
            case "QR" -> throw new BadRequestException(
                    "QR scans need the image itself: POST /api/scans/qr with multipart form field 'file'.");
            default -> throw new BadRequestException(
                    "Unknown inputType '" + type + "'. Use WEBSITE, EMAIL, SMS or QR.");
        };
        return scanService.persist(type, ai, owner());
    }

    // ---------- request shaping ----------

    private Map<String, Object> websiteBody(String url, Boolean fetch, Boolean render) {
        Map<String, Object> body = new LinkedHashMap<>();
        body.put("url", url);
        body.put("fetch", fetch == null || fetch);
        body.put("render", render == null || render);
        return body;
    }

    private Map<String, Object> emailBody(String subject, String body, String sender,
                                          String spf, String dkim, String dmarc,
                                          Boolean analyzeLinks) {
        Map<String, Object> out = new LinkedHashMap<>();
        out.put("subject", subject == null ? "" : subject);
        out.put("body", body);
        out.put("sender", sender == null ? "" : sender);
        out.put("spf", spf == null ? "" : spf);
        out.put("dkim", dkim == null ? "" : dkim);
        out.put("dmarc", dmarc == null ? "" : dmarc);
        out.put("analyzeLinks", analyzeLinks == null || analyzeLinks);
        return out;
    }

    private Map<String, Object> smsBody(String message, String sender, Boolean analyzeLinks) {
        Map<String, Object> out = new LinkedHashMap<>();
        out.put("message", message);
        out.put("sender", sender == null ? "" : sender);
        out.put("analyzeLinks", analyzeLinks == null || analyzeLinks);
        return out;
    }

    private void require(String value, String field) {
        if (value == null || value.isBlank()) {
            throw new BadRequestException(field + " is required for this inputType.");
        }
    }
}
