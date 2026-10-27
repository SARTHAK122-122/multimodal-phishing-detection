package com.phishingdet.controller;

import com.fasterxml.jackson.databind.ObjectMapper;
import com.phishingdet.entity.EvaluationRun;
import com.phishingdet.entity.ModelVersion;
import com.phishingdet.repository.EvaluationRunRepository;
import com.phishingdet.repository.ModelVersionRepository;
import jakarta.validation.Valid;
import jakarta.validation.constraints.DecimalMax;
import jakarta.validation.constraints.DecimalMin;
import jakarta.validation.constraints.NotBlank;
import org.springframework.http.HttpStatus;
import org.springframework.transaction.annotation.Transactional;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.ResponseStatus;
import org.springframework.web.bind.annotation.RestController;

import java.time.ZonedDateTime;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;

/**
 * Model registry and evaluation history (metrics stay NULL until measured).
 *
 * <pre>
 * GET  /api/models        registry rows
 * GET  /api/evaluations   measured evaluation runs
 * POST /api/models/registrations   called by the Python training script AFTER
 *                                  a real train/eval run; never accepts invented
 *                                  numbers without a metrics block (0..1 range
 *                                  is validated), and records an evaluation_runs
 *                                  row so every published metric is auditable.
 * </pre>
 */
@RestController
@RequestMapping("/api")
public class ModelController {

    private final ModelVersionRepository modelVersionRepository;
    private final EvaluationRunRepository evaluationRunRepository;
    private final ObjectMapper mapper;

    public ModelController(ModelVersionRepository modelVersionRepository,
                           EvaluationRunRepository evaluationRunRepository,
                           ObjectMapper mapper) {
        this.modelVersionRepository = modelVersionRepository;
        this.evaluationRunRepository = evaluationRunRepository;
        this.mapper = mapper;
    }

    public record ModelVersionDto(
            Long id, String modelName, String modelType, String version,
            String trainingDate, String modelArtifactPath, String evaluationStatus,
            String metricsJson, String notes) {}

    public record EvaluationRunDto(
            Long id, Long modelVersionId, String modelName, String modelVersion,
            String evaluationDate, String splitStrategy, Long randomSeed, String ablationConfig,
            Double accuracy, Double precisionScore, Double recallScore, Double f1Score,
            Double rocAuc, Double falsePositiveRate, Double falseNegativeRate,
            String resultsJson) {}

    /** Metrics block accepted by the registration endpoint - all values are ratios in [0,1]. */
    public record RegisterMetrics(
            @DecimalMin(value = "0", message = "accuracy must be in [0,1]")
            @DecimalMax(value = "1", message = "accuracy must be in [0,1]")
            Double accuracy,
            @DecimalMin(value = "0", message = "precision must be in [0,1]")
            @DecimalMax(value = "1", message = "precision must be in [0,1]")
            Double precisionScore,
            @DecimalMin(value = "0", message = "recall must be in [0,1]")
            @DecimalMax(value = "1", message = "recall must be in [0,1]")
            Double recallScore,
            @DecimalMin(value = "0", message = "f1 must be in [0,1]")
            @DecimalMax(value = "1", message = "f1 must be in [0,1]")
            Double f1Score,
            @DecimalMin(value = "0", message = "rocAuc must be in [0,1]")
            @DecimalMax(value = "1", message = "rocAuc must be in [0,1]")
            Double rocAuc,
            @DecimalMin(value = "0", message = "fpr must be in [0,1]")
            @DecimalMax(value = "1", message = "fpr must be in [0,1]")
            Double falsePositiveRate,
            @DecimalMin(value = "0", message = "fnr must be in [0,1]")
            @DecimalMax(value = "1", message = "fnr must be in [0,1]")
            Double falseNegativeRate,
            String resultsJson) {}

    public record RegisterModelRequest(
            @NotBlank(message = "modelName is required") String modelName,
            String modelType,
            @NotBlank(message = "version is required") String version,
            String artifactPath,
            String trainingDate,
            String notes,
            String splitStrategy,
            Long randomSeed,
            String ablationConfig,
            @Valid RegisterMetrics metrics) {}

    public record RegisterResponse(Long modelVersionId, Long evaluationRunId, String evaluationStatus) {}

    @GetMapping("/models")
    @Transactional(readOnly = true)
    public List<ModelVersionDto> models() {
        return modelVersionRepository.findAllByOrderByIdAsc().stream()
                .map(ModelController::toDto)
                .toList();
    }

    @GetMapping("/evaluations")
    @Transactional(readOnly = true)
    public List<EvaluationRunDto> evaluations() {
        return evaluationRunRepository.findAllByOrderByEvaluationDateDesc().stream()
                .map(ModelController::toDto)
                .toList();
    }

    /**
     * Upsert a registry row and (when metrics are present) append an
     * evaluation_runs row. Called by ai-service/training/train_url_models.py
     * after the hold-out evaluation actually executed.
     */
    @PostMapping("/models/registrations")
    @ResponseStatus(HttpStatus.CREATED)
    @Transactional
    public RegisterResponse register(@Valid @RequestBody RegisterModelRequest request) {
        ModelVersion model = modelVersionRepository
                .findFirstByModelNameOrderByVersionDesc(request.modelName())
                .orElseGet(ModelVersion::new);

        model.setModelName(request.modelName());
        if (request.modelType() != null && !request.modelType().isBlank()) {
            model.setModelType(request.modelType());
        } else if (model.getModelType() == null) {
            model.setModelType(ModelVersion.ModelType.ML.name());
        }
        model.setVersion(request.version());
        model.setModelArtifactPath(request.artifactPath());
        model.setTrainingDate(parseOrNow(request.trainingDate()));
        if (request.notes() != null && !request.notes().isBlank()) {
            model.setNotes(request.notes());
        }

        RegisterMetrics metrics = request.metrics();
        model.setEvaluationStatus(metrics != null
                ? ModelVersion.EvaluationStatus.EVALUATED.name()
                : ModelVersion.EvaluationStatus.TRAINED.name());
        if (metrics == null) {
            model.setMetricsJson(null);
        } else {
            // LinkedHashMap (not Map.of): partial metrics blocks may contain nulls
            Map<String, Object> summary = new LinkedHashMap<>();
            summary.put("accuracy", metrics.accuracy());
            summary.put("precision", metrics.precisionScore());
            summary.put("recall", metrics.recallScore());
            summary.put("f1", metrics.f1Score());
            summary.put("rocAuc", metrics.rocAuc());
            summary.put("falsePositiveRate", metrics.falsePositiveRate());
            summary.put("falseNegativeRate", metrics.falseNegativeRate());
            summary.put("randomSeed", request.randomSeed());
            summary.put("splitStrategy", request.splitStrategy());
            summary.put("ablationConfig", request.ablationConfig());
            model.setMetricsJson(toJson(summary));
        }
        model = modelVersionRepository.save(model);

        Long evaluationRunId = null;
        if (metrics != null) {
            EvaluationRun run = new EvaluationRun();
            run.setModelVersion(model);
            run.setEvaluationDate(ZonedDateTime.now(java.time.ZoneOffset.UTC));
            run.setSplitStrategy(request.splitStrategy());
            run.setRandomSeed(request.randomSeed());
            run.setAblationConfig(request.ablationConfig());
            run.setAccuracy(metrics.accuracy());
            run.setPrecisionScore(metrics.precisionScore());
            run.setRecallScore(metrics.recallScore());
            run.setF1Score(metrics.f1Score());
            run.setRocAuc(metrics.rocAuc());
            run.setFalsePositiveRate(metrics.falsePositiveRate());
            run.setFalseNegativeRate(metrics.falseNegativeRate());
            run.setResultsJson(metrics.resultsJson());
            evaluationRunId = evaluationRunRepository.save(run).getId();
        }

        return new RegisterResponse(model.getId(), evaluationRunId, model.getEvaluationStatus());
    }

    private static ZonedDateTime parseOrNow(String iso) {
        if (iso == null || iso.isBlank()) {
            return ZonedDateTime.now(java.time.ZoneOffset.UTC);
        }
        try {
            return ZonedDateTime.parse(iso);
        } catch (RuntimeException ex) {
            try {
                return java.time.OffsetDateTime.parse(iso).toZonedDateTime();
            } catch (RuntimeException ex2) {
                return ZonedDateTime.now(java.time.ZoneOffset.UTC);
            }
        }
    }

    private String toJson(Map<String, Object> values) {
        Map<String, Object> compact = new LinkedHashMap<>();
        values.forEach((k, v) -> {
            if (v != null) compact.put(k, v);
        });
        try {
            return mapper.writeValueAsString(compact);
        } catch (Exception e) {
            return null;
        }
    }

    private static ModelVersionDto toDto(ModelVersion m) {
        return new ModelVersionDto(
                m.getId(), m.getModelName(), m.getModelType(), m.getVersion(),
                iso(m.getTrainingDate()), m.getModelArtifactPath(), m.getEvaluationStatus(),
                m.getMetricsJson(), m.getNotes());
    }

    private static EvaluationRunDto toDto(EvaluationRun e) {
        return new EvaluationRunDto(
                e.getId(),
                e.getModelVersion().getId(),
                e.getModelVersion().getModelName(),
                e.getModelVersion().getVersion(),
                iso(e.getEvaluationDate()),
                e.getSplitStrategy(), e.getRandomSeed(), e.getAblationConfig(),
                e.getAccuracy(), e.getPrecisionScore(), e.getRecallScore(), e.getF1Score(),
                e.getRocAuc(), e.getFalsePositiveRate(), e.getFalseNegativeRate(),
                e.getResultsJson());
    }

    private static String iso(ZonedDateTime time) {
        return time == null ? null : time.toString();
    }
}
