from twilio.request_validator import RequestValidator

from app.config import settings


_validator = RequestValidator(settings.twilio_auth_token) if settings.twilio_auth_token else None


def verify_twilio_signature(url: str, post_data: dict, signature: str) -> bool:
    """
    Validate that an incoming request truly came from Twilio.

    `url` must be the FULL public URL Twilio called (e.g. ngrok HTTPS URL),
    not the internal localhost URL. Mismatch = signature fails.
    """
    if _validator is None:
        return False
    return _validator.validate(url, post_data, signature)
