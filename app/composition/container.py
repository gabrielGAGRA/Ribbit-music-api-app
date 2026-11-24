"""Dependency injection container and builder wiring application adapters and use cases."""

from dataclasses import dataclass, field
from typing import Any
lazy import sqlite3

import niquests

from app.application.ports.repositories import (
    AuditLogRepositoryPort,
    InteractionRepositoryPort,
    JamRepositoryPort,
    PlanRepositoryPort,
    PlatformCostRepositoryPort,
    PlaylistRepositoryPort,
    ReviewRepositoryPort,
    TrackAccessRepositoryPort,
    TrackRepositoryPort,
    UserRepositoryPort,
)
from app.application.ports.services import (
    GoogleIdpVerifierPort,
    GoogleOAuthPort,
    PasswordHasherPort,
    PlaylistExportPort,
    PlaylistSourcePort,
    SpotifyUserProfilePort,
    TokenServicePort,
    TrackCatalogFilePort,
    TrackCatalogPort,
    TrackPreviewPort,
)
from app.application.use_cases.admin import (
    BlockTrackUseCase,
    CompactCatalogUseCase,
    CreateTrackUseCase,
    GetAudienceReportUseCase,
    GetAuditLogsUseCase,
    GetExecutiveDashboardUseCase,
    GetPlatformCostsUseCase,
    GetTopModerationReviewsUseCase,
    IngestTracksFromCatalogUseCase,
    ListAdminAccessHistoryUseCase,
    ListAdminCatalogTracksUseCase,
    ListAdministratorsUseCase,
    ListBlockedTracksUseCase,
    ListUsersWithPlansUseCase,
    PromoteUserToAdminUseCase,
    RegisterAdministratorUseCase,
    SyncCatalogVersionUseCase,
    UpdateAdminRoleUseCase,
    UpdatePlatformCostsUseCase,
    UpdateSubscriptionPlanUseCase,
    UpdateTrackExplicitFlagUseCase,
    UpdateTrackGenreUseCase,
)
from app.application.use_cases.auth import (
    AuthenticateAdminUseCase,
    AuthenticateUserUseCase,
    AuthenticateWithGoogleUseCase,
    CompleteGoogleOAuthUseCase,
    GetGoogleAuthorizeUrlUseCase,
    RegisterUserUseCase,
)
from app.application.use_cases.discovery import (
    GetNextDiscoveryTrackUseCase,
    RecordSwipeInteractionUseCase,
    RecordTrackAccessUseCase,
    UndoLatestDiscoveryInteractionUseCase,
)
from app.application.use_cases.jam import (
    AdvanceJamPlaybackUseCase,
    CloseJamUseCase,
    CreateJamUseCase,
    GetJamDeckUseCase,
    GetJamStateUseCase,
    JoinJamUseCase,
    SaveQueueTrackUseCase,
    VoteJamTrackUseCase,
    VoteSkipJamTrackUseCase,
)
from app.application.use_cases.playlist import (
    AddTrackToPlaylistUseCase,
    CreateDeckPlaylistUseCase,
    DeletePlaylistUseCase,
    ExportPlaylistToSpotifyUseCase,
    GetPlaylistCoverUseCase,
    GetPlaylistDeckUseCase,
    ListUserPlaylistsUseCase,
    RemoveTrackFromPlaylistUseCase,
    UploadPlaylistCoverUseCase,
)
from app.application.use_cases.review import (
    DeleteReviewUseCase,
    GetCommunityFeedUseCase,
    GetRecentlyInteractedTracksUseCase,
    GetTrackReviewsUseCase,
    GetUserReviewsUseCase,
    LikeReviewCommentUseCase,
    PublishReviewUseCase,
    SaveSearchTrackLikeUseCase,
    SearchTracksUseCase,
)
from app.application.use_cases.spotify import (
    ConnectSpotifyAccountUseCase,
    DisconnectSpotifyAccountUseCase,
    GetSpotifyAuthorizeUrlUseCase,
    SyncPlaylistFromSpotifyUseCase,
    SyncTracksFromSpotifyUseCase,
)
from app.application.use_cases.user import (
    AddFamilyMemberUseCase,
    CancelSubscriptionPlanUseCase,
    ChangeSubscriptionPlanUseCase,
    ChangeTrackInteractionUseCase,
    DeleteUserAccountUseCase,
    GetAnnualListeningStatsUseCase,
    GetPreferredThemeUseCase,
    GetUserProfileUseCase,
    LinkSpotifyAccountUseCase,
    ListBlockedGenresUseCase,
    ListFamilyMembersUseCase,
    ListFavoriteGenresUseCase,
    ListPlansUseCase,
    ListUserAccessHistoryUseCase,
    ListUserInteractionsUseCase,
    RemoveFamilyMemberUseCase,
    UpdateBlockedGenresUseCase,
    UpdateFavoriteGenresUseCase,
    UpdatePreferredThemeUseCase,
    UpdateProfileUseCase,
)
from app.infrastructure.adapters import (
    GCSTrackCatalogAdapter,
    ITunesAdapter,
    SpotifyAdapter,
)
from app.infrastructure.adapters.google_auth_adapter import (
    GoogleIdpVerifierAdapter,
    GoogleOAuthAdapter,
)
from app.infrastructure.adapters.spotify import SpotifyCredentials
from app.infrastructure.adapters.spotify.auth import SpotifyAuth
from app.infrastructure.adapters.spotify.user_profile import SpotifyUserProfileAdapter
from app.infrastructure.repositories import (
    SQLiteAuditLogRepository,
    SQLiteInteractionRepository,
    SQLiteJamRepository,
    SQLitePlanRepository,
    SQLitePlatformCostRepository,
    SQLitePlaylistRepository,
    SQLiteReviewRepository,
    SQLiteTrackAccessRepository,
    SQLiteTrackRepository,
    SQLiteUserRepository,
    SQLiteUserStatsRepository,
    create_connection,
)
from app.infrastructure.security import HMACTokenService, PBKDF2PasswordHasher
lazy from app.config import Settings


@dataclass(slots=True, kw_only=True)
class Container:
    """Dependency injection container holding application adapters and use cases."""

    settings: Settings
    connection: sqlite3.Connection
    http_session: niquests.Session
    password_hasher: PBKDF2PasswordHasher
    token_service: HMACTokenService
    preview_service: ITunesAdapter
    music_service: SpotifyAdapter
    user_repo: SQLiteUserRepository
    plan_repo: SQLitePlanRepository
    track_repo: SQLiteTrackRepository
    playlist_repo: SQLitePlaylistRepository
    interaction_repo: SQLiteInteractionRepository
    jam_repo: SQLiteJamRepository
    review_repo: SQLiteReviewRepository
    audit_log_repo: SQLiteAuditLogRepository
    track_access_repo: SQLiteTrackAccessRepository
    platform_cost_repo: SQLitePlatformCostRepository
    google_verifier: GoogleIdpVerifierPort
    google_oauth: GoogleOAuthPort | None = None
    spotify_user_profile: SpotifyUserProfilePort
    # Auth
    authenticate_with_google_use_case: AuthenticateWithGoogleUseCase
    get_google_authorize_url_use_case: GetGoogleAuthorizeUrlUseCase | None = None
    complete_google_oauth_use_case: CompleteGoogleOAuthUseCase | None = None
    register_user_use_case: RegisterUserUseCase
    authenticate_user_use_case: AuthenticateUserUseCase
    authenticate_admin_use_case: AuthenticateAdminUseCase
    # Discovery
    get_next_discovery_track_use_case: GetNextDiscoveryTrackUseCase
    record_swipe_interaction_use_case: RecordSwipeInteractionUseCase
    record_track_access_use_case: RecordTrackAccessUseCase
    undo_latest_discovery_interaction_use_case: UndoLatestDiscoveryInteractionUseCase
    # Playlist
    create_deck_playlist_use_case: CreateDeckPlaylistUseCase
    get_playlist_deck_use_case: GetPlaylistDeckUseCase
    add_track_to_playlist_use_case: AddTrackToPlaylistUseCase
    remove_track_from_playlist_use_case: RemoveTrackFromPlaylistUseCase
    delete_playlist_use_case: DeletePlaylistUseCase
    export_playlist_to_spotify_use_case: ExportPlaylistToSpotifyUseCase
    list_user_playlists_use_case: ListUserPlaylistsUseCase
    upload_playlist_cover_use_case: UploadPlaylistCoverUseCase
    get_playlist_cover_use_case: GetPlaylistCoverUseCase
    # Jam
    create_jam_use_case: CreateJamUseCase
    join_jam_use_case: JoinJamUseCase
    get_jam_deck_use_case: GetJamDeckUseCase
    get_jam_state_use_case: GetJamStateUseCase
    vote_jam_track_use_case: VoteJamTrackUseCase
    vote_skip_jam_track_use_case: VoteSkipJamTrackUseCase
    advance_jam_playback_use_case: AdvanceJamPlaybackUseCase
    save_queue_track_use_case: SaveQueueTrackUseCase
    close_jam_use_case: CloseJamUseCase
    # Review
    search_tracks_use_case: SearchTracksUseCase
    publish_review_use_case: PublishReviewUseCase
    delete_review_use_case: DeleteReviewUseCase
    get_track_reviews_use_case: GetTrackReviewsUseCase
    get_user_reviews_use_case: GetUserReviewsUseCase
    get_community_feed_use_case: GetCommunityFeedUseCase
    like_review_comment_use_case: LikeReviewCommentUseCase
    get_recently_interacted_tracks_use_case: GetRecentlyInteractedTracksUseCase
    save_search_track_like_use_case: SaveSearchTrackLikeUseCase
    # User
    get_user_profile_use_case: GetUserProfileUseCase
    update_profile_use_case: UpdateProfileUseCase
    delete_user_account_use_case: DeleteUserAccountUseCase
    list_plans_use_case: ListPlansUseCase
    change_subscription_plan_use_case: ChangeSubscriptionPlanUseCase
    cancel_subscription_plan_use_case: CancelSubscriptionPlanUseCase
    add_family_member_use_case: AddFamilyMemberUseCase
    remove_family_member_use_case: RemoveFamilyMemberUseCase
    list_family_members_use_case: ListFamilyMembersUseCase
    list_blocked_genres_use_case: ListBlockedGenresUseCase
    update_blocked_genres_use_case: UpdateBlockedGenresUseCase
    list_favorite_genres_use_case: ListFavoriteGenresUseCase
    update_favorite_genres_use_case: UpdateFavoriteGenresUseCase
    get_preferred_theme_use_case: GetPreferredThemeUseCase
    update_preferred_theme_use_case: UpdatePreferredThemeUseCase
    list_user_interactions_use_case: ListUserInteractionsUseCase
    list_user_access_history_use_case: ListUserAccessHistoryUseCase
    change_track_interaction_use_case: ChangeTrackInteractionUseCase
    get_annual_listening_stats_use_case: GetAnnualListeningStatsUseCase
    link_spotify_account_use_case: LinkSpotifyAccountUseCase
    # Spotify
    get_spotify_authorize_url_use_case: GetSpotifyAuthorizeUrlUseCase | None = None
    connect_spotify_account_use_case: ConnectSpotifyAccountUseCase | None = None
    disconnect_spotify_account_use_case: DisconnectSpotifyAccountUseCase
    sync_tracks_from_spotify_use_case: SyncTracksFromSpotifyUseCase
    sync_playlist_from_spotify_use_case: SyncPlaylistFromSpotifyUseCase
    # Admin
    get_executive_dashboard_use_case: GetExecutiveDashboardUseCase
    list_users_with_plans_use_case: ListUsersWithPlansUseCase
    list_administrators_use_case: ListAdministratorsUseCase
    update_admin_role_use_case: UpdateAdminRoleUseCase
    update_subscription_plan_use_case: UpdateSubscriptionPlanUseCase
    update_track_explicit_flag_use_case: UpdateTrackExplicitFlagUseCase
    update_track_genre_use_case: UpdateTrackGenreUseCase
    block_track_use_case: BlockTrackUseCase
    list_blocked_tracks_use_case: ListBlockedTracksUseCase
    create_track_use_case: CreateTrackUseCase
    list_admin_catalog_tracks_use_case: ListAdminCatalogTracksUseCase
    get_top_moderation_reviews_use_case: GetTopModerationReviewsUseCase
    get_audience_report_use_case: GetAudienceReportUseCase
    get_audit_logs_use_case: GetAuditLogsUseCase
    promote_user_to_admin_use_case: PromoteUserToAdminUseCase
    register_administrator_use_case: RegisterAdministratorUseCase
    list_admin_access_history_use_case: ListAdminAccessHistoryUseCase
    get_platform_costs_use_case: GetPlatformCostsUseCase
    update_platform_costs_use_case: UpdatePlatformCostsUseCase
    catalog_file_port: TrackCatalogFilePort | None = None
    ingest_tracks_from_catalog_use_case: IngestTracksFromCatalogUseCase | None = None
    compact_catalog_use_case: CompactCatalogUseCase | None = None
    sync_catalog_version_use_case: SyncCatalogVersionUseCase | None = None
    _type_registry: dict[type, Any] = field(
        default_factory=dict, init=False, repr=False
    )

    def __post_init__(self) -> None:
        registry: dict[type, Any] = {}
        for field_name in self.__dataclass_fields__:
            if field_name.startswith("_"):
                continue
            val = getattr(self, field_name)
            if val is not None:
                registry[type(val)] = val

        # Register interface protocols explicitly
        registry[TokenServicePort] = self.token_service
        registry[GoogleIdpVerifierPort] = self.google_verifier
        registry[SpotifyUserProfilePort] = self.spotify_user_profile
        registry[TrackPreviewPort] = self.preview_service
        registry[TrackCatalogPort] = self.music_service
        registry[PlaylistExportPort] = self.music_service
        registry[PlaylistSourcePort] = self.music_service
        registry[PasswordHasherPort] = self.password_hasher
        registry[UserRepositoryPort] = self.user_repo
        registry[PlanRepositoryPort] = self.plan_repo
        registry[TrackRepositoryPort] = self.track_repo
        registry[PlaylistRepositoryPort] = self.playlist_repo
        registry[InteractionRepositoryPort] = self.interaction_repo
        registry[JamRepositoryPort] = self.jam_repo
        registry[ReviewRepositoryPort] = self.review_repo
        registry[AuditLogRepositoryPort] = self.audit_log_repo
        registry[TrackAccessRepositoryPort] = self.track_access_repo
        registry[PlatformCostRepositoryPort] = self.platform_cost_repo

        optional_mappings: tuple[tuple[type, Any], ...] = (
            (GoogleOAuthPort, self.google_oauth),
            (GetGoogleAuthorizeUrlUseCase, self.get_google_authorize_url_use_case),
            (CompleteGoogleOAuthUseCase, self.complete_google_oauth_use_case),
            (
                GetSpotifyAuthorizeUrlUseCase,
                self.get_spotify_authorize_url_use_case,
            ),
            (
                ConnectSpotifyAccountUseCase,
                self.connect_spotify_account_use_case,
            ),
            (TrackCatalogFilePort, self.catalog_file_port),
            (
                IngestTracksFromCatalogUseCase,
                self.ingest_tracks_from_catalog_use_case,
            ),
            (CompactCatalogUseCase, self.compact_catalog_use_case),
            (SyncCatalogVersionUseCase, self.sync_catalog_version_use_case),
        )
        registry.update(
            {
                target_type: service
                for target_type, service in optional_mappings
                if service is not None
            }
        )

        object.__setattr__(self, "_type_registry", registry)

    def resolve[T](self, target_type: type[T]) -> T:
        """Resolves an application use case or adapter by type."""
        comp = self._type_registry.get(target_type)
        if comp is not None:
            return comp
        for candidate in self._type_registry.values():
            try:
                if isinstance(candidate, target_type):
                    return candidate
            except TypeError:
                continue
        raise KeyError(f"No component registered for type {target_type}")

    def resolve_optional[T](self, target_type: type[T]) -> T | None:
        """Resolves an application component by type, returning None if unconfigured."""
        try:
            return self.resolve(target_type)
        except KeyError:
            return None


def build_container(
    settings: Settings,
    connection: sqlite3.Connection | None = None,
) -> Container:
    """Builds and wires all application infrastructure and use cases into a Container."""
    conn = (
        connection
        if connection is not None
        else create_connection(settings.database_path)
    )
    http_session = niquests.Session()
    password_hasher = PBKDF2PasswordHasher(iterations=settings.password_hash_iterations)
    token_service = HMACTokenService(
        secret_key=settings.secret_key,
        expiration_seconds=settings.token_expiration_seconds,
    )
    preview_service = ITunesAdapter(session=http_session)
    spotify_credentials = (
        SpotifyCredentials(
            client_id=settings.spotify_client_id,
            client_secret=settings.spotify_client_secret,
        )
        if settings.spotify_client_id and settings.spotify_client_secret
        else None
    )
    music_service = SpotifyAdapter(spotify_credentials, session=http_session)

    user_repo = SQLiteUserRepository(conn)
    plan_repo = SQLitePlanRepository(conn)
    track_repo = SQLiteTrackRepository(conn)
    playlist_repo = SQLitePlaylistRepository(conn)
    interaction_repo = SQLiteInteractionRepository(conn)
    jam_repo = SQLiteJamRepository(conn)
    review_repo = SQLiteReviewRepository(conn)
    audit_log_repo = SQLiteAuditLogRepository(conn)
    track_access_repo = SQLiteTrackAccessRepository(conn)
    platform_cost_repo = SQLitePlatformCostRepository(conn)

    catalog_adapter = (
        GCSTrackCatalogAdapter(
            bucket_name=settings.gcs_bucket_name,
            file_path=settings.gcs_tracks_file_path,
            max_tracks=settings.gcs_max_ingest_tracks,
        )
        if settings.gcs_bucket_name
        else None
    )
    ingest_tracks_use_case = (
        IngestTracksFromCatalogUseCase(
            track_repo=track_repo,
            catalog_file_port=catalog_adapter,
        )
        if catalog_adapter is not None
        else None
    )
    compact_catalog_use_case = (
        CompactCatalogUseCase(
            catalog_file_port=catalog_adapter,
            audit_log_repo=audit_log_repo,
        )
        if catalog_adapter is not None
        else None
    )
    sync_catalog_version_use_case = (
        SyncCatalogVersionUseCase(
            catalog_file_port=catalog_adapter,
            ingest_use_case=ingest_tracks_use_case,
            audit_log_repo=audit_log_repo,
        )
        if catalog_adapter is not None and ingest_tracks_use_case is not None
        else None
    )

    google_verifier = GoogleIdpVerifierAdapter(
        expected_client_id=settings.google_client_id,
        session=http_session,
    )
    google_oauth = (
        GoogleOAuthAdapter(
            client_id=settings.google_client_id,
            client_secret=settings.google_client_secret,
            redirect_uri=settings.google_redirect_uri,
            auth_uri=settings.google_auth_uri,
            token_uri=settings.google_token_uri,
            session=http_session,
        )
        if (
            settings.google_client_id
            and settings.google_client_secret
            and settings.google_redirect_uri
        )
        else None
    )
    get_google_authorize_url_use_case = (
        GetGoogleAuthorizeUrlUseCase(oauth_port=google_oauth)
        if google_oauth is not None
        else None
    )
    authenticate_with_google_use_case = AuthenticateWithGoogleUseCase(
        user_repo=user_repo,
        token_service=token_service,
        google_verifier=google_verifier,
    )
    complete_google_oauth_use_case = (
        CompleteGoogleOAuthUseCase(
            oauth_port=google_oauth,
            authenticate_with_google_use_case=authenticate_with_google_use_case,
        )
        if google_oauth is not None
        else None
    )
    spotify_user_profile = SpotifyUserProfileAdapter(session=http_session)
    user_spotify_auth = (
        SpotifyAuth(
            SpotifyCredentials(
                client_id=settings.spotify_client_id,
                client_secret=settings.spotify_client_secret,
                redirect_uri=settings.spotify_redirect_uri,
            ),
            session=http_session,
        )
        if settings.spotify_client_id and settings.spotify_redirect_uri
        else None
    )
    get_spotify_authorize_url_use_case = (
        GetSpotifyAuthorizeUrlUseCase(spotify_auth=user_spotify_auth)
        if user_spotify_auth is not None
        else None
    )
    connect_spotify_account_use_case = (
        ConnectSpotifyAccountUseCase(
            user_repo=user_repo,
            spotify_auth=user_spotify_auth,
            spotify_profile=spotify_user_profile,
        )
        if user_spotify_auth is not None
        else None
    )
    user_stats_repo = SQLiteUserStatsRepository(conn)

    return Container(
        settings=settings,
        connection=conn,
        http_session=http_session,
        password_hasher=password_hasher,
        token_service=token_service,
        preview_service=preview_service,
        music_service=music_service,
        user_repo=user_repo,
        plan_repo=plan_repo,
        track_repo=track_repo,
        playlist_repo=playlist_repo,
        interaction_repo=interaction_repo,
        jam_repo=jam_repo,
        review_repo=review_repo,
        audit_log_repo=audit_log_repo,
        track_access_repo=track_access_repo,
        platform_cost_repo=platform_cost_repo,
        google_verifier=google_verifier,
        google_oauth=google_oauth,
        spotify_user_profile=spotify_user_profile,
        authenticate_with_google_use_case=authenticate_with_google_use_case,
        get_google_authorize_url_use_case=get_google_authorize_url_use_case,
        complete_google_oauth_use_case=complete_google_oauth_use_case,
        get_spotify_authorize_url_use_case=get_spotify_authorize_url_use_case,
        connect_spotify_account_use_case=connect_spotify_account_use_case,
        disconnect_spotify_account_use_case=DisconnectSpotifyAccountUseCase(
            user_repo=user_repo,
        ),
        # Auth
        register_user_use_case=RegisterUserUseCase(
            user_repo, plan_repo, password_hasher
        ),
        authenticate_user_use_case=AuthenticateUserUseCase(
            user_repo, password_hasher, token_service=token_service
        ),
        authenticate_admin_use_case=AuthenticateAdminUseCase(
            user_repo, password_hasher, token_service=token_service
        ),
        # Discovery
        get_next_discovery_track_use_case=GetNextDiscoveryTrackUseCase(
            user_repo,
            track_repo,
            interaction_repo,
            track_preview_port=preview_service,
            catalog_file_port=catalog_adapter,
        ),
        record_swipe_interaction_use_case=RecordSwipeInteractionUseCase(
            user_repo,
            track_repo,
            interaction_repo,
            track_access_repo=track_access_repo,
        ),
        record_track_access_use_case=RecordTrackAccessUseCase(
            user_repo, track_repo, track_access_repo
        ),
        undo_latest_discovery_interaction_use_case=UndoLatestDiscoveryInteractionUseCase(
            user_repo, plan_repo, interaction_repo
        ),
        # Playlist
        create_deck_playlist_use_case=CreateDeckPlaylistUseCase(
            user_repo, track_repo, playlist_repo
        ),
        get_playlist_deck_use_case=GetPlaylistDeckUseCase(
            user_repo, playlist_repo, track_repo, interaction_repo
        ),
        add_track_to_playlist_use_case=AddTrackToPlaylistUseCase(
            user_repo,
            track_repo,
            playlist_repo,
            interaction_repo=interaction_repo,
            track_access_repo=track_access_repo,
        ),
        remove_track_from_playlist_use_case=RemoveTrackFromPlaylistUseCase(
            user_repo, playlist_repo
        ),
        delete_playlist_use_case=DeletePlaylistUseCase(user_repo, playlist_repo),
        export_playlist_to_spotify_use_case=ExportPlaylistToSpotifyUseCase(
            user_repo,
            playlist_repo,
            music_service,
            track_catalog=music_service,
            track_repo=track_repo,
        ),
        list_user_playlists_use_case=ListUserPlaylistsUseCase(user_repo, playlist_repo),
        upload_playlist_cover_use_case=UploadPlaylistCoverUseCase(
            playlist_repo=playlist_repo
        ),
        get_playlist_cover_use_case=GetPlaylistCoverUseCase(
            playlist_repo=playlist_repo
        ),
        # Jam
        create_jam_use_case=CreateJamUseCase(
            jam_repo, user_repo, playlist_repo=playlist_repo
        ),
        join_jam_use_case=JoinJamUseCase(jam_repo, user_repo=user_repo),
        get_jam_deck_use_case=GetJamDeckUseCase(
            jam_repo,
            user_repo,
            track_repo,
            playlist_repo=playlist_repo,
            interaction_repo=interaction_repo,
        ),
        get_jam_state_use_case=GetJamStateUseCase(jam_repo, user_repo, track_repo),
        vote_jam_track_use_case=VoteJamTrackUseCase(
            jam_repo,
            user_repo,
            track_repo,
            interaction_repo=interaction_repo,
            track_access_repo=track_access_repo,
        ),
        vote_skip_jam_track_use_case=VoteSkipJamTrackUseCase(
            jam_repo, user_repo, track_repo
        ),
        advance_jam_playback_use_case=AdvanceJamPlaybackUseCase(
            jam_repo, track_repo=track_repo
        ),
        save_queue_track_use_case=SaveQueueTrackUseCase(
            jam_repo,
            user_repo,
            track_repo,
            interaction_repo,
            playlist_repo=playlist_repo,
            track_access_repo=track_access_repo,
        ),
        close_jam_use_case=CloseJamUseCase(jam_repo),
        # Review
        search_tracks_use_case=SearchTracksUseCase(
            user_repo,
            track_repo,
            music_service=music_service,
            track_preview_port=preview_service,
            catalog_file_port=catalog_adapter,
        ),
        publish_review_use_case=PublishReviewUseCase(
            user_repo, track_repo, review_repo
        ),
        delete_review_use_case=DeleteReviewUseCase(review_repo),
        get_track_reviews_use_case=GetTrackReviewsUseCase(track_repo, review_repo),
        get_user_reviews_use_case=GetUserReviewsUseCase(review_repo),
        get_community_feed_use_case=GetCommunityFeedUseCase(review_repo),
        like_review_comment_use_case=LikeReviewCommentUseCase(review_repo),
        get_recently_interacted_tracks_use_case=GetRecentlyInteractedTracksUseCase(
            user_repo, interaction_repo, track_repo
        ),
        save_search_track_like_use_case=SaveSearchTrackLikeUseCase(
            user_repo,
            track_repo,
            interaction_repo,
            playlist_repo=playlist_repo,
            track_access_repo=track_access_repo,
        ),
        # User
        get_user_profile_use_case=GetUserProfileUseCase(
            user_repo,
            plan_repo,
            interaction_repo=interaction_repo,
            track_repo=track_repo,
        ),
        list_user_access_history_use_case=ListUserAccessHistoryUseCase(
            user_repo, track_repo, track_access_repo
        ),
        update_profile_use_case=UpdateProfileUseCase(user_repo, password_hasher),
        delete_user_account_use_case=DeleteUserAccountUseCase(
            user_repo, plan_repo=plan_repo
        ),
        list_plans_use_case=ListPlansUseCase(plan_repo),
        change_subscription_plan_use_case=ChangeSubscriptionPlanUseCase(
            user_repo, plan_repo
        ),
        cancel_subscription_plan_use_case=CancelSubscriptionPlanUseCase(
            user_repo, plan_repo
        ),
        add_family_member_use_case=AddFamilyMemberUseCase(
            user_repo, plan_repo, password_hasher=password_hasher
        ),
        remove_family_member_use_case=RemoveFamilyMemberUseCase(user_repo, plan_repo),
        list_family_members_use_case=ListFamilyMembersUseCase(user_repo),
        list_blocked_genres_use_case=ListBlockedGenresUseCase(user_repo),
        update_blocked_genres_use_case=UpdateBlockedGenresUseCase(user_repo, plan_repo),
        list_favorite_genres_use_case=ListFavoriteGenresUseCase(user_repo),
        update_favorite_genres_use_case=UpdateFavoriteGenresUseCase(user_repo),
        get_preferred_theme_use_case=GetPreferredThemeUseCase(user_repo),
        update_preferred_theme_use_case=UpdatePreferredThemeUseCase(user_repo),
        list_user_interactions_use_case=ListUserInteractionsUseCase(
            user_repo, interaction_repo, track_repo
        ),
        change_track_interaction_use_case=ChangeTrackInteractionUseCase(
            user_repo, plan_repo, interaction_repo, track_repo=track_repo
        ),
        get_annual_listening_stats_use_case=GetAnnualListeningStatsUseCase(
            user_repo, plan_repo, user_stats_repo
        ),
        link_spotify_account_use_case=LinkSpotifyAccountUseCase(user_repo),
        # Spotify
        sync_tracks_from_spotify_use_case=SyncTracksFromSpotifyUseCase(
            music_service, track_repo
        ),
        sync_playlist_from_spotify_use_case=SyncPlaylistFromSpotifyUseCase(
            user_repo, track_repo, playlist_repo, music_service
        ),
        # Admin
        get_executive_dashboard_use_case=GetExecutiveDashboardUseCase(
            user_repo,
            plan_repo,
            track_repo=track_repo,
            cost_repo=platform_cost_repo,
        ),
        list_users_with_plans_use_case=ListUsersWithPlansUseCase(user_repo, plan_repo),
        list_administrators_use_case=ListAdministratorsUseCase(user_repo),
        update_admin_role_use_case=UpdateAdminRoleUseCase(
            user_repo=user_repo,
            eligible_emails=settings.admin_eligible_emails,
            audit_log_repo=audit_log_repo,
        ),
        register_administrator_use_case=RegisterAdministratorUseCase(
            user_repo=user_repo,
            plan_repo=plan_repo,
            password_hasher=password_hasher,
            audit_log_repo=audit_log_repo,
            eligible_emails=settings.admin_eligible_emails,
        ),
        update_subscription_plan_use_case=UpdateSubscriptionPlanUseCase(
            plan_repo, user_repo=user_repo
        ),
        update_track_explicit_flag_use_case=UpdateTrackExplicitFlagUseCase(
            track_repo=track_repo, catalog_file_port=catalog_adapter
        ),
        update_track_genre_use_case=UpdateTrackGenreUseCase(
            track_repo=track_repo, catalog_file_port=catalog_adapter
        ),
        block_track_use_case=BlockTrackUseCase(
            track_repo=track_repo, catalog_file_port=catalog_adapter
        ),
        list_blocked_tracks_use_case=ListBlockedTracksUseCase(track_repo),
        create_track_use_case=CreateTrackUseCase(
            track_repo=track_repo, catalog_file_port=catalog_adapter
        ),
        list_admin_catalog_tracks_use_case=ListAdminCatalogTracksUseCase(track_repo),
        get_top_moderation_reviews_use_case=GetTopModerationReviewsUseCase(review_repo),
        get_audience_report_use_case=GetAudienceReportUseCase(
            user_repo, track_repo, track_access_repo=track_access_repo
        ),
        get_audit_logs_use_case=GetAuditLogsUseCase(audit_log_repo),
        promote_user_to_admin_use_case=PromoteUserToAdminUseCase(user_repo),
        list_admin_access_history_use_case=ListAdminAccessHistoryUseCase(
            track_access_repo
        ),
        get_platform_costs_use_case=GetPlatformCostsUseCase(platform_cost_repo),
        update_platform_costs_use_case=UpdatePlatformCostsUseCase(platform_cost_repo),
        catalog_file_port=catalog_adapter,
        ingest_tracks_from_catalog_use_case=ingest_tracks_use_case,
        compact_catalog_use_case=compact_catalog_use_case,
        sync_catalog_version_use_case=sync_catalog_version_use_case,
    )


__all__ = ["Container", "build_container"]
