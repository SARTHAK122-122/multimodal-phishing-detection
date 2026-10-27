package com.phishingdet.service;

import com.fasterxml.jackson.databind.ObjectMapper;
import com.phishingdet.entity.Evidence;
import com.phishingdet.entity.ModalityResult;
import com.phishingdet.entity.Scan;
import com.phishingdet.repository.EvidenceRepository;
import com.phishingdet.repository.ModalityResultRepository;
import com.phishingdet.repository.ScanRepository;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.io.TempDir;
import org.mockito.ArgumentCaptor;

import java.nio.file.Files;
import java.nio.file.Path;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;

import static org.assertj.core.api.Assertions.assertThat;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.when;

/**
 * Unit tests for the write side of scan persistence: the mapping from an
 * AI-service payload to the database schema, including the normalisation rules
 * that keep stored rows inside the schema's CHECK constraints.
 *
 * <p>No Spring context and no database are needed: the repositories are mocked
 * and the scan entity is captured so its child rows can be inspected.</p>
 */
class ScanServicePersistTest {

    private static final Long SAVED_ID = 42L;

    private ScanRepository scanRepository;
    private ScanService service;
    private Path uploadDir;

    @org.junit.jupiter.api.io.TempDir
    Path tempDir;

    @BeforeEach
    void init() throws Exception {
        uploadDir = Files.createDirectories(tempDir.resolve("uploads"));
        Files.createDirectories(uploadDir.resolve("screenshots"));
        Files.createDirectories(tempDir.resolve("processed"));

        scanRepository = mock(ScanRepository.class);
        when(scanRepository.save(any(Scan.class))).thenAnswer(invocation -> {
            Scan scan = invocation.getArgument(0);
            scan.setId(SAVED_ID);
            return scan;
        });

        StorageService storage = new StorageService(
                uploadDir.toString(), tempDir.resolve("processed").toString());
        service = new ScanService(
                scanRepository,
                mock(ModalityResultRepository.class),
                mock(EvidenceRepository.class),
                new ObjectMapper(),
                storage);
    }

    /* ----------------------------- fixtures ------------------------------ */

    /** Mirrors one real FastAPI /analyze/website payload. */
    private Map<String, Object> aiPayload() {
        Map<String, Object> ai = new LinkedHashMap<>();
        ai.put("inputType", "WEBSITE");
        ai.put("submittedInput", "https://example.com");
        ai.put("normalizedInput", "https://example.com/");
        ai.put("status", "PARTIAL");
        ai.put("classification", "LEGITIMATE");
        ai.put("riskLevel", "LOW");
        ai.put("riskScore", 0.1234);
        ai.put("processingTimeMs", 1500);
        ai.put("explanation", "Fused 4 modality scores.");
        ai.put("missingModalities", List.of("VISION"));
        ai.put("caveats", List.of("Some modalities were unavailable (VISION)."));
        ai.put("weightsUsed", Map.of("URL", 0.18, "NLP", 0.20, "HTML", 0.26));
        ai.put("screenshot", uploadDir.resolve("screenshots").resolve("scan_1.png").toString());

        Map<String, Object> modality = new LinkedHashMap<>();
        modality.put("modality", "URL");
        modality.put("status", "OK");
        modality.put("prediction", "LEGITIMATE");
        modality.put("riskScore", 0.05);
        modality.put("modelName", "url_random_forest+url_xgboost");
        modality.put("modelVersion", "v3-host16");
        modality.put("modelType", "ML");
        modality.put("detail", Map.of("note", "ensemble average"));
        ai.put("modalities", List.of(modality));

        Map<String, Object> evidence = new LinkedHashMap<>();
        evidence.put("modality", "URL");
        evidence.put("evidenceType", "url_feature_host_entropy");
        evidence.put("description", "Host character entropy is 3.21 (order-based).");
        evidence.put("severity", "MEDIUM");
        evidence.put("supportingValue", "3.21");
        evidence.put("direction", "risk");
        evidence.put("kind", "INFERENCE");
        ai.put("evidence", List.of(evidence));
        return ai;
    }

    private Scan capturedScan() {
        ArgumentCaptor<Scan> captor = ArgumentCaptor.forClass(Scan.class);
        org.mockito.Mockito.verify(scanRepository).save(captor.capture());
        return captor.getValue();
    }

    /* -------------------------------- tests ------------------------------ */

    @Test
    void persistStoresScanModalitiesAndEvidence() {
        Map<String, Object> out = service.persist("WEBSITE", aiPayload());

        assertThat(out.get("id")).isEqualTo(SAVED_ID);
        assertThat(out.get("inputType")).isEqualTo("WEBSITE");

        Scan scan = capturedScan();
        assertThat(scan.getInputType()).isEqualTo("WEBSITE");
        assertThat(scan.getSubmittedUrl()).isEqualTo("https://example.com");
        assertThat(scan.getFinalPrediction()).isEqualTo("LEGITIMATE");
        assertThat(scan.getRiskLevel()).isEqualTo("LOW");
        assertThat(scan.getRiskScore()).isEqualTo(0.1234);
        assertThat(scan.getStatus()).isEqualTo("PARTIAL");
        assertThat(scan.getMissingModalities()).contains("VISION");
        assertThat(scan.isSeedData()).isFalse();
        // The engine payload is kept verbatim so the report page can reproduce it.
        assertThat(scan.getResultJson()).contains("caveats").contains("weightsUsed");

        assertThat(scan.getModalityResults()).hasSize(1);
        ModalityResult modality = scan.getModalityResults().get(0);
        assertThat(modality.getModality()).isEqualTo("URL");
        assertThat(modality.getModelName()).isEqualTo("url_random_forest+url_xgboost");
        assertThat(modality.getModelVersion()).isEqualTo("v3-host16");
        assertThat(modality.getPrediction()).isEqualTo("LEGITIMATE");
        assertThat(modality.getStatus()).isEqualTo("OK");

        assertThat(scan.getEvidence()).hasSize(1);
        Evidence evidence = scan.getEvidence().get(0);
        assertThat(evidence.getSeverity()).isEqualTo("MEDIUM");
        assertThat(evidence.getDirection()).isEqualTo("risk");
        assertThat(evidence.getKind()).isEqualTo("INFERENCE");
        assertThat(evidence.getEvidenceType()).isEqualTo("url_feature_host_entropy");
    }

    @Test
    void persistNormalisesValuesTheSchemaWouldReject() {
        Map<String, Object> ai = aiPayload();
        ai.put("classification", "phishing");   // lowercase: not an enum value
        ai.put("riskLevel", "SEVERE");          // unknown level
        ai.put("riskScore", 1.7);               // out of the [0,1] check range
        ai.put("status", "DONE");               // unknown lifecycle value

        service.persist("mobile", ai);          // unknown input type

        Scan scan = capturedScan();
        assertThat(scan.getInputType()).isEqualTo("WEBSITE");     // falls back
        assertThat(scan.getFinalPrediction()).isEqualTo("UNKNOWN");
        assertThat(scan.getRiskLevel()).isEqualTo("UNKNOWN");
        assertThat(scan.getRiskScore()).isEqualTo(1.0);           // clamped
        assertThat(scan.getStatus()).isEqualTo("COMPLETED");      // falls back
    }

    @Test
    void persistNormalisesEvidenceSeverityAndKeepsTruncationSafe() {
        Map<String, Object> ai = aiPayload();
        Map<String, Object> evidence = new LinkedHashMap<>();
        evidence.put("modality", "NLP");
        evidence.put("evidenceType", "manipulative_language_credential_request".repeat(4));
        evidence.put("description", "Asks for a password.");
        evidence.put("severity", "WARNING");     // not in the CHECK list
        evidence.put("direction", "up");         // not in the CHECK list
        evidence.put("kind", "GUESS");           // not in the CHECK list
        ai.put("evidence", List.of(evidence));

        service.persist("EMAIL", ai);

        Evidence stored = capturedScan().getEvidence().get(0);
        assertThat(stored.getSeverity()).isEqualTo("INFO");      // safe default
        assertThat(stored.getDirection()).isEqualTo("neutral");
        assertThat(stored.getKind()).isEqualTo("FINDING");
        assertThat(stored.getEvidenceType()).hasSizeLessThanOrEqualTo(60);
        assertThat(stored.getModality()).hasSizeLessThanOrEqualTo(30);
    }

    @Test
    void persistRelativisesScreenshotInsideTheUploadDirectory() {
        Map<String, Object> ai = aiPayload();
        ai.put("screenshot", uploadDir.resolve("screenshots").resolve("scan_7.png").toString());

        service.persist("WEBSITE", ai);

        assertThat(capturedScan().getScreenshotFile())
                .isEqualTo("screenshots/scan_7.png");
    }

    @Test
    void persistRejectsScreenshotReferencesOutsideTheUploadDirectory() {
        Map<String, Object> ai = aiPayload();
        ai.put("screenshot", Path.of("C:", "Windows", "System32", "evil.png").toString());

        service.persist("WEBSITE", ai);

        assertThat(capturedScan().getScreenshotFile()).isNull();
    }

    @Test
    void persistFoldsModelTypeIntoDetailJson() {
        service.persist("WEBSITE", aiPayload());

        String detail = capturedScan().getModalityResults().get(0).getDetailJson();
        assertThat(detail).contains("\"modelType\":\"ML\"").contains("ensemble average");
    }

    @Test
    void toFullRebuildsReportFieldsFromTheStoredPayload() {
        Map<String, Object> ai = aiPayload();
        ai.put("screenshot", uploadDir.resolve("screenshots").resolve("scan_9.png").toString());
        service.persist("WEBSITE", ai);

        var dto = service.toFull(capturedScan());

        assertThat(dto.caveats()).containsExactly("Some modalities were unavailable (VISION).");
        assertThat(dto.weightsUsed())
                .containsEntry("URL", 0.18)
                .containsEntry("NLP", 0.20)
                .containsEntry("HTML", 0.26);
        assertThat(dto.screenshotUrl()).isEqualTo("/api/scans/" + SAVED_ID + "/screenshot");
        assertThat(dto.inputType()).isEqualTo("WEBSITE");
    }

    @Test
    void persistToleratesMissingOptionalSections() {
        Map<String, Object> ai = new LinkedHashMap<>();
        ai.put("submittedInput", "");
        ai.put("classification", "UNKNOWN");
        ai.put("riskScore", null);
        ai.put("status", "FAILED");
        ai.put("modalities", List.of());
        ai.put("evidence", List.of());

        service.persist("SMS", ai);

        Scan scan = capturedScan();
        // A failed scan is still stored, honestly: UNKNOWN verdict, no invented score.
        assertThat(scan.getSubmittedUrl()).isEqualTo("unknown");
        assertThat(scan.getFinalPrediction()).isEqualTo("UNKNOWN");
        assertThat(scan.getRiskScore()).isNull();
        assertThat(scan.getStatus()).isEqualTo("FAILED");
        assertThat(scan.getCompletedAt()).isNotNull();
        assertThat(scan.getModalityResults()).isEmpty();
        assertThat(scan.getEvidence()).isEmpty();
    }
}
