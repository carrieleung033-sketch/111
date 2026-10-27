"""Provider boundary for future paid integrations; no external API calls yet.

Adapters must submit only on explicit execution, return provider task IDs for
polling/recovery, and download verified output into the controlled media store.
"""
from dataclasses import dataclass
from typing import Protocol

@dataclass(frozen=True)
class GenerationRequest:
    script: str
    product: str
    language: str
    duration: int
    asset_ids: tuple[str, ...] = ()

@dataclass(frozen=True)
class GenerationResult:
    status: str  # pending, running, succeeded, failed
    media_id: str | None = None
    error: str | None = None

class VideoProvider(Protocol):
    def submit(self, request: GenerationRequest) -> str: ...
    def poll(self, provider_task_id: str) -> GenerationResult: ...

# Populate only after implementing and validating the vendor-specific adapter.
# Keys: product / avatar. Never treat an API key alone as readiness.
VIDEO_PROVIDERS: dict[str, VideoProvider] = {}

MISSING_SERVICE = {
    'product': '尚未接入商品视频生成服务',
    'avatar': '尚未接入数字人服务',
    'reference': '参考已保存；待接入视频分析与生成服务。目标国家是创作设置，尚未验证参考视频的热度或所在市场。',
}
