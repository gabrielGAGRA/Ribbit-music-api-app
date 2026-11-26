Fiz meus proprios comentarios de algumas coisas que vi. O que acha deles? Dá pra adicionar no plano

<comments>
### Geral

* **Recommended:** Nada aqui parece usar Python 3.15 (ex.: lazy imports, profiling package, frozendict & sentinel) or older maybe needed (Deferred Evaluation of Annotations, Standard Library Multiple Interpreters, Type Parameter Syntax & Type Alias Statement, Low-Impact Monitoring API sys.monitoring, Exception Groups and except*, Task Groups in asyncio, Typing Expansions: Self TypeVarTuple LiteralString TypedDict, Structural Pattern Matching, Union Type Operator, Explicit Type Aliases TypeAlias, ParamSpec).

---

### Application
* **Required:** Revisar use cases e colocar em uma pasta própria. Também faltam as outras pastas da camada.
---
### Domain
* **Required:** `constants.py` não deveria existir; cada constante deve estar em sua respectiva camada de negócio (ex.: constante de idade do usuário fica na classe de `User` no domínio ou similar).

* **Required:** Dividir `entities.py` em seus respectivos arquivos de classe dentro de `domain/models/`.

* **Required:** Revisar `exceptions.py`: são classes vazias que não dão `raise` nem possuem inicializador/construtor. Além disso, deveria haver outro arquivo de `exceptions` (ou nome similar) em `presentation`.

* **Required:** Dividir `ports` em uma pasta `ports/`.
---
### Infrastructure
* **Required:** `apis_externas.py` tem funções de serviços específicos (Spotify, iTunes), mas deveria ser genérico. Além disso, o nome está fora de convenção; deveria ser uma port de serviço de música.

* **Required:** `database`: falta ser clean code.

* **Recommended:** `db_models`: deveria ser subdividido em arquivos.

* **Required:** `repositories` deve ser uma pasta, não um arquivo único.

* **Recommended:** `seed.py` não deveria existir aqui ou deveria ser colocado em outro arquivo fora do pacote da aplicação.
---
### Presentation
* **Nit:** Olhando por cima, está ok. Depois faço uma revisão mais profunda.
---
### Main
* **Required:** Tem muito código e não está seguindo clean code; precisa ser dividido em mais arquivos.
</comments>
