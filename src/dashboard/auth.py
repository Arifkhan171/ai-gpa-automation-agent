"""
src/dashboard/auth.py
=====================
Role-Based Access Control — GPA Dashboard
University of Loralai | CS Department
Tech Lead: Arif Khan

Two roles:
  Coordinator  — full system control (pipeline, save, transcripts, analytics)
  HOD          — read-only observer (analytics, search, transcript view only)

Credentials are read from environment variables.
Add these to your .env file before going live:
    GPA_COORD_USER=coordinator
    GPA_COORD_PASS=your_strong_password
    GPA_HOD_USER=hod
    GPA_HOD_PASS=your_strong_password

Falls back to default dev credentials if env vars are not set.
"""

from __future__ import annotations

import os
import streamlit as st

# ── Credential store ───────────────────────────────────────────────────────────
# Keys are usernames (lowercased at login time).
# In production replace plain-text passwords with hashed values + bcrypt check.
_USERS: dict[str, dict[str, str]] = {
    os.getenv("GPA_COORD_USER", "coordinator"): {
        "password": os.getenv("GPA_COORD_PASS", "coord2024"),
        "role"    : "Coordinator",
        "display" : "GPA Coordinator",
    },
    os.getenv("GPA_HOD_USER", "hod"): {
        "password": os.getenv("GPA_HOD_PASS", "hod2024"),
        "role"    : "HOD",
        "display" : "Head of Department",
    },
}

# ── CSS ────────────────────────────────────────────────────────────────────────
_LOGIN_CSS = """
<style>
/* hide Streamlit chrome on the login page */
header[data-testid="stHeader"]   { display: none !important; }
.block-container                  { padding-top: 1rem !important; }

/* login card header */
.auth-card-header {
    background: linear-gradient(135deg, #0B1E3D 0%, #1E3A6E 100%);
    border-radius: 18px 18px 0 0;
    padding: 38px 40px 32px 40px;
    text-align: center;
}
.auth-logo {
    font-size: 2.4rem;
    margin-bottom: 12px;
}
.auth-card-title {
    font-size: 1.45rem;
    font-weight: 900;
    color: #F1F5F9;
    letter-spacing: -0.5px;
    line-height: 1.2;
}
.auth-card-univ {
    font-size: 0.75rem;
    color: #64748B;
    margin-top: 6px;
    text-transform: uppercase;
    letter-spacing: 1.2px;
    font-weight: 600;
}

/* card body wrapper */
.auth-card-body {
    background: #ffffff;
    border-radius: 0 0 18px 18px;
    padding: 28px 36px 32px 36px;
    box-shadow: 0 8px 32px rgba(0,0,0,0.12), 0 2px 8px rgba(0,0,0,0.08);
    border: 1px solid #E2E8F0;
    border-top: none;
}

/* error banner */
.auth-error {
    background: linear-gradient(135deg, #FEF2F2, #FEE2E2);
    border: 1px solid #FECACA;
    border-left: 4px solid #DC2626;
    border-radius: 10px;
    padding: 12px 16px;
    font-size: 0.84rem;
    color: #7F1D1D;
    font-weight: 500;
    margin-bottom: 16px;
    line-height: 1.5;
}

/* role hint below form */
.auth-hint {
    text-align: center;
    font-size: 0.72rem;
    color: #94A3B8;
    margin-top: 16px;
    line-height: 1.6;
}

/* sidebar user strip */
.auth-user-strip {
    border-top: 1px solid rgba(255,255,255,.08);
    padding: 14px 0 6px 0;
    margin-top: 8px;
}
.auth-user-label {
    font-size: 0.64rem;
    font-weight: 700;
    text-transform: uppercase;
    letter-spacing: 1.1px;
    color: #475569;
    margin-bottom: 8px;
}
.auth-user-row {
    display: flex;
    align-items: center;
    gap: 8px;
    margin-bottom: 12px;
}
.auth-role-badge {
    font-size: 0.62rem;
    font-weight: 800;
    letter-spacing: 0.6px;
    text-transform: uppercase;
    padding: 3px 9px;
    border-radius: 20px;
}
.auth-role-badge.coord {
    background: rgba(37,99,235,.18);
    color: #93C5FD;
}
.auth-role-badge.hod {
    background: rgba(255,255,255,.10);
    color: #94A3B8;
}
.auth-user-name {
    font-size: 0.82rem;
    color: #CBD5E1;
    font-weight: 500;
}

/* locked action banner */
.auth-locked {
    background: linear-gradient(135deg, #FFF7ED, #FED7AA);
    border: 1px solid #FED7AA;
    border-left: 4px solid #EA580C;
    border-radius: 10px;
    padding: 14px 18px;
    font-size: 0.86rem;
    color: #7C2D12;
    font-weight: 500;
    line-height: 1.5;
}
</style>
"""


# ══════════════════════════════════════════════════════════════════════════════
# PUBLIC HELPERS
# ══════════════════════════════════════════════════════════════════════════════

def get_role() -> str | None:
    """Return 'Coordinator', 'HOD', or None if not logged in."""
    return st.session_state.get("auth_role")


def get_display() -> str | None:
    """Return the human-readable display name of the logged-in user."""
    return st.session_state.get("auth_display")


def is_coordinator() -> bool:
    return get_role() == "Coordinator"


def is_hod() -> bool:
    return get_role() == "HOD"


def require_coordinator(action_label: str = "This action") -> None:
    """
    Render a locked banner when a Coordinator-only action is accessed by HOD.
    Call this instead of rendering the restricted UI element.
    """
    st.markdown(
        f'<div class="auth-locked">'
        f'🔒 <strong>{action_label}</strong> is restricted to the '
        f'GPA Coordinator. HOD access is read-only.</div>',
        unsafe_allow_html=True,
    )


# ══════════════════════════════════════════════════════════════════════════════
# LOGIN PAGE
# ══════════════════════════════════════════════════════════════════════════════

def render_login() -> None:
    """
    Render the full-page login screen.
    Call this from main() and then st.stop() so nothing else renders.
    """
    st.markdown(_LOGIN_CSS, unsafe_allow_html=True)

    # Center the card with columns
    _, center, _ = st.columns([1, 1.5, 1])

    with center:

        # ── Card header ────────────────────────────────────────────────────────
        st.markdown("""
        <div class="auth-card-header">
            <div class="auth-logo">🎓</div>
            <div class="auth-card-title">GPA Management System</div>
            <div class="auth-card-univ">University of Loralai · CS Department</div>
        </div>""", unsafe_allow_html=True)

        # ── Card body ──────────────────────────────────────────────────────────
        st.markdown('<div class="auth-card-body">', unsafe_allow_html=True)

        # Error banner (shown after a failed attempt)
        if st.session_state.get("_login_failed"):
            st.markdown(
                '<div class="auth-error">'
                '⚠️ Incorrect username or password. Please try again.'
                '</div>',
                unsafe_allow_html=True,
            )

        # Form — groups inputs and button so Enter key works
        with st.form("login_form", clear_on_submit=False):
            username = st.text_input(
                "Username",
                placeholder="Enter your username",
                label_visibility="visible",
            )
            password = st.text_input(
                "Password",
                type="password",
                placeholder="Enter your password",
                label_visibility="visible",
            )
            submitted = st.form_submit_button(
                "Sign In",
                use_container_width=True,
                type="primary",
            )

        if submitted:
            _handle_login(username.strip().lower(), password)

        st.markdown(
            '<div class="auth-hint">'
            'Contact your system administrator if you cannot log in.'
            '</div>',
            unsafe_allow_html=True,
        )

        st.markdown('</div>', unsafe_allow_html=True)  # close auth-card-body


def _handle_login(username: str, password: str) -> None:
    """Validate credentials and update session state."""
    user = _USERS.get(username)
    if user and user["password"] == password:
        st.session_state["auth_user"]    = username
        st.session_state["auth_role"]    = user["role"]
        st.session_state["auth_display"] = user["display"]
        st.session_state["_login_failed"] = False
        st.rerun()
    else:
        st.session_state["_login_failed"] = True
        st.rerun()


# ══════════════════════════════════════════════════════════════════════════════
# SIDEBAR USER STRIP + LOGOUT
# ══════════════════════════════════════════════════════════════════════════════

def render_logout() -> None:
    """
    Render the signed-in user strip and Logout button inside the sidebar.
    Call this at the bottom of render_sidebar() in app.py.
    """
    role    = get_role()
    display = get_display()

    if not role:
        return

    badge_cls = "coord" if role == "Coordinator" else "hod"

    st.markdown(
        f"""
        <div class="auth-user-strip">
            <div class="auth-user-label">Signed in as</div>
            <div class="auth-user-row">
                <span class="auth-role-badge {badge_cls}">{role}</span>
                <span class="auth-user-name">{display}</span>
            </div>
        </div>""",
        unsafe_allow_html=True,
    )

    if st.button("Sign Out", use_container_width=True, key="auth_logout_btn"):
        _do_logout()


def _do_logout() -> None:
    """Clear all auth keys and rerun so the login screen appears."""
    for key in ["auth_user", "auth_role", "auth_display", "_login_failed"]:
        st.session_state.pop(key, None)
    st.rerun()