"""Unit tests for track access history use cases and interaction tracking."""

from datetime import UTC, datetime

import pytest

from app.application.dtos.discovery_dtos import RecordSwipeCommand
from app.application.dtos.playlist_dtos import AddTrackToPlaylistCommand
from app.application.use_cases.admin import ListAdminAccessHistoryUseCase
from app.application.use_cases.discovery import (
    RecordSwipeInteractionUseCase,
    RecordTrackAccessUseCase,
)
from app.application.use_cases.playlist import AddTrackToPlaylistUseCase
from app.application.use_cases.review import SaveSearchTrackLikeUseCase
from app.application.use_cases.user import (
    GetUserProfileUseCase,
    ListUserAccessHistoryUseCase,
)
from app.domain.exceptions import BusinessRuleViolationError, EntityNotFoundError
from app.domain.models.interaction import Interaction, InteractionAction
from app.domain.models.plan import Plan
from app.domain.models.playlist import Playlist
from app.domain.models.track import Track
from app.domain.models.track_access import TrackAccess
from app.domain.models.user import User
from app.infrastructure.repositories import (
    SQLiteInteractionRepository,
    SQLitePlanRepository,
    SQLitePlaylistRepository,
    SQLiteTrackAccessRepository,
    SQLiteTrackRepository,
    SQLiteUserRepository,
    create_connection,
)
from app.infrastructure.repositories.connection import transaction
from app.infrastructure.repositories.seed import migrate_additive_columns


def _setup_repos():
    conn = create_connection(":memory:")
    migrate_additive_columns(conn)
    user_repo = SQLiteUserRepository(conn)
    plan_repo = SQLitePlanRepository(conn)
    track_repo = SQLiteTrackRepository(conn)
    interaction_repo = SQLiteInteractionRepository(conn)
    playlist_repo = SQLitePlaylistRepository(conn)
    access_repo = SQLiteTrackAccessRepository(conn)

    plan = plan_repo.save(
        Plan(name="Free", initial_monthly_price=0.0, initial_max_profiles=1)
    )
    assert plan.plan_id is not None

    adult = user_repo.save(
        User(
            email="adult@example.com",
            password_hash="hash",
            display_name="Adult",
            age=25,
            plan_id=plan.plan_id,
        )
    )
    minor = user_repo.save(
        User(
            email="minor@example.com",
            password_hash="hash",
            display_name="Minor",
            age=15,
            plan_id=plan.plan_id,
        )
    )
    active_track = track_repo.save(
        Track(
            title="Active Song",
            artist="Artist A",
            duration_seconds=200,
            genre="Pop",
            explicit=False,
        )
    )
    explicit_track = track_repo.save(
        Track(
            title="Explicit Song",
            artist="Artist B",
            duration_seconds=210,
            genre="Hip Hop",
            explicit=True,
        )
    )
    deleted_track = track_repo.save(
        Track(
            title="Deleted Song",
            artist="Artist C",
            duration_seconds=180,
            genre="Rock",
            explicit=False,
        )
    )
    assert deleted_track.track_id is not None
    with transaction(conn) as cur:
        cur.execute(
            "UPDATE tracks SET is_deleted = 1 WHERE track_id = ?",
            (deleted_track.track_id,),
        )
    deleted_track_reloaded = track_repo.find_by_id(deleted_track.track_id)
    assert deleted_track_reloaded is not None

    return (
        conn,
        user_repo,
        plan_repo,
        track_repo,
        interaction_repo,
        playlist_repo,
        access_repo,
        adult,
        minor,
        active_track,
        explicit_track,
        deleted_track_reloaded,
    )


def test_record_track_access_validations_and_success() -> None:
    (
        conn,
        user_repo,
        _plan_repo,
        track_repo,
        _interaction_repo,
        _playlist_repo,
        access_repo,
        adult,
        minor,
        active_track,
        explicit_track,
        deleted_track,
    ) = _setup_repos()
    try:
        uc = RecordTrackAccessUseCase(user_repo, track_repo, access_repo)
        assert adult.user_id is not None
        assert minor.user_id is not None
        assert active_track.track_id is not None
        assert explicit_track.track_id is not None
        assert deleted_track.track_id is not None

        recorded = uc.execute(adult.user_id, active_track.track_id, "play")
        assert recorded.access_id is not None
        assert recorded.source == "play"

        with pytest.raises(BusinessRuleViolationError):
            uc.execute(adult.user_id, active_track.track_id, "invalid_source")

        with pytest.raises(EntityNotFoundError):
            uc.execute(99999, active_track.track_id, "play")

        with pytest.raises(EntityNotFoundError):
            uc.execute(adult.user_id, deleted_track.track_id, "play")

        with pytest.raises(BusinessRuleViolationError):
            uc.execute(minor.user_id, explicit_track.track_id, "play")
    finally:
        conn.close()


def test_list_user_and_admin_access_history_soft_delete_isolation() -> None:
    (
        conn,
        user_repo,
        _plan_repo,
        track_repo,
        interaction_repo,
        _playlist_repo,
        access_repo,
        adult,
        _minor,
        active_track,
        _explicit_track,
        deleted_track,
    ) = _setup_repos()
    try:
        assert adult.user_id is not None
        assert active_track.track_id is not None
        assert deleted_track.track_id is not None

        access_repo.record(
            TrackAccess(
                user_id=adult.user_id,
                track_id=active_track.track_id,
                source="details",
                accessed_at=datetime(2026, 2, 1, 10, 0, tzinfo=UTC),
            )
        )
        access_repo.record(
            TrackAccess(
                user_id=adult.user_id,
                track_id=deleted_track.track_id,
                source="play",
                accessed_at=datetime(2026, 2, 1, 11, 0, tzinfo=UTC),
            )
        )
        interaction_repo.save(
            Interaction(
                user_id=adult.user_id,
                track_id=deleted_track.track_id,
                action=InteractionAction.LIKE,
                source="discovery",
            )
        )

        user_uc = ListUserAccessHistoryUseCase(user_repo, track_repo, access_repo)
        user_res = user_uc.execute(adult.user_id)
        assert [item.track_id for item in user_res.items] == [active_track.track_id]
        assert user_res.seen_track_ids == [active_track.track_id]

        admin_uc = ListAdminAccessHistoryUseCase(access_repo)
        all_entries = admin_uc.execute()
        assert len(all_entries) == 2
        assert all_entries[0].track_id == deleted_track.track_id
        assert all_entries[0].track_is_deleted is True

        only_deleted_entries = admin_uc.execute(only_deleted=True)
        assert [e.track_id for e in only_deleted_entries] == [deleted_track.track_id]
    finally:
        conn.close()


def test_get_user_profile_filters_deleted_and_minor_restricted_interactions() -> None:
    (
        conn,
        user_repo,
        plan_repo,
        track_repo,
        interaction_repo,
        _playlist_repo,
        _access_repo,
        _adult,
        minor,
        active_track,
        explicit_track,
        deleted_track,
    ) = _setup_repos()
    try:
        assert minor.user_id is not None
        assert active_track.track_id is not None
        assert explicit_track.track_id is not None
        assert deleted_track.track_id is not None

        for tid in (
            active_track.track_id,
            explicit_track.track_id,
            deleted_track.track_id,
        ):
            interaction_repo.save(
                Interaction(
                    user_id=minor.user_id,
                    track_id=tid,
                    action=InteractionAction.LIKE,
                    source="discovery",
                )
            )

        profile_uc = GetUserProfileUseCase(
            user_repo,
            plan_repo,
            interaction_repo=interaction_repo,
            track_repo=track_repo,
        )
        profile = profile_uc.execute(minor.user_id)
        assert [i.track_id for i in profile.recent_interactions] == [
            active_track.track_id
        ]
    finally:
        conn.close()


def test_interaction_use_cases_record_track_access_sources() -> None:
    (
        conn,
        user_repo,
        _plan_repo,
        track_repo,
        interaction_repo,
        playlist_repo,
        access_repo,
        adult,
        _minor,
        active_track,
        _explicit_track,
        _deleted_track,
    ) = _setup_repos()
    try:
        assert adult.user_id is not None
        assert active_track.track_id is not None

        swipe_uc = RecordSwipeInteractionUseCase(
            user_repo, track_repo, interaction_repo, track_access_repo=access_repo
        )
        swipe_uc.execute(
            RecordSwipeCommand(
                user_id=adult.user_id, track_id=active_track.track_id, action="like"
            )
        )

        search_uc = SaveSearchTrackLikeUseCase(
            user_repo,
            track_repo,
            interaction_repo,
            playlist_repo=playlist_repo,
            track_access_repo=access_repo,
        )
        search_uc.execute(adult.user_id, active_track.track_id)

        pl = playlist_repo.save(Playlist(user_id=adult.user_id, name="Test PL"))
        assert pl.playlist_id is not None
        pl_uc = AddTrackToPlaylistUseCase(
            user_repo,
            track_repo,
            playlist_repo,
            interaction_repo=interaction_repo,
            track_access_repo=access_repo,
        )
        pl_uc.execute(
            AddTrackToPlaylistCommand(
                user_id=adult.user_id,
                playlist_id=pl.playlist_id,
                track_id=active_track.track_id,
            )
        )

        entries = access_repo.list_by_user(adult.user_id)
        sources = {e.source for e in entries}
        assert sources == {"swipe", "search", "playlist"}
    finally:
        conn.close()
