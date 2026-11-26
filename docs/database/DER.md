# Diagrama Entidade-Relacionamento (DER)

O esquema relacional completo do SQLite está implementado em [`app/infrastructure/repositories/schema.sql`](../../app/infrastructure/repositories/schema.sql), documentado em DBML em [`DER.sql`](DER.sql) e nos módulos SQL em [`docs/database/`](./), sendo representado tanto pelo diagrama estático [`DER.png`](DER.png) quanto pelo diagrama Mermaid abaixo:

```mermaid
erDiagram
    plans {
        INTEGER plan_id PK
        TEXT name UK
        REAL monthly_price
        INTEGER max_profiles
    }

    users {
        INTEGER user_id PK
        TEXT email UK
        TEXT password_hash
        TEXT spotify_id UK
        INTEGER spotify_premium
        TEXT spotify_access_token
        TEXT spotify_refresh_token
        TEXT spotify_token_expires_at
        TEXT display_name
        INTEGER age
        INTEGER plan_id FK
        INTEGER primary_account_id FK
        TEXT blocked_genres
        TEXT favorite_genres
        TEXT preferred_theme
        INTEGER is_admin
        TEXT created_at
        TEXT birth_date
    }

    tracks {
        INTEGER track_id PK
        TEXT spotify_id
        TEXT title
        TEXT artist
        INTEGER duration_seconds
        TEXT genre
        TEXT country
        INTEGER release_year
        TEXT cover_url
        TEXT itunes_preview_url
        INTEGER explicit
        INTEGER is_deleted
        TEXT created_at
    }

    interactions {
        INTEGER interaction_id PK
        INTEGER user_id FK
        INTEGER track_id FK
        TEXT action
        TEXT created_at
        TEXT source
        INTEGER jam_id FK
    }

    playlists {
        INTEGER playlist_id PK
        INTEGER user_id FK
        TEXT name
        TEXT description
        TEXT spotify_playlist_id
        INTEGER is_exported
        TEXT created_at
        INTEGER max_duration_seconds
        TEXT deck_filters
        TEXT cover_image_url
        INTEGER source_playlist_id
    }

    playlist_images {
        INTEGER playlist_id PK,FK
        TEXT content_type
        BLOB image_data
        TEXT updated_at
    }

    playlist_tracks {
        INTEGER playlist_track_id PK
        INTEGER playlist_id FK
        INTEGER track_id FK
        TEXT added_at
    }

    jams {
        INTEGER jam_id PK
        INTEGER host_user_id FK
        TEXT room_name
        TEXT room_code UK
        INTEGER is_active
        INTEGER current_track_id FK
        TEXT created_at
        INTEGER duration_minutes
        INTEGER max_superlikes
        INTEGER superlikes_used
        INTEGER skip_votes_threshold
        INTEGER accumulated_duration_seconds
        TEXT deck_source
        INTEGER source_playlist_id
    }

    jam_queue_items {
        INTEGER jam_queue_id PK
        INTEGER jam_id FK
        INTEGER track_id FK
        INTEGER vote_points
        TEXT added_at
    }

    jam_participants {
        INTEGER jam_id PK,FK
        INTEGER user_id PK,FK
        TEXT joined_at
    }

    jam_skip_votes {
        INTEGER jam_id PK,FK
        INTEGER track_id PK,FK
        INTEGER user_id PK,FK
        TEXT voted_at
    }

    reviews {
        INTEGER review_id PK
        INTEGER user_id FK
        INTEGER track_id FK
        INTEGER rating
        TEXT text
        INTEGER likes_count
        INTEGER is_deleted
        TEXT created_at
    }

    review_likes {
        INTEGER review_id PK,FK
        INTEGER user_id PK,FK
        TEXT created_at
    }

    track_accesses {
        INTEGER access_id PK
        INTEGER user_id FK
        INTEGER track_id FK
        TEXT source
        TEXT accessed_at
    }

    audit_logs {
        INTEGER log_id PK
        TEXT event
        TEXT status
        TEXT created_at
    }

    platform_cost_settings {
        INTEGER settings_id PK
        REAL content_cost_per_track
        REAL infrastructure_fixed_cost
        REAL infrastructure_cost_per_user
        TEXT updated_at
    }

    plans ||--o{ users : "assina"
    users o|--o{ users : "titular_dependente"
    users ||--o{ playlists : "possui"
    playlists o|--o{ playlists : "origem"
    playlists ||--o| playlist_images : "capa"
    playlists ||--o{ playlist_tracks : "contem"
    tracks ||--o{ playlist_tracks : "integra"
    users ||--o{ interactions : "registra"
    tracks ||--o{ interactions : "recebe"
    jams o|--o{ interactions : "origem_jam"
    users ||--o{ jams : "hospeda"
    tracks o|--o{ jams : "toca_atual"
    playlists o|--o{ jams : "deck_base"
    jams ||--o{ jam_queue_items : "enfileira"
    tracks ||--o{ jam_queue_items : "na_fila"
    jams ||--o{ jam_participants : "participa"
    users ||--o{ jam_participants : "entra"
    jams ||--o{ jam_skip_votes : "voto_pulo"
    tracks ||--o{ jam_skip_votes : "pulada_em"
    users ||--o{ jam_skip_votes : "vota_pular"
    users ||--o{ reviews : "escreve"
    tracks ||--o{ reviews : "avaliada_em"
    reviews ||--o{ review_likes : "curtida_em"
    users ||--o{ review_likes : "curte_review"
    users ||--o{ track_accesses : "acessa"
    tracks ||--o{ track_accesses : "acessada_em"
```
