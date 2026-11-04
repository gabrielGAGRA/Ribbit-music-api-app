"""Discovery and swipe use cases."""

from app.application.use_cases.discovery.get_next_discovery_track import (
    GetNextDiscoveryTrackUseCase,
)
from app.application.use_cases.discovery.record_swipe_interaction import (
    RecordSwipeInteractionUseCase,
)
from app.application.use_cases.discovery.undo_latest_discovery_interaction import (
    UndoLatestDiscoveryInteractionUseCase,
)

__all__ = [
    "GetNextDiscoveryTrackUseCase",
    "RecordSwipeInteractionUseCase",
    "UndoLatestDiscoveryInteractionUseCase",
]
