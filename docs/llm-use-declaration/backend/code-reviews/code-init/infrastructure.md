| `infrastructure/repositories.py` | 7 repositórios mais 8 funções `_to_*_entity` soltas. §3 diz para não misturar funções livres e classes. Deve ser transformado em uma pasta `infrastructure/db/repositories/` com um arquivo por repositório e mappers isolados. |
| `infrastructure/db_models.py` | Subdividir em arquivos individuais por agregado dentro de `infrastructure/db/models/`. |
| `infrastructure/database.py` | Falta seguir clean code; precisa ser adaptado para instanciar engine/sessão sem side-effects no import e suportar banco cloud (GCP) ou local via configuração. |
| `infrastructure/apis_externas.py` | Único arquivo com nome pt-BR e "plural" na infra (`adapters/music_service.py`). Deve implementar uma porta genérica de serviço de música e utilizar cliente com pool (`niquests` ou `requests.Session`). |
| `infrastructure/seed.py` | Não deve rodar no startup da aplicação; deve ser extraído para script/comando sob demanda para dev/testes, sem poluir instâncias cloud. |
