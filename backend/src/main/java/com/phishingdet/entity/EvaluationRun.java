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
 * Metrics measured by one evaluation run of one model version.
 *
 * <p>Every metric column is <b>nullable</b>: NULL means "not measured".
 * Rows are only inserted by the evaluation pipeline after it has actually
 * executed - fabricated figures are prohibited.</p>
 */
@Entity
@Table(name = "evaluation_runs")
public class EvaluationRun {

    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    private Long id;

    @ManyToOne(optional = false, fetch = FetchType.LAZY)
    @JoinColumn(name = "model_version_id", nullable = false)
    private ModelVersion modelVersion;

    @ManyToOne(fetch = FetchType.LAZY)
    @JoinColumn(name = "dataset_id")
    private Dataset dataset;

    @Column(name = "evaluation_date", nullable = false, updatable = false)
    private ZonedDateTime evaluationDate;

    @Column(name = "split_strategy", length = 120)
    private String splitStrategy;

    @Column(name = "random_seed")
    private Long randomSeed;

    /** e.g. "URL", "URL+HTML", "URL+HTML+NLP", "URL+HTML+VISION", "FULL" */
    @Column(name = "ablation_config", length = 60)
    private String ablationConfig;

    private Double accuracy;

    @Column(name = "precision_score")
    private Double precisionScore;

    private Double recallScore;

    @Column(name = "f1_score")
    private Double f1Score;

    @Column(name = "roc_auc")
    private Double rocAuc;

    @Column(name = "false_positive_rate")
    private Double falsePositiveRate;

    @Column(name = "false_negative_rate")
    private Double falseNegativeRate;

    @Column(name = "results_json", columnDefinition = "text")
    private String resultsJson;

    @jakarta.persistence.PrePersist
    void onCreate() {
        if (evaluationDate == null) {
            evaluationDate = ZonedDateTime.now(java.time.ZoneOffset.UTC);
        }
    }

    public Long getId() { return id; }
    public void setId(Long id) { this.id = id; }
    public ModelVersion getModelVersion() { return modelVersion; }
    public void setModelVersion(ModelVersion modelVersion) { this.modelVersion = modelVersion; }
    public Dataset getDataset() { return dataset; }
    public void setDataset(Dataset dataset) { this.dataset = dataset; }
    public ZonedDateTime getEvaluationDate() { return evaluationDate; }
    public void setEvaluationDate(ZonedDateTime evaluationDate) { this.evaluationDate = evaluationDate; }
    public String getSplitStrategy() { return splitStrategy; }
    public void setSplitStrategy(String splitStrategy) { this.splitStrategy = splitStrategy; }
    public Long getRandomSeed() { return randomSeed; }
    public void setRandomSeed(Long randomSeed) { this.randomSeed = randomSeed; }
    public String getAblationConfig() { return ablationConfig; }
    public void setAblationConfig(String ablationConfig) { this.ablationConfig = ablationConfig; }
    public Double getAccuracy() { return accuracy; }
    public void setAccuracy(Double accuracy) { this.accuracy = accuracy; }
    public Double getPrecisionScore() { return precisionScore; }
    public void setPrecisionScore(Double precisionScore) { this.precisionScore = precisionScore; }
    public Double getRecallScore() { return recallScore; }
    public void setRecallScore(Double recallScore) { this.recallScore = recallScore; }
    public Double getF1Score() { return f1Score; }
    public void setF1Score(Double f1Score) { this.f1Score = f1Score; }
    public Double getRocAuc() { return rocAuc; }
    public void setRocAuc(Double rocAuc) { this.rocAuc = rocAuc; }
    public Double getFalsePositiveRate() { return falsePositiveRate; }
    public void setFalsePositiveRate(Double falsePositiveRate) { this.falsePositiveRate = falsePositiveRate; }
    public Double getFalseNegativeRate() { return falseNegativeRate; }
    public void setFalseNegativeRate(Double falseNegativeRate) { this.falseNegativeRate = falseNegativeRate; }
    public String getResultsJson() { return resultsJson; }
    public void setResultsJson(String resultsJson) { this.resultsJson = resultsJson; }
}
