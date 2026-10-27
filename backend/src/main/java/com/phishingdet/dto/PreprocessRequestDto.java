package com.phishingdet.dto;

import jakarta.validation.constraints.NotBlank;

import java.util.List;
import java.util.Map;

/**
 * Request body for POST /api/datasets/{id}/preprocessing-runs.
 * The options mirror the Python pipeline configuration one-to-one so the exact
 * parameters can be stored and replayed.
 */
public record PreprocessRequestDto(
        @NotBlank(message = "targetColumn is required")
        String targetColumn,

        Options options,

        String outputFilename) {

    public record Options(
            Boolean normalizeLabels,
            Boolean dropInvalidRows,
            Boolean convertTypes,
            Boolean detectConflictingDuplicates,
            Boolean removeDuplicates,
            Boolean handleMissing,
            String missingStrategy,
            Double missingMaxFraction,
            String dedupeOnColumn,
            List<String> dropColumns,
            List<String> selectColumns,
            Boolean validateFeatures,
            Map<String, String> labelMapping) {

        /** Null-tolerant conversion to the JSON body expected by Python. */
        public Map<String, Object> toPayload() {
            Map<String, Object> map = new java.util.LinkedHashMap<>();
            if (normalizeLabels != null) map.put("normalizeLabels", normalizeLabels);
            if (dropInvalidRows != null) map.put("dropInvalidRows", dropInvalidRows);
            if (convertTypes != null) map.put("convertTypes", convertTypes);
            if (detectConflictingDuplicates != null) map.put("detectConflictingDuplicates", detectConflictingDuplicates);
            if (removeDuplicates != null) map.put("removeDuplicates", removeDuplicates);
            if (handleMissing != null) map.put("handleMissing", handleMissing);
            if (missingStrategy != null) map.put("missingStrategy", missingStrategy);
            if (missingMaxFraction != null) map.put("missingMaxFraction", missingMaxFraction);
            if (dedupeOnColumn != null) map.put("dedupeOnColumn", dedupeOnColumn);
            if (dropColumns != null) map.put("dropColumns", dropColumns);
            if (selectColumns != null) map.put("selectColumns", selectColumns);
            if (validateFeatures != null) map.put("validateFeatures", validateFeatures);
            if (labelMapping != null) map.put("labelMapping", labelMapping);
            return map;
        }
    }
}
