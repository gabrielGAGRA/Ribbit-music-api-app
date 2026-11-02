// https://dbdiagram.io/d/Diagrama-Entidade-Relacionamento-6acbd98250a8c6fc36259a47
// RIBBIT PLATFORM - SCHEMA UNIFICADO (9 TABELAS)

Table planos {
  plano_id int [pk, increment]
  nome varchar [not null, unique]
  preco_mensal decimal [not null]
  max_perfis int [not null, default: 1]
}

Table usuarios {
  usuario_id int [pk, increment]
  email varchar [not null, unique]
  senha_hash varchar [not null]
  spotify_id varchar [unique]
  nome_exibicao varchar [not null]
  idade int [not null]
  plano_id int [not null, ref: > planos.plano_id]
  titular_id int [ref: >? usuarios.usuario_id] // Auto-relacionamento para Plano Família
  generos_bloqueados text
  is_admin boolean [not null, default: false]
  criado_em timestamp [default: `CURRENT_TIMESTAMP`]
}

Table musicas {
  musica_id int [pk, increment]
  spotify_id varchar
  titulo varchar [not null]
  artista varchar [not null]
  album varchar
  duracao_segundos int [not null]
  genero varchar [not null]
  pais varchar
  ano_lancamento int
  capa_url text
  itunes_preview_url text
  is_deleted boolean [not null, default: false]
}

Table interacoes {
  Interaction_id int [pk, increment]
  usuario_id int [not null, ref: > usuarios.usuario_id]
  musica_id int [not null, ref: > musicas.musica_id]
  acao varchar [not null]
  criado_em timestamp [default: `CURRENT_TIMESTAMP`]

  indexes {
    (usuario_id, musica_id) [unique]
  }
}

Table playlists {
  playlist_id int [pk, increment]
  usuario_id int [not null, ref: > usuarios.usuario_id]
  nome varchar [not null]
  descricao text
  spotify_playlist_id varchar
  is_exportada boolean [default: false]
  criado_em timestamp [default: `CURRENT_TIMESTAMP`]
}

Table playlist_musicas {
  playlist_musica_id int [pk, increment]
  playlist_id int [not null, ref: > playlists.playlist_id]
  musica_id int [not null, ref: > musicas.musica_id]
  adicionado_em timestamp [default: `CURRENT_TIMESTAMP`]

  indexes {
    (playlist_id, musica_id) [unique]
  }
}

Table jams {
  jam_id int [pk, increment]
  host_usuario_id int [not null, ref: > usuarios.usuario_id]
  nome_sala varchar [not null]
  codigo_sala varchar [not null, unique]
  is_ativa boolean [default: true]
  musica_atual_id int [ref: >? musicas.musica_id]
  criado_em timestamp [default: `CURRENT_TIMESTAMP`]
}

Table jam_fila {
  jam_fila_id int [pk, increment]
  jam_id int [not null, ref: > jams.jam_id]
  musica_id int [not null, ref: > musicas.musica_id]
  pontos_voto int [default: 0]
  adicionado_em timestamp [default: `CURRENT_TIMESTAMP`]

  indexes {
    (jam_id, musica_id) [unique]
  }
}

Table avaliacoes_comentarios {
  avaliacao_id int [pk, increment]
  usuario_id int [not null, ref: > usuarios.usuario_id]
  musica_id int [not null, ref: > musicas.musica_id]
  nota int [not null]
  texto text
  likes_count int [default: 0]
  is_deleted boolean [not null, default: false]
  criado_em timestamp [default: `CURRENT_TIMESTAMP`]

  indexes {
    (usuario_id, musica_id) [unique]
  }
}