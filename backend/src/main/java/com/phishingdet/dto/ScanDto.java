package com.phishingdet.dto;

import java.util.List;
import java.util.Map;

/** A stored scan: verdict, score, timing and (optionally) its module outputs. */
public record ScanDto(
        Long id,
        String inputType,
        String submittedUrl,
        String normalizedUrl,
        String submittedAt,
        String completedAt,
        String finalPrediction,
        String riskLevel,
        Double riskScore,
        Long processingTimeMs,
        String status,
        String modelVersion,
        String explanation,
        List<String> missingModalities,
        boolean seedData,
        List<ModalityResultDto> modalityResults,
        List<EvidenceDto> evidence,
        List<String> caveats,
        Map<String, Double> weightsUsed,
        String screenshotUrl) {

    public record ModalityResultDto(
            Long id,
            String modality,
            String modelName,
            String modelVersion,
            String prediction,
            Double riskScore,
            String status,
            Long processingTimeMs,
            String detailJson) {
    }

    public record EvidenceDto(
            Long id,
            String modality,
            String evidenceType,
            String description,
            String severity,
            String supportingValue,
            String direction,
            String kind) {
    }
}
