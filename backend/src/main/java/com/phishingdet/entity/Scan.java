package com.phishingdet.entity;

import jakarta.persistence.CascadeType;
import jakarta.persistence.Column;
import jakarta.persistence.Entity;
import jakarta.persistence.FetchType;
import jakarta.persistence.GeneratedValue;
import jakarta.persistence.GenerationType;
import jakarta.persistence.Id;
import jakarta.persistence.JoinColumn;
import jakarta.persistence.ManyToOne;
import jakarta.persistence.OneToMany;
import jakarta.persistence.Table;

import java.time.ZonedDateTime;
import java.util.ArrayList;
import java.util.List;

/**
 * One URL analysis: the submitted URL, the final verdict produced by the
 * fusion engine, and (through child rows) every modality result and evidence
 * item.
 *
 * <p>{@code isSeedData = TRUE} marks illustrative rows written by the database
 * seed script - they were <b>not</b> produced by the detection engine.</p>
 */
@Entity
@Table(name = "scans")
public class Scan {

    public enum Prediction { PHISHING, LEGITIMATE, SUSPICIOUS, UNKNOWN }
    public enum RiskLevel { LOW, MEDIUM, HIGH, CRITICAL, UNKNOWN }
    /** PARTIAL = some modalities could not run; the verdict is real but incomplete. */
    public enum Status { PENDING, RUNNING, COMPLETED, PARTIAL, FAILED, SEED_DEMO }
    public enum InputType { WEBSITE, EMAIL, SMS, QR }

    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    private Long id;

    @ManyToOne(fetch = FetchType.LAZY)
    @JoinColumn(name = "user_id")
    private User user;

    @Column(name = "submitted_url", nullable = false, columnDefinition = "text")
    private String submittedUrl;

    /** Which of the four detectors produced this scan: WEBSITE | EMAIL | SMS | QR. */
    @Column(name = "input_type", nullable = false, length = 20)
    private String inputType = InputType.WEBSITE.name();

    @Column(name = "normalized_url", columnDefinition = "text")
    private String normalizedUrl;

    @Column(name = "submitted_at", nullable = false, updatable = false)
    private ZonedDateTime submittedAt;

    @Column(name = "completed_at")
    private ZonedDateTime completedAt;

    @Column(name = "final_prediction", length = 20)
    private String finalPrediction;

    @Column(name = "risk_level", length = 20)
    private String riskLevel;

    /** 0..1 score produced by the documented scoring method. NULL when not computed. */
    @Column(name = "risk_score")
    private Double riskScore;

    @Column(name = "processing_time_ms")
    private Long processingTimeMs;

    @Column(nullable = false, length = 20)
    private String status = Status.PENDING.name();

    @Column(name = "model_version", length = 50)
    private String modelVersion;

    @Column(columnDefinition = "text")
    private String explanation;

    /** JSON array of modalities that could not be analysed (failure/absent model). */
    @Column(name = "missing_modalities", columnDefinition = "text")
    private String missingModalities = "[]";

    @Column(name = "is_seed_data", nullable = false)
    private boolean seedData;

    /** Complete engine payload (caveats, fusion weights, per-modality detail). */
    @Column(name = "result_json", columnDefinition = "text")
    private String resultJson;

    /** File name (inside the shared uploads directory) of the captured screenshot. */
    @Column(name = "screenshot_file", length = 255)
    private String screenshotFile;

    @OneToMany(mappedBy = "scan", cascade = CascadeType.ALL, orphanRemoval = true)
    private List<ModalityResult> modalityResults = new ArrayList<>();

    @OneToMany(mappedBy = "scan", cascade = CascadeType.ALL, orphanRemoval = true)
    private List<Evidence> evidence = new ArrayList<>();

    @jakarta.persistence.PrePersist
    void onCreate() {
        if (submittedAt == null) {
            submittedAt = ZonedDateTime.now(java.time.ZoneOffset.UTC);
        }
    }

    public Long getId() { return id; }
    public void setId(Long id) { this.id = id; }
    public User getUser() { return user; }
    public void setUser(User user) { this.user = user; }
    public String getSubmittedUrl() { return submittedUrl; }
    public void setSubmittedUrl(String submittedUrl) { this.submittedUrl = submittedUrl; }
    public String getInputType() { return inputType; }
    public void setInputType(String inputType) { this.inputType = inputType; }
    public String getNormalizedUrl() { return normalizedUrl; }
    public void setNormalizedUrl(String normalizedUrl) { this.normalizedUrl = normalizedUrl; }
    public ZonedDateTime getSubmittedAt() { return submittedAt; }
    public void setSubmittedAt(ZonedDateTime submittedAt) { this.submittedAt = submittedAt; }
    public ZonedDateTime getCompletedAt() { return completedAt; }
    public void setCompletedAt(ZonedDateTime completedAt) { this.completedAt = completedAt; }
    public String getFinalPrediction() { return finalPrediction; }
    public void setFinalPrediction(String finalPrediction) { this.finalPrediction = finalPrediction; }
    public String getRiskLevel() { return riskLevel; }
    public void setRiskLevel(String riskLevel) { this.riskLevel = riskLevel; }
    public Double getRiskScore() { return riskScore; }
    public void setRiskScore(Double riskScore) { this.riskScore = riskScore; }
    public Long getProcessingTimeMs() { return processingTimeMs; }
    public void setProcessingTimeMs(Long processingTimeMs) { this.processingTimeMs = processingTimeMs; }
    public String getStatus() { return status; }
    public void setStatus(String status) { this.status = status; }
    public String getModelVersion() { return modelVersion; }
    public void setModelVersion(String modelVersion) { this.modelVersion = modelVersion; }
    public String getExplanation() { return explanation; }
    public void setExplanation(String explanation) { this.explanation = explanation; }
    public String getMissingModalities() { return missingModalities; }
    public void setMissingModalities(String missingModalities) { this.missingModalities = missingModalities; }
    public boolean isSeedData() { return seedData; }
    public void setSeedData(boolean seedData) { this.seedData = seedData; }
    public String getResultJson() { return resultJson; }
    public void setResultJson(String resultJson) { this.resultJson = resultJson; }
    public String getScreenshotFile() { return screenshotFile; }
    public void setScreenshotFile(String screenshotFile) { this.screenshotFile = screenshotFile; }
    public List<ModalityResult> getModalityResults() { return modalityResults; }
    public List<Evidence> getEvidence() { return evidence; }
}
