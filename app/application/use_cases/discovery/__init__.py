"""Discovery and swipe use cases."""

from app.application.use_cases.discovery.get_next_discovery_track import (
    GetNextDiscoveryTrackUseCase,
)
from app.application.use_cases.discovery.record_swipe_interaction import (
    RecordSwipeInteractionUseCase,
)

__all__ = [
    "GetNextDiscoveryTrackUseCase",
    "RecordSwipeInteractionUseCase",
]
