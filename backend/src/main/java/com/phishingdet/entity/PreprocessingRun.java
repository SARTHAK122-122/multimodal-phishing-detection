package com.phishingdet.entity;

import jakarta.persistence.Column;
import jakarta.persistence.Entity;
import jakarta.persistence.FetchType;
import jakarta.persistence.GeneratedValue;
import jakarta.persistence.GenerationType;
import jakarta.persistence.Id;
import jakarta.persistence.JoinColumn;
import jakarta.persistence.ManyToOne;
import jakarta.persistence.Table;

import java.time.ZonedDateTime;

/**
 * One executed preprocessing job. Stores the exact before/after counts and the
 * reproducible parameters of the run so the whole operation can be audited and
 * repeated on the original (never modified) dataset.
 */
@Entity
@Table(name = "preprocessing_runs")
public class PreprocessingRun {

    public enum Status { RUNNING, COMPLETED, FAILED }

    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    private Long id;

    @ManyToOne(optional = false, fetch = FetchType.LAZY)
    @JoinColumn(name = "dataset_id", nullable = false)
    private Dataset dataset;

    @Column(name = "started_at", nullable = false, updatable = false)
    private ZonedDateTime startedAt;

    @Column(name = "completed_at")
    private ZonedDateTime completedAt;

    @Column(name = "input_rows", nullable = false)
    private int inputRows;

    @Column(name = "output_rows", nullable = false)
    private int outputRows;

    @Column(name = "duplicates_removed", nullable = false)
    private int duplicatesRemoved;

    @Column(name = "invalid_rows_removed", nullable = false)
    private int invalidRowsRemoved;

    @Column(name = "missing_values_handled", nullable = false)
    private int missingValuesHandled;

    /** JSON array describing every transformation that was actually applied. */
    @Column(name = "transformations_applied", nullable = false, columnDefinition = "text")
    private String transformationsApplied = "[]";

    /** JSON object with the exact parameters used (seed, mappings, thresholds...). */
    @Column(name = "parameters_json", nullable = false, columnDefinition = "text")
    private String parametersJson = "{}";

    /** JSON array of non-fatal warnings raised by the pipeline. */
    @Column(name = "warnings_json", nullable = false, columnDefinition = "text")
    private String warningsJson = "[]";

    /** Full JSON result payload returned by the Python service (STEP 5 of the workflow). */
    @Column(name = "result_json", columnDefinition = "text")
    private String resultJson;

    @Column(name = "output_filename")
    private String outputFilename;

    @Column(nullable = false, length = 20)
    private String status = Status.RUNNING.name();

    @Column(name = "error_message", columnDefinition = "text")
    private String errorMessage;

    @jakarta.persistence.PrePersist
    void onCreate() {
        if (startedAt == null) {
            startedAt = ZonedDateTime.now(java.time.ZoneOffset.UTC);
        }
    }

    public Long getId() { return id; }
    public void setId(Long id) { this.id = id; }
    public Dataset getDataset() { return dataset; }
    public void setDataset(Dataset dataset) { this.dataset = dataset; }
    public ZonedDateTime getStartedAt() { return startedAt; }
    public void setStartedAt(ZonedDateTime startedAt) { this.startedAt = startedAt; }
    public ZonedDateTime getCompletedAt() { return completedAt; }
    public void setCompletedAt(ZonedDateTime completedAt) { this.completedAt = completedAt; }
    public int getInputRows() { return inputRows; }
    public void setInputRows(int inputRows) { this.inputRows = inputRows; }
    public int getOutputRows() { return outputRows; }
    public void setOutputRows(int outputRows) { this.outputRows = outputRows; }
    public int getDuplicatesRemoved() { return duplicatesRemoved; }
    public void setDuplicatesRemoved(int duplicatesRemoved) { this.duplicatesRemoved = duplicatesRemoved; }
    public int getInvalidRowsRemoved() { return invalidRowsRemoved; }
    public void setInvalidRowsRemoved(int invalidRowsRemoved) { this.invalidRowsRemoved = invalidRowsRemoved; }
    public int getMissingValuesHandled() { return missingValuesHandled; }
    public void setMissingValuesHandled(int missingValuesHandled) { this.missingValuesHandled = missingValuesHandled; }
    public String getTransformationsApplied() { return transformationsApplied; }
    public void setTransformationsApplied(String transformationsApplied) { this.transformationsApplied = transformationsApplied; }
    public String getParametersJson() { return parametersJson; }
    public void setParametersJson(String parametersJson) { this.parametersJson = parametersJson; }
    public String getWarningsJson() { return warningsJson; }
    public void setWarningsJson(String warningsJson) { this.warningsJson = warningsJson; }
    public String getOutputFilename() { return outputFilename; }
    public void setOutputFilename(String outputFilename) { this.outputFilename = outputFilename; }
    public String getResultJson() { return resultJson; }
    public void setResultJson(String resultJson) { this.resultJson = resultJson; }
    public String getStatus() { return status; }
    public void setStatus(String status) { this.status = status; }
    public String getErrorMessage() { return errorMessage; }
    public void setErrorMessage(String errorMessage) { this.errorMessage = errorMessage; }
}
