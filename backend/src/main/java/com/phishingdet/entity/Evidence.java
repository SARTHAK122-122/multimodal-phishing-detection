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

/**
 * A single piece of evidence supporting a verdict. Every row must point at a
 * concrete extracted feature, measured model output or recorded analysis
 * result - generic, invented explanations are not allowed.
 */
@Entity
@Table(name = "evidence")
public class Evidence {

    public enum Severity { INFO, LOW, MEDIUM, HIGH, CRITICAL }
    /** Did this item push the verdict toward phishing, toward legitimate, or neither? */
    public enum Direction { risk, safety, neutral }

    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    private Long id;

    @ManyToOne(optional = false, fetch = FetchType.LAZY)
    @JoinColumn(name = "scan_id", nullable = false)
    private Scan scan;

    @Column(nullable = false, length = 30)
    private String modality;

    @Column(name = "evidence_type", nullable = false, length = 60)
    private String evidenceType;

    @Column(nullable = false, columnDefinition = "text")
    private String description;

    @Column(nullable = false, length = 20)
    private String severity = Severity.INFO.name();

    @Column(name = "supporting_value", columnDefinition = "text")
    private String supportingValue;

    @Column(name = "is_seed_data", nullable = false)
    private boolean seedData;

    /** risk = toward phishing, safety = toward legitimate, neutral = context only. */
    @Column(nullable = false, length = 10)
    private String direction = Direction.neutral.name();

    /** FINDING = directly observed in the input; INFERENCE = produced by a model. */
    @Column(nullable = false, length = 12)
    private String kind = "FINDING";

    public Long getId() { return id; }
    public void setId(Long id) { this.id = id; }
    public Scan getScan() { return scan; }
    public void setScan(Scan scan) { this.scan = scan; }
    public String getModality() { return modality; }
    public void setModality(String modality) { this.modality = modality; }
    public String getEvidenceType() { return evidenceType; }
    public void setEvidenceType(String evidenceType) { this.evidenceType = evidenceType; }
    public String getDescription() { return description; }
    public void setDescription(String description) { this.description = description; }
    public String getSeverity() { return severity; }
    public void setSeverity(String severity) { this.severity = severity; }
    public String getSupportingValue() { return supportingValue; }
    public void setSupportingValue(String supportingValue) { this.supportingValue = supportingValue; }
    public boolean isSeedData() { return seedData; }
    public void setSeedData(boolean seedData) { this.seedData = seedData; }
    public String getDirection() { return direction; }
    public void setDirection(String direction) { this.direction = direction; }
    public String getKind() { return kind; }
    public void setKind(String kind) { this.kind = kind; }
}
