"""
Email utilities for sending emails via SendGrid
"""
import os
from sendgrid import SendGridAPIClient
from sendgrid.helpers.mail import Mail
from typing import List, Optional


def send_email(
    to_email: str,
    subject: str,
    html_content: str,
    from_email: Optional[str] = None,
    from_name: Optional[str] = None
) -> bool:
    """
    Send an email via SendGrid
    
    Args:
        to_email: Recipient email address
        subject: Email subject
        html_content: HTML content of the email
        from_email: Sender email (defaults to SENDGRID_FROM_EMAIL env var)
        from_name: Sender name (defaults to SENDGRID_FROM_NAME env var)
    
    Returns:
        True if email was sent successfully, False otherwise
    """
    api_key = os.getenv('SENDGRID_API_KEY')
    if not api_key:
        print("ERROR: SENDGRID_API_KEY not set in environment variables")
        return False
    
    from_email = from_email or os.getenv('SENDGRID_FROM_EMAIL', 'spliffan78@gmail.com')
    from_name = from_name or os.getenv('SENDGRID_FROM_NAME', 'MX Fantasy League')
    
    message = Mail(
        from_email=(from_email, from_name),
        to_emails=to_email,
        subject=subject,
        html_content=html_content
    )
    
    try:
        sg = SendGridAPIClient(api_key)
        response = sg.send(message)
        if response.status_code in [200, 201, 202]:
            return True
        else:
            print(f"ERROR: SendGrid returned status code {response.status_code}")
            return False
    except Exception as e:
        print(f"ERROR sending email: {e}")
        return False


def send_pick_reminder(user_email: str, user_name: str, competition_name: str, deadline_time: str, competition_url: str) -> bool:
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
    
    return send_email(user_email, subject, html_content)


def send_admin_announcement(user_email: str, user_name: str, subject: str, message: str) -> bool:
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
