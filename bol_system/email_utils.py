"""
Email utilities for BOL notifications
"""
import logging
from django.core.mail import EmailMessage
from django.conf import settings
import requests

logger = logging.getLogger(__name__)


def send_bol_notification(bol, pdf_url):
    """
    Send BOL notification email to PrimeTrade recipients

    Args:
        bol: BOL model instance
        pdf_url: URL to the BOL PDF

    Returns:
        bool: True if email sent successfully, False otherwise
    """
    try:
        # Get email config from database
        from bol_system.models import EmailNotificationConfig
        config = EmailNotificationConfig.get_active()

        if not config:
            logger.info(f"Email notifications disabled or not configured - skipping for BOL {bol.bol_number}")
            return True  # Not an error, just disabled

        to_email = config.get_to_list()
        cc_emails = config.get_cc_list()

        if not to_email:
            logger.warning(f"No TO recipients configured - skipping email for BOL {bol.bol_number}")
            return True

        # Email subject
        subject = f"New BOL: {bol.bol_number} - {bol.buyer_name}"

        # Email body
        body = f"""A new Bill of Lading has been created and is ready for shipment.

BOL Details:
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
BOL Number:      {bol.bol_number}
Date:            {bol.date}
Customer:        {bol.buyer_name}
Product:         {bol.product_name}
Quantity:        {bol.net_tons} tons ({bol.net_tons * 2000:.0f} lbs)
Carrier:         {bol.carrier_name}
Truck #:         {bol.truck_number or 'N/A'}
Trailer #:       {bol.trailer_number or 'N/A'}
Customer PO:     {bol.customer_po or 'N/A'}

Ship To:
{bol.ship_to}

Special Instructions:
{bol.special_instructions or 'None'}

Notes:
{bol.notes or 'None'}
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

The BOL PDF is attached to this email and is also available at:
{pdf_url}

Created by: {bol.created_by_email}

---
This is an automated notification from PrimeTrade BOL System
"""

        # Create email message
        email = EmailMessage(
            subject=subject,
            body=body,
            from_email=settings.DEFAULT_FROM_EMAIL,
            to=to_email,
            cc=cc_emails,
            reply_to=[settings.DEFAULT_REPLY_TO_EMAIL],
        )

        # Attach PDF if URL is accessible
        try:
            # If it's an S3 URL, fetch and attach
            if pdf_url and (pdf_url.startswith('http://') or pdf_url.startswith('https://')):
                logger.info(f"Fetching PDF from {pdf_url} for email attachment")
                response = requests.get(pdf_url, timeout=30)
                if response.status_code == 200:
                    email.attach(
                        filename=f"{bol.bol_number}.pdf",
                        content=response.content,
                        mimetype='application/pdf'
                    )
                    logger.info(f"PDF attached to email for BOL {bol.bol_number}")
                else:
                    logger.warning(f"Could not fetch PDF from {pdf_url}: HTTP {response.status_code}")
            else:
                logger.warning(f"PDF URL not accessible for attachment: {pdf_url}")
        except Exception as e:
            logger.error(f"Error attaching PDF to email: {str(e)}")
            # Continue without attachment - email is still valuable

        # Send email
        email.send(fail_silently=False)

        logger.info(f"BOL notification email sent for {bol.bol_number} to {', '.join(to_email)} (CC: {', '.join(cc_emails)})")
        return True

    except Exception as e:
        logger.error(f"Failed to send BOL notification email for {bol.bol_number}: {str(e)}", exc_info=True)
        return False
