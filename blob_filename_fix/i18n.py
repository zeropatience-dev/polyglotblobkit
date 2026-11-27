"""Localization is presentation only; never changes filenames or validation."""
import json
from importlib.resources import files

_MESSAGES = json.loads(files(__package__).joinpath('messages.json').read_text(encoding='utf-8'))
SUPPORTED_LOCALES = tuple(_MESSAGES)


def resolve_locale(locale: str = 'en') -> str:
    base = locale.strip().lower().replace('_', '-').split('-')[0] if isinstance(locale, str) else ''
    return base if base in _MESSAGES else 'en'


def message(code: str, locale: str = 'en', *, limit: int | None = None) -> str:
    text = _MESSAGES[resolve_locale(locale)][code]
    if code == 'UPLOAD_TOO_LARGE':
        if type(limit) is not int or limit < 1:
            raise ValueError('A positive integer MB limit is required')
        return text.replace('{limit}', str(limit))
    return text
