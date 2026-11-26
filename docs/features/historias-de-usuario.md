# Histórias de Usuário

As 35 histórias de usuário (HU01–HU35) abaixo consolidam o escopo funcional do projeto, detalhando **tipo de usuário**, **tarefas e subtarefas**, **responsável** e **critérios de aceitação**.

## Definição de Done (DoD)

Uma história de usuário é considerada **Done** apenas quando atende a todos os critérios abaixo:
- [ ] **Código e Arquitetura:** Implementação aderente à arquitetura hexagonal (`app/`) e standalone/Signals (`view/`), revisada via Pull Request.
- [ ] **Qualidade Estática:** Aprovado no *Quality Gate* sem erros (`ruff format --check`, `ruff check`, `pyrefly check`, `npm run lint`, `npm run typecheck`).
- [ ] **Testes e Cobertura:** Testes unitários e/ou de integração cobrindo os critérios de aceitação, mantendo cobertura $\ge 85\%$ (`pytest --cov=app --cov-fail-under=85` e `vitest --coverage`).
- [ ] **Validação E2E e Documentação:** Fluxos principais validados em navegador (`npm run test:e2e`) e documentação (`README.md`, `docs/database/`) atualizada quando aplicável.

## Épico 1 — Cadastro e Preferências

| ID | Título | Tipo de Usuário | Tarefas e Subtarefas | Responsável | Critérios de Aceitação |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **HU01** | Criar conta | Novo Usuário | **Backend:** Endpoint `POST /api/auth/register`, hash PBKDF2 e validação Pydantic.<br>**Frontend:** Tela de cadastro (`AuthComponent`) com validação de e-mail, senha e idade. | Gabriel Agra | • Consegue criar conta com solicitação e validação de dados.<br>• Acessa a conta imediatamente após o cadastro. |
| **HU02** | Definir preferências musicais | Novo Usuário | **Backend:** Persistência de `favorite_genres` em `users` e endpoint de atualização.<br>**Frontend:** Seleção de gêneros e artistas favoritos no perfil/onboarding. | Carolina Haddad | • Seleciona gêneros e artistas de interesse.<br>• Preferências são salvas no perfil e usadas nas recomendações. |
| **HU03** | Bloquear gêneros musicais | Usuário Padrão | **Backend:** Campo `blocked_genres` no modelo `User` e filtro em `recommendation.py` (`select_weighted_track`, `order_tracks_by_weighted_seed`).<br>**Frontend:** Gestão de gêneros bloqueados em Configurações/Perfil. | Carolina Haddad | • Adiciona e remove gêneros bloqueados.<br>• Faixas exclusivamente desses gêneros não aparecem em Descobertas nem Playlists. |

## Épico 2 — Descoberta de Músicas

| ID | Título | Tipo de Usuário | Tarefas e Subtarefas | Responsável | Critérios de Aceitação |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **HU04** | Descobrir músicas | Usuário Padrão | **Backend:** Caso de uso `GetNextDiscoveryTrackUseCase` e rota `/api/discovery/next`.<br>**Frontend:** Deck de cartões com suporte a swipe em `DiscoverComponent`. | Gabriel Agra | • Sugere apenas faixas inéditas (fora de Curtidas, Amadas e Rejeitadas).<br>• Respeita preferências e gêneros bloqueados.<br>• Apresenta nova faixa após cada swipe. |
| **HU05** | Curtir uma música | Usuário Padrão | **Backend:** `RecordSwipeInteractionUseCase` gravando `action='like'`.<br>**Frontend:** Gesto de swipe para a direita / botão Like e listagem em `/likes`. | Fernando Seraco | • Dá like e salva a faixa em Curtidas.<br>• Faixa não retorna como descoberta inédita e fica visível em Curtidas. |
| **HU06** | Amar uma música | Usuário Padrão | **Backend:** `RecordSwipeInteractionUseCase` gravando `action='superlike'`.<br>**Frontend:** Gesto de swipe para cima / botão Superlike e listagem em `/loved`. | Fernando Seraco | • Dá superlike e adiciona a faixa às Amadas e Curtidas.<br>• Não reaparece na descoberta; visualizada separadamente em Amadas. |
| **HU07** | Rejeitar uma música | Usuário Padrão | **Backend:** `RecordSwipeInteractionUseCase` gravando `action='dislike'`.<br>**Frontend:** Gesto de swipe para a esquerda / botão Rejeitar e listagem em `/rejected`. | Mateus Araújo | • Rejeita a faixa e a envia para Rejeitadas.<br>• Não retorna em Descobertas nem sugestões de Playlists.<br>• Listagem consultável pelo usuário. |
| **HU08** | Descobrir músicas a partir das preferências | Usuário Padrão | **Backend:** Ponderação em `recommendation.py` (`select_weighted_track`, `order_tracks_by_weighted_seed`) por artistas/gêneros curtidos e amados.<br>**Frontend:** Atualização dinâmica do feed em `DiscoverComponent`. | Gabriel Agra | • Considera Curtidas, Amadas, artistas e gêneros favoritos.<br>• Exclui Rejeitadas e gêneros bloqueados.<br>• Permite avaliação por swipe. |

## Épico 3 — Playlists Inteligentes e Contextuais

| ID | Título | Tipo de Usuário | Tarefas e Subtarefas | Responsável | Critérios de Aceitação |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **HU09** | Criar playlist | Usuário Padrão | **Backend:** CRUD de playlists em `playlists.py` e cálculo `total_duration_seconds`.<br>**Frontend:** Modal/tela de criação e edição em `PlaylistsComponent`. | Mateus Araújo | • Cria, edita e exclui playlist com nome e descrição.<br>• Adiciona/remove faixas e exibe duração total. |
| **HU10** | Adicionar músicas à playlist por swipe | Usuário Padrão | **Backend:** `GetPlaylistDeckUseCase` e `AddTrackToPlaylistUseCase` isolados de Curtidas globais.<br>**Frontend:** Deck de swipe contextual dentro da playlist. | Mateus Araújo | • Sugere faixas fora de Rejeitadas.<br>• Like adiciona só à playlist; Superlike adiciona à playlist e Amadas.<br>• Rejeição na sessão não polui Rejeitadas globais e não repete na sessão. |
| **HU11** | Criar playlist a partir de referências | Usuário Padrão | **Backend:** `CreateDeckPlaylistUseCase` aceitando `source_playlist_id` e filtros de referência.<br>**Frontend:** Seletor de Curtidas, Amadas ou playlists existentes como base. | Carolina Haddad | • Seleciona Curtidas, Amadas ou playlists como referência.<br>• Gera sugestões relacionadas avaliáveis por swipe para adicionar à nova playlist. |
| **HU12** | Criar playlist com duração definida | Usuário Padrão | **Backend:** `max_duration_seconds` na entidade `Playlist` e ajuste no deck.<br>**Frontend:** Campo de duração desejada e barra de progresso/tempo restante. | Gabriel Agra | • Define duração desejada; exibe duração atual e restante.<br>• Sugestões respeitam tolerância máxima de ±1 minuto. |
| **HU13** | Criar playlist baseada em lineup | Usuário Padrão | **Backend:** Filtragem/ranqueamento por artistas em `deck_filters`.<br>**Frontend:** Entrada de artistas para lineup de festival/show. | Fernando Seraco | • Informa artistas; sistema identifica e sugere faixas relacionadas.<br>• Permite adicionar via swipe. |
| **HU14** | Criar playlist baseada em época | Usuário Padrão | **Backend:** Filtro por `release_year`/década em `deck_filters`.<br>**Frontend:** Seletor de época no criador contextual. | Mateus Araújo | • Informa época; recebe sugestões relacionadas para adicionar via swipe. |

## Épico 4 — Jams Colaborativas (Pond)

| ID | Título | Tipo de Usuário | Tarefas e Subtarefas | Responsável | Critérios de Aceitação |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **HU15** | Criar uma Jam e convidar amigos | Usuário Padrão | **Backend:** `CreateJamUseCase` e `JoinJamUseCase` com `room_code` de 6 dígitos.<br>**Frontend:** Criação/entrada em sala em `JamsComponent`. | Gabriel Agra | • Cria Jam, compartilha código e participantes entram, avaliam e veem a fila atualizada. |
| **HU16** | Adicionar músicas à Jam por swipe | Participante de Jam | **Backend:** `VoteJamTrackUseCase` registrando like, superlike e deslike.<br>**Frontend:** Deck de swipe dentro da sala de Jam. | Gabriel Agra | • Participante dá like, superlike ou deslike; avaliação é registrada e altera pontuação da faixa. |
| **HU17** | Organizar a Jam pelas avaliações | Participante de Jam | **Backend:** Ordenação da `JamQueueItem` por `vote_points` (+1 like, +2 superlike, 0 deslike).<br>**Frontend:** Fila reordenada dinamicamente. | Fernando Seraco | • Like soma +1, deslike soma 0, superlike soma +2 com prioridade.<br>• Fila reordena conforme votos de todos os participantes. |
| **HU18** | Votar para pular uma música | Participante de Jam | **Backend:** `VoteSkipJamTrackUseCase` e `skip_votes_threshold` configurável pelo host.<br>**Frontend:** Botão de pular faixa com contador de votos. | Fernando Seraco | • Contabiliza votos; ao atingir limite definido pelo criador, pula a faixa e informa participantes. |
| **HU19** | Acompanhar o tempo da Jam | Participante de Jam | **Backend:** `duration_minutes`, `accumulated_duration_seconds` e `AdvanceJamPlaybackUseCase`.<br>**Frontend:** Indicadores de duração planejada, reproduzida e restante. | Gabriel Agra | • Exibe tempo planejado, reproduzido e restante atualizados em tempo real, com margem de ±1 minuto. |

## Épico 5 — Busca e Avaliações

| ID | Título | Tipo de Usuário | Tarefas e Subtarefas | Responsável | Critérios de Aceitação |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **HU20** | Buscar músicas | Usuário Padrão | **Backend:** Busca unificada em `tracks_reviews.py` com enriquecimento GCS/Spotify/iTunes.<br>**Frontend:** Barra de busca e filtros em `ExploreComponent`. | Carolina Haddad | • Pesquisa por música, artista, álbum, gênero ou ano e adiciona resultados a playlists. |
| **HU21** | Avaliar uma música | Usuário Padrão | **Backend:** `ReviewComment` (nota 1–5) e `PublishReviewUseCase`.<br>**Frontend:** Seletor de nota no modal de detalhes da faixa. | Fernando Seraco | • Registra avaliação vinculada ao usuário e à música. |
| **HU22** | Comentar uma música | Usuário Padrão | **Backend:** Endpoints de criação e exclusão lógica de comentários em `tracks_reviews.py`.<br>**Frontend:** Formulário e ação de excluir comentário próprio. | Fernando Seraco | • Publica e exclui o próprio comentário associado à faixa. |
| **HU23** | Visualizar avaliações e comentários | Usuário Padrão | **Backend:** `GetTrackReviewsUseCase` e `GetCommunityFeedUseCase`.<br>**Frontend:** Feed comunitário e lista de reviews por música. | Mateus Araújo | • Exibe avaliações e comentários publicados na plataforma. |

## Épico 6 — Perfil, Playlists, Assinaturas e Dados

| ID | Título | Tipo de Usuário | Tarefas e Subtarefas | Responsável | Critérios de Aceitação |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **HU24** | Visualizar meu perfil musical | Usuário Padrão | **Backend:** `GetUserProfileUseCase`, `ListUserAccessHistoryUseCase` e listagens em `profile.py`.<br>**Frontend:** `ProfileComponent` (abas Curtidas, Amadas, Rejeitadas e Histórico) e `CollectionComponent` (`/likes`, `/loved`, `/rejected`). | Carolina Haddad | • Visualiza Curtidas, Amadas, Rejeitadas, Histórico de acessos (Ouvidas) e playlists. |
| **HU25** | Visualizar estatísticas e dashboard | Usuário Padrão | **Backend:** `GetAnnualListeningStatsUseCase` e `SQLiteUserStatsRepository`.<br>**Frontend:** `DashboardComponent` (`/dashboard`). | Mateus Araújo | • Apresenta principais artistas, gêneros predominantes e estatísticas de uso. |
| **HU26** | Gerenciar playlists | Usuário Padrão | **Backend:** `ListUserPlaylistsUseCase`, `AddTrackToPlaylistUseCase`, `RemoveTrackFromPlaylistUseCase` e `DeletePlaylistUseCase`.<br>**Frontend:** Lista e detalhes de playlists com remoção. | Mateus Araújo | • Visualiza, adiciona/remove músicas e exclui playlists. |
| **HU27** | Editar meus dados e preferências | Usuário Padrão | **Backend:** `UpdateProfileUseCase` e `UpdatePreferredThemeUseCase`.<br>**Frontend:** `SettingsComponent` (`/settings`). | Carolina Haddad | • Visualiza e edita dados cadastrais e preferências com validação e persistência. |
| **HU28** | Excluir meus dados | Usuário Padrão | **Backend:** Remoção de interações e dados pessoais via `DeleteUserAccountUseCase`.<br>**Frontend:** Fluxo de confirmação em Configurações/Perfil. | Gabriel Agra | • Informa que os dados serão removidos, exige confirmação, exclui e notifica conclusão. |
| **HU29** | Desfazer swipe | Usuário Pagante | **Backend:** `UndoLatestDiscoveryInteractionUseCase` em `discovery.py`.<br>**Frontend:** Botão "Desfazer" na tela de Descoberta (planos pagos). | Fernando Seraco | • Desfaz a última ação, restaura estado anterior e exibe a faixa novamente. |
| **HU30** | Planos e verificação de idade | Novo Usuário | **Backend:** `Plan`, `User.is_minor()` e validação de maioridade (18+) para titular e planos pagos (Individual/Família).<br>**Frontend:** Escolha entre planos em `PlansComponent`, checkout e cadastro em `AuthComponent`. | Gabriel Agra | • Seleciona Plano Free, Individual ou Familiar; valida 18+ para planos pagos/titular e registra plano no perfil. |
| **HU31** | Gestão de perfis na assinatura familiar | Titular de Plano Familiar | **Backend:** `FamilyPlanService`, `AddFamilyMemberUseCase`, `RemoveFamilyMemberUseCase` (até 4 perfis) e filtro de menoridade.<br>**Frontend:** Gerenciamento de dependentes em `FamilyComponent` (`/family`) e restrição etária. | Gabriel Agra | • Cadastra até 4 perfis independentes (1 titular + até 3 dependentes) com histórico/curtidas isolados.<br>• Bloqueia faixas explícitas e de Funk/Trap/Rap/Hip Hop para menores. |
| **HU32** | Gerenciar e cancelar assinatura | Assinante | **Backend:** `ChangeSubscriptionPlanUseCase` e `CancelSubscriptionPlanUseCase`.<br>**Frontend:** Status do plano e cancelamento em `/plans`, `/profile` e `/settings`. | Fernando Seraco | • Consulta status/plano e solicita cancelamento retornando ao plano Free.<br>• Atualiza status do plano. |
| **HU33** | Encerrar e excluir conta | Usuário Padrão | **Backend:** `DeleteUserAccountUseCase` e desvinculação de dependentes.<br>**Frontend:** Seção "Excluir conta" com modal de confirmação em `/settings` e `/profile`. | Gabriel Agra | • Cancela assinatura vinculada; revoga dependentes de plano familiar e remove dados. |

## Épico 7 — Administração e Governança

| ID | Título | Tipo de Usuário | Tarefas e Subtarefas | Responsável | Critérios de Aceitação |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **HU34** | Gestão de catálogo (Cadastro & Soft Delete) | Administrador | **Backend:** `CreateTrackUseCase`, `BlockTrackUseCase`, `UpdateTrackGenreUseCase`, `UpdateTrackExplicitFlagUseCase`, `ListAdminAccessHistoryUseCase` e `is_deleted` em `tracks`.<br>**Frontend:** `AdminModerationComponent` (`/admin/moderation`), `AdminUsersComponent` (`/admin/users` — Histórico de Acessos) e guarda `adminAuthGuard`. | Fernando Seraco | • Área restrita a administradores.<br>• Permite cadastro de faixas, curadoria de metadados e remoção lógica (*Soft Delete*), ocultando a faixa das buscas públicas enquanto preserva o histórico administrativo. |
| **HU35** | Dashboard ADM e cálculo de receita | Administrador | **Backend:** `GetExecutiveDashboardUseCase`, `GetAudienceReportUseCase`, `GetPlatformCostsUseCase`, `UpdatePlatformCostsUseCase` e `SubscriptionAnalyticsService`.<br>**Frontend:** `AdminDashboardComponent` (`/admin/dashboard`). | Mateus Araújo | • Exibe total de usuários ativos, planos, acessos por conteúdo/gênero e Receita Líquida descontando custos configuráveis de conteúdo e infraestrutura. |
