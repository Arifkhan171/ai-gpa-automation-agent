# AcadTrack — Module 8: Next.js Frontend Foundation

## Quick Start (3 commands)

```bash
# 1. Navigate to the frontend directory
cd gpa-agentic-system/frontend

# 2. Install all packages
npm install --legacy-peer-deps

# 3. Start the dev server
npm run dev
```

Open **http://localhost:3000** — it redirects to the login page.

---

## Test Credentials

| Role        | Username       | Password     | Redirects to          |
|-------------|---------------|--------------|----------------------|
| Coordinator | `coordinator` | `Coord@123`  | `/dashboard/upload`  |
| Super Admin | `admin`       | `Admin@123`  | `/dashboard/overview`|
| Controller  | `controller`  | `Control@123`| `/dashboard/transcripts`|
| HOD         | `hod`         | `Hod@123`    | `/dashboard/analytics`|
| Student     | *your roll_no*| `Student@123`| `/portal`            |

---

## What's in Module 8

| Area              | Status   | Details                                  |
|-------------------|----------|------------------------------------------|
| Login page        | ✅ Done   | Two-column, navy + white, show/hide pw  |
| Auth (cookie+JWT) | ✅ Done   | Token in cookie, user in localStorage   |
| Dashboard layout  | ✅ Done   | Navy sidebar + header, role-guarded     |
| Student portal    | ✅ Done   | Separate sidebar, student-only access   |
| All stub pages    | ✅ Done   | 12 pages with consistent styling        |
| API client        | ✅ Done   | Axios with auto 401 redirect            |
| TypeScript types  | ✅ Done   | Full type coverage                      |
| Design system     | ✅ Done   | Exact colors, fonts, spacing            |
| shadcn/ui         | ✅ Done   | Button, Input, Card, Badge, Table, etc. |

---

## Project Structure

```
frontend/
├── src/
│   ├── app/
│   │   ├── login/page.tsx          ← Login (fully functional)
│   │   ├── dashboard/
│   │   │   ├── layout.tsx          ← Auth guard + sidebar
│   │   │   ├── overview/page.tsx   ← Stub (Module 9)
│   │   │   ├── upload/page.tsx     ← Stub (Module 9)
│   │   │   ├── students/page.tsx   ← Stub (Module 9)
│   │   │   ├── analytics/page.tsx  ← Stub (Module 9)
│   │   │   ├── transcripts/page.tsx← Stub (Module 9)
│   │   │   ├── payments/page.tsx   ← Stub (Module 9)
│   │   │   ├── notifications/page.tsx ← Stub (Module 9)
│   │   │   └── audit/page.tsx      ← Stub (Module 9)
│   │   └── portal/
│   │       ├── layout.tsx          ← Student portal guard
│   │       ├── page.tsx            ← Stub (Module 9)
│   │       ├── grades/page.tsx     ← Stub (Module 9)
│   │       ├── transcript/page.tsx ← Stub (Module 9)
│   │       └── payments/page.tsx   ← Stub (Module 9)
│   ├── components/
│   │   ├── layout/
│   │   │   ├── Sidebar.tsx         ← Role-aware staff nav
│   │   │   ├── Header.tsx          ← Top bar + user dropdown
│   │   │   └── StudentSidebar.tsx  ← Student portal nav
│   │   ├── shared/
│   │   │   ├── StatCard.tsx        ← KPI card with colored border
│   │   │   ├── StatusBadge.tsx     ← Colored student status pill
│   │   │   ├── PageTitle.tsx       ← Page heading
│   │   │   ├── LoadingSpinner.tsx  ← Animated spinner
│   │   │   └── ErrorMessage.tsx    ← Red error box
│   │   └── ui/                     ← shadcn components
│   ├── lib/
│   │   ├── api.ts                  ← All API calls (axios)
│   │   ├── auth.ts                 ← Cookie/localStorage helpers
│   │   └── utils.ts                ← cn(), formatCGPA(), etc.
│   ├── hooks/
│   │   ├── useAuth.ts              ← Login/logout/role check
│   │   └── useApi.ts               ← Generic data fetching
│   └── types/index.ts              ← All TypeScript interfaces
├── .env.local                      ← API URL config
└── package.json
```

---

## Environment Variables

Edit `frontend/.env.local` if your backend runs on a different port:

```env
NEXT_PUBLIC_API_URL=http://localhost:8000
NEXT_PUBLIC_APP_NAME=AcadTrack
NEXT_PUBLIC_UNIVERSITY_NAME=University of Loralai
```

---

## Acceptance Criteria Status

All 12 criteria from the Module 8 spec are satisfied:

1. ✅ `npm run dev` starts without errors on port 3000
2. ✅ `http://localhost:3000` redirects to `/login`
3. ✅ Login page has professional two-column layout
4. ✅ `coordinator / Coord@123` logs in → `/dashboard/upload`
5. ✅ Student roll_no / `Student@123` logs in → `/portal`
6. ✅ Wrong password shows red error, no crash
7. ✅ Dashboard shows sidebar + header + content area
8. ✅ Sidebar items are role-filtered correctly
9. ✅ Student portal has simpler sidebar
10. ✅ Logout clears session and redirects to `/login`
11. ✅ All 12 stub pages load without errors
12. ✅ `src/` and `backend/` are untouched
