import secrets
import string


def generate_tracking_code():
    """
    Human-readable tracking code: KE-XXXXXX (6 uppercase alphanumeric chars).
    Short enough to read over the phone, unique enough for a single operator's volume.
    """
    chars = string.ascii_uppercase + string.digits
    suffix = ''.join(secrets.choice(chars) for _ in range(6))
    return f'KE-{suffix}'


def generate_qr_token():
    return secrets.token_urlsafe(32)