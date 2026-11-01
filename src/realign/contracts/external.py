"""Public attribution and hash lineage for third-party physical recordings."""
from dataclasses import dataclass
from urllib.parse import urlparse


@dataclass(frozen=True)
class ExternalVideoSource:
    source_page_url: str
    original_video_url: str
    creator: str
    license_id: str
    license_url: str
    attribution: str
    original_sha256: str
    processed_sha256: str
    modifications: str
    physical_recording: bool
    capture_time_scale_verified: bool = False

    def __post_init__(self):
        for value in (self.source_page_url, self.original_video_url, self.license_url):
            u = urlparse(value)
            if u.scheme != 'https' or not u.netloc or u.username or u.password:
                raise ValueError('public HTTPS provenance URLs required')
        if self.license_id not in ('CC0-1.0', 'CC-BY-3.0', 'CC-BY-4.0', 'CC-BY-SA-3.0', 'CC-BY-SA-4.0'):
            raise ValueError('supported openly licensed source required')
        if any(len(s) != 64 or any(c not in '0123456789abcdef' for c in s) for s in (self.original_sha256, self.processed_sha256)):
            raise ValueError('original and processed content SHA-256 required')
        if not self.creator.strip() or not self.attribution.strip() or not self.modifications.strip():
            raise ValueError('creator, attribution and explicit modification history required')
        if self.physical_recording is not True or type(self.capture_time_scale_verified) is not bool:
            raise ValueError('REAL_EXTERNAL requires a physical recording, not a rendered animation')
