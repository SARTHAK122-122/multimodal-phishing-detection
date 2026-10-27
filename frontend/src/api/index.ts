import { api } from './client'
import type {
  AuthUser, ChangePasswordInput, Dataset, DatasetPreview, EvaluationRun,
  HealthResponse, LoginInput, ModelVersion, PreprocessOptions,
  PreprocessingRun, ProfileUpdateInput, RegisterInput, Scan, ScanResult,
  UploadResult,
} from './types'

/* ----------------------------- system ----------------------------- */
export const getHealth = () => api.get<HealthResponse>('/health').then(r => r.data)

/* --------------------------- authentication ----------------------- */
export const getMe = () => api.get<AuthUser>('/auth/me').then(r => r.data)

export const login = (body: LoginInput) =>
  api.post<AuthUser>('/auth/login', body).then(r => r.data)

export const register = (body: RegisterInput) =>
  api.post<AuthUser>('/auth/register', body).then(r => r.data)

export const logout = () => api.post<{ ok: boolean }>('/auth/logout').then(r => r.data)

export const changePassword = (body: ChangePasswordInput) =>
  api.post<{ ok: boolean }>('/auth/change-password', body).then(r => r.data)

export const updateProfile = (body: ProfileUpdateInput) =>
  api.patch<AuthUser>('/auth/profile', body).then(r => r.data)

/* ----------------------------- datasets --------------------------- */
export const listDatasets = () => api.get<Dataset[]>('/datasets').then(r => r.data)

export const getDataset = (id: number) => api.get<Dataset>(`/datasets/${id}`).then(r => r.data)

export const uploadDataset = (form: FormData) =>
  api.post<UploadResult>('/datasets/upload', form, {
    headers: { 'Content-Type': 'multipart/form-data' },
  }).then(r => r.data)

export const previewDataset = (id: number, targetColumn?: string) =>
  api.get<DatasetPreview>(`/datasets/${id}/preview`, {
    params: targetColumn ? { targetColumn } : {},
  }).then(r => r.data)

export interface PreprocessBody {
  targetColumn: string
  options: PreprocessOptions
  outputFilename?: string
}

export const runPreprocessing = (id: number, body: PreprocessBody) =>
  api.post<PreprocessingRun>(`/datasets/${id}/preprocessing-runs`, body).then(r => r.data)

export const listRuns = (datasetId?: number) =>
  api.get<PreprocessingRun[]>('/preprocessing-runs', {
    params: datasetId ? { datasetId } : {},
  }).then(r => r.data)

export const getRun = (id: number) => api.get<PreprocessingRun>(`/preprocessing-runs/${id}`).then(r => r.data)

export const downloadRunUrl = (id: number) =>
  `${api.defaults.baseURL}/preprocessing-runs/${id}/download`

/* ------------------------------ scans ----------------------------- */
export const listScans = (page = 0, size = 25) =>
  api.get<{ content: Scan[]; totalElements: number; totalPages: number; number: number }>(
    '/scans', { params: { page, size } },
  ).then(r => r.data)

export const getScan = (id: number) => api.get<Scan>(`/scans/${id}`).then(r => r.data)

export const getScanHistory = (limit = 10) =>
  api.get<Scan[]>('/scans/history', { params: { limit } }).then(r => r.data)

export const createScan = (url: string) =>
  api.post<ScanResult>('/scans', { inputType: 'WEBSITE', url }).then(r => r.data)

export interface WebsiteScanBody { url: string; fetch?: boolean; render?: boolean }
export interface EmailScanBody {
  subject?: string; body: string; sender?: string;
  spf?: string; dkim?: string; dmarc?: string; analyzeLinks?: boolean;
}
export interface SmsScanBody { message: string; sender?: string; analyzeLinks?: boolean }

export const scanWebsite = (body: WebsiteScanBody) =>
  api.post<ScanResult>('/scans/website', body).then(r => r.data)

export const scanEmail = (body: EmailScanBody) =>
  api.post<ScanResult>('/scans/email', body).then(r => r.data)

export const scanSms = (body: SmsScanBody) =>
  api.post<ScanResult>('/scans/sms', body).then(r => r.data)

export const scanQr = (file: File) => {
  const form = new FormData()
  form.append('file', file)
  return api.post<ScanResult>('/scans/qr', form, {
    headers: { 'Content-Type': 'multipart/form-data' },
  }).then(r => r.data)
}

/* ----------------------------- models ----------------------------- */
export const listModels = () => api.get<ModelVersion[]>('/models').then(r => r.data)
export const listEvaluations = () => api.get<EvaluationRun[]>('/evaluations').then(r => r.data)
