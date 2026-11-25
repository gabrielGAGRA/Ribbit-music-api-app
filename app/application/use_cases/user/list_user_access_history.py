"""Use case for listing a listener's active track access history and seen track IDs."""

from dataclasses import dataclass

from app.domain.exceptions import EntityNotFoundError
lazy from app.application.ports.repositories.track_access_repository import (
    TrackAccessRepositoryPort,
)
lazy from app.application.ports.repositories.track_repository import TrackRepositoryPort
lazy from app.application.ports.repositories.user_repository import UserRepositoryPort
lazy from app.domain.models.track_access import TrackAccessEntry


@dataclass(slots=True, frozen=True, kw_only=True)
class UserAccessHistoryResult:
    """Result containing active access history entries and distinct seen track IDs."""

    items: list[TrackAccessEntry]
    seen_track_ids: list[int]


@dataclass(slots=True, frozen=True)
class ListUserAccessHistoryUseCase:
    """Returns listener access history excluding soft-deleted and minor-restricted tracks."""

    user_repo: UserRepositoryPort
    track_repo: TrackRepositoryPort
    track_access_repo: TrackAccessRepositoryPort

    def execute(
        self,
        user_id: int,
        *,
        limit: int = 100,
        offset: int = 0,
    ) -> UserAccessHistoryResult:
        user = self.user_repo.find_by_id(user_id)
        if not user:
            raise EntityNotFoundError(f"User with ID {user_id} not found.")

        raw_entries = self.track_access_repo.list_by_user(
            user_id,
            include_deleted=False,
            limit=limit,
            offset=offset,
        )
        filtered_items: list[TrackAccessEntry] = []
        for entry in raw_entries:
            track = self.track_repo.find_by_id(entry.track_id)
            if (
                track is None
                or track.is_deleted
                or user.is_track_restricted_for_minor(track)
            ):
                continue
            filtered_items.append(entry)

        seen_ids = self.track_access_repo.list_seen_track_ids(user_id)
        if user.is_minor():
            allowed_seen: list[int] = []
            for tid in seen_ids:
                track = self.track_repo.find_by_id(tid)
                if (
                    track is not None
                    and not track.is_deleted
                    and not user.is_track_restricted_for_minor(track)
                ):
                    allowed_seen.append(tid)
            seen_ids = allowed_seen

        return UserAccessHistoryResult(items=filtered_items, seen_track_ids=seen_ids)
