"""
Email utilities for sending emails via Gmail SMTP
"""
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
) -> tuple[bool, Optional[str]]:
    """
    Send a reminder email to a user about upcoming picks deadline.

    Args:
        user_email: User's email address
        user_name: User's display name or username
        competition_name: Name of the competition
        deadline_time: When picks deadline is (formatted string)
        competition_url: URL to the picks page
        base_url: Site base URL for logo/trackmap images (e.g. https://example.com)
        trackmap_url: Full URL to current competition trackmap image (optional)
    """
    subject = f"⏰ Påminnelse: Sätt dina picks för {competition_name}"
    logo_url = f"{base_url}/static/images/mx_fantasy_logo.png" if base_url else None
    logo_html = f'<img src="{logo_url}" alt="MX Fantasy League" width="180" height="auto" style="display:block;margin:0 auto 12px;max-width:180px;height:auto;" />' if logo_url else '<div class="logo">🏁</div>'

    trackmap_html = ""
    if trackmap_url:
        trackmap_html = f"""
                    <div class="trackmap-section">
                        <p class="trackmap-label">Banan för denna tävling</p>
                        <img src="{trackmap_url}" alt="Trackmap {competition_name}" class="trackmap-img" />
                    </div>
        """

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
            .content p:last-of-type {{ margin-bottom: 0; }}
            .deadline-box {{ display: inline-block; background: rgba(251, 191, 36, 0.15); color: #fcd34d; padding: 12px 20px; border-radius: 12px; margin: 12px 0 28px; font-size: 15px; font-weight: 600; border: 1px solid rgba(251, 191, 36, 0.3); }}
            .trackmap-section {{ margin: 32px 0 36px; text-align: center; }}
            .trackmap-label {{ font-size: 14px; color: #94a3b8; margin-bottom: 12px; text-transform: uppercase; letter-spacing: 0.05em; }}
            .trackmap-img {{ max-width: 100%; height: auto; border-radius: 12px; border: 1px solid #334155; display: block; margin: 0 auto; }}
            .cta-wrap {{ text-align: center; margin: 36px 0 28px; }}
            .cta {{ display: inline-block; background: linear-gradient(180deg, #34d399 0%, #10b981 100%); color: #fff !important; padding: 16px 32px; text-decoration: none; border-radius: 12px; font-weight: 700; font-size: 16px; letter-spacing: 0.02em; box-shadow: 0 4px 14px rgba(16, 185, 129, 0.4); }}
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
                    <p>Det är dags att sätta dina picks för <strong style="color:#fff;">{competition_name}</strong>!</p>
                    <div class="deadline-box">⏰ Deadline: {deadline_time}</div>
                    <p>Glöm inte att göra dina val innan tävlingen börjar!</p>
                    {trackmap_html}
                    <div class="cta-wrap">
                        <a href="{competition_url}" class="cta">Gör dina picks nu →</a>
                    </div>
                    <p class="fallback">Om knappen inte fungerar, kopiera denna länk:<br>{competition_url}</p>
                </div>
                <div class="footer">
                    <p>Hälsning från oss på MX Fantasy teamet</p>
                </div>
            </div>
        </div>
    </body>
    </html>
    """

    success, error_msg = send_email(user_email, subject, html_content)
    return success, error_msg


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


def send_bulk_emails(emails: List[str], subject: str, html_content: str) -> dict:
    """
    Send emails to multiple recipients
    
    Args:
        emails: List of email addresses
        subject: Email subject
        html_content: HTML content of the email
    
    Returns:
        Dictionary with 'success' count and 'failed' count
    """
    results = {'success': 0, 'failed': 0}
    
    for email in emails:
        success, _error_msg = send_email(email, subject, html_content)
        if success:
            results['success'] += 1
        else:
            results['failed'] += 1
    
    return results
