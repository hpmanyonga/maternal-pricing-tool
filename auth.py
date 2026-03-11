"""Supabase auth wrapper for Streamlit apps."""

import os
import streamlit as st


def _get_supabase():
    """Return a Supabase client."""
    url = os.getenv("SUPABASE_URL", "")
    key = os.getenv("SUPABASE_KEY", "")
    if not url or not key:
        try:
            url = st.secrets.get("SUPABASE_URL", url)
            key = st.secrets.get("SUPABASE_KEY", key)
        except Exception:
            pass
    if not url or not key:
        return None
    from supabase import create_client
    return create_client(url, key)


def require_auth():
    """Show login form if not authenticated. Returns True if authenticated."""
    if st.session_state.get("authenticated"):
        col1, col2 = st.sidebar.columns([3, 1])
        with col1:
            st.sidebar.caption(f"Signed in as {st.session_state.get('user_email', '')}")
        with col2:
            if st.sidebar.button("Logout", key="logout_btn"):
                st.session_state.clear()
                st.rerun()
        return True

    st.title("Sign in")
    st.caption("Network One Health — Authorised access only")

    email = st.text_input("Email")
    password = st.text_input("Password", type="password")

    if st.button("Sign in", type="primary"):
        sb = _get_supabase()
        if sb is None:
            st.error("Authentication service unavailable. Check environment variables.")
            return False
        try:
            result = sb.auth.sign_in_with_password({"email": email, "password": password})
            if result.user:
                st.session_state["authenticated"] = True
                st.session_state["user_email"] = result.user.email
                st.session_state["access_token"] = result.session.access_token
                st.rerun()
        except Exception as e:
            error_msg = str(e)
            if "Invalid login" in error_msg or "invalid" in error_msg.lower():
                st.error("Invalid email or password.")
            else:
                st.error("Sign in failed. Please try again.")
    return False
