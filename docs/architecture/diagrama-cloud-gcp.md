# Diagrama de Arquitetura em Nuvem & Pipeline GCP

Pipeline de dados, hospedagem em produção no Google Compute Engine, armazenamento do catálogo em Parquet no Google Cloud Storage, sincronização e controle de custos no Cloud Firestore e autenticação/APIs externas do **Ribbit**.

```mermaid
flowchart TB
    User([Usuário / Admin - Navegador])
    DuckDNS["DuckDNS<br/>ribbitmusic.duckdns.org"]
    Ops["Automação GCP e VM<br/>Instance Schedule 08h-20h BRT<br/>systemd DuckDNS Boot"]

    subgraph GCP_VM["Google Compute Engine — VM Linux (Docker Compose)"]
        Caddy["Caddy Reverse Proxy<br/>HTTPS TLS automático<br/>Portas 80 e 443"]
        SPA["Frontend Angular<br/>SPA estática"]
        Backend["Backend FastAPI / Uvicorn<br/>app/"]
        SQLite[(SQLite 3<br/>local.db)]
        IAM["Service Account IAM<br/>ADC sem arquivo de chave"]
        Caddy -->|"Arquivos estáticos"| SPA
        Caddy -->|"Proxy API e Health"| Backend
        Backend -->|"Leitura e escrita local"| SQLite
        IAM -.->|"Credenciais nativas"| Backend
    end

    subgraph GCP_GCS["Google Cloud Storage — Catálogo Parquet"]
        BaseParquet[(tracks.parquet<br/>catalog_version.json)]
        Deltas[(deltas Parquet<br/>Micro-deltas incrementais)]
        Deltas -->|"Compactação em lote"| BaseParquet
    end

    subgraph GCP_FS["Google Cloud Firestore — Estado e Custos"]
        Firestore[(Cloud Firestore<br/>REST API v1)]
        CostDash["Painel Admin /admin/dashboard<br/>Cotas Free Tier e Receita Líquida"]
        Firestore -->|"FirestoreUsageTracker<br/>leituras, escritas, deletes, egress"| CostDash
    end

    subgraph ExtAuth["Identidade e APIs Externas"]
        GoogleAuth([Google Auth Platform / OAuth 2.0])
        MusicAPIs([Spotify Web API / iTunes Preview API])
    end

    User -->|"HTTPS"| DuckDNS
    DuckDNS -->|"DNS dinâmico"| Caddy
    Ops -.->|"Agenda 08h-20h BRT"| Backend
    Ops -.->|"Atualiza IP no boot"| DuckDNS
    BaseParquet -->|"Ingestão e Sync"| Backend
    Backend -->|"Enriquecimento, Cadastro e Soft Delete"| Deltas
    Backend -->|"FirestoreSyncService<br/>sync_all, pull_deltas, tombstones"| Firestore
    Firestore -->|"Pull incremental"| Backend
    Backend -->|"Login Google e PKCE"| GoogleAuth
    Backend -->|"Capas, prévias, buscas e filas"| MusicAPIs
```
