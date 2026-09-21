import axios from "axios";
import { getToken, removeToken, removeUser } from "./auth";

const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

export const api = axios.create({
  baseURL: API_URL,
  headers: { "Content-Type": "application/json" },
});

// Request interceptor — attach bearer token from cookie
api.interceptors.request.use((config) => {
  const token = getToken();
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

// Response interceptor — handle 401 globally
api.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response?.status === 401) {
      removeToken();
      removeUser();
      if (typeof window !== "undefined") {
        window.location.href = "/login";
      }
    }
    return Promise.reject(error);
  }
);

// ────────────────────────────────────────────────
// AUTH
// ────────────────────────────────────────────────
export const authApi = {
  login: (username: string, password: string) =>
    api.post("/api/v1/auth/login", { username, password }),

  me: () => api.get("/api/v1/auth/me"),

  logout: () => api.post("/api/v1/auth/logout"),

  changePassword: (current_password: string, new_password: string) =>
    api.post("/api/v1/auth/change-password", {
      current_password,
      new_password,
    }),
};

// ────────────────────────────────────────────────
// STUDENTS
// ────────────────────────────────────────────────
export const studentsApi = {
  list: (params?: Record<string, unknown>) =>
    api.get("/api/v1/students", { params }),

  detail: (roll_no: string) => api.get(`/api/v1/students/${roll_no}`),

  atRisk: () => api.get("/api/v1/students/at-risk"),

  deansList: () => api.get("/api/v1/students/deans-list"),

  search: (q: string) => api.get("/api/v1/students/search", { params: { q } }),

  cgpaHistory: (roll_no: string) =>
    api.get(`/api/v1/students/${roll_no}/cgpa-history`),

  departmentSummary: () => api.get("/api/v1/students/department-summary"),

  portalMe: () => api.get("/api/v1/students/portal/me"),

  portalGrades: () => api.get("/api/v1/students/portal/my-grades"),

  portalTranscripts: () => api.get("/api/v1/students/portal/my-transcripts"),

  portalVouchers: () => api.get("/api/v1/students/portal/my-vouchers"),
};

// ────────────────────────────────────────────────
// GRADES / UPLOAD
// ────────────────────────────────────────────────
export const gradesApi = {
  upload: (formData: FormData) =>
    api.post("/api/v1/grades/upload", formData, {
      headers: { "Content-Type": "multipart/form-data" },
    }),

  uploadBatch: (formData: FormData) =>
    api.post("/api/v1/grades/upload/batch", formData, {
      headers: { "Content-Type": "multipart/form-data" },
    }),

  jobStatus: (job_id: string) => api.get(`/api/v1/grades/jobs/${job_id}`),

  jobReport: (job_id: string) =>
    api.get(`/api/v1/grades/jobs/${job_id}/report`),

  approve: (job_id: string, data: Record<string, unknown>) =>
    api.post(`/api/v1/grades/jobs/${job_id}/approve`, data),

  approveBatch: (data: Record<string, unknown>) =>
    api.post("/api/v1/grades/approve-batch", data),

  jobs: (params?: Record<string, unknown>) =>
    api.get("/api/v1/grades/jobs", { params }),
};

// ────────────────────────────────────────────────
// ANALYTICS
// ────────────────────────────────────────────────
export const analyticsApi = {
  kpi: (params?: Record<string, unknown>) =>
    api.get("/api/v1/analytics/kpi", { params }),

  gradeDistribution: (params?: Record<string, unknown>) =>
    api.get("/api/v1/analytics/grade-distribution", { params }),

  cgpaTrend: (params?: Record<string, unknown>) =>
    api.get("/api/v1/analytics/cgpa-trend", { params }),

  subjectDifficulty: (params?: Record<string, unknown>) =>
    api.get("/api/v1/analytics/subject-difficulty", { params }),

  meritList: (params?: Record<string, unknown>) =>
    api.get("/api/v1/analytics/merit-list", { params }),

  summaryReport: (params?: Record<string, unknown>) =>
    api.get("/api/v1/analytics/summary-report", { params }),

  departmentBreakdown: () => api.get("/api/v1/analytics/department-breakdown"),
};

// ────────────────────────────────────────────────
// TRANSCRIPTS
// ────────────────────────────────────────────────
export const transcriptsApi = {
  generate: (data: Record<string, unknown>) =>
    api.post("/api/v1/transcripts/generate", data, {
      responseType: "blob",
    }),

  generateBulk: (data: Record<string, unknown>) =>
    api.post("/api/v1/transcripts/generate-bulk", data, {
      responseType: "blob",
    }),

  records: (params?: Record<string, unknown>) =>
    api.get("/api/v1/transcripts/records", { params }),

  revoke: (token: string) =>
    api.delete(`/api/v1/transcripts/records/${token}/revoke`),

  verify: (token: string) => api.get(`/verify/${token}`),
};

// ────────────────────────────────────────────────
// PAYMENTS
// ────────────────────────────────────────────────
export const paymentsApi = {
  requestVoucher: (data: Record<string, unknown>) =>
    api.post("/api/v1/payments/request-voucher", data),

  vouchers: (params?: Record<string, unknown>) =>
    api.get("/api/v1/payments/vouchers", { params }),

  markPaid: (voucher_number: string, data: Record<string, unknown>) =>
    api.patch(
      `/api/v1/payments/vouchers/${voucher_number}/mark-paid`,
      data
    ),

  cancel: (voucher_number: string) =>
    api.patch(`/api/v1/payments/vouchers/${voucher_number}/cancel`),

  dailyReport: (date: string) =>
    api.get("/api/v1/payments/daily-report", { params: { date } }),

  downloadTranscript: (voucher_number: string) =>
    api.get(`/api/v1/payments/download-transcript/${voucher_number}`, {
      responseType: "blob",
    }),
};

// ────────────────────────────────────────────────
// NOTIFICATIONS
// ────────────────────────────────────────────────
export const notificationsApi = {
  sendGradesPublished: (data: Record<string, unknown>) =>
    api.post("/api/v1/notifications/send-grades-published", data),

  queue: (params?: Record<string, unknown>) =>
    api.get("/api/v1/notifications/queue", { params }),

  processQueue: () => api.post("/api/v1/notifications/process-queue"),

  stats: () => api.get("/api/v1/notifications/stats"),

  auditLog: (params?: Record<string, unknown>) =>
    api.get("/api/v1/notifications/audit-log", { params }),

  auditExport: (params?: Record<string, unknown>) =>
    api.get("/api/v1/notifications/audit-log/export", {
      params,
      responseType: "blob",
    }),
};
