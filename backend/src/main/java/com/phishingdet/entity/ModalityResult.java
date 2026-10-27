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
import jakarta.persistence.UniqueConstraint;

/**
 * Output of a single analysis module (modality) for one scan.
 * Exactly one row per (scan, modality) - enforced by a unique constraint.
 */
@Entity
@Table(name = "modality_results",
        uniqueConstraints = @UniqueConstraint(name = "uq_modality_per_scan", columnNames = {"scan_id", "modality"}))
public class ModalityResult {

    public enum Modality { URL, HTML, NLP, VISION, FORM_LINK, METADATA, FUSION }
    public enum Prediction { PHISHING, LEGITIMATE, SUSPICIOUS, UNKNOWN }
    public enum Status { OK, FAILED, SKIPPED, MODEL_MISSING }

    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    private Long id;

    @ManyToOne(optional = false, fetch = FetchType.LAZY)
    @JoinColumn(name = "scan_id", nullable = false)
    private Scan scan;

    @Column(nullable = false, length = 30)
    private String modality;

    @Column(name = "model_name", nullable = false, length = 80)
    private String modelName;

    @Column(name = "model_version", length = 50)
    private String modelVersion;

    @Column(length = 20)
    private String prediction;

    /** 0..1 module score, or NULL when the module produced no score. */
    @Column(name = "risk_score")
    private Double riskScore;

    @Column(nullable = false, length = 20)
    private String status = Status.OK.name();

    @Column(name = "processing_time_ms")
    private Long processingTimeMs;

    /** JSON object with module-specific details (features, probabilities, ...). */
    @Column(name = "detail_json", columnDefinition = "text")
    private String detailJson;

    @Column(name = "is_seed_data", nullable = false)
    private boolean seedData;

    public Long getId() { return id; }
    public void setId(Long id) { this.id = id; }
    public Scan getScan() { return scan; }
    public void setScan(Scan scan) { this.scan = scan; }
    public String getModality() { return modality; }
    public void setModality(String modality) { this.modality = modality; }
    public String getModelName() { return modelName; }
    public void setModelName(String modelName) { this.modelName = modelName; }
    public String getModelVersion() { return modelVersion; }
    public void setModelVersion(String modelVersion) { this.modelVersion = modelVersion; }
    public String getPrediction() { return prediction; }
    public void setPrediction(String prediction) { this.prediction = prediction; }
    public Double getRiskScore() { return riskScore; }
    public void setRiskScore(Double riskScore) { this.riskScore = riskScore; }
    public String getStatus() { return status; }
    public void setStatus(String status) { this.status = status; }
    public Long getProcessingTimeMs() { return processingTimeMs; }
    public void setProcessingTimeMs(Long processingTimeMs) { this.processingTimeMs = processingTimeMs; }
    public String getDetailJson() { return detailJson; }
    public void setDetailJson(String detailJson) { this.detailJson = detailJson; }
    public boolean isSeedData() { return seedData; }
    public void setSeedData(boolean seedData) { this.seedData = seedData; }
}
