# Plano de Refatoração e Avaliação de `app/` vs. python-engineering-rules

falta trocar tudo do app/ pra ingles


## Plano de Refatoração (Design Doc)

### Goal
Reorganizar a base de código em `app/` para cumprir a arquitetura hexagonal estrita e as diretrizes de `python-engineering-rules.md`. 

### Approach

- **Configuração e Composition Root**:
  - Criar `app/config.py` com modelo de `Settings` (lendo `DATABASE_URL`, ambiente, flags de seed).
  - Criar `app/bootstrap.py` para instanciar engine, repositórios, adaptadores de música e injetar nos use cases.
  - Reduzir `app/main.py` à inicialização básica do FastAPI e montagem de rotas e manipuladores de erro.


- **Vertical Slices de Execução**:
  1. *Fatia 1 (Configuração & Domínio)*: Criar `config.py`;
  3. *Fatia 3 (Infraestrutura & Banco)*: Modularizar `db/models/`, `db/repositories/` e `db/mappers/`; criar `session.py` sem chamadas globais de `create_engine`; adaptar adaptador de música para `niquests` com pool; desacoplar `seed.py`.
  5. *Fatia 5 (Configuração do Projeto)*: Corrigir `pyproject.toml` (apontar coverage para `["app"]`, remover `src` inexistente do `pythonpath`).


- Validação incremental após cada vertical slice executando os testes existentes.
- Execução do quality gate:
  - `ruff format`
  - `ruff check --fix`
  - `zuban app tests`
  - `find-dup-defs app --only py --error-thickness 0.3 -D @find-dup-defs.directives`

---

Referências `§N` apontam para seções de `python-engineering-rules.md`.

## 1. Veredito geral

Os problemas estão no que acontece dentro e entre as camadas:

- Não existe composition root.
- O domínio é anêmico.
- Segurança e autenticação estão ausentes.
- Há muito código simulado ou morto em produção.
- A infraestrutura tem efeitos colaterais no import.

## 2. Organização / distribuição

| Pasta/arquivo | Observação |
| --- | --- | --- |
| `main.py` | Mistura lifespan, seed, 5 handlers de exceção, rotas utilitárias e wiring. §6 diz "entry module: logging + app construction only". Precisa ser dividido para seguir clean code. |
| Idioma | Docstrings de módulo em inglês, docstrings de função e identificadores em português, arquivos em ambos. Escolher inglês para a pasta app/. |

- **Sem composition root (§6, §7).**
   - `dependencies.py` (presentation) instancia `UsuarioRepository(db)`, `ExternalMusicServiceAdapter()` etc. a cada request.
   - A cada request reconstrói todos os repositórios, e cada use case recebe repositórios novos sobre a mesma `Session`.
   - `ExternalMusicServiceAdapter()` é sempre criado sem token, então o modo "real" nunca é ativado.
   - Deveria existir um `bootstrap` que recebe `Settings` carregadas uma vez.

- **Efeitos colaterais no import e sem Settings (§1, §6).**
   - `database.py` lê `os.getenv("DATABASE_URL")` e chama `create_engine(...)` ao importar. Isso acontece só por importar `app.main` ou `repositories`. Deve ser refatorado para clean code, suportando conexão com banco cloud (GCP futuramente) enquanto permite execução local/demonstração e testes de forma desacoplada.
   - Não há modelo de settings. `DATABASE_URL` tem default silencioso e `connect_args = {}` é um global mutável sem tipo (`allow_untyped_globals=false` deve reclamar).
   - O `lifespan` roda `create_all` e `run_seed` incondicionalmente em qualquer ambiente, sem migrations. O seed deve ficar fora do ciclo de vida padrão da aplicação.

- **Domínio anêmico + duplicação (§3, §6, §8).**
   - ~~Use cases fazem `usuario.is_admin = True`, `musica.is_deleted = True`, `usuario.plano_id = …`.~~ (Concluído no domínio: entidades agora encapsulam estado limitado, `eq=False`, validação de invariantes e remoção de setters anêmicos).
   - Regras de negócio estão em use cases e repetidas:
     - O bloco "buscar usuário ou `EntityNotFoundError`" aparece ~15 vezes. Existe como `_obter_usuario` só em `PerfilUseCases`.
     - O plano "Free" é buscado em 3 lugares (`cadastrar_usuario`, `cancelar_plano_assinatura`, `remover_membro_familia`).

- **Use case sem fronteira transacional (§6 SRP).**
   - Cada `salvar`/`adicionar_*` do repositório faz `commit()` sozinho.
   - `criar_deck_playlist_por_parametros` faz 1 + N commits. `iniciar_ou_avancar_jam` faz `salvar(jam)` e depois `remover_musica_fila`: se o segundo falhar, a música fica promovida e ainda na fila.
   - O commit deveria ficar no use case ou numa unit-of-work, e os repositórios só fazem `add/flush`.


- **Responsabilidade no lugar errado.**
    - `hash_password`/`verify_password` são funções livres dentro de `auth_use_cases.py`, misturadas com a classe (§3). Hash de senha é infraestrutura: deveria ser um port `PasswordHasher` injetado.
    - `perfil_use_cases` importa de `auth_use_cases` (use case depende de use case).
    - PBKDF2 com `100_000` iterações, literal duplicado duas vezes; abaixo do recomendado atual (≥ 600k para SHA-256).
    - `obter_estado_e_checar_progresso` (nome enganoso: não checa progresso) muta `jam.musica_atual_id = None` sem salvar, e faz N+1 de `buscar_por_id` dentro de uma list comprehension com walrus (§3).

- **Repositórios (§3, duplicação).**
    - O padrão "se tem id → carrega, copia campo a campo, commit; senão cria" é repetido em 6 repositórios (~15 linhas cada). Candidato claro ao `find-dup-defs`.
    - Se o `id` existe mas o registro não, cai silenciosamente num `INSERT` novo (mascara defeito).
    - `listar_ativas(limite=1)` sem `ORDER BY`: a "próxima música" não é determinística.
    - `buscar_por_filtros` não tem limite e ignora `pais`, que o use case de playlist aceita.
    - `PlaylistRepository.listar_por_usuario` devolve playlists sem músicas, enquanto `buscar_por_id` devolve com músicas. Contrato inconsistente.
    - O check-then-insert em `Interaction.salvar`/`adicionar_musica` tem condição de corrida (já há `UniqueConstraint`, deveria tratar `IntegrityError`).
    - `obter_relatorio_audiencia` faz `len(listar_ativas(limite=1000))`: conta limitada a 1000 e carrega todos os registros. Precisa de `contar_ativas()`.
    - `repositories.py` é monolítico (744 linhas) e deve ser transformado em pasta com arquivos dedicados.

- **SQLAlchemy em estilo legado (§5, `strict=true` no zuban).** `Column(...)` sem tipos, `session.query(...)`, `declarative_base()`. Com zuban strict isso gera ruído ou `Any`. Migrar para `DeclarativeBase`, `Mapped[...]`/`mapped_column` e `select()`. `preco_mensal` é `Float`; para dinheiro usar `Numeric`/`Decimal`. `db_models.py` deve ser desmembrado em arquivos individuais.
- `lifespan(app)` sombreia o global `app`. `request` não usado nos handlers.
- `perfil.py`: `req: AtualizarPerfilRequest = ...` depois de `Query(...)` é pouco idiomático. Usar `Annotated[..., Depends/Query]` e, por contrato, body sem default.
- Rotas com regra hardcoded na URL (`/feed-top5dias`) e redundância (`/api/reviews/reviews-musica`). O router chama `obter_feed_comunidade(dias=5, limite=3)` enquanto o use case expõe parâmetros que ninguém varia.
- `schemas.py`: `acao: str` e `nova_acao: str` deveriam usar `InteractionAction`/`Literal`. Defaults mutáveis `= []` em `PlaylistResponse` e `JamEstadoResponse` (Pydantic copia, mas vale `Field(default_factory=list)`). Strings sem validação de tamanho (`nome_sala`, `nome`).
- `admin.py`: imports fora de ordem (`AtualizarRestricaoMenoresRequest` antes de `AtualizarPlanoAdminRequest`): o ruff `I001` vai falhar; rodar `ruff check --fix`.



EXTRA:

**Adoção de Python 3.15 / Modern Python**: O código atual usa padrões genéricos sem tirar proveito do target `py315` configurado (como nova sintaxe de type aliases `type`, `Self`, `StrEnum`, `sentinel()` nativo para defaults/sentinelas e `frozendict`), pontos que serão incorporados conforme as diretrizes do projeto.
