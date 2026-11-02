não deveria usar sqlalchemy, definimos sqlite e postgresql

não deveria nem ter infra e seed pra banco de dados local, o que usamos na matéria era local .db
  
  2. *Fatia 2 (Ports & Use Cases)*: Em `application/ports/` e `application/use_cases/`, ajustar tipagens com `collections.abc.Sequence` e eliminando retornos genéricos `dict[str, Any]`.


  - **Contratos `dict[str, Any]` em vez de tipos (§5, §8).** `AdminUseCases` (5 métodos), `JamUseCases.obter_estado_e_checar_progresso`, `PerfilUseCases.obter_perfil_usuario/obter_frequencia_anual` e os ports externos devolvem dicts livres. Os routers de perfil, jams e admin retornam `dict[str, Any]` sem `response_model`, então o contrato OpenAPI fica vazio. Criar DTOs na camada `application` (§8).

  - **Use cases com dependências opcionais mortas.** `PerfilUseCases.musica_repo` é opcional e nunca usado. `PlaylistUseCases.external_service` é opcional e gera um ramo "serviço indisponível" que, na prática, nunca ocorre (a adapter é sempre injetada).  As dependências dos use cases também estão públicas (`self.usuario_repo`) em vez de privadas. Os casos de uso devem ser agrupados na pasta `application/use_cases/`.


  ### Aspetos de Engenharia de Software e APIs

* **Sincronismo vs. Laço de Eventos Assíncrono (`async`)**:
* As portas definem métodos exclusivamente síncronos (`def search_tracks(...)`, `def export_playlist(...)`, `def find_by_id(...)`).


* Se esta aplicação operar sobre um motor assíncrono (FastAPI, Starlette, Litestar), as chamadas de rede a catálogos externos ou operações de I/O em base de dados irão bloquear a linha de execução (*thread*) do laço de eventos se não forem envolvidas em *threadpools* delegadas. Para ecossistemas assíncronos modernos, os protocolos devem declarar corrotinas:
```python
class TrackCatalogPort(Protocol):
    async def search_tracks(self, query: str, limit: int) -> list[CatalogTrack]: ...

```




* **Vulnerabilidade de Esgotamento de Memória em `find_by_filters**`:
* O método `list_active` exige o parâmetro `limit: int`, mas `find_by_filters` aceita múltiplos filtros sem impor limites de paginação (`limit` e `offset` / `cursor`). Numa base de dados com milhões de faixas, uma pesquisa vazia ou com filtros alargados (ex.: `genre="Rock"`) forçará a instanciação de milhares de entidades em memória, criando um vetor de negação de serviço (DoS).




* **Disparidade de Identificadores Primitivos**:
* O repositório utiliza identificadores internos inteiros (`track_id: int`), ao passo que os serviços externos trabalham com identificadores alfanuméricos (`external_id: str | None`, `track_ids: Sequence[str]`). Recomenda-se a definição explícita de tipos com semântica própria recorrendo a `typing.NewType` (por exemplo, `TrackId = NewType("TrackId", int)` e `ExternalTrackId = NewType("ExternalTrackId", str)`) para impedir trocas acidentais de parâmetros posicionais em chamadas de negócio.




* **Falta de Especificação de Exceções de Domínio nos Contratos**:
* O método `find_preview` documenta `failures raise`, mas omite a tipologia do erro. Os adaptadores concretos nunca devem deixar vazar exceções de transporte (como `httpx.HTTPError`, `requests.RequestException` ou erros de SDKs específicos) para a camada de aplicação; as portas devem pressupor que qualquer falha de rede seja traduzida para uma exceção derivada de `DomainError` ou `ApplicationError`.