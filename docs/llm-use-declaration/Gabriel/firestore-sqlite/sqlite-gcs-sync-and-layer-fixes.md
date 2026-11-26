Corrija
Use subagentes hydrogen medium

1. O único resquício desnecessário aí são os aliases duplicados de env vars (RIBBIT_SECRET_KEY/SECRET_KEY, DATABASE_PATH/DATABASE_URL, ENVIRONMENT/RIBBIT_ENV), que só aumentam superfície sem ganho real se o projeto padronizar um nome por variável no .env.

2. É uma violação real de camada (§2 e §7 de python-engineering-rules.md): detalhes de protocolo de um único provedor externo (SpotifyError, SpotifyAuthError, SpotifyForbiddenError, SpotifyQuotaExceededError, etc.) vazam para o domínio.
O restante é um acoplamento nominal que, se mantido, não causa bug em runtime, mas idealmente seria reduzido para exceções de domínio genéricas + ExternalServiceError(service_name="Spotify") para erros de infraestrutura do adapter.

3. Portanto, manter o motor em firestore_sync.py e tipá-lo via FirestoreSyncPort em sync_port.py foi a mitigação mínima segura; porém, estruturalmente continua sendo o maior foco de complexidade e risco de bugs (replicação bidirecional artesanal multi-master entre 7 tabelas).
Vamos usar o SQLITE para uma base de dados local e o postgresql para a GCS. So quero manter a divisao clara local e cloud como pedi. Podemos substituir se possivel esse arquivo gigante. Se for necessario que o local nao pegue os dados do GCS, ai podemos deixar um database de arquivo no repo. Mas acho que isso era pra estar resolvido com meu script que puxa da GCS. Mas enfim, avalie.

4. Foi uma decisão de contenção de risco nesta rodada para não quebrar testes :memory: e repositórios que assumem uma única conexão injetada no container, mas arquiteturalmente continua sendo um ponto problemático: Uma conexão compartilhada entre threads com RLock por chamada não isola transações concorrentes que façam múltiplas queries fora de transaction(conn) (um commit()/rollback() em uma thread afeta a outra).
   Para banco em arquivo (WAL), conexão por request/thread com busy_timeout é mais simples e segura (eliminando ThreadSafeConnection e BufferedCursor), ficando :memory: apenas com StaticPool ou ThreadSafeConnection restrita a testes.
5. python -m scripts.init_db + seed_database no create_app: é apenas uma redundância leve (idempotente) — init_db garante criação inicial do arquivo /data/local.db a partir do schema/dump antes do bootstrap_local_gcs e do Uvicorn subirem, embora create_app também chame seed_database.
6. Os dois pontos que realmente faltaram e são fáceis de corrigir são:
   _spotify_sync.py ficou de fora da padronização com extra={"event": ..., "status": "warning"} (enquanto create_track.py, update_track_genre.py, get_next_discovery_track.py e search_tracks.py já foram atualizados).
   configure_logging formata apenas o logger "app", deixando logs do uvicorn fora do formato JSON em produção. (Já o nome telemetry é apenas cosmético).
