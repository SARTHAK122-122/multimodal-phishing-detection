package com.phishingdet.service;

import com.fasterxml.jackson.core.JsonProcessingException;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.phishingdet.dto.DatasetDto;
import com.phishingdet.dto.DatasetPreviewDto;
import com.phishingdet.entity.Dataset;
import com.phishingdet.exception.ResourceNotFoundException;
import com.phishingdet.repository.DatasetRepository;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.stereotype.Service;
import org.springframework.web.multipart.MultipartFile;

import java.util.List;

/**
 * Dataset lifecycle: upload -> metadata in PostgreSQL -> inspection via Python.
 * The uploaded file itself is never modified; processed copies live under
 * {@code uploads/processed/}.
 */
@Service
public class DatasetService {

    private static final Logger log = LoggerFactory.getLogger(DatasetService.class);

    private final DatasetRepository repository;
    private final StorageService storage;
    private final AiServiceClient aiClient;
    private final ObjectMapper mapper;

    public DatasetService(DatasetRepository repository,
                          StorageService storage,
                          AiServiceClient aiClient,
                          ObjectMapper mapper) {
        this.repository = repository;
        this.storage = storage;
        this.aiClient = aiClient;
        this.mapper = mapper;
    }

    public List<DatasetDto> list() {
        return repository.findAllByOrderByUploadedAtDesc().stream().map(this::toDto).toList();
    }

    public DatasetDto get(Long id) {
        return toDto(require(id));
    }

    public Dataset entity(Long id) {
        return require(id);
    }

    /**
     * STEP 1 - store the file, record metadata, and profile it immediately so
     * the dashboard can show rows/columns right after upload.
     */
    public record UploadResult(DatasetDto dataset, DatasetPreviewDto preview) {}

    public UploadResult upload(MultipartFile file, String name, String source,
                               String description, boolean synthetic) {
        String stored = storage.saveUpload(file);

        Dataset dataset = new Dataset();
        dataset.setName(name == null || name.isBlank() ? stored : name.trim());
        dataset.setSource(source == null || source.isBlank() ? "manual upload" : source.trim());
        dataset.setDescription(description);
        dataset.setOriginalFilename(StorageService.sanitize(file.getOriginalFilename()));
        dataset.setStoredFilename(stored);
        dataset.setFileFormat("csv");
        dataset.setFileSizeBytes(file.getSize());
        dataset.setSynthetic(synthetic);
        dataset = repository.save(dataset);

        DatasetPreviewDto preview = null;
        try {
            preview = aiClient.inspect(stored, null);
            applyProfile(dataset, preview, null);
            repository.save(dataset);
        } catch (RuntimeException ex) {
            // Keep the row so the upload is visible/auditable, but flag the failure.
            log.warn("Inspection after upload failed for dataset {}: {}", dataset.getId(), ex.getMessage());
            dataset.setStatus(Dataset.Status.FAILED.name());
            dataset = repository.save(dataset);
        }
        return new UploadResult(toDto(dataset), preview);
    }

    /**
     * STEP 2 - re-profile the raw data (optionally with a selected target
     * column) and persist the label statistics on the dataset row.
     */
    public DatasetPreviewDto preview(Long id, String targetColumn) {
        Dataset dataset = require(id);
        String target = (targetColumn == null || targetColumn.isBlank()) ? dataset.getTargetColumn() : targetColumn;
        DatasetPreviewDto preview = aiClient.inspect(dataset.getStoredFilename(), target);
        applyProfile(dataset, preview, target);
        repository.save(dataset);
        return preview;
    }

    private void applyProfile(Dataset dataset, DatasetPreviewDto preview, String targetColumn) {
        dataset.setTotalRows((int) preview.rows());
        if (targetColumn != null && !targetColumn.isBlank()) {
            dataset.setTargetColumn(targetColumn);
            dataset.setStatus(Dataset.Status.INSPECTED.name());
            var distribution = preview.target() == null ? null : preview.target().distribution();
            if (distribution != null) {
                dataset.setPhishingRows(Math.toIntExact(distribution.getOrDefault("phishing", 0L)));
                dataset.setLegitimateRows(Math.toIntExact(distribution.getOrDefault("legitimate", 0L)));
            }
        }
        try {
            dataset.setColumnNames(mapper.writeValueAsString(preview.columnNames()));
        } catch (JsonProcessingException e) {
            dataset.setColumnNames("[]");
        }
    }

    private Dataset require(Long id) {
        return repository.findById(id)
                .orElseThrow(() -> new ResourceNotFoundException("Dataset " + id + " not found."));
    }

    public DatasetDto toDto(Dataset dataset) {
        List<String> columns;
        try {
            columns = mapper.readValue(dataset.getColumnNames() == null ? "[]" : dataset.getColumnNames(),
                    mapper.getTypeFactory().constructCollectionType(List.class, String.class));
        } catch (Exception e) {
            columns = List.of();
        }
        return new DatasetDto(
                dataset.getId(),
                dataset.getName(),
                dataset.getSource(),
                dataset.getDescription(),
                dataset.getOriginalFilename(),
                dataset.getFileFormat(),
                dataset.getFileSizeBytes(),
                columns,
                dataset.getTargetColumn(),
                dataset.getTotalRows(),
                dataset.getPhishingRows(),
                dataset.getLegitimateRows(),
                dataset.getUploadedAt() == null ? null : dataset.getUploadedAt().toString(),
                dataset.getDatasetVersion(),
                dataset.getStatus(),
                dataset.isSynthetic());
    }
}
