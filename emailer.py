"""
Email sending for GLORi Evangelists Platform.
Uses Resend (https://resend.com) via HTTP API. If RESEND_API_KEY is not set,
sends are skipped with a warning log so the app never crashes on missing config.
"""
import os
import logging
import httpx

logger = logging.getLogger("glori_evangelists.emailer")

RESEND_API_KEY = os.environ.get("RESEND_API_KEY", "")
FROM_EMAIL = os.environ.get("FROM_EMAIL", "GLORi Evangelists <reps@glori.com>")
APP_BASE_URL = os.environ.get("APP_BASE_URL", "https://glori-evangelists.fly.dev")

NAVY = "#1C2B35"
GOLD = "#C9A84C"


def _send(to_email: str, subject: str, html: str) -> bool:
    if not RESEND_API_KEY:
        logger.warning(
            "RESEND_API_KEY not set - skipping email to %s (subject: %s)",
            to_email, subject,
        )
        return False
    try:
        resp = httpx.post(
            "https://api.resend.com/emails",
            headers={"Authorization": f"Bearer {RESEND_API_KEY}"},
            json={
                "from": FROM_EMAIL,
                "to": [to_email],
                "subject": subject,
                "html": html,
            },
            timeout=10.0,
        )
        resp.raise_for_status()
        return True
    except Exception:
        logger.exception("Failed to send email to %s", to_email)
        return False


def _wrap(title: str, body_html: str) -> str:
    return f"""
    <div style="font-family: Georgia, 'Times New Roman', serif; max-width: 560px;
                margin: 0 auto; background:#ffffff;">
      <div style="background:{NAVY}; padding: 28px 32px;">
        <span style="color:#F5F1E6; font-size:22px; font-weight:bold; letter-spacing:1px;">
          GLOR<span style="color:{GOLD};">i</span> Evangelists
        </span>
      </div>
      <div style="padding: 32px; color:{NAVY}; font-size:15px; line-height:1.6;">
        <h2 style="color:{NAVY}; margin-top:0;">{title}</h2>
        {body_html}
        <p style="margin-top:32px; font-size:13px; color:#6b7280;">
          g to G &mdash; man&rsquo;s glori to God&rsquo;s Glori
        </p>
      </div>
    </div>
    """


def send_invite_email(to_email: str, name: str, token: str) -> bool:
    link = f"{APP_BASE_URL}/accept-invite?token={token}"
    body = f"""
    <p>Hi {name},</p>
    <p>Welcome to the GLORi Evangelists team! An account has been created for you so you
    can track your territory, clients, commissions, and Kingdom impact in real time.</p>
    <p style="text-align:center; margin:32px 0;">
      <a href="{link}" style="background:{GOLD}; color:{NAVY}; text-decoration:none;
         font-weight:bold; padding:14px 28px; border-radius:6px; display:inline-block;">
        Accept Invite &amp; Set Password
      </a>
    </p>
    <p>This link expires in 7 days. If you weren't expecting this invite, you can ignore
    this email.</p>
    """
    return _send(to_email, "You're invited - GLORi Evangelists", _wrap("Welcome to GLORi Evangelists", body))


def send_dispute_filed_email(admin_email: str, rep_name: str, dispute_type: str,
                              description: str, dispute_id: int) -> bool:
    link = f"{APP_BASE_URL}/leadership/disputes"
    body = f"""
    <p>{rep_name} just filed a commission dispute (#{dispute_id}, type: {dispute_type}).</p>
    <p style="background:#f4f4f4; padding:16px; border-radius:6px;">{description}</p>
    <p style="text-align:center; margin:32px 0;">
      <a href="{link}" style="background:{GOLD}; color:{NAVY}; text-decoration:none;
         font-weight:bold; padding:14px 28px; border-radius:6px; display:inline-block;">
        Review Dispute
      </a>
    </p>
    """
    return _send(admin_email, f"New commission dispute from {rep_name}", _wrap("Commission Dispute Filed", body))


def send_dispute_resolved_email(to_email: str, rep_name: str, status: str, resolution_notes: str) -> bool:
    link = f"{APP_BASE_URL}/rep/disputes"
    pretty_status = {"resolved": "Resolved", "rejected": "Rejected"}.get(status, status.title())
    notes_html = (
        f'<p style="background:#f4f4f4; padding:16px; border-radius:6px;">{resolution_notes}</p>'
        if resolution_notes else ""
    )
    body = f"""
    <p>Hi {rep_name},</p>
    <p>Your commission dispute has been reviewed. Status: <strong>{pretty_status}</strong></p>
    {notes_html}
    <p style="text-align:center; margin:32px 0;">
      <a href="{link}" style="background:{GOLD}; color:{NAVY}; text-decoration:none;
         font-weight:bold; padding:14px 28px; border-radius:6px; display:inline-block;">
        View My Disputes
      </a>
    </p>
    """
    return _send(to_email, "Update on your commission dispute", _wrap("Dispute Update", body))
