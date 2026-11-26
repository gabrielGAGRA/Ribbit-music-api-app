- avaliar nossa arquitetura, sem ler todos arquivos.
- se faz sentido nossa estrutura de diviisao de composition, config, middleware e main. o main bem curto como esta. como costuma ser dita a boa pratica?
- avaliar nossa estrutura de exceptions e exception_handlers
- avaliar o uso de infrastructure externa - gcp principalmente, sqlite e docker, e menos importante as apis externas de musica
- me incomoda que itunes adapter ta fora da pasta itunes em infra/adapters. nao sei porque. o mesmo ocorre com spotify adapter. nao sei se eh a melhor estrutura ou se deviamos refatorar pra algo diferente.
- acho que vale a pena avaliar a arquitetura de telemetry, logging e middleware
- avaliar composition.py, se esta com excesso ou ok

*ignore arquivos de tests/ e de configuracoes, assim como leitura completa de arquivos muito grandes desnecessários.

Codebase tambem deveria principio do ponytail: 
"1. Does it need to exist? Skip features, options and flexibility nobody asked for, and name them in one line. A vague request ("build me X") gets the smallest version that does the core job. 
2. Already in this codebase (a helper, component, service, pattern)? Use it the way the surrounding code does.
3. Standard library or a platform feature? Use it, unless the project has its own. A house component beats a native widget.
4. An installed dependency? Use it. Never add a dependency for a few lines.
5. Can it be one line a reader gets at a glance? One line.
6. Otherwise: the minimum code that works." 
Mas não tão literalmente, pois deve seguir as regras de docs/llm também.
