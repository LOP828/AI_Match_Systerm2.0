import { clearStoredSession, getStoredSession } from '../auth/session'

const BASE = '/api'

export class ApiError extends Error {
  status: number

  constructor(message: string, status: number) {
    super(message)
    this.name = 'ApiError'
    this.status = status
  }
}

type RequestOptions = RequestInit & {
  authToken?: string
  skipAuth?: boolean
}

async function toErrorMessage(res: Response): Promise<string> {
  const text = await res.text()
  if (!text) {
    return `Request failed with status ${res.status}`
  }

  try {
    const payload = JSON.parse(text) as { detail?: string }
    return payload.detail || text
  } catch {
    return text
  }
}

async function request<T>(path: string, options?: RequestOptions): Promise<T> {
  const headers = new Headers(options?.headers)
  const hasBody = options?.body !== undefined && options?.body !== null
  const isFormData = typeof FormData !== 'undefined' && options?.body instanceof FormData

  if (hasBody && !isFormData && !headers.has('Content-Type')) {
    headers.set('Content-Type', 'application/json')
  }

  if (!options?.skipAuth) {
    const token = options?.authToken || getStoredSession()?.accessToken
    if (token) {
      headers.set('Authorization', `Bearer ${token}`)
    }
  }

  const res = await fetch(`${BASE}${path}`, {
    ...options,
    headers,
  })

  if (!res.ok) {
    const message = await toErrorMessage(res)
    if (res.status === 401) {
      clearStoredSession('unauthorized')
    }
    throw new ApiError(message, res.status)
  }

  if (res.status === 204) {
    return undefined as T
  }

  return res.json()
}

export const api = {
  auth: {
    login: (body: LoginRequest) =>
      request<TokenResponse>('/auth/login', { method: 'POST', body: JSON.stringify(body), skipAuth: true }),
    me: (authToken?: string) =>
      request<MeResponse>('/auth/me', { authToken, skipAuth: !authToken }),
  },
  profile: {
    get: (userId: number) => request<ProfileFull>(`/profile/${userId}`),
    update: (userId: number, data: ProfileUpdate) =>
      request<ProfileResponse>(`/profile/${userId}`, { method: 'POST', body: JSON.stringify(data) }),
    addPreference: (userId: number, data: PreferenceCreate) =>
      request<PreferenceResponse>(`/profile/${userId}/preference`, { method: 'POST', body: JSON.stringify(data) }),
    deletePreference: (userId: number, preferenceId: number) =>
      request<{ success: boolean }>(`/profile/${userId}/preference/${preferenceId}`, { method: 'DELETE' }),
    addConstraint: (userId: number, data: ConstraintCreate) =>
      request<ConstraintResponse>(`/profile/${userId}/constraint`, { method: 'POST', body: JSON.stringify(data) }),
    deleteConstraint: (userId: number, constraintId: number) =>
      request<{ success: boolean }>(`/profile/${userId}/constraint/${constraintId}`, { method: 'DELETE' }),
    addObservationTag: (userId: number, data: ObservationTagCreate) =>
      request<ObservationTagResponse>(`/profile/${userId}/observation-tag`, { method: 'POST', body: JSON.stringify(data) }),
    deleteObservationTag: (userId: number, tagId: number) =>
      request<{ success: boolean }>(`/profile/${userId}/observation-tag/${tagId}`, { method: 'DELETE' }),
  },
  recommendation: {
    generate: (body: GenerateRequest) =>
      request<GenerateResponse>('/recommendation/generate', { method: 'POST', body: JSON.stringify(body) }),
    get: (requesterId: number, stage?: string) =>
      request<SnapshotItem[]>(`/recommendation/${requesterId}${stage ? `?stage=${stage}` : ''}`),
    regenerate: (requesterId: number, body?: { topN?: number }) =>
      request<RegenerateResponse>(`/recommendation/regenerate/${requesterId}`, {
        method: 'POST',
        body: JSON.stringify(body || {}),
      }),
  },
  verifyTasks: {
    get: (requesterUserId: number, status?: string) =>
      request<VerifyTaskItem[]>(`/verify-tasks/?requesterUserId=${requesterUserId}${status ? `&status=${status}` : ''}`),
    confirm: (taskId: number, body: ConfirmVerifyRequest) =>
      request<ConfirmVerifyResponse>(`/verify-tasks/${taskId}/confirm`, { method: 'POST', body: JSON.stringify(body) }),
  },
  feedback: {
    recordMeeting: (body: RecordMeetingRequest) =>
      request<{ success: boolean; eventId: number }>('/feedback/meeting', { method: 'POST', body: JSON.stringify(body) }),
    getHistory: (userAId: number, userBId: number) =>
      request<InteractionHistoryItem[]>(`/feedback/history?userAId=${userAId}&userBId=${userBId}`),
    getUserHistory: (userId: number, limit?: number) =>
      request<InteractionHistoryItem[]>(`/feedback/history/${userId}${limit ? `?limit=${limit}` : ''}`),
    getSignals: (userId: number) =>
      request<FeedbackSignals>(`/feedback/signals/${userId}`),
  },
  aiExtraction: {
    get: (entityType: string, entityId: number, status?: string) =>
      request<AiExtractionItem[]>(`/ai-extraction/?entityType=${entityType}&entityId=${entityId}${status ? `&status=${status}` : ''}`),
    approve: (extractionId: number, reviewedBy?: number) =>
      request<ApproveExtractionResponse>(`/ai-extraction/${extractionId}/approve${reviewedBy ? `?reviewedBy=${reviewedBy}` : ''}`, { method: 'POST' }),
    reject: (extractionId: number, reviewedBy?: number) =>
      request<{ success: boolean }>(`/ai-extraction/${extractionId}/reject${reviewedBy ? `?reviewedBy=${reviewedBy}` : ''}`, { method: 'POST' }),
  },
}

export interface LoginRequest {
  userId: number
  password: string
}

export interface TokenResponse {
  accessToken: string
  tokenType: string
  expiresInSeconds: number
}

export interface MeResponse {
  userId: number
  role: string
  source: string
  privileged: boolean
}

export interface ProfileResponse {
  user_id: number
  gender?: string
  age?: number
  height_cm?: number
  city_code?: string
  education_level?: string
  marital_status?: string
  occupation?: string
  smoking_status?: string
  drinking_status?: string
  pet_status?: string
  open_to_match?: number
  active_status?: string
}

export interface PreferenceResponse {
  preference_id: number
  user_id: number
  dimension: string
  operator: string
  value_json?: Record<string, unknown>
  priority_level?: string
}

export interface ConstraintResponse {
  constraint_id: number
  user_id: number
  tag_code: string
  tag_type: string
  applies_to_field?: string
  status?: string
}

export interface ObservationTagResponse {
  tag_id: number
  user_id: number
  tag_code: string
  tag_value?: string
  confidence?: number
  observer_type?: string
  status?: string
}

export interface ProfileFull {
  profile: ProfileResponse | null
  preferences: PreferenceResponse[]
  constraints: ConstraintResponse[]
  tags: ObservationTagResponse[]
}

export interface ProfileUpdate {
  gender?: string
  age?: number
  height_cm?: number
  city_code?: string
  education_level?: string
  marital_status?: string
  occupation?: string
  smoking_status?: string
  drinking_status?: string
  pet_status?: string
  open_to_match?: number
  active_status?: string
}

export interface PreferenceCreate {
  dimension: string
  operator: string
  value_json?: Record<string, unknown>
  priority_level?: string
  source_type?: string
}

export interface ConstraintCreate {
  tag_code: string
  tag_type: string
  applies_to_field: string
  source_type?: string
}

export interface ObservationTagCreate {
  tag_code: string
  tag_value?: string
  confidence?: number
  observer_type: string
}

export interface GenerateRequest {
  requesterUserId: number
  filters?: { ageMin?: number; ageMax?: number; cities?: string[]; educationLevels?: string[] }
}

export interface TopCandidate {
  candidateId: number
  profile?: Record<string, unknown>
  scores: { safetyScore: number; chatScore: number; secondDateScore: number; conflictRiskScore: number }
  unknownConstraintCount: number
  unknownConstraints: { tagCode: string; appliesToField?: string }[]
}

export interface GenerateResponse {
  basicCandidatesCount: number
  safeCandidatesCount: number
  topCandidates: TopCandidate[]
}

export interface SnapshotItem {
  rec_id: number
  requester_user_id: number
  candidate_user_id: number
  safety_score?: number
  chat_score?: number
  final_rank_score?: number
  snapshot_stage?: string
  explanation_json?: Record<string, unknown>
  verify_pending_count?: number
  created_at?: string
}

export interface VerifyTaskItem {
  task_id: number
  requester_user_id: number
  candidate_user_id: number
  verify_field: string
  trigger_reason?: string
  rough_rank_score?: number
  task_status?: string
  confirmed_value?: string
  created_at?: string
}

export interface ConfirmVerifyRequest {
  confirmedValue: string
  confirmedBy?: number
}

export interface RecordMeetingRequest {
  userAId: number
  userBId: number
  willingnessA: string
  willingnessB: string
  conversationSmoothness?: number
  appearanceAcceptance?: number
  valuesAlignment?: number
  rejectReasonPrimary?: string
  rejectReasonSecondary?: string
  issueTagsJson?: string[]
  memoText: string
}

export interface InteractionHistoryItem {
  event_id: number
  event_type: string
  user_a_id: number
  user_b_id: number
  willingness_a?: string
  willingness_b?: string
  conversation_smoothness?: number
  appearance_acceptance?: number
  values_alignment?: number
  reject_reason_primary?: string
  reject_reason_secondary?: string
  issue_tags_json?: string[]
  memo_text?: string
  event_time?: string
  created_at?: string
}

export interface FeedbackSignals {
  userId: number
  totalMeetings: number
  avgConversationSmoothness?: number
  avgAppearanceAcceptance?: number
  avgValuesAlignment?: number
  topRejectReasons: string[]
  continueRate?: number
}

export interface AiExtractionItem {
  extraction_id: number
  entity_type: string
  entity_id: number
  extracted_label: string
  extracted_value?: string
  extraction_type?: string
  confidence?: number
  evidence_text?: string
  extraction_status?: string
  suggested_action?: string
  created_at?: string
}

export interface ApproveExtractionResponse {
  success: boolean
  extractionId: number
  status: string
  appliedAction: string
  targetEntity?: string
  createdObservationTagId?: number
  createdConstraintId?: number
  createdVerifyTaskId?: number
}

export interface RegenerateItem {
  candidateId: number
  score: number
  rank: number
}

export interface RegenerateResponse {
  requesterId: number
  stage: string
  usedConfirmedVerifyTasks: number
  items: RegenerateItem[]
}

export interface ConfirmVerifyResponse {
  success: boolean
  taskId: number
  status: string
  writtenField: string
  writtenValue: string
  pendingCount: number
  confirmedCount: number
  shouldRegenerateRecommendation: boolean
}
