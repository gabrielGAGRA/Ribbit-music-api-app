Table plans {
  plan_id integer [pk, increment]
  name text [not null, unique]
  monthly_price real [not null]
  max_profiles integer [not null, default: 1]
}

Table users {
  user_id integer [pk, increment]
  email text [not null, unique]
  password_hash text [not null]
  spotify_id text [unique]
  display_name text [not null]
  age integer [not null]
  plan_id integer [not null, ref: > plans.plan_id]
  primary_account_id integer [ref: > users.user_id]
  blocked_genres text
  favorite_genres text
  preferred_theme text [not null, default: 'light']
  is_admin integer [not null, default: 0]
  created_at text [not null]
  birth_date text

  indexes {
    email [name: 'idx_users_email']
  }
}

Table tracks {
  track_id integer [pk, increment]
  spotify_id text
  title text [not null]
  artist text [not null]
  album text
  duration_seconds integer [not null]
  genre text [not null]
  country text
  release_year integer
  cover_url text
  itunes_preview_url text
  explicit integer [not null, default: 0]
  is_deleted integer [not null, default: 0]
  created_at text [not null]

  indexes {
    title [name: 'idx_tracks_title']
    artist [name: 'idx_tracks_artist']
    genre [name: 'idx_tracks_genre']
  }
}

Table interactions {
  interaction_id integer [pk, increment]
  user_id integer [not null, ref: > users.user_id]
  track_id integer [not null, ref: > tracks.track_id]
  action text [not null]
  created_at text [not null]
  source text
  jam_id integer [ref: > jams.jam_id]

  indexes {
    (user_id, track_id) [unique, name: 'uq_interactions_user_track']
  }
}

Table playlists {
  playlist_id integer [pk, increment]
  user_id integer [not null, ref: > users.user_id]
  name text [not null]
  description text
  spotify_playlist_id text
  is_exported integer [not null, default: 0]
  created_at text [not null]
  max_duration_seconds integer
  deck_filters text
  cover_image_url text
  source_playlist_id integer [ref: > playlists.playlist_id]
}

Table playlist_images {
  playlist_id integer [pk, ref: > playlists.playlist_id]
  content_type text [not null]
  image_data blob [not null]
  updated_at text [not null]
}

Table playlist_tracks {
  playlist_track_id integer [pk, increment]
  playlist_id integer [not null, ref: > playlists.playlist_id]
  track_id integer [not null, ref: > tracks.track_id]
  added_at text [not null]

  indexes {
    (playlist_id, track_id) [unique, name: 'uq_playlist_tracks_playlist_track']
  }
}

Table jams {
  jam_id integer [pk, increment]
  host_user_id integer [not null, ref: > users.user_id]
  room_name text [not null]
  room_code text [not null, unique]
  is_active integer [not null, default: 1]
  current_track_id integer [ref: > tracks.track_id]
  created_at text [not null]
  duration_minutes integer [not null, default: 60]
  max_superlikes integer [not null, default: 10]
  superlikes_used integer [not null, default: 0]
  skip_votes_threshold integer [not null, default: 3]
  accumulated_duration_seconds integer [not null, default: 0]
  deck_source text [not null, default: 'livre']
  source_playlist_id integer [ref: > playlists.playlist_id]
}

Table jam_queue_items {
  jam_queue_id integer [pk, increment]
  jam_id integer [not null, ref: > jams.jam_id]
  track_id integer [not null, ref: > tracks.track_id]
  vote_points integer [not null, default: 0]
  added_at text [not null]

  indexes {
    (jam_id, track_id) [unique, name: 'uq_jam_queue_items_jam_track']
  }
}

Table jam_participants {
  jam_id integer [not null, ref: > jams.jam_id]
  user_id integer [not null, ref: > users.user_id]
  joined_at text [not null]

  indexes {
    (jam_id, user_id) [pk]
  }
}

Table jam_skip_votes {
  jam_id integer [not null, ref: > jams.jam_id]
  track_id integer [not null, ref: > tracks.track_id]
  user_id integer [not null, ref: > users.user_id]
  voted_at text [not null]

  indexes {
    (jam_id, track_id, user_id) [pk]
  }
}

Table reviews {
  review_id integer [pk, increment]
  user_id integer [not null, ref: > users.user_id]
  track_id integer [not null, ref: > tracks.track_id]
  rating integer [not null]
  text text
  likes_count integer [not null, default: 0]
  is_deleted integer [not null, default: 0]
  created_at text [not null]

  indexes {
    track_id [name: 'idx_reviews_track_id']
    (user_id, track_id) [unique, name: 'idx_reviews_active_user_track', note: 'Índice único parcial: aplica quando is_deleted = 0']
  }
}

Table review_likes {
  review_id integer [not null, ref: > reviews.review_id]
  user_id integer [not null, ref: > users.user_id]
  created_at text [not null]

  indexes {
    (review_id, user_id) [pk]
  }
}

Table audit_logs {
  log_id integer [pk, increment]
  event text [not null]
  status text [not null]
  created_at text [not null]
}