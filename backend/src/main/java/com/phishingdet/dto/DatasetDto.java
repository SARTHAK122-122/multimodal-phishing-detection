package com.phishingdet.dto;

import java.util.List;

/** Dataset metadata as exposed by the REST API. */
public record DatasetDto(
        Long id,
        String name,
        String source,
        String description,
        String originalFilename,
        String fileFormat,
        long fileSizeBytes,
        List<String> columnNames,
        String targetColumn,
        Integer totalRows,
        Integer phishingRows,
        Integer legitimateRows,
        String uploadedAt,
        String datasetVersion,
        String status,
        boolean synthetic) {
}
