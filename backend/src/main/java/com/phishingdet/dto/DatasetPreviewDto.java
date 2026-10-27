package com.phishingdet.dto;

import java.util.List;
import java.util.Map;

/**
 * Dataset profile produced by the Python inspector (workflow STEP 2).
 * The nested structure mirrors the documented Python payload.
 */
public record DatasetPreviewDto(
        String filename,
        long rows,
        List<ColumnProfile> columns,
        List<String> columnNames,
        long duplicateRows,
        long missingCells,
        TargetProfile target,
        List<Map<String, Object>> head,
        List<String> warnings,
        Integer elapsedMs) {

    public record ColumnProfile(
            String name,
            String dtype,
            long missing,
            double missingPct,
            long unique,
            List<Object> samples) {
    }

    public record TargetProfile(
            String column,
            boolean present,
            Map<String, Long> distribution,
            List<String> uniqueValues,
            List<String> unrecognisedValues,
            List<String> warnings) {
    }
}
