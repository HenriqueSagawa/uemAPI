# uemAPI

API comunitária, independente e **não oficial** para informações públicas da Universidade Estadual de Maringá. Este repositório contém a base da v0.1 Fundação. Ainda não há fontes revisadas nem dados de produção aprovados.

## O que já existe

- Aplicação FastAPI com rotas de lista e detalhe para câmpus, centros, departamentos e cursos de graduação em `/v1`.
- Câmpus consultados por ID em `/v1/campi/{id}`: `sede` para Maringá e siglas institucionais em minúsculas para os seis regionais. A sigla da sede é `null`, pois não foi encontrada uma sigla institucional para ela. Consulte [a regra e as fontes](docs/campus-identifiers.md).
- Paginação fixa: `page` começa em 1; `page_size` usa 50 por padrão e aceita até 100.
- Filtros de departamentos por `centro` e `campus`, e de cursos por `campus`, `centro`, `grau` e `modalidade`.
- Schemas, formato de erro, proveniência por registro e documentação OpenAPI em `/docs`.
- Carregamento de um snapshot JSON completo na inicialização, com validação de modelos, unicidade e referências. Se um arquivo estiver ausente ou inválido, `/v1/health` e as consultas respondem 503.

Os registros dos testes servem apenas para verificar o contrato e não constituem um dataset aprovado para `data/`. O contrato de dados poderá ser refinado depois da conferência das fontes reais.

## Desenvolvimento local

Requer Python 3.13 ou superior.

```bash
python3.13 -m venv .venv
source .venv/bin/activate
python -m pip install -e '.[dev]'
python -m uvicorn app.main:app --reload
```

A documentação interativa estará em <http://127.0.0.1:8000/docs>. Até que os quatro arquivos aprovados existam em `data/`, as consultas retornam 503. Para usar outro diretório de dados, defina `UEM_API_DATA_DIR` (consulte `.env.example`).

Também é possível construir uma imagem com `docker build -t uem-api .` e iniciar com `docker run --rm -p 8000:8000 uem-api`. A imagem atual inclui apenas o diretório `data/` vazio e, portanto, informa indisponibilidade até receber dados revisados.

## Prévia local do coletor de câmpus

O primeiro coletor lê somente um arquivo HTML local. Ele confere a presença da sede em Maringá e o conjunto dos seis municípios regionais descritos na [página de câmpus](https://www.uem.br/a-uem/campus). Em seguida, aplica o mapeamento local definido conforme a [tabela revisada](docs/campus-identifiers.md) para obter IDs, nomes, siglas e a associação de cada câmpus ao município. Ele não confere os nomes dos links da página. A prévia em JSON traz esses limites no campo `proveniencia`; o `fonte.url` de cada registro aponta para a página institucional de referência, mas não comprova que o arquivo local veio dela nem que ela sustenta todos os campos. O comando não acessa a rede nem grava em `data/`.

```bash
.venv/bin/python -m app.collectors.campi \
  --html tests/fixtures/campi_page.html \
  --consultado-em 2026-09-25T12:00:00Z
```

A fixture acima é um exemplo criado para testes. Ao usar um HTML capturado da página real, informe em `--consultado-em` a data e hora dessa captura. Se a lista de câmpus não corresponder aos sete registros esperados, o comando falha e exige revisão. A saída é apenas uma prévia: as condições de reutilização e o snapshot completo ainda precisam ser aprovados antes da publicação.

## Prévia local dos cursos da PEN

O coletor de cursos lê um HTML local da [lista de graduação da PEN](https://www.pen.uem.br/site/public/cursos). Ele extrai as entradas presenciais por câmpus e o link para a EaD, sem acessar a rede ou gravar em `data/`.

```bash
python -m app.collectors.cursos \
  --html tests/fixtures/cursos_pen.html \
  --consultado-em 2026-09-25T12:00:00Z
```

Para comparar com uma captura anterior, acrescente `--html-anterior caminho/para/cursos-anteriores.html`. A prévia lista entradas removidas e adicionadas por câmpus, mostra as contagens antes e depois e sinaliza mudanças de nome ou no link da EaD. Sem esse arquivo, `comparacao.status` fica como `sem_captura_anterior` e a revisão manual continua necessária. O comando apenas lê os arquivos locais e imprime JSON.

A fixture é um exemplo para testes. Com uma cópia da página real, informe a hora em que ela foi capturada. A saída é uma prévia não publicável: cada entrada corresponde a um link da lista em um câmpus, e cursos de mesmo nome em câmpus diferentes permanecem separados. O coletor compara as seções de câmpus com a cobertura observada na PEN em 25 de setembro de 2026; se uma seção desaparecer ou surgir, a prévia falha e pede revisão. O coletor não usa o código da URL como ID institucional nem infere grau, centro ou departamento. Turnos e habilitações das páginas de detalhe e os cursos da EaD exigem uma etapa própria de revisão. As condições de reutilização da fonte também continuam pendentes.

## Qualidade

```bash
python -m ruff check .
python -m ruff format --check .
python -m pytest
```

## Formato do snapshot

O diretório configurado deve conter `campi.json`, `centros.json`, `departamentos.json` e `cursos.json`. Cada arquivo contém uma lista JSON não vazia de registros do schema correspondente. Cada registro inclui `id`, `nome` e `fonte` com `source_id`, `url` e `consultado_em` com fuso horário. Os schemas em `app/schemas/` definem os demais campos. Todos os quatro arquivos são validados juntos; nenhum subconjunto é publicado isoladamente.

## Próximas etapas

1. Verificar fontes institucionais públicas para cada dataset, condições de uso e identificadores disponíveis.
2. Implementar o Source Registry e os coletores, com fixtures sem dados pessoais.
3. Definir o processo de revisão dos diffs e publicar os primeiros JSON reais aprovados.

O projeto não coleta dados pessoais, conteúdos restritos ou informações que exijam autenticação.
