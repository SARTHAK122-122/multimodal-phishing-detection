/** TypeScript mirrors of the Spring Boot DTOs. */

export interface HealthResponse {
  status: 'UP' | 'DEGRADED' | 'DOWN';
  service: string;
  timestamp: string;
  database: { status: string; detail: string };
  aiService: { status: string; detail: string };
  counts: Record<string, number>;
}

export interface Dataset {
  id: number;
  name: string;
  source: string;
  description: string | null;
  originalFilename: string;
  fileFormat: string;
  fileSizeBytes: number;
  columnNames: string[];
  targetColumn: string | null;
  totalRows: number | null;
  phishingRows: number | null;
  legitimateRows: number | null;
  uploadedAt: string;
  datasetVersion: string;
  status: string;
  synthetic: boolean;
}

export interface ColumnProfile {
  name: string;
  dtype: string;
  missing: number;
  missingPct: number;
  unique: number;
  samples: unknown[];
}

export interface TargetProfile {
  column: string | null;
  present: boolean;
  distribution: Record<string, number>;
  uniqueValues: string[];
  unrecognisedValues: string[];
  warnings: string[];
}

export interface DatasetPreview {
  filename: string;
  rows: number;
  columns: ColumnProfile[];
  columnNames: string[];
  duplicateRows: number;
  missingCells: number;
  target: TargetProfile;
  head: Record<string, unknown>[];
  warnings: string[];
  elapsedMs?: number;
}

export interface UploadResult {
  dataset: Dataset;
  preview: DatasetPreview | null;
}

export interface PreprocessOptions {
  normalizeLabels?: boolean;
  dropInvalidRows?: boolean;
  convertTypes?: boolean;
  detectConflictingDuplicates?: boolean;
  removeDuplicates?: boolean;
  handleMissing?: boolean;
  missingStrategy?: 'drop_rows' | 'median_mode' | 'drop_columns';
  missingMaxFraction?: number;
  dedupeOnColumn?: string | null;
  dropColumns?: string[];
  selectColumns?: string[];
  validateFeatures?: boolean;
  labelMapping?: Record<string, string>;
}

export interface Transformation {
  step: string;
  description: string;
  rowsAffected: number;
  details: Record<string, unknown>;
}

export interface PreprocessingRun {
  id: number;
  datasetId: number;
  datasetName: string | null;
  startedAt: string | null;
  completedAt: string | null;
  inputRows: number;
  outputRows: number;
  duplicatesRemoved: number;
  invalidRowsRemoved: number;
  missingValuesHandled: number;
  status: string;
  errorMessage: string | null;
  outputFilename: string | null;
  transformations: Transformation[];
  parameters: Record<string, unknown>;
  warnings: string[];
  classDistributionBefore: Record<string, number>;
  classDistributionAfter: Record<string, number>;
  missingBefore: Record<string, number>;
  missingAfter: Record<string, number>;
  featureReport: Record<string, unknown>;
  elapsedMs?: number;
}

export interface ModalityResult {
  id: number;
  modality: string;
  modelName: string;
  modelVersion: string | null;
  prediction: string | null;
  riskScore: number | null;
  status: string;
  processingTimeMs: number | null;
  detailJson: string | null;
}

export interface EvidenceItem {
  id: number;
  modality: string;
  evidenceType: string;
  description: string;
  severity: string;
  supportingValue: string | null;
  direction?: 'risk' | 'safety' | 'neutral';
  kind?: 'FINDING' | 'INFERENCE';
}

export interface Scan {
  id: number;
  inputType?: string;
  submittedUrl: string;
  normalizedUrl: string | null;
  submittedAt: string;
  completedAt: string | null;
  finalPrediction: string | null;
  riskLevel: string | null;
  riskScore: number | null;
  processingTimeMs: number | null;
  status: string;
  modelVersion: string | null;
  explanation: string | null;
  missingModalities: string[];
  seedData: boolean;
  modalityResults?: ModalityResult[];
  evidence?: EvidenceItem[];
  caveats?: string[];
  weightsUsed?: Record<string, number>;
  screenshotUrl?: string | null;
}

/* ---- live scan payloads returned by POST /api/scans/* (the AI engine) ---- */

export type InputType = 'WEBSITE' | 'EMAIL' | 'SMS' | 'QR';
export type Classification = 'PHISHING' | 'LEGITIMATE' | 'SUSPICIOUS' | 'UNKNOWN';
export type RiskLevel = 'LOW' | 'MEDIUM' | 'HIGH' | 'CRITICAL' | 'UNKNOWN';

export interface ScanModality {
  modality: string;
  status: 'OK' | 'SKIPPED' | 'FAILED' | 'MODEL_MISSING';
  prediction: string | null;
  riskScore: number | null;
  modelName: string;
  modelVersion?: string | null;
  modelType?: string;
  detail: Record<string, unknown>;
  processingTimeMs?: number | null;
  note?: string | null;
}

export interface ScanEvidence {
  modality: string;
  evidenceType: string;
  description: string;
  severity: string;
  supportingValue?: string;
  kind?: 'FINDING' | 'INFERENCE';
  direction?: 'risk' | 'safety' | 'neutral';
}

export interface ScanResult {
  id?: number;
  inputType: InputType;
  submittedInput: string;
  normalizedInput?: string;
  status: 'COMPLETED' | 'PARTIAL' | 'FAILED';
  classification: Classification;
  riskLevel: RiskLevel;
  riskScore: number | null;
  explanation: string;
  caveats: string[];
  weightsUsed?: Record<string, number>;
  evidenceModifier?: number;
  missingModalities: string[];
  modalities: ScanModality[];
  evidence: ScanEvidence[];
  screenshot?: string;
  processingTimeMs: number;
  decodedPayload?: string;
  payloadType?: string;
  extractedLinks?: string[];
  storedFile?: string;
}

export interface ModelVersion {
  id: number;
  modelName: string;
  modelType: string;
  version: string;
  trainingDate: string | null;
  modelArtifactPath: string | null;
  evaluationStatus: string;
  metricsJson: string | null;
  notes: string | null;
}

export interface EvaluationRun {
  id: number;
  modelVersionId: number;
  modelName?: string;
  modelVersion?: string;
  evaluationDate: string;
  splitStrategy: string | null;
  randomSeed: number | null;
  ablationConfig: string | null;
  accuracy: number | null;
  precisionScore: number | null;
  recallScore: number | null;
  f1Score: number | null;
  rocAuc: number | null;
  falsePositiveRate: number | null;
  falseNegativeRate: number | null;
  resultsJson: string | null;
}

/* ------------------------------ authentication ---------------------------- */

/** The signed-in account as /api/auth/me returns it (never contains a hash). */
export interface AuthUser {
  id: number;
  username: string;
  email: string;
  displayName: string | null;
  role: 'USER' | 'ADMIN';
  createdAt: string;
  lastLoginAt: string | null;
}

export interface RegisterInput {
  username: string;
  email: string;
  password: string;
  displayName?: string;
}

export interface LoginInput {
  username: string;
  password: string;
}

export interface ChangePasswordInput {
  currentPassword: string;
  newPassword: string;
}

export interface ProfileUpdateInput {
  displayName?: string;
  email?: string;
}
