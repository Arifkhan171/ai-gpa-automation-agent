export interface User {
  id: number;
  username: string;
  full_name: string;
  role: "super_admin" | "controller" | "hod" | "coordinator" | "student";
  department: string | null;
  email: string;
}

export interface AuthToken {
  access_token: string;
  token_type: string;
  expires_in: number;
  user: User;
}

export interface Student {
  id: number;
  roll_no: string;
  student_name: string;
  father_name: string | null;
  department: string | null;
  cgpa: number | null;
  total_credit_hours: number;
  semesters_completed: number;
  status: "excellent" | "good" | "satisfactory" | "at_risk" | "no_grades";
}

export interface SubjectMark {
  subject_name: string;
  credit_hours: number;
  obtained_marks: number;
  total_marks: number;
  percentage: number;
  grade_point: number;
  grade: string;
  quality_points: number;
  is_non_credit: boolean;
}

export interface SemesterDetail {
  semester: number;
  academic_year: string | null;   // BUG FIX: backend can return null
  subjects: SubjectMark[];
  total_credit_hours: number;
  total_quality_points: number;
  gpa: number | null;
}

export interface StudentDetail extends Student {
  father_name: string | null;
  created_at: string;
  semesters: SemesterDetail[];
}

export interface KPIData {
  total_students: number;
  total_departments: number;
  average_cgpa: number | null;
  at_risk_count: number;
  excellent_count: number;
  semesters_active: number;
  total_marks_recorded: number;
}

export interface GradeDistributionItem {
  grade: string;
  count: number;
  percentage: number;
}

export interface CGPATrendItem {
  semester: number;
  academic_year: string;
  average_gpa: number | null;
  student_count: number;
}

export interface PaymentVoucher {
  id: number;
  voucher_number: string;
  student_name: string;
  roll_no: string;
  purpose: string;
  amount: number;
  status: "pending" | "paid" | "cancelled" | "expired";
  semester_range: string | null;
  created_at: string;
  expires_at: string;
  paid_at: string | null;
  action_taken: boolean;
  message: string;
}

export interface TranscriptRecord {
  id: number;
  verification_token: string;
  roll_no: string;
  student_name: string;
  semester_range: string;
  cgpa_at_issue: number | null;
  is_unofficial: boolean;
  issued_by: string;
  issued_at: string;
  scan_count: number;
  is_valid: boolean;
}

export interface ApiError {
  detail: string;
}

export type UserRole = User["role"];
