import logging
from decouple import config

logger = logging.getLogger(__name__)

# Set AT_SMS_STUB=True in .env to skip real AT calls during development.
# Remove or set to False in production once AT credentials are confirmed working.
SMS_STUB = config('AT_SMS_STUB', default=True, cast=bool)


def send_sms(phone_number, message):
    if SMS_STUB:
        logger.info(f'[SMS STUB] To: {phone_number} | Message: {message}')
        return {'SMSMessageData': {'Message': 'Sent to 1/1 Total Cost: KES 0 (STUB)'}}

    import africastalking
    _initialize()
    sms = africastalking.SMS
    sender = config('AT_SENDER_ID', default=None) or None
    response = sms.send(message, [phone_number], sender_id=sender)
    return response


_initialized = False


def _initialize():
    global _initialized
    if not _initialized:
        import africastalking
        africastalking.initialize(
            username=config('AT_USERNAME'),
            api_key=config('AT_API_KEY'),
        )
        _initialized = True