# Ribbit
<img width="300" height="300" alt="image" src="https://github.com/user-attachments/assets/3195384c-1bf5-4b72-8710-29e3af00807e" />


### Time: Crazy Frogs
- Carolina Britto Haddad
- Fernando Mendes Seraco
- Gabriel Agra de Castro Motta
- Mateus Silva de Araújo

## Sumário
- [Sobre](#-sobre)
- [Funcionalidades](#-funcionalidades)
  - [Aplicativo](#aplicativo)
  - [Painel Administrativo](#painel-administrativo)
- [Arquitetura e Tecnologias](#-arquitetura-e-tecnologias)
- [Como Executar](#-como-executar)

---

## Sobre

O **Ribbit** redefine a experiência de ouvir novas músicas através de uma mecânica interativa inspirada em *swipe*, usando da geração dinâmica de playlists e sessões colaborativas em tempo real (*Jams*).

O projeto é composto por duas frentes:
1. **Ribbit**: Aplicativo voltado ao usuário final para descoberta, criação de playlists inteligentes e interação social em grupo.
2. **Ribbit Admin Console**: Painel web restrito para curadoria de catálogo com *soft delete* e monitoramento de métricas.

---

## Funcionalidades

### Aplicativo 

#### 1. Onboarding e Preferências
- Cadastro completo de usuários com validação de dados.
- Seleção personalizada de gêneros e artistas favoritos para alimentar as recomendações.
- Bloqueio de gêneros musicais indesejados, impedindo que faixas associadas exclusivamente a eles apareçam nas Descobertas e Playlists.

#### 2. Descoberta por Swipe
- Feed central de novas faixas que descarta músicas já avaliadas ou gêneros bloqueados.
- Avaliação gestual rápida:
  - **Like (Direita)**: Envia a música para as Curtidas.
  - **Superlike (Cima)**: Adiciona a faixa às Amadas e Curtidas em lista separada.
  - **Rejeitar (Esquerda)**: Remove a música de futuras recomendações e sugestões de playlists.
  - **Desfazer Ação (Premium Ribbit)**: Restaura a última faixa avaliada na Descoberta em caso de toque acidental; disponível nos planos pagos.

#### 3. Playlists Inteligentes e Contextuais
- **Montagem por Swipe**: Modo de adicionar músicas a uma playlist via gestos sem poluir a lista global de Curtidas.
- **Duração Exata**: Ajuste algorítmico da duração planejada com margem de erro máxima de $\pm 1$ minuto.
- **Momentos de Evento**: Criação de blocos com durações e gêneros distintos para eventos complexos.
- **Lineup de Festivais**: Geração de sugestões baseada em múltiplos artistas informados.
- **Filtros Contextuais**: Playlists por localização/viagem, clima/vibe, época (década ou ano) e atividades específicas (treino, estudo).
- **Modo Referência**: Geração automática com base em Curtidas, Amadas ou playlists prévias.

#### 4. Jams Colaborativas
- Criação de salas em grupo com convite para amigos.
- Sistema de pontuação coletiva por swipe: Like (+1), Deslike (0) e Superlike (+1 com destaque de prioridade).
- Envio direto de faixas supercurtidas para o *deck* de um amigo participante.
- Votação democrática para pular músicas da fila em reprodução.
- Acompanhamento do tempo total e restante com margem de tolerância de $\pm 1$ minuto.

#### 5. Busca, Comunidade e Lançamentos
- Busca universal por faixa, artista, álbum ou gênero.
- Feed com suporte à avaliação imediata.
- Publicação, edição e exclusão de comentários e avaliações comunitárias em cada música.

#### 6. Perfil e Dados
- Gestão e edição de listas de Curtidas, Amadas, Rejeitadas e Artistas favoritos.
- Dashboard pessoal com artistas principais, gêneros predominantes, entre outras estatísticas.
- Exclusão transparente de dados sob solicitação do usuário.
- Edição do plano de assinatura

#### 7. Restrições de conteúdo para menores
- Contas de menores não recebem nem podem interagir com faixas explícitas ou classificadas como Funk, Trap, Rap ou Hip Hop.
- A regra se aplica à descoberta, busca, decks de playlists e Jams, histórico e ações sobre faixas.
- Para menores, a busca externa não é usada como alternativa quando não há resultado local, pois os resultados externos não têm gênero confiável para aplicar o filtro.


---

### Painel Administrativo (Web)

#### 1. Gestão de Catálogo & Soft Delete 
- Acesso seguro exclusivo para contas com permissão de administrador.
- Formulário de cadastro com metadados completos (título, artista, gênero) e upload de arquivos de áudio.
- **Soft Delete de Conteúdo**: Ao remover uma faixa, ela é ocultada das buscas públicas e das descobertas, permanecendo registrada nos históricos de reprodução dos usuários para integridade de dados e auditoria.

#### 2. Dashboard Executivo e Cálculo de Receita
- Visualização de acessos agrupados por conteúdo e por categoria/gênero.
- Contagem dinâmica de usuários ativos sincronizada com a base.
- Cálculo da Receita Líquida da plataforma


---


## Arquitetura e Tecnologias

- **Frontend**: TypeScript e Angular.
- **Backend**: Python.

---

## Como Executar

### 1. Pré-requisitos
- **NPM**: gerenciador de pacotes incluído com o Node.
- **Python 3.15 ou superior**: necessário para executar o backend.

### 2. Iniciar o Backend
Na raiz do repositório, crie e ative o ambiente virtual, instale as dependências e inicie a API:
```powershell
py -3.15 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python -m uvicorn app.main:app --reload
```

O backend ficará disponível em `http://127.0.0.1:8000`, e a documentação interativa da API em `http://127.0.0.1:8000/docs`.

### 3. Instalação das Dependências do Frontend
Na raiz do repositório, instale as dependências executando:
```bash
npm install
```

### 4. Iniciar o Frontend em Desenvolvimento
Inicie o servidor de desenvolvimento a partir da raiz:
```bash
npm run dev:web
```

O servidor é iniciado automaticamente com `--host 0.0.0.0 --port 4200`, disponibilizando a aplicação para conexões locais e na rede interna.

---

## Como Visualizar

### No Computador
Abra qualquer navegador moderno (Chrome, Edge, Firefox, Brave) e acesse:
- **URL**: [http://localhost:4200](http://localhost:4200)

### No Celular

#### Opção A: Acesso Direto (Mesma rede Wi-Fi)
1. Conecte o computador e o celular na **mesma rede Wi-Fi**.
2. No navegador do celular (Chrome ou Samsung Internet), acesse a URL da rede exibida no terminal:
   - **URL**: `http://<SEU_IP_LOCAL>:4200` *(no seu caso: `http://10.46.214.63:4200`)*

---

### Testes Automatizados & Qualidade

- **Executar testes unitários**:
  ```bash
  npm test
  ```
- **Checar tipagem estrita com TypeScript**:
  ```bash
  npm run typecheck
  ```
- **Gerar build de produção**:
  ```bash
  npm run build
  ```
