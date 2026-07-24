"""
Email utilities for sending emails via Gmail SMTP
"""
import html
import os
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from typing import List, Optional


def send_email(
    to_email: str,
    subject: str,
    html_content: str,
    from_email: Optional[str] = None,
    from_name: Optional[str] = None
) -> tuple[bool, Optional[str]]:
    """
    Send an email via Gmail SMTP
    
    Args:
        to_email: Recipient email address
        subject: Email subject
        html_content: HTML content of the email
        from_email: Sender email (defaults to GMAIL_USER env var)
        from_name: Sender name (defaults to GMAIL_FROM_NAME env var)
    
    Returns:
        Tuple of (success: bool, error_message: Optional[str])
    """
    # Get Gmail credentials from environment variables
    gmail_user = os.getenv('GMAIL_USER', 'spliffan78@gmail.com')
    gmail_password = os.getenv('GMAIL_PASSWORD')  # App Password
    
    if not gmail_password:
        print("ERROR: GMAIL_PASSWORD not set in environment variables")
        print("ERROR: You need to set GMAIL_PASSWORD to your Gmail App Password")
        return False, "GMAIL_PASSWORD not configured"
    
    from_email = from_email or gmail_user
    from_name = from_name or os.getenv('GMAIL_FROM_NAME', 'MX Fantasy League')
    
    try:
        # Create message
        msg = MIMEMultipart('alternative')
        msg['Subject'] = subject
        msg['From'] = f"{from_name} <{from_email}>"
        msg['To'] = to_email
        
        # Add HTML content
        html_part = MIMEText(html_content, 'html', 'utf-8')
        msg.attach(html_part)
        
        # Connect to Gmail SMTP server
        print(f"DEBUG: Connecting to Gmail SMTP server...")
        server = smtplib.SMTP('smtp.gmail.com', 587)
        server.starttls()  # Enable encryption
        print(f"DEBUG: Logging in to Gmail...")
        server.login(gmail_user, gmail_password)
        
        # Send email
        print(f"DEBUG: Sending email to {to_email}...")
        text = msg.as_string()
        server.sendmail(from_email, to_email, text)
        server.quit()
        
        print(f"DEBUG: ✅ Email sent successfully to {to_email}")
        return True, None
        
    except smtplib.SMTPAuthenticationError as e:
        error_msg = f"Gmail authentication failed: {str(e)}"
        print(f"ERROR: {error_msg}")
        print(f"ERROR: Make sure you're using an App Password, not your regular Gmail password")
        return False, error_msg
    except smtplib.SMTPRecipientsRefused as e:
        error_msg = f"Recipient email rejected: {str(e)}"
        print(f"ERROR: {error_msg}")
        return False, error_msg
    except smtplib.SMTPSenderRefused as e:
        error_msg = f"Sender email rejected: {str(e)}"
        print(f"ERROR: {error_msg}")
        return False, error_msg
    except smtplib.SMTPDataError as e:
        error_msg = f"Gmail data error (possibly daily limit reached): {str(e)}"
        print(f"ERROR: {error_msg}")
        print(f"ERROR: Gmail free accounts have a limit of 500 emails per day")
        return False, error_msg
    except Exception as e:
        error_msg = f"Error sending email: {str(e)}"
        print(f"ERROR: {error_msg}")
        import traceback
        print(f"Traceback: {traceback.format_exc()}")
        return False, error_msg


def send_pick_reminder(
    user_email: str,
    user_name: str,
    competition_name: str,
    deadline_time: str,
    competition_url: str,
    base_url: Optional[str] = None,
    trackmap_url: Optional[str] = None,
    invite_url: Optional[str] = None,
) -> tuple[bool, Optional[str]]:
    """Send inviting picks-reminder email (dark gaming card style)."""
    html_content = build_pick_reminder_html(
        user_name=user_name,
        competition_name=competition_name,
        deadline_time=deadline_time,
        competition_url=competition_url,
        base_url=base_url,
        trackmap_url=trackmap_url,
        invite_url=invite_url,
    )
    subject = f"🏁 {competition_name} — dags att sätta picks"
    return send_email(user_email, subject, html_content)


def build_pick_reminder_html(
    *,
    user_name: str,
    competition_name: str,
    deadline_time: str,
    competition_url: str,
    base_url: Optional[str] = None,
    trackmap_url: Optional[str] = None,
    invite_url: Optional[str] = None,
) -> str:
    """HTML for picks-reminder email / admin preview (table layout for clients)."""
    safe_name = html.escape(user_name or "du")
    safe_comp = html.escape(competition_name or "nästa race")
    safe_deadline = html.escape(deadline_time or "")
    safe_picks_url = html.escape(competition_url or "", quote=True)
    safe_invite = html.escape(invite_url or "", quote=True) if invite_url else ""
    logo_url = f"{base_url}/static/images/mx_fantasy_logo.png" if base_url else ""
    safe_logo = html.escape(logo_url, quote=True) if logo_url else ""

    logo_block = (
        f'<img src="{safe_logo}" alt="MX Fantasy League" width="160" '
        f'style="display:block;margin:0 auto 10px;max-width:160px;height:auto;border:0;" />'
        if safe_logo
        else '<div style="font-size:40px;line-height:1;margin-bottom:8px;">🏁</div>'
    )

    hero_block = ""
    if trackmap_url:
        safe_map = html.escape(trackmap_url, quote=True)
        hero_block = f"""
          <tr>
            <td style="padding:0;line-height:0;font-size:0;">
              <img src="{safe_map}" alt="{safe_comp}" width="560"
                   style="display:block;width:100%;max-width:560px;height:auto;border:0;" />
            </td>
          </tr>
        """

    invite_block = ""
    if invite_url:
        invite_block = f"""
          <tr>
            <td style="padding:8px 28px 6px;">
              <table role="presentation" width="100%" cellpadding="0" cellspacing="0"
                     style="border-collapse:collapse;background:#0b1c2e;border:1px solid rgba(34,211,238,0.35);border-radius:14px;">
                <tr>
                  <td style="padding:18px 16px;text-align:center;">
                    <p style="margin:0 0 6px;font-size:11px;font-weight:800;letter-spacing:0.14em;text-transform:uppercase;color:#67e8f9;">
                      BJUD IN EN KOMPIS
                    </p>
                    <p style="margin:0 0 14px;font-size:14px;line-height:1.5;color:#cbd5e1;">
                      Tipsa någon — ju fler som spelar, desto hetare race.
                    </p>
                    <a href="{safe_invite}"
                       style="display:inline-block;background:transparent;color:#a5f3fc;padding:11px 22px;text-decoration:none;border-radius:999px;font-weight:700;font-size:13px;border:1px solid rgba(103,232,249,0.55);">
                      Dela din inbjudan →
                    </a>
                    <p style="margin:12px 0 0;font-size:11px;color:#64748b;word-break:break-all;line-height:1.4;">
                      {safe_invite}
                    </p>
                  </td>
                </tr>
              </table>
            </td>
          </tr>
        """

    footer_logo = (
        f'<img src="{safe_logo}" alt="" width="36" '
        f'style="display:inline-block;vertical-align:middle;margin-right:8px;border:0;" />'
        if safe_logo
        else ""
    )

    return f"""<!DOCTYPE html>
<html lang="sv">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>Picks-påminnelse</title>
</head>
<body style="margin:0;padding:0;background:#070b14;font-family:'Segoe UI',Arial,Helvetica,sans-serif;">
  <table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="border-collapse:collapse;background:#070b14;">
    <tr>
      <td align="center" style="padding:28px 14px;">
        <table role="presentation" width="560" cellpadding="0" cellspacing="0"
               style="border-collapse:collapse;width:100%;max-width:560px;background:#121820;border:1px solid #22d3ee;border-radius:18px;overflow:hidden;box-shadow:0 0 28px rgba(34,211,238,0.22);">
          {hero_block}
          <tr>
            <td align="center" style="padding:28px 24px 8px;background:#152033;">
              {logo_block}
              <p style="margin:0;font-size:18px;font-weight:800;letter-spacing:0.04em;color:#ffffff;">
                MX Fantasy League
              </p>
            </td>
          </tr>
          <tr>
            <td style="padding:18px 28px 8px;">
              <p style="margin:0 0 14px;font-size:28px;font-weight:800;font-style:italic;color:#ffffff;line-height:1.15;">
                Hej {safe_name}!
              </p>
              <p style="margin:0 0 18px;font-size:17px;line-height:1.55;color:#dbe4ee;">
                Det är dags att sätta dina picks för
                <strong style="color:#ffffff;">{safe_comp}!</strong>
              </p>
            </td>
          </tr>
          <tr>
            <td style="padding:0 28px 16px;">
              <table role="presentation" width="100%" cellpadding="0" cellspacing="0"
                     style="border-collapse:collapse;background:#083344;border:2px solid #22d3ee;border-radius:12px;">
                <tr>
                  <td style="padding:14px 16px;font-size:16px;font-weight:700;color:#67e8f9;text-align:center;">
                    ⏱&nbsp; Deadline:&nbsp;<span style="color:#ecfeff;">{safe_deadline}</span>
                  </td>
                </tr>
              </table>
            </td>
          </tr>
          <tr>
            <td style="padding:0 28px 10px;">
              <p style="margin:0;font-size:15px;line-height:1.55;color:#94a3b8;">
                Glöm inte att göra dina val innan tävlingen börjar!
              </p>
            </td>
          </tr>
          <tr>
            <td style="padding:10px 28px 6px;">
              <table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="border-collapse:collapse;">
                <tr>
                  <td width="44" valign="middle" style="font-size:28px;line-height:1;padding-right:10px;">🏆</td>
                  <td valign="middle" style="font-size:15px;line-height:1.45;color:#e2e8f0;font-weight:600;">
                    Tävla om exklusiva priser och visa att du är bäst!
                  </td>
                </tr>
              </table>
            </td>
          </tr>
          <tr>
            <td align="center" style="padding:22px 28px 10px;">
              <a href="{safe_picks_url}"
                 style="display:inline-block;background:#22c55e;color:#052e16;padding:16px 36px;text-decoration:none;border-radius:999px;font-weight:900;font-size:16px;letter-spacing:0.06em;text-transform:uppercase;border:1px solid #86efac;">
                GÖR DINA PICKS NU 🏁
              </a>
            </td>
          </tr>
          {invite_block}
          <tr>
            <td style="padding:16px 28px 22px;">
              <table role="presentation" width="100%" cellpadding="0" cellspacing="0"
                     style="border-collapse:collapse;background:#0a1018;border:1px solid #1f2937;border-radius:12px;">
                <tr>
                  <td style="padding:14px 14px;">
                    <p style="margin:0 0 6px;font-size:12px;color:#94a3b8;">
                      Om knappen inte fungerar, kopiera denna länk:
                    </p>
                    <p style="margin:0;font-size:12px;color:#67e8f9;word-break:break-all;line-height:1.4;">
                      {safe_picks_url}
                    </p>
                  </td>
                </tr>
              </table>
            </td>
          </tr>
          <tr>
            <td align="center" style="padding:8px 24px 24px;border-top:1px solid #1e293b;">
              {footer_logo}
              <span style="display:inline-block;vertical-align:middle;font-size:12px;color:#64748b;">
                Hälsning från oss på MX Fantasy teamet
              </span>
            </td>
          </tr>
        </table>
      </td>
    </tr>
  </table>
</body>
</html>
"""


def send_admin_announcement(
    user_email: str,
    user_name: str,
    subject: str,
    message: str,
    base_url: Optional[str] = None,
) -> tuple[bool, Optional[str]]:
    """
    Send an admin announcement/update to a user.

    Args:
        user_email: User's email address
        user_name: User's display name or username
        subject: Email subject
        message: HTML message content
        base_url: Site base URL for logo image (e.g. https://example.com)
    """
    logo_url = f"{base_url}/static/images/mx_fantasy_logo.png" if base_url else None
    logo_html = f'<img src="{logo_url}" alt="MX Fantasy League" width="180" height="auto" style="display:block;margin:0 auto 12px;max-width:180px;height:auto;" />' if logo_url else '<div class="logo">🏁</div>'

    html_content = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <style>
            body {{ margin: 0; padding: 0; font-family: 'Segoe UI', system-ui, -apple-system, sans-serif; background: #0f172a; }}
            .wrapper {{ background: #0f172a; padding: 40px 24px; min-height: 100vh; }}
            .card {{ max-width: 560px; margin: 0 auto; border-radius: 20px; overflow: hidden; box-shadow: 0 25px 50px -12px rgba(0,0,0,0.4); border: 1px solid rgba(255,255,255,0.06); }}
            .header {{ background: linear-gradient(135deg, #1e3a5f 0%, #1e40af 50%, #2563eb 100%); color: #fff; padding: 40px 32px; text-align: center; }}
            .header h1 {{ margin: 0; font-size: 24px; font-weight: 700; letter-spacing: 0.02em; }}
            .header .logo {{ font-size: 32px; margin-bottom: 8px; }}
            .content {{ background: #1e293b; color: #e2e8f0; padding: 40px 36px; line-height: 1.7; }}
            .content h2 {{ margin: 0 0 28px; font-size: 22px; font-weight: 600; color: #fff; }}
            .content p {{ margin: 0 0 20px; font-size: 16px; color: #cbd5e1; }}
            .content .message {{ margin-top: 24px; }}
            .footer {{ background: #0f172a; color: #64748b; padding: 28px 36px; text-align: center; font-size: 13px; border-top: 1px solid #1e293b; }}
            .footer p {{ margin: 8px 0; color: #64748b; }}
        </style>
    </head>
    <body>
        <div class="wrapper">
            <div class="card">
                <div class="header">
                    {logo_html}
                    <h1>MX Fantasy League</h1>
                </div>
                <div class="content">
                    <h2>Hej {user_name}!</h2>
                    <div class="message">
                        {message}
                    </div>
                    <p style="margin-top: 28px; font-size: 15px; color: #cbd5e1;">
                        Hälsningar,<br>
                        MX Fantasy teamet
                    </p>
                </div>
                <div class="footer">
                    <p>Hälsning från oss på MX Fantasy teamet</p>
                </div>
            </div>
        </div>
    </body>
    </html>
    """

    return send_email(user_email, subject, html_content)


def send_password_reset_email(
    user_email: str,
    user_name: str,
    reset_url: str,
    base_url: Optional[str] = None,
) -> tuple[bool, Optional[str]]:
    """
    Send password reset link to user.

    Args:
        user_email: User's email address
        user_name: User's display name or username
        reset_url: Full URL to the reset page (with token)
        base_url: Site base URL for logo image
    """
    subject = "Återställ ditt lösenord – MX Fantasy League"
    logo_url = f"{base_url}/static/images/mx_fantasy_logo.png" if base_url else None
    logo_html = f'<img src="{logo_url}" alt="MX Fantasy League" width="180" height="auto" style="display:block;margin:0 auto 12px;max-width:180px;height:auto;" />' if logo_url else '<div class="logo">🏁</div>'

    html_content = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <style>
            body {{ margin: 0; padding: 0; font-family: 'Segoe UI', system-ui, -apple-system, sans-serif; background: #0f172a; }}
            .wrapper {{ background: #0f172a; padding: 40px 24px; min-height: 100vh; }}
            .card {{ max-width: 560px; margin: 0 auto; border-radius: 20px; overflow: hidden; box-shadow: 0 25px 50px -12px rgba(0,0,0,0.4); border: 1px solid rgba(255,255,255,0.06); }}
            .header {{ background: linear-gradient(135deg, #1e3a5f 0%, #1e40af 50%, #2563eb 100%); color: #fff; padding: 40px 32px; text-align: center; }}
            .header h1 {{ margin: 0; font-size: 24px; font-weight: 700; letter-spacing: 0.02em; }}
            .header .logo {{ font-size: 32px; margin-bottom: 8px; }}
            .content {{ background: #1e293b; color: #e2e8f0; padding: 40px 36px; line-height: 1.7; }}
            .content h2 {{ margin: 0 0 28px; font-size: 22px; font-weight: 600; color: #fff; }}
            .content p {{ margin: 0 0 20px; font-size: 16px; color: #cbd5e1; }}
            .cta-wrap {{ text-align: center; margin: 36px 0 28px; }}
            .cta {{ display: inline-block; background-color: #22c55e; background-image: linear-gradient(135deg, #4ade80 0%, #16a34a 100%); color: #0b1120 !important; padding: 16px 38px; text-decoration: none; border-radius: 9999px; font-weight: 800; font-size: 16px; letter-spacing: 0.08em; text-transform: uppercase; box-shadow: 0 0 24px rgba(34, 197, 94, 0.75); border: 1px solid rgba(34, 197, 94, 0.9); }}
            .fallback {{ margin-top: 28px; padding-top: 24px; border-top: 1px solid #334155; font-size: 12px; color: #64748b; word-break: break-all; }}
            .footer {{ background: #0f172a; color: #64748b; padding: 28px 36px; text-align: center; font-size: 13px; border-top: 1px solid #1e293b; }}
            .footer p {{ margin: 8px 0; color: #64748b; }}
        </style>
    </head>
    <body>
        <div class="wrapper">
            <div class="card">
                <div class="header">
                    {logo_html}
                    <h1>MX Fantasy League</h1>
                </div>
                <div class="content">
                    <h2>Hej {user_name}!</h2>
                    <p>Du har begärt att återställa ditt lösenord. Klicka på knappen nedan för att välja ett nytt lösenord.</p>
                    <p><strong style="color:#94a3b8;">Länken gäller i 24 timmar.</strong></p>
                    <div class="cta-wrap">
                        <a href="{reset_url}" class="cta">Återställ lösenord</a>
                    </div>
                    <p class="fallback">Om knappen inte fungerar, kopiera denna länk:<br>{reset_url}</p>
                </div>
                <div class="footer">
                    <p>Hälsning från oss på MX Fantasy teamet</p>
                </div>
            </div>
        </div>
    </body>
    </html>
    """
    return send_email(user_email, subject, html_content)


def _pit_lane_email_shell(
    user_name: str,
    headline: str,
    body_html: str,
    cta_label: str,
    cta_url: str,
    base_url: Optional[str] = None,
) -> str:
    logo_url = f"{base_url}/static/images/mx_fantasy_logo.png" if base_url else None
    logo_html = (
        f'<img src="{logo_url}" alt="MX Fantasy League" width="160" style="display:block;margin:0 auto 10px;" />'
        if logo_url
        else '<div style="font-size:28px;margin-bottom:8px;">🏁</div>'
    )
    safe_name = html.escape(user_name)
    safe_headline = html.escape(headline)
    return f"""
    <!DOCTYPE html>
    <html>
    <head><meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1.0"></head>
    <body style="margin:0;padding:0;font-family:'Segoe UI',system-ui,sans-serif;background:#0f172a;">
        <div style="background:#0f172a;padding:32px 20px;">
            <div style="max-width:560px;margin:0 auto;border-radius:16px;overflow:hidden;border:1px solid #334155;">
                <div style="background:linear-gradient(135deg,#0e7490,#1e3a8a);padding:28px;text-align:center;color:#fff;">
                    {logo_html}
                    <h1 style="margin:0;font-size:20px;">Pit Lane</h1>
                </div>
                <div style="background:#1e293b;padding:28px;color:#e2e8f0;">
                    <p style="margin:0 0 16px;font-size:16px;">Hej {safe_name}!</p>
                    <p style="margin:0 0 20px;font-size:18px;font-weight:600;color:#fff;">{safe_headline}</p>
                    <div style="background:#0f172a;border-radius:12px;padding:16px;margin-bottom:24px;font-size:15px;line-height:1.6;color:#cbd5e1;">
                        {body_html}
                    </div>
                    <div style="text-align:center;">
                        <a href="{html.escape(cta_url)}" style="display:inline-block;background:#22d3ee;color:#0f172a;padding:14px 28px;border-radius:999px;font-weight:700;text-decoration:none;">{html.escape(cta_label)}</a>
                    </div>
                    <p style="margin:24px 0 0;font-size:12px;color:#64748b;word-break:break-all;">{html.escape(cta_url)}</p>
                </div>
            </div>
        </div>
    </body>
    </html>
    """


def send_pit_lane_dm_email(
    user_email: str,
    user_name: str,
    sender_name: str,
    message_preview: str,
    pit_lane_url: str,
    base_url: Optional[str] = None,
) -> tuple[bool, Optional[str]]:
    preview = html.escape((message_preview or "")[:500]).replace("\n", "<br>")
    body = f"<strong>{html.escape(sender_name)}</strong> skrev:<br><br>{preview}"
    html_content = _pit_lane_email_shell(
        user_name,
        "Du har fått ett nytt privat meddelande",
        body,
        "Öppna Pit Lane",
        pit_lane_url,
        base_url,
    )
    subject = f"💬 Nytt meddelande från {sender_name} — MX Fantasy"
    return send_email(user_email, subject, html_content)


def send_pit_lane_race_control_email(
    user_email: str,
    user_name: str,
    announcement_body: str,
    pit_lane_url: str,
    *,
    important: bool = False,
    base_url: Optional[str] = None,
) -> tuple[bool, Optional[str]]:
    body = html.escape((announcement_body or "")[:2000]).replace("\n", "<br>")
    html_content = _pit_lane_email_shell(
        user_name,
        "Nytt meddelande från Race Control",
        body,
        "Läs i Pit Lane",
        pit_lane_url,
        base_url,
    )
    prefix = "❗ " if important else "📢 "
    subject = f"{prefix}Race Control — MX Fantasy League"
    return send_email(user_email, subject, html_content)


def send_bulk_emails(emails: List[str], subject: str, html_content: str) -> dict:
    """Send emails to multiple recipients."""
    results = {"success": 0, "failed": 0}
    for email in emails:
        success, _error_msg = send_email(email, subject, html_content)
        if success:
            results["success"] += 1
        else:
            results["failed"] += 1
    return results

