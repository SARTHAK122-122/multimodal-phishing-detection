package com.phishingdet.service;

import com.fasterxml.jackson.core.type.TypeReference;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.phishingdet.dto.ScanDto;
import com.phishingdet.entity.Evidence;
import com.phishingdet.entity.ModalityResult;
import com.phishingdet.entity.Scan;
import com.phishingdet.exception.ResourceNotFoundException;
import com.phishingdet.repository.EvidenceRepository;
import com.phishingdet.repository.ModalityResultRepository;
import com.phishingdet.repository.ScanRepository;
import org.springframework.data.domain.Page;
import org.springframework.data.domain.PageRequest;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;

/** Read side for stored scans (history, report, evidence). */
@Service
public class ScanService {

    private final ScanRepository scanRepository;
    private final ModalityResultRepository modalityResultRepository;
    private final EvidenceRepository evidenceRepository;
    private final ObjectMapper mapper;
    private final StorageService storageService;

    public ScanService(ScanRepository scanRepository,
                       ModalityResultRepository modalityResultRepository,
                       EvidenceRepository evidenceRepository,
                       ObjectMapper mapper,
                       StorageService storageService) {
        this.scanRepository = scanRepository;
        this.modalityResultRepository = modalityResultRepository;
        this.evidenceRepository = evidenceRepository;
        this.mapper = mapper;
        this.storageService = storageService;
    }

    /** Scans visible to {@code visibleTo}: own + unattributed (see repository). */
    public Page<ScanDto> list(int page, int size, Long visibleTo) {
        int safeSize = Math.min(Math.max(size, 1), 200);
        int safePage = Math.max(page, 0);
        return scanRepository.findVisiblePage(visibleTo, PageRequest.of(safePage, safeSize))
                .map(this::toSummary);
    }

    public List<ScanDto> recent(int limit, Long visibleTo) {
        return scanRepository.findVisibleTop(visibleTo,
                        PageRequest.of(0, Math.max(Math.min(limit, 200), 1)))
                .stream()
                .map(this::toSummary)
                .toList();
    }

    @Transactional(readOnly = true)
    public ScanDto get(Long id, Long visibleTo) {
        // Loaded inside a read-only transaction so the two bag collections
        // (modalityResults, evidence) are initialised by two separate lazy
        // SELECTs - fetching both with JOIN FETCH is illegal for bags.
        Scan scan = scanRepository.findById(id)
                .orElseThrow(() -> new ResourceNotFoundException("Scan " + id + " not found."));
        requireVisible(scan, visibleTo);
        return toFull(scan);
    }

    /** Stored screenshot file name for a scan, or null when none was captured. */
    @Transactional(readOnly = true)
    public String screenshotFile(Long scanId, Long visibleTo) {
        Scan scan = scanRepository.findById(scanId)
                .orElseThrow(() -> new ResourceNotFoundException("Scan " + scanId + " not found."));
        requireVisible(scan, visibleTo);
        return scan.getScreenshotFile();
    }

    @Transactional(readOnly = true)
    public List<ScanDto.EvidenceDto> evidence(Long scanId, Long visibleTo) {
        Scan scan = scanRepository.findById(scanId)
                .orElseThrow(() -> new ResourceNotFoundException("Scan " + scanId + " not found."));
        requireVisible(scan, visibleTo);
        return evidenceRepository.findByScanId(scanId).stream().map(this::evidenceDto).toList();
    }

    /**
     * A scan owned by another account is reported as missing (404), never as
     * forbidden - other users' scan ids must not be enumerable.
     */
    private void requireVisible(Scan scan, Long visibleTo) {
        com.phishingdet.entity.User owner = scan.getUser();
        if (owner != null && (visibleTo == null || !owner.getId().equals(visibleTo))) {
            throw new ResourceNotFoundException("Scan " + scan.getId() + " not found.");
        }
    }

    private ScanDto.EvidenceDto evidenceDto(Evidence e) {
        return new ScanDto.EvidenceDto(
                e.getId(), e.getModality(), e.getEvidenceType(), e.getDescription(),
                e.getSeverity(), e.getSupportingValue(), e.getDirection(), e.getKind());
    }

    public ScanDto toSummary(Scan scan) {
        return new ScanDto(
                scan.getId(), scan.getInputType(), scan.getSubmittedUrl(), scan.getNormalizedUrl(),
                iso(scan.getSubmittedAt()), iso(scan.getCompletedAt()),
                scan.getFinalPrediction(), scan.getRiskLevel(), scan.getRiskScore(),
                scan.getProcessingTimeMs(), scan.getStatus(), scan.getModelVersion(),
                scan.getExplanation(), parseStringList(scan.getMissingModalities()),
                scan.isSeedData(), List.of(), List.of(), List.of(), Map.of(), null);
    }

    public ScanDto toFull(Scan scan) {
        List<ScanDto.ModalityResultDto> modalities = scan.getModalityResults().stream()
                .map(m -> new ScanDto.ModalityResultDto(
                        m.getId(), m.getModality(), m.getModelName(), m.getModelVersion(),
                        m.getPrediction(), m.getRiskScore(), m.getStatus(),
                        m.getProcessingTimeMs(), m.getDetailJson()))
                .toList();

        List<ScanDto.EvidenceDto> evidence = scan.getEvidence().stream()
                .map(this::evidenceDto)
                .toList();

        if (modalities.isEmpty()) {
            modalities = modalityResultRepository.findByScanIdOrderByModality(scan.getId()).stream()
                    .map(m -> new ScanDto.ModalityResultDto(
                            m.getId(), m.getModality(), m.getModelName(), m.getModelVersion(),
                            m.getPrediction(), m.getRiskScore(), m.getStatus(),
                            m.getProcessingTimeMs(), m.getDetailJson()))
                    .toList();
        }
        if (evidence.isEmpty()) {
            evidence = evidenceRepository.findByScanId(scan.getId()).stream()
                    .map(this::evidenceDto)
                    .toList();
        }

        return new ScanDto(
                scan.getId(), scan.getInputType(), scan.getSubmittedUrl(), scan.getNormalizedUrl(),
                iso(scan.getSubmittedAt()), iso(scan.getCompletedAt()),
                scan.getFinalPrediction(), scan.getRiskLevel(), scan.getRiskScore(),
                scan.getProcessingTimeMs(), scan.getStatus(), scan.getModelVersion(),
                scan.getExplanation(), parseStringList(scan.getMissingModalities()),
                scan.isSeedData(), modalities, evidence,
                parseStringList(resultField(scan.getResultJson(), "caveats")),
                parseWeights(resultField(scan.getResultJson(), "weightsUsed")),
                scan.getScreenshotFile() == null ? null : "/api/scans/" + scan.getId() + "/screenshot");
    }

    /** Pulls one array-of-strings field out of the stored engine payload. */
    @SuppressWarnings("unchecked")
    private List<String> parseStringList(String json) {
        if (json == null || json.isBlank()) {
            return List.of();
        }
        try {
            return mapper.readValue(json, new TypeReference<List<String>>() {});
        } catch (Exception e) {
            return List.of();
        }
    }

    /** Returns the named field of result_json as a raw JSON string, or null. */
    private String resultField(String resultJson, String field) {
        if (resultJson == null || resultJson.isBlank()) {
            return null;
        }
        try {
            Map<String, Object> parsed = mapper.readValue(resultJson, new TypeReference<Map<String, Object>>() {});
            Object value = parsed.get(field);
            return value == null ? null : mapper.writeValueAsString(value);
        } catch (Exception ex) {
            return null;
        }
    }

    /** Parses the fusion weights ({name: weight}) from a JSON object string. */
    private Map<String, Double> parseWeights(String json) {
        if (json == null || json.isBlank()) {
            return Map.of();
        }
        try {
            Map<String, Object> raw = mapper.readValue(json, new TypeReference<Map<String, Object>>() {});
            Map<String, Double> out = new java.util.LinkedHashMap<>();
            raw.forEach((k, v) -> {
                if (v instanceof Number n) {
                    out.put(k, n.doubleValue());
                }
            });
            return out;
        } catch (Exception ex) {
            return Map.of();
        }
    }

    private String iso(java.time.ZonedDateTime time) {
        return time == null ? null : time.toString();
    }

    /**
     * Persists one AI-service result (website / email / SMS / QR) as a Scan row
     * with its child modality_results and evidence rows, and returns the original
     * AI payload enriched with the stored {@code id}.
     *
     * <p>Every value is normalised against the schema's CHECK constraints rather
     * than trusted: a value the database would reject becomes a safe default
     * (UNKNOWN / INFO) instead of failing the whole scan write.</p>
     */
    @Transactional
    public Map<String, Object> persist(String inputType, Map<String, Object> ai) {
        return persist(inputType, ai, null);
    }

    /**
     * Persists an engine result. {@code owner} is the signed-in user when the
     * scan came from an authenticated session, or {@code null} for anonymous
     * callers (browser extension / open API) - unattributed scans stay visible
     * to signed-in users as shared device scans.
     */
    @Transactional
    public Map<String, Object> persist(String inputType, Map<String, Object> ai,
                                       com.phishingdet.entity.User owner) {
        Scan scan = new Scan();
        scan.setUser(owner);
        scan.setInputType(oneOf(inputType, List.of("WEBSITE", "EMAIL", "SMS", "QR"), "WEBSITE"));
        scan.setSubmittedUrl(nonBlank(text(ai.get("submittedInput"), null), "unknown"));
        scan.setNormalizedUrl(text(ai.get("normalizedInput"), null));
        scan.setStatus(oneOf(ai.get("status"),
                List.of("PENDING", "RUNNING", "COMPLETED", "PARTIAL", "FAILED", "SEED_DEMO"), "COMPLETED"));
        scan.setFinalPrediction(oneOf(ai.get("classification"),
                List.of("PHISHING", "LEGITIMATE", "SUSPICIOUS", "UNKNOWN"), "UNKNOWN"));
        scan.setRiskLevel(oneOf(ai.get("riskLevel"),
                List.of("LOW", "MEDIUM", "HIGH", "CRITICAL", "UNKNOWN"), "UNKNOWN"));
        scan.setRiskScore(clampedNumber(ai.get("riskScore")));
        scan.setProcessingTimeMs(wholeNumber(ai.get("processingTimeMs")));
        scan.setExplanation(text(ai.get("explanation"), null));
        scan.setMissingModalities(jsonList(ai.get("missingModalities")));
        scan.setCompletedAt(java.time.ZonedDateTime.now(java.time.ZoneOffset.UTC));
        scan.setSeedData(false);
        // The full engine payload so the report page can show exactly what the
        // user saw (caveats, fusion weights, per-modality detail) after a reload.
        scan.setResultJson(objectToJson(ai));
        // Screenshot references from the engine are absolute paths inside the
        // shared uploads directory; only the upload-relative name is stored.
        scan.setScreenshotFile(storageService.storedImageRef(text(ai.get("screenshot"), null)));

        List<String> modelVersions = new ArrayList<>();
        if (ai.get("modalities") instanceof List<?> rows) {
            for (Object row : rows) {
                if (!(row instanceof Map<?, ?> m)) {
                    continue;
                }
                ModalityResult mr = new ModalityResult();
                mr.setScan(scan);
                mr.setModality(oneOf(m.get("modality"),
                        List.of("URL", "HTML", "NLP", "VISION", "FORM_LINK", "METADATA", "FUSION"), "NLP"));
                mr.setModelName(nonBlank(text(m.get("modelName"), null), "n/a"));
                mr.setModelVersion(nonBlank(text(m.get("modelVersion"), null), null));
                // prediction stays NULL when the module produced no verdict - the
                // CHECK constraint accepts NULL, which is how the UI distinguishes
                // "no score" from "scored as legitimate".
                mr.setPrediction(allowNullOneOf(m.get("prediction"),
                        List.of("PHISHING", "LEGITIMATE", "SUSPICIOUS", "UNKNOWN")));
                mr.setRiskScore(clampedNumber(m.get("riskScore")));
                mr.setStatus(oneOf(m.get("status"),
                        List.of("OK", "FAILED", "SKIPPED", "MODEL_MISSING"), "OK"));
                mr.setProcessingTimeMs(wholeNumber(m.get("processingTimeMs")));
                mr.setDetailJson(detailWithModelType(m));
                mr.setSeedData(false);
                scan.getModalityResults().add(mr);
                if (mr.getModelVersion() != null) {
                    modelVersions.add(mr.getModelVersion());
                }
            }
        }
        scan.setModelVersion(modelVersions.isEmpty() ? null : String.join(", ", modelVersions));

        if (ai.get("evidence") instanceof List<?> rows) {
            for (Object row : rows) {
                if (!(row instanceof Map<?, ?> m)) {
                    continue;
                }
                Evidence e = new Evidence();
                e.setScan(scan);
                String modality = nonBlank(text(m.get("modality"), null), "NLP");
                String evidenceType = nonBlank(text(m.get("evidenceType"), null), "finding");
                e.setModality(modality.substring(0, Math.min(modality.length(), 30)));
                e.setEvidenceType(evidenceType.substring(0, Math.min(evidenceType.length(), 60)));
                e.setDescription(nonBlank(text(m.get("description"), null), "(no description)"));
                e.setSeverity(oneOf(m.get("severity"),
                        List.of("INFO", "LOW", "MEDIUM", "HIGH", "CRITICAL"), "INFO"));
                e.setDirection(oneOf(m.get("direction"),
                        List.of("risk", "safety", "neutral"), "neutral"));
                e.setKind(oneOf(m.get("kind"), List.of("FINDING", "INFERENCE"), "FINDING"));
                e.setSupportingValue(text(m.get("supportingValue"), null));
                e.setSeedData(false);
                scan.getEvidence().add(e);
            }
        }

        scanRepository.save(scan);

        Map<String, Object> out = new LinkedHashMap<>(ai);
        out.put("id", scan.getId());
        out.put("inputType", scan.getInputType());
        return out;
    }

    // ---- normalisation helpers (schema CHECK constraints are the contract) ----

    private String text(Object value, String fallback) {
        if (value == null) {
            return fallback;
        }
        String s = String.valueOf(value).trim();
        return s.isEmpty() ? fallback : s;
    }

    private String nonBlank(String value, String fallback) {
        return value == null || value.isBlank() ? fallback : value;
    }

    private String oneOf(Object value, List<String> allowed, String fallback) {
        String s = text(value, null);
        return s != null && allowed.contains(s) ? s : fallback;
    }

    private String allowNullOneOf(Object value, List<String> allowed) {
        String s = text(value, null);
        return s == null ? null : (allowed.contains(s) ? s : null);
    }

    private Double clampedNumber(Object value) {
        if (value == null) {
            return null;
        }
        try {
            double d = Double.parseDouble(String.valueOf(value));
            if (Double.isNaN(d) || Double.isInfinite(d)) {
                return null;
            }
            return Math.max(0.0, Math.min(1.0, d));
        } catch (NumberFormatException ex) {
            return null;
        }
    }

    private Long wholeNumber(Object value) {
        if (value == null) {
            return null;
        }
        try {
            return (long) Math.round(Double.parseDouble(String.valueOf(value)));
        } catch (NumberFormatException ex) {
            return null;
        }
    }

    private String jsonList(Object value) {
        if (value == null) {
            return "[]";
        }
        if (value instanceof List<?>) {
            return objectToJson(value);
        }
        String s = String.valueOf(value).trim();
        return s.startsWith("[") ? s : "[]";
    }

    private String objectToJson(Object value) {
        if (value == null) {
            return null;
        }
        try {
            return mapper.writeValueAsString(value);
        } catch (Exception ex) {
            return null;
        }
    }

    /**
     * Serialises a modality's detail object with the module's type folded in, so
     * the report UI can distinguish a trained model (ML) from a transparent rule
     * scorer (RULE_BASED) - the honesty requirement for every module.
     */
    private String detailWithModelType(Map<?, ?> modality) {
        Object modelType = modality.get("modelType");
        Object detail = modality.get("detail");
        if (modelType == null) {
            return objectToJson(detail);
        }
        Map<String, Object> merged = new LinkedHashMap<>();
        merged.put("modelType", String.valueOf(modelType));
        if (detail instanceof Map<?, ?> d) {
            d.forEach((k, v) -> merged.put(String.valueOf(k), v));
        } else if (detail != null) {
            merged.put("detail", detail);
        }
        return objectToJson(merged);
    }

    /** Exposed for the create-scan flow (Phase 8) so mapping stays in one place. */
    public ObjectMapper objectMapper() {
        return mapper;
    }
}
