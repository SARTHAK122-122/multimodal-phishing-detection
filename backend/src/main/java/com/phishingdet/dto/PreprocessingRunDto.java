package com.phishingdet.dto;

import java.time.ZonedDateTime;
import java.util.List;
import java.util.Map;

/** A persisted preprocessing run plus the full result payload from Python. */
public record PreprocessingRunDto(
        Long id,
        Long datasetId,
        String datasetName,
        String startedAt,
        String completedAt,
        int inputRows,
        int outputRows,
        int duplicatesRemoved,
        int invalidRowsRemoved,
        int missingValuesHandled,
        String status,
        String errorMessage,
        String outputFilename,
        List<Map<String, Object>> transformations,
        Map<String, Object> parameters,
        List<String> warnings,
        Map<String, Long> classDistributionBefore,
        Map<String, Long> classDistributionAfter,
        Map<String, Long> missingBefore,
        Map<String, Long> missingAfter,
        Map<String, Object> featureReport,
        Integer elapsedMs) {

    public static PreprocessingRunDto from(com.phishingdet.entity.PreprocessingRun run,
                                           String datasetName,
                                           Map<String, Object> result) {
        return new PreprocessingRunDto(
                run.getId(),
                run.getDataset().getId(),
                datasetName,
                iso(run.getStartedAt()),
                iso(run.getCompletedAt()),
                run.getInputRows(),
                run.getOutputRows(),
                run.getDuplicatesRemoved(),
                run.getInvalidRowsRemoved(),
                run.getMissingValuesHandled(),
                run.getStatus(),
                run.getErrorMessage(),
                run.getOutputFilename(),
                jsonList(run.getTransformationsApplied()),
                jsonMap(run.getParametersJson()),
                jsonStringList(run.getWarningsJson()),
                resultMap(result, "classDistributionBefore"),
                resultMap(result, "classDistributionAfter"),
                resultMap(result, "missingBefore"),
                resultMap(result, "missingAfter"),
                resultObjectMap(result, "featureReport"),
                result.get("elapsedMs") instanceof Integer i ? i : null);
    }

    private static String iso(ZonedDateTime time) {
        return time == null ? null : time.toString();
    }

    @SuppressWarnings("unchecked")
    private static List<Map<String, Object>> jsonList(String json) {
        if (json == null || json.isBlank()) return List.of();
        try {
            com.fasterxml.jackson.databind.ObjectMapper mapper = new com.fasterxml.jackson.databind.ObjectMapper();
            return mapper.readValue(json, List.class);
        } catch (Exception e) {
            return List.of(Map.of("error", "unreadable JSON: " + e.getMessage()));
        }
    }

    @SuppressWarnings("unchecked")
    private static Map<String, Object> jsonMap(String json) {
        if (json == null || json.isBlank()) return Map.of();
        try {
            com.fasterxml.jackson.databind.ObjectMapper mapper = new com.fasterxml.jackson.databind.ObjectMapper();
            return mapper.readValue(json, Map.class);
        } catch (Exception e) {
            return Map.of("error", "unreadable JSON");
        }
    }

    private static List<String> jsonStringList(String json) {
        if (json == null || json.isBlank()) return List.of();
        try {
            com.fasterxml.jackson.databind.ObjectMapper mapper = new com.fasterxml.jackson.databind.ObjectMapper();
            return mapper.readValue(json, mapper.getTypeFactory()
                    .constructCollectionType(java.util.List.class, String.class));
        } catch (Exception e) {
            return List.of();
        }
    }

    @SuppressWarnings("unchecked")
    private static Map<String, Long> resultMap(Map<String, Object> result, String key) {
        Object value = result == null ? null : result.get(key);
        if (value instanceof Map<?, ?> map) {
            Map<String, Long> out = new java.util.LinkedHashMap<>();
            map.forEach((k, v) -> out.put(String.valueOf(k), v instanceof Number n ? n.longValue() : null));
            return out;
        }
        return Map.of();
    }

    @SuppressWarnings("unchecked")
    private static Map<String, Object> resultObjectMap(Map<String, Object> result, String key) {
        Object value = result == null ? null : result.get(key);
        if (value instanceof Map<?, ?> map) {
            Map<String, Object> out = new java.util.LinkedHashMap<>();
            map.forEach((k, v) -> out.put(String.valueOf(k), v));
            return out;
        }
        return Map.of();
    }
}
