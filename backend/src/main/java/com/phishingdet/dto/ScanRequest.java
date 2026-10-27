package com.phishingdet.dto;

import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.Size;

/**
 * Request payloads for the four scan endpoints.
 *
 * <p>Bean Validation runs at the controller boundary so malformed input is
 * rejected with a 400 before any network call is made to the AI service. The
 * fields that only one modality needs (e.g. {@code url} for WEBSITE) are
 * optional at the type level and checked per-branch in the generic dispatcher.</p>
 */
public final class ScanRequest {

    private ScanRequest() {
    }

    /** POST /api/scans/website */
    public record Website(
            @NotBlank(message = "url is required.") @Size(max = 2048) String url,
            Boolean fetch,
            Boolean render) {
    }

    /** POST /api/scans/email */
    public record Email(
            @Size(max = 980) String subject,
            @NotBlank(message = "body is required.") @Size(max = 100000) String body,
            @Size(max = 320) String sender,
            @Size(max = 40) String spf,
            @Size(max = 40) String dkim,
            @Size(max = 40) String dmarc,
            Boolean analyzeLinks) {
    }

    /** POST /api/scans/sms */
    public record Sms(
            @NotBlank(message = "message is required.") @Size(max = 10000) String message,
            @Size(max = 64) String sender,
            Boolean analyzeLinks) {
    }

    /**
     * POST /api/scans - generic dispatcher (used by the browser extension and
     * simple clients that post {inputType, url}).
     */
    public record Create(
            @NotBlank(message = "inputType is required.") @Size(max = 20) String inputType,
            @Size(max = 2048) String url,
            @Size(max = 980) String subject,
            @Size(max = 100000) String body,
            @Size(max = 320) String sender,
            @Size(max = 40) String spf,
            @Size(max = 40) String dkim,
            @Size(max = 40) String dmarc,
            @Size(max = 10000) String message,
            Boolean fetch,
            Boolean render,
            Boolean analyzeLinks) {
    }
}
