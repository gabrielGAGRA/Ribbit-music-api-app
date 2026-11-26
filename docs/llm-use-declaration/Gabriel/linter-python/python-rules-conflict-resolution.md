Antes de tentar resolver os conflitos de regras, veja os docs de regras para conferir qual regra manter ou como mudar. Se necessario, pesquise a best practice atual, state of art.
Alem disso, existe lazy import e sentinel no python 3.15. Isso so mostra que voe esta desatualizado e precisa sim pesquisar (em ingles) antes de resolver qualquer conflito de regra. pesquise sobre os outros.
Adversarial review eh so risky changes mesmo

arrume drifts
na linha 13, era um exemplo da google (e.g.), mas pode remover se achar melhor
e talvez tirar esses [lint:no] e lint yes. o que tiver lint , nem precisa estar ai, no maximo como uma orientacao qunado ja nao for o padrao da LLM.

nao tem docs/design e nem vai ter. a llm so deve acessar docs/llm, que pretendo no futuro adicionar domainguide.md etc

arrume as regras repetidas que pedi
arrume formatacao
