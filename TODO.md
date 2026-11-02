# TODO — Ribbit

---

## Backend

- **PostgreSQL em produção**: `DATABASE_URL` default é SQLite local. Provisionar instância Postgres e configurar a variável de ambiente no ambiente de deploy.
- **Integração real Spotify/iTunes**: `app/infrastructure/apis_externas.py` tem os adaptadores estruturados, mas requer `SPOTIFY_CLIENT_ID` / `SPOTIFY_CLIENT_SECRET` reais. Testar fluxo OAuth de exportação de playlist.
- **Rate limiting**: Nenhum throttle nos endpoints. Adicionar middleware (ex: `slowapi`) especialmente em `/api/descoberta/proxima` e autenticação.

---

## Infraestrutura

- Sem Dockerfile, CI/CD ou configuração de deploy. Definir quando o projeto sair do ambiente universitário local.

---

## Funcionalidades Futuras

- **Deck de amigo na Jam**: Envio direto de superlikes para o deck de outro participante não está modelado na V0. Definir tabela e use case quando a feature for detalhada.
- **Perfis infantis**: Perfis sem e-mail/senha própria (dependentes sem conta Ribbit) ficaram fora do MVP.
- **Playlists contextuais avançadas**: Filtros por localização, clima e atividade específica (treino, estudo) planejados mas não implementados.
- **Desfazer interação (Undo swipe)**: Botão de desfazer da última faixa avaliada está na especificação de UI mas sem rota no backend.
- **WebSocket para Jams**: `obter_estado_e_checar_progresso` é hoje um endpoint REST com polling. Migrar para WebSocket para UX em tempo real.