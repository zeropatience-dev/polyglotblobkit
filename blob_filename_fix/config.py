"""Versioned configuration shared with the browser; server owns the policy."""
import json
from dataclasses import dataclass, field
from pathlib import Path

MAX_CONFIG_MB = 9_007_199_254  # decimal MB, within JS safe integer bytes

@dataclass(frozen=True)
class Modules:
    ui_limiter: bool = True
    backend_limiter: bool = True
    legacy_support: bool = True

    def __post_init__(self):
        if any(type(v) is not bool for v in vars(self).values()):
            raise ValueError('Module flags must be booleans')

@dataclass(frozen=True)
class Config:
    version: int = 1
    max_upload_mb: int = 50
    locale: str = 'en'
    modules: Modules = field(default_factory=Modules)

    def __post_init__(self):
        if type(self.version) is not int or self.version != 1:
            raise ValueError('Unsupported configuration version')
        if type(self.max_upload_mb) is not int or not 1 <= self.max_upload_mb <= MAX_CONFIG_MB:
            raise ValueError('max_upload_mb must be a positive safe integer in MB')
        if not isinstance(self.locale, str) or not self.locale.strip():
            raise ValueError('locale must be a non-empty string')
        if not isinstance(self.modules, Modules):
            raise ValueError('modules must be Modules')

    @classmethod
    def from_dict(cls, data):
        if not isinstance(data, dict) or set(data) - {'version','max_upload_mb','locale','modules'}:
            raise ValueError('Invalid configuration fields')
        modules = data.get('modules', {})
        if not isinstance(modules, dict) or set(modules) - {'ui_limiter','backend_limiter','legacy_support'}:
            raise ValueError('Invalid module fields')
        return cls(**{k:v for k,v in data.items() if k != 'modules'}, modules=Modules(**modules))

    @classmethod
    def load(cls, path: str | Path):
        return cls.from_dict(json.loads(Path(path).read_text(encoding='utf-8')))

    def browser_policy(self):
        """Publish only UI settings, not server module flags or credentials."""
        return {'version': self.version, 'max_upload_mb': self.max_upload_mb,
                'locale': self.locale, 'modules': {'ui_limiter': self.modules.ui_limiter}}
