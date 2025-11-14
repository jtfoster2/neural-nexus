import os
from sendgrid import SendGridAPIClient
from sendgrid.helpers.mail import Mail
from langchain_core.tools import tool


@tool
def send_email(recipient_email: str, order_id: str, event_type: str, details: str) -> str:
    """
    Sends an automated email to a customer about an order event.

    This tool is used for transactional emails like order confirmations, shipping updates,
    or delivery notifications. The LLM agent will call this tool when a specific
    order event is detected in the conversation or system state.

    Args:
        recipient_email (str): The email address of the customer.
        order_id (str): The unique identifier for the order.
        event_type (str): The type of order event (e.g., 'Order Confirmation', 'Shipped', 'Delivered').
        details (str): Additional details about the event, such as a tracking number or a personalized message.
    """
    try:
        sg = SendGridAPIClient(os.environ.get('SENDGRID_API_KEY'))

        # Craft the email content
        subject = f"{event_type} for Order #{order_id}"
        html_content = f"""
        <h1>{event_type}</h1>
        <p>Dear Customer,</p>
        <p>This is an update regarding your order with ID **{order_id}**.</p>
        <p>Event: {event_type}</p>
        <p>Details: {details}</p>
        <p>Thank you for your business!</p>
        """

        message = Mail(
            from_email=os.environ.get(
                'SENDER_EMAIL', 'your_verified_sender@example.com'),
            to_emails=recipient_email,
            subject=subject,
            html_content=html_content
        )

        response = sg.send(message)
        if response.status_code == 202:
            return f"Successfully sent email for order {order_id} to {recipient_email}. Status: {response.status_code}"
        else:
            return f"Failed to send email. Status code: {response.status_code}. Response body: {response.body.decode('utf-8')}"
    except Exception as e:
        return f"An error occurred: {e}"