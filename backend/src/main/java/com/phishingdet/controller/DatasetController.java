package com.phishingdet.controller;

import com.phishingdet.dto.DatasetDto;
import com.phishingdet.dto.DatasetPreviewDto;
import com.phishingdet.dto.PreprocessRequestDto;
import com.phishingdet.dto.PreprocessingRunDto;
import com.phishingdet.service.DatasetService;
import com.phishingdet.service.PreprocessingService;
import com.phishingdet.service.StorageService;
import jakarta.validation.Valid;
import org.springframework.http.HttpStatus;
import org.springframework.http.MediaType;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.ResponseStatus;
import org.springframework.web.bind.annotation.RestController;
import org.springframework.web.multipart.MultipartFile;

import java.net.URLConnection;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.List;

/**
 * Dataset management + manual preprocessing API (dashboard workflow STEP 1-6).
 *
 * <pre>
 * GET  /api/datasets                          list datasets
 * POST /api/datasets/upload                   STEP 1 upload CSV (multipart)
 * GET  /api/datasets/{id}                     metadata
 * GET  /api/datasets/{id}/preview             STEP 2 raw profile (?targetColumn=)
 * POST /api/datasets/{id}/preprocessing-runs  STEP 4 execute preprocessing
 * GET  /api/preprocessing-runs                history
 * GET  /api/preprocessing-runs/{id}           STEP 5 results
 * GET  /api/preprocessing-runs/{id}/download  STEP 6 processed CSV
 * </pre>
 */
@RestController
@RequestMapping("/api")
public class DatasetController {

    private final DatasetService datasetService;
    private final PreprocessingService preprocessingService;
    private final StorageService storageService;

    public DatasetController(DatasetService datasetService,
                             PreprocessingService preprocessingService,
                             StorageService storageService) {
        this.datasetService = datasetService;
        this.preprocessingService = preprocessingService;
        this.storageService = storageService;
    }

    @GetMapping("/datasets")
    public List<DatasetDto> listDatasets() {
        return datasetService.list();
    }

    @PostMapping(value = "/datasets/upload", consumes = MediaType.MULTIPART_FORM_DATA_VALUE)
    @ResponseStatus(HttpStatus.CREATED)
    public DatasetService.UploadResult upload(@RequestParam("file") MultipartFile file,
                                              @RequestParam(value = "name", required = false) String name,
                                              @RequestParam(value = "source", required = false) String source,
                                              @RequestParam(value = "description", required = false) String description,
                                              @RequestParam(value = "synthetic", defaultValue = "false") boolean synthetic) {
        return datasetService.upload(file, name, source, description, synthetic);
    }

    @GetMapping("/datasets/{id}")
    public DatasetDto getDataset(@PathVariable Long id) {
        return datasetService.get(id);
    }

    @GetMapping("/datasets/{id}/preview")
    public DatasetPreviewDto preview(@PathVariable Long id,
                                     @RequestParam(value = "targetColumn", required = false) String targetColumn) {
        return datasetService.preview(id, targetColumn);
    }

    @PostMapping("/datasets/{id}/preprocessing-runs")
    @ResponseStatus(HttpStatus.CREATED)
    public PreprocessingRunDto runPreprocessing(@PathVariable Long id,
                                                @Valid @RequestBody PreprocessRequestDto request) {
        return preprocessingService.execute(id, request);
    }

    @GetMapping("/preprocessing-runs")
    public List<PreprocessingRunDto> listRuns(
            @RequestParam(value = "datasetId", required = false) Long datasetId) {
        return preprocessingService.list(datasetId);
    }

    @GetMapping("/preprocessing-runs/{id}")
    public PreprocessingRunDto getRun(@PathVariable Long id) {
        return preprocessingService.get(id);
    }

    @GetMapping("/preprocessing-runs/{id}/download")
    public ResponseEntity<byte[]> downloadRun(@PathVariable Long id) throws Exception {
        String relative = preprocessingService.outputPath(id);
        Path file = storageService.resolveProcessed(relative);
        if (!Files.exists(file)) {
            return ResponseEntity.notFound().build();
        }
        byte[] bytes = Files.readAllBytes(file);
        String contentType = URLConnection.guessContentTypeFromName(file.getFileName().toString());
        return ResponseEntity.ok()
                .contentType(MediaType.parseMediaType(contentType == null ? "text/csv" : contentType))
                .header("Content-Disposition", "attachment; filename=\"" + file.getFileName() + "\"")
                .body(bytes);
    }
}
