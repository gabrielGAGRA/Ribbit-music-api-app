essas mudancas do google style guide, mudam em algo nosso @[docs/llm/app/python-engineering-rules.md] ou @[pyproject.toml] ?


essas sao as mudancas de regras:
Remoção da isenção de import do six.moves (Diff #9)



Removida a tolerância de imports para o pacote de compatibilidade com Python 2 (six.moves).

Flexibilização e restrições de docstrings em testes unitários (Diffs #61 a #70, #72)



Docstrings em classes derivadas de unittest.TestCase e em métodos test_* não são mais obrigatórias.

Proíbe explicitamente docstrings que apenas repetem o nome do método ou classe de teste (ex: """Tests that bar is applied to foo.""").

Docstrings em funções decoradas (Diff #75)



A docstring de uma função com decorador deve agora obrigatoriamente descrever o comportamento resultante após a aplicação do decorador (o que o chamador externo de fato observa, ex: geradores com @contextlib.contextmanager).

Migração do decorador @override para a biblioteca padrão (Diffs #76, #78)



Atualizado para importar diretamente de typing (from typing import override, introduzido na PEP 698 / Python 3.12) em vez de typing_extensions.

Docstrings em classes decoradas (Diff #83)



Se uma classe for decorada, a docstring da classe deve especificar o comportamento pós-decorador.

Nova sintaxe padrão para comentários de TODO (Diffs #104 a #110, #112)



A sintaxe recomendada mudou para parênteses: TODO(contexto): mensagem.

O formato antigo TODO: contexto - mensagem agora é formalmente desencorajado em código novo.

Convenções de Nomenclatura: Acrônimos em maiúsculas e isenção para FFI/C++ (Diffs #123 a #125)



Adoção explícita da recomendação da PEP 8 para acrônimos em nomes CapWords: todas as letras maiúsculas (ex: preferir HTTPServerError em vez de HttpServerError).

Adicionada a subseção 3.16.2.1 Exemptions: permite quebrar as convenções de nomes de Python quando o código interage diretamente com código externo em C++ ou FFI.

Regras e restrições para TypeAlias (Diffs #144 a #147)



Apelidos de tipos devem ser explicitamente anotados como typing.TypeAlias para não se confundirem com constantes globais.

Proibido usar type aliases como atalho para contornar a regra que veda importação direta de símbolos (import foo; foo = foo.foo).

estao disponiveis aqui tambem@[c:\Users\gabri\Documents\PROJETOS\POLI\Lab_Engenharia_Software\diff_palavras.txt]
