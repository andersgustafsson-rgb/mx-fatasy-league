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


def send_pick_reminder(user_email: str, user_name: str, competition_name: str, deadline_time: str, competition_url: str) -> tuple[bool, Optional[str]]:
    """
    Send a reminder email to a user about upcoming picks deadline
    
    Args:
        user_email: User's email address
        user_name: User's display name or username
        competition_name: Name of the competition
        deadline_time: When picks deadline is (formatted string)
        competition_url: URL to the picks page
    
    Returns:
        True if email was sent successfully, False otherwise
    """
    subject = f"⏰ Påminnelse: Sätt dina picks för {competition_name}"
    
    html_content = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="UTF-8">
        <style>
            body {{ font-family: Arial, sans-serif; line-height: 1.6; color: #333; }}
            .container {{ max-width: 600px; margin: 0 auto; padding: 20px; }}
            .header {{ background-color: #1e40af; color: white; padding: 20px; text-align: center; border-radius: 5px 5px 0 0; }}
            .content {{ background-color: #f9fafb; padding: 30px; border-radius: 0 0 5px 5px; }}
            .button {{ display: inline-block; background-color: #22c55e; color: white; padding: 12px 24px; text-decoration: none; border-radius: 5px; margin-top: 20px; }}
            .footer {{ text-align: center; margin-top: 30px; color: #6b7280; font-size: 12px; }}
        </style>
    </head>
    <body>
        <div class="container">
            <div class="header">
                <h1>🏁 MX Fantasy League</h1>
            </div>
            <div class="content">
                <h2>Hej {user_name}!</h2>
                <p>Det är dags att sätta dina picks för <strong>{competition_name}</strong>!</p>
                <p>⏰ <strong>Deadline:</strong> {deadline_time}</p>
                <p>Glöm inte att göra dina val innan tävlingen börjar!</p>
                <p style="text-align: center;">
                    <a href="{competition_url}" class="button">Gör dina picks nu →</a>
                </p>
                <p style="margin-top: 30px; color: #6b7280; font-size: 14px;">
                    Om knappen inte fungerar, kopiera denna länk: {competition_url}
                </p>
            </div>
            <div class="footer">
                <p>Detta är ett automatiskt meddelande från MX Fantasy League.</p>
                <p>Du får detta e-post eftersom du är registrerad i spelet.</p>
            </div>
        </div>
    </body>
    </html>
    """
    
    success, error_msg = send_email(user_email, subject, html_content)
    return success, error_msg


def send_admin_announcement(user_email: str, user_name: str, subject: str, message: str) -> tuple[bool, Optional[str]]:
    """
    Send an admin announcement/update to a user
    
    Args:
        user_email: User's email address
        user_name: User's display name or username
        subject: Email subject
        message: HTML message content
    
    Returns:
        True if email was sent successfully, False otherwise
    """
    html_content = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="UTF-8">
        <style>
            body {{ font-family: Arial, sans-serif; line-height: 1.6; color: #333; }}
            .container {{ max-width: 600px; margin: 0 auto; padding: 20px; }}
            .header {{ background-color: #1e40af; color: white; padding: 20px; text-align: center; border-radius: 5px 5px 0 0; }}
            .content {{ background-color: #f9fafb; padding: 30px; border-radius: 0 0 5px 5px; }}
            .footer {{ text-align: center; margin-top: 30px; color: #6b7280; font-size: 12px; }}
        </style>
    </head>
    <body>
        <div class="container">
            <div class="header">
                <h1>🏁 MX Fantasy League</h1>
            </div>
            <div class="content">
                <h2>Hej {user_name}!</h2>
                <div style="margin-top: 20px;">
                    {message}
                </div>
            </div>
            <div class="footer">
                <p>Detta är ett meddelande från MX Fantasy League.</p>
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
        if send_email(email, subject, html_content):
            results['success'] += 1
        else:
            results['failed'] += 1
    
    return results
