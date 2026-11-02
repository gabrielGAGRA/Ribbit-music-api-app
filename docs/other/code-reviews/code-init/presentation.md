  4. *Fatia 4 (Bootstrap & Presentation)*: Criar `presentation/error_handlers.py`; criar `bootstrap.py` que alimenta as dependências FastAPI; enxugar `main.py`.


Deve haver também um módulo de mapeamento de exceções (ex.: `exceptions_handlers.py`) em `presentation`. |
| `presentation/dependencies.py` | É a composição de fato, mas fica em presentation e importa infraestrutura (§6 "NEVER in presentation", §7). Deve ser movido para o composition root (`bootstrap.py`). |
| `presentation/routers/admin.py` | Importa `Session`, `get_db` e `UsuarioRepository`. Há um use case contornado dentro de `verificar_admin`. |


- **Tratamento de exceções de domínio em `main.py` (§2).**
   - Cinco handlers quase idênticos, copiados, com `request` não usado. Deveria ser um dict `{tipo → status}` com um único handler (type-based lookup), em módulo de presentation (`error_handlers.py`), aliviando `main.py`.
   - Com isso `CustomError` fica como fallback 400.