/plan /boost . Use subagentes hydrogen medium assim que for apropriado.
Dividindo as mudanças ao final em branchs diferentes de proposito especifico.

Precisamos implementar avaliacoes de usuarios (e filtro disso), ter uma dash de estatisticas no painel de admin com tudo pedido, histórico de acessos.

e "na página de comentários avaliações e tudo mais, eu quero poder filtrar com as músicas que tenha notas mais altas na parte de avaliacoes e as que tem a nota mais baixa. Também quero  que o administrador consiga ver as músicas da quantidade de likes, dislikes super likes em cada música no catálogo de músicas do ADM, então por exemplo que o ADM consiga filtrar as músicas com mais dislikes pra caso ele queira  tirar alguma música"

---

### Feito parcialmente

1. **Busca com filtros**: filtra por categoria (gênero) e metadados (texto, artista, álbum, intervalo de ano), mas não filtra por avaliações dos usuários.
2. **Painel do Administrador**:
   - **Catálogo**: remoção lógica (*soft delete*), restauração, selo `+18` e gênero funcionam, mas o cadastro de novos conteúdos ainda está indicado no próprio README como *(placeholder — em implementação)*.
   - **Estatísticas**: mostra quantidade de usuários, receita bruta por plano e gêneros bloqueados, mas faltam as métricas de acessos por conteúdo, acessos por categoria e a dedução de custos de conteúdo e infraestrutura no cálculo de receita em [subscription_analytics_service.py](file:///c:/Users/gabri/Documents/PROJETOS/poli-usp-code/Lab_Engenharia_Software/app/domain/services/subscription_analytics_service.py).

---

### Ainda falta

1. **Cadastro de novos conteúdos na área de administrador**: criar endpoint `POST /api/admin/tracks` em [admin.py](file:///c:/Users/gabri/Documents/PROJETOS/poli-usp-code/Lab_Engenharia_Software/app/presentation/routers/admin.py) e o formulário correspondente na aba de moderação/catálogo do admin.
2. **Histórico de acessos para controle do administrador com conteúdos removidos**: endpoint e visualização no painel admin que listem os históricos de acesso dos usuários preservando faixas removidas (`is_deleted = 1`), enquanto elas seguem ocultas para os demais usuários.
3. **Estatísticas restantes do painel admin**:
   - Acessos por conteúdo;
   - Acessos por categoria (gênero), substituindo ou complementando o ranking de gêneros bloqueados em [get_audience_report.py](file:///c:/Users/gabri/Documents/PROJETOS/poli-usp-code/Lab_Engenharia_Software/app/application/use_cases/admin/get_audience_report.py);
   - Receita líquida considerando número de assinantes menos custo dos conteúdos disponibilizados e custo de infraestrutura.
4. **Filtro por avaliações dos usuários na busca**: parâmetro de nota mínima (`min_rating`) em `TrackSearchQuery` / `SearchTracksUseCase` e controle no modal de filtros de busca.
5. **Marcação explícita de conteúdos como "vistos"**: indicador visual ("Visto" / "Ouvido") nos cards/listas de busca e catálogo para faixas já acessadas pelo usuário, registrando o acesso também quando tocadas/abertas fora do swipe.
