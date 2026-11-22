## 3. bugs por severidade

### Crítico

1. **Autorização opcional ignorável.** Em `iniciar_ou_avancar_jam`, `solicitante_usuario_id` é opcional. Se for omitido, o check de host é pulado e qualquer um avança a jam (`jam_use_cases.py:156`).

2. **Entradas de negócio controladas pelo cliente.**
   - `pontos` em `votar_musica_fila` não tem limite nem sinal. Pontos negativos ou gigantes manipulam a fila.
   - `dar_like_comentario` incrementa sem checagem de usuário, então o like é ilimitado.
   - `atualizar_perfil` troca a senha sem exigir a senha atual.

3. **Dados falsos como se fossem reais (§2: nunca engolir erro).**
   - `ExternalMusicServiceAdapter` devolve faixas "Demo Album" sem token.
   - No erro do iTunes, devolve um `preview_url` fabricado.
   - `exportar_playlist_spotify` não exporta: gera `hash(...)` no lugar. `hash()` de `str` varia por processo (PYTHONHASHSEED), então o ID não é estável.
   - `obter_frequencia_anual` retorna `42.0`, gêneros e artistas fixos. `obter_logs_auditoria` retorna uma lista fixa.
   - Ou isso vira stub/fake explicitamente injetado só em dev/teste, ou falha de forma tipada.

### Alto

4. **Infraestrutura silencia falhas e não é observável (§2, §4).**
    - O Spotify retorna `[]` quando `status != 200` sem log.
    - Não há logging estruturado em lugar nenhum (só um `logger.warning("... %s")` em `apis_externas`). Sem eventos start/success/failure, sem correlation id.
    - `httpx.Client` é criado por chamada, sem pool, sem retry limitado e sem `from exc`/mapeamento para erro de infraestrutura que o use case possa tratar. Na medida do possível, substituir por `niquests` (ou `requests.Session`) com pool reutilizado.


### Baixo

5. Seed com URLs `https://example.com/...` e dados fixos dentro de uma função de ~110 linhas. Separar dados de lógica e só executar sob demanda em dev, sem poluir instâncias cloud.
