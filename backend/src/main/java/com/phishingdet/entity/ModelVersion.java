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

import java.time.ZonedDateTime;

/**
 * Registry entry for one version of one model artifact.
 * {@code metricsJson} stays NULL until a real evaluation has been executed -
 * no performance numbers are ever invented.
 */
@Entity
@Table(name = "model_versions",
        uniqueConstraints = @UniqueConstraint(name = "uq_model_name_version", columnNames = {"model_name", "version"}))
public class ModelVersion {

    public enum ModelType { ML, DL, FUSION, RULE_BASED }
    public enum EvaluationStatus { NOT_TRAINED, TRAINED, EVALUATED, PENDING }

    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    private Long id;

    @Column(name = "model_name", nullable = false, length = 80)
    private String modelName;

    @Column(name = "model_type", nullable = false, length = 40)
    private String modelType;

    @Column(nullable = false, length = 30)
    private String version;

    @ManyToOne(fetch = FetchType.LAZY)
    @JoinColumn(name = "dataset_id")
    private Dataset dataset;

    @Column(name = "training_date")
    private ZonedDateTime trainingDate;

    /** Relative path inside the repository's models directory - never an absolute path. */
    @Column(name = "model_artifact_path", length = 255)
    private String modelArtifactPath;

    @Column(name = "evaluation_status", nullable = false, length = 30)
    private String evaluationStatus = EvaluationStatus.NOT_TRAINED.name();

    @Column(name = "metrics_json", columnDefinition = "text")
    private String metricsJson;

    @Column(columnDefinition = "text")
    private String notes;

    public Long getId() { return id; }
    public void setId(Long id) { this.id = id; }
    public String getModelName() { return modelName; }
    public void setModelName(String modelName) { this.modelName = modelName; }
    public String getModelType() { return modelType; }
    public void setModelType(String modelType) { this.modelType = modelType; }
    public String getVersion() { return version; }
    public void setVersion(String version) { this.version = version; }
    public Dataset getDataset() { return dataset; }
    public void setDataset(Dataset dataset) { this.dataset = dataset; }
    public ZonedDateTime getTrainingDate() { return trainingDate; }
    public void setTrainingDate(ZonedDateTime trainingDate) { this.trainingDate = trainingDate; }
    public String getModelArtifactPath() { return modelArtifactPath; }
    public void setModelArtifactPath(String modelArtifactPath) { this.modelArtifactPath = modelArtifactPath; }
    public String getEvaluationStatus() { return evaluationStatus; }
    public void setEvaluationStatus(String evaluationStatus) { this.evaluationStatus = evaluationStatus; }
    public String getMetricsJson() { return metricsJson; }
    public void setMetricsJson(String metricsJson) { this.metricsJson = metricsJson; }
    public String getNotes() { return notes; }
    public void setNotes(String notes) { this.notes = notes; }
}
