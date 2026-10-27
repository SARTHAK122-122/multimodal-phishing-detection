package com.phishingdet.entity;

import jakarta.persistence.Column;
import jakarta.persistence.Entity;
import jakarta.persistence.GeneratedValue;
import jakarta.persistence.GenerationType;
import jakarta.persistence.Id;
import jakarta.persistence.Table;

import java.time.ZonedDateTime;

/**
 * Metadata of an uploaded CSV dataset. The file itself lives on disk
 * ({@code stored_filename}); only its description and statistics live here.
 *
 * <p>{@code is_synthetic = TRUE} marks a dataset whose records were generated
 * locally for demonstration. Such rows must never be presented as real
 * phishing observations.</p>
 */
@Entity
@Table(name = "datasets")
public class Dataset {

    public enum Status { UPLOADED, INSPECTED, PROCESSED, FAILED }

    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    private Long id;

    @Column(nullable = false, length = 120)
    private String name;

    @Column(nullable = false)
    private String source;

    @Column(columnDefinition = "text")
    private String description;

    @Column(name = "original_filename", nullable = false)
    private String originalFilename;

    @Column(name = "stored_filename", nullable = false)
    private String storedFilename;

    @Column(name = "file_format", nullable = false, length = 10)
    private String fileFormat = "csv";

    @Column(name = "file_size_bytes", nullable = false)
    private long fileSizeBytes;

    @Column(name = "column_names", columnDefinition = "text")
    private String columnNames;

    @Column(name = "target_column", length = 120)
    private String targetColumn;

    @Column(name = "total_rows")
    private Integer totalRows;

    @Column(name = "phishing_rows")
    private Integer phishingRows;

    @Column(name = "legitimate_rows")
    private Integer legitimateRows;

    @Column(name = "uploaded_at", nullable = false, updatable = false)
    private ZonedDateTime uploadedAt;

    @Column(name = "dataset_version", nullable = false, length = 30)
    private String datasetVersion = "v1";

    /** One of {@link Status}. Stored as a plain string so the DB CHECK constraint stays the guard. */
    @Column(nullable = false, length = 30)
    private String status = Status.UPLOADED.name();

    @Column(name = "is_synthetic", nullable = false)
    private boolean synthetic;

    @Column(name = "uploaded_by")
    private Long uploadedBy;

    @jakarta.persistence.PrePersist
    void onCreate() {
        if (uploadedAt == null) {
            uploadedAt = ZonedDateTime.now(java.time.ZoneOffset.UTC);
        }
    }

    public Long getId() { return id; }
    public void setId(Long id) { this.id = id; }
    public String getName() { return name; }
    public void setName(String name) { this.name = name; }
    public String getSource() { return source; }
    public void setSource(String source) { this.source = source; }
    public String getDescription() { return description; }
    public void setDescription(String description) { this.description = description; }
    public String getOriginalFilename() { return originalFilename; }
    public void setOriginalFilename(String originalFilename) { this.originalFilename = originalFilename; }
    public String getStoredFilename() { return storedFilename; }
    public void setStoredFilename(String storedFilename) { this.storedFilename = storedFilename; }
    public String getFileFormat() { return fileFormat; }
    public void setFileFormat(String fileFormat) { this.fileFormat = fileFormat; }
    public long getFileSizeBytes() { return fileSizeBytes; }
    public void setFileSizeBytes(long fileSizeBytes) { this.fileSizeBytes = fileSizeBytes; }
    public String getColumnNames() { return columnNames; }
    public void setColumnNames(String columnNames) { this.columnNames = columnNames; }
    public String getTargetColumn() { return targetColumn; }
    public void setTargetColumn(String targetColumn) { this.targetColumn = targetColumn; }
    public Integer getTotalRows() { return totalRows; }
    public void setTotalRows(Integer totalRows) { this.totalRows = totalRows; }
    public Integer getPhishingRows() { return phishingRows; }
    public void setPhishingRows(Integer phishingRows) { this.phishingRows = phishingRows; }
    public Integer getLegitimateRows() { return legitimateRows; }
    public void setLegitimateRows(Integer legitimateRows) { this.legitimateRows = legitimateRows; }
    public ZonedDateTime getUploadedAt() { return uploadedAt; }
    public void setUploadedAt(ZonedDateTime uploadedAt) { this.uploadedAt = uploadedAt; }
    public String getDatasetVersion() { return datasetVersion; }
    public void setDatasetVersion(String datasetVersion) { this.datasetVersion = datasetVersion; }
    public String getStatus() { return status; }
    public void setStatus(String status) { this.status = status; }
    public boolean isSynthetic() { return synthetic; }
    public void setSynthetic(boolean synthetic) { this.synthetic = synthetic; }
    public Long getUploadedBy() { return uploadedBy; }
    public void setUploadedBy(Long uploadedBy) { this.uploadedBy = uploadedBy; }
}
