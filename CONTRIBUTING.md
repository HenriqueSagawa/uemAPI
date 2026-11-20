# Como contribuir com a uemAPI

Obrigado pelo interesse em contribuir. A uemAPI é uma API comunitária,
independente e **não oficial** para informações públicas da Universidade Estadual
de Maringá. O projeto publica um snapshot revisado em `data/` e não substitui os
canais oficiais da UEM.

Contribuições de código, documentação, testes e correções de dados são
bem-vindas. Como o projeto lida com dados institucionais, algumas mudanças exigem
evidência e revisão antes de serem aceitas.

## Princípios do projeto

- **Não invente dados.** Nomes, vínculos, graus, IDs e status precisam vir de uma
  fonte registrada e de uma decisão de revisão.
- **Não edite `data/*.json` manualmente.** O snapshot é gerado a partir dos lotes
  revisados declarados em `reviews/snapshot-inputs.json`.
- **Preserve a proveniência.** Cada registro publicado mantém `source_id`, URL e
  data de consulta.
- **Não inclua dados pessoais.** Contatos, nomes de pessoas e conteúdos restritos
  não fazem parte do escopo.
- **A API é não oficial.** Mudanças não devem sugerir vínculo institucional,
  endosso da UEM ou substituição de sistemas oficiais.
- **Mudanças de contrato exigem cuidado.** Rotas, schemas, paginação, erros e
  campos publicados são consumidos por terceiros.

## Formas de contribuir

- Relate bugs pelo [modelo de bug](.github/ISSUE_TEMPLATE/bug_report.yml).
- Sugira melhorias pelo [modelo de funcionalidade](.github/ISSUE_TEMPLATE/feature_request.yml).
- Corrija dados pelo [modelo de correção de dados](.github/ISSUE_TEMPLATE/data_correction.yml).
- Envie código ou documentação por pull request.
- Relate vulnerabilidades de forma privada, conforme [SECURITY.md](SECURITY.md).
- Antes de mudanças grandes, abra uma issue para alinhar o escopo.

## Preparar o ambiente

Requisitos: Python 3.13 ou superior e Git.

```bash
git clone git@github.com:HenriqueSagawa/uemAPI.git
cd uemAPI
python3.13 -m venv .venv
source .venv/bin/activate
python -m pip install -e '.[dev]'
```

Para executar a API localmente:

```bash
python -m uvicorn app.main:app --reload
```

A documentação interativa fica em <http://127.0.0.1:8000/docs>. Se o snapshot de
`data/` estiver inválido ou ausente, a API responde 503.

## Qualidade e testes

Antes de abrir um pull request, execute:

```bash
python -m ruff check .
python -m ruff format --check .
python -m pytest
python scripts/validate_sources.py
python scripts/validate_data.py --require
python scripts/update_data.py --check
python scripts/validate_publication.py
```

O CI executa esses comandos, constrói a imagem Docker e testa `/v1/health` em um
contêiner. Pull requests com CI vermelho não são mesclados.

## Contribuições de código

- Use Python 3.13 e mantenha o estilo existente.
- Prefira tipos explícitos e modelos Pydantic já usados no projeto.
- Adicione ou atualize testes para mudanças de comportamento.
- Mantenha mensagens de erro curtas e sem expor conteúdo de arquivos ou dados
  pessoais.
- Não adicione dependências sem necessidade clara; justifique no pull request.
- Mudanças em rotas ou schemas devem atualizar a documentação e os testes de
  contrato.
- Não inclua segredos, tokens, caminhos locais ou capturas institucionais brutas.

## Contribuições de dados

Mudanças de dados seguem um fluxo próprio:

1. Leia [o fluxo de revisão](docs/review-workflow.md), [a geração do snapshot](docs/snapshot-generation.md)
   e [o inventário de fontes](docs/source-inventory.md).
2. Registre a captura local, a prévia, a revisão e as decisões nos diretórios
   `reviews/`.
3. Declare os arquivos usados em `reviews/snapshot-inputs.json`.
4. Novas fontes entram em `sources/registry.yaml` como `candidate`. A promoção
   para `approved` exige decisão explícita e escopo documentado.
5. IDs de cursos são persistentes em `reviews/course-ids.json`. Uma URL nova exige
   uma nova entrada; um nome novo não deve trocar o ID.
6. Gere o snapshot com `python scripts/update_data.py --write` e revise o diff.
7. Execute `python scripts/validate_publication.py`.
8. Se a mudança for publicada, atualize o registro de aprovação em
   `reviews/2026-11-20-publicacao/` ou crie um novo registro datado.

Não são aceitas correções baseadas apenas em memória, suposição ou semelhança de
nomes. Também não são aceitos vínculos institucionais inferidos sem fonte.

## Commits e pull requests

- Crie uma branch a partir de `main`.
- Use mensagens curtas com prefixos como `feat:`, `fix:`, `docs:`, `test:`,
  `data:` ou `chore:`.
- Um pull request deve explicar o problema, a solução, o impacto e como foi
  testado.
- Preencha o [modelo de pull request](.github/pull_request_template.md).
- Referencie a issue relacionada quando existir.
- Mantenha o escopo do pull request pequeno e revisável.
- Atualize o [CHANGELOG.md](CHANGELOG.md) quando a mudança for relevante para
  quem consome a API ou os dados.

## Licença das contribuições

O projeto é distribuído sob a [licença MIT](LICENSE). Ao enviar uma contribuição,
você concorda que ela pode ser distribuída sob a mesma licença. Não é exigido
acordo de contribuição (CLA).

Você declara ter direito de enviar o conteúdo e que ele não viola direitos de
terceiros. Dados de fontes institucionais continuam sujeitos às condições
registradas em `sources/registry.yaml` e ao escopo aprovado para publicação.

## Conduta

A participação no projeto segue o [Código de Conduta](CODE_OF_CONDUCT.md).
Comportamentos abusivos, assédio ou exposição de dados pessoais não são aceitos.

## Dúvidas

Consulte o [SUPPORT.md](SUPPORT.md). Para vulnerabilidades, não abra issue
pública: use o canal privado descrito em [SECURITY.md](SECURITY.md).
