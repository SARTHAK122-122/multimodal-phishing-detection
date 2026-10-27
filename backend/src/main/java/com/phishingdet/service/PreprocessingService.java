package com.phishingdet.service;

import com.fasterxml.jackson.databind.ObjectMapper;
import com.phishingdet.dto.PreprocessRequestDto;
import com.phishingdet.dto.PreprocessingRunDto;
import com.phishingdet.entity.Dataset;
import com.phishingdet.entity.PreprocessingRun;
import com.phishingdet.exception.BadRequestException;
import com.phishingdet.exception.ResourceNotFoundException;
import com.phishingdet.repository.PreprocessingRunRepository;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.stereotype.Service;

import java.time.ZonedDateTime;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;

/**
 * Executes preprocessing by delegating to Python, then persists an auditable
 * record of what happened (counts, transformations, warnings, parameters).
 */
@Service
public class PreprocessingService {

    private static final Logger log = LoggerFactory.getLogger(PreprocessingService.class);

    private final PreprocessingRunRepository repository;
    private final DatasetService datasetService;
    private final com.phishingdet.repository.DatasetRepository datasetRepository;
    private final AiServiceClient aiClient;
    private final ObjectMapper mapper;

    public PreprocessingService(PreprocessingRunRepository repository,
                                DatasetService datasetService,
                                com.phishingdet.repository.DatasetRepository datasetRepository,
                                AiServiceClient aiClient,
                                ObjectMapper mapper) {
        this.repository = repository;
        this.datasetService = datasetService;
        this.datasetRepository = datasetRepository;
        this.aiClient = aiClient;
        this.mapper = mapper;
    }

    public List<PreprocessingRunDto> list(Long datasetId) {
        List<PreprocessingRun> runs = datasetId == null
                ? repository.findAll()
                : repository.findByDatasetIdOrderByStartedAtDesc(datasetId);
        return runs.stream().map(this::toDto).toList();
    }

    public PreprocessingRunDto get(Long id) {
        return toDto(require(id));
    }

    /** Path (relative to the upload dir) of the processed file produced by a run. */
    public String outputPath(Long id) {
        PreprocessingRun run = require(id);
        if (run.getOutputFilename() == null || !run.getStatus().equals(PreprocessingRun.Status.COMPLETED.name())) {
            throw new BadRequestException("This preprocessing run has no downloadable output (status=" + run.getStatus() + ").");
        }
        return run.getOutputFilename();
    }

    /**
     * STEP 4 - run the real pipeline in Python and record the outcome.
     */
    public PreprocessingRunDto execute(Long datasetId, PreprocessRequestDto request) {
        Dataset dataset = datasetService.entity(datasetId);
        if (dataset.getStoredFilename() == null) {
            throw new BadRequestException("Dataset has no stored file - upload it again.");
        }

        PreprocessingRun run = new PreprocessingRun();
        run.setDataset(dataset);
        run.setStatus(PreprocessingRun.Status.RUNNING.name());
        run = repository.save(run);   // committed immediately so a crash still leaves a FAILED/RUNNING trail

        long started = System.currentTimeMillis();
        try {
            Map<String, Object> options = new LinkedHashMap<>(request.options() == null
                    ? Map.of()
                    : request.options().toPayload());
            Map<String, Object> result = aiClient.preprocess(
                    dataset.getStoredFilename(), request.targetColumn(), options, request.outputFilename());

            run.setInputRows(intOf(result.get("inputRows")));
            run.setOutputRows(intOf(result.get("outputRows")));
            run.setDuplicatesRemoved(intOf(result.get("duplicatesRemoved")));
            run.setInvalidRowsRemoved(intOf(result.get("invalidRowsRemoved")));
            run.setMissingValuesHandled(intOf(result.get("missingValuesHandled")));
            run.setTransformationsApplied(toJson(result.get("transformations")));
            run.setWarningsJson(toJson(result.get("warnings")));
            run.setParametersJson(toJson(mergedParameters(request, result)));
            run.setResultJson(toJson(result));
            run.setOutputFilename(str(result.get("outputFile")));
            run.setStatus(PreprocessingRun.Status.COMPLETED.name());
            run.setCompletedAt(ZonedDateTime.now(java.time.ZoneOffset.UTC));
            run = repository.save(run);

            dataset.setStatus(Dataset.Status.PROCESSED.name());
            datasetRepository.save(dataset);

            log.info("Preprocessing run {} completed: {} -> {} rows in {} ms",
                    run.getId(), run.getInputRows(), run.getOutputRows(), System.currentTimeMillis() - started);
            return toDto(run, dataset.getName(), result);
        } catch (RuntimeException ex) {
            log.error("Preprocessing run {} failed", run.getId(), ex);
            run.setStatus(PreprocessingRun.Status.FAILED.name());
            run.setErrorMessage(truncate(ex.getMessage(), 2000));
            run.setCompletedAt(ZonedDateTime.now(java.time.ZoneOffset.UTC));
            run = repository.save(run);
            throw ex;
        }
    }

    private Map<String, Object> mergedParameters(PreprocessRequestDto request, Map<String, Object> result) {
        Object params = result.get("parameters");
        if (params instanceof Map<?, ?> map) {
            Map<String, Object> out = new LinkedHashMap<>();
            map.forEach((k, v) -> out.put(String.valueOf(k), v));
            out.put("targetColumn", request.targetColumn());
            return out;
        }
        Map<String, Object> out = new LinkedHashMap<>();
        if (request.options() != null) {
            out.putAll(request.options().toPayload());
        }
        out.put("targetColumn", request.targetColumn());
        return out;
    }

    private PreprocessingRun require(Long id) {
        return repository.findById(id)
                .orElseThrow(() -> new ResourceNotFoundException("Preprocessing run " + id + " not found."));
    }

    public PreprocessingRunDto toDto(PreprocessingRun run) {
        Map<String, Object> stored = new LinkedHashMap<>();
        if (run.getResultJson() != null && !run.getResultJson().isBlank()) {
            try {
                @SuppressWarnings("unchecked")
                Map<String, Object> parsed = mapper.readValue(run.getResultJson(), Map.class);
                stored = parsed;
            } catch (Exception e) {
                log.warn("Could not parse stored result of run {}", run.getId());
            }
        }
        return toDto(run, stored);
    }

    public PreprocessingRunDto toDto(PreprocessingRun run, Map<String, Object> result) {
        String datasetName = run.getDataset() != null ? run.getDataset().getName() : null;
        return toDto(run, datasetName, result);
    }

    /**
     * @param datasetName passed explicitly by callers that already hold a fully
     *                    loaded {@link Dataset}; read paths rely on the
     *                    repository's {@code @EntityGraph} to initialise it.
     */
    public PreprocessingRunDto toDto(PreprocessingRun run, String datasetName, Map<String, Object> result) {
        return PreprocessingRunDto.from(run, datasetName, result == null ? Map.of() : result);
    }

    private String toJson(Object value) {
        if (value == null) {
            return "[]";
        }
        try {
            return mapper.writeValueAsString(value);
        } catch (Exception e) {
            return "[]";
        }
    }

    private static int intOf(Object value) {
        return value instanceof Number n ? n.intValue() : 0;
    }

    private static String str(Object value) {
        return value == null ? null : String.valueOf(value);
    }

    private static String truncate(String value, int max) {
        if (value == null) return null;
        return value.length() <= max ? value : value.substring(0, max);
    }
}
