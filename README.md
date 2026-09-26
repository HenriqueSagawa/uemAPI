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

## Prévia local dos centros de ensino

O coletor de centros lê uma cópia local do [índice da PLD](https://pld.uem.br/dvl/regulamentos/centros-de-ensino). Ele confere as sete siglas esperadas e extrai os nomes exibidos e os links das páginas vinculadas. O ID candidato é a sigla em minúsculas; o sufixo “(Departamentos e Órgãos)” é retirado do nome. A prévia registra essas transformações em `proveniencia`.

```bash
python -m app.collectors.centros \
  --html tests/fixtures/centros_pld.html \
  --consultado-em 2026-09-26T12:00:00Z
```

A fixture é apenas um exemplo de teste. Para uma captura real, informe a hora da captura. O comando não acessa a rede, não visita as páginas vinculadas e não grava em `data/`. Os departamentos e demais órgãos dessas páginas ainda precisam ser separados e conferidos. `fonte.url` identifica o índice de referência, sem comprovar a origem do arquivo local. A saída permanece `publicavel: false` até a revisão dos registros e das condições de reutilização.

## Prévia local dos cursos da PEN

O coletor de cursos lê um HTML local da [lista de graduação da PEN](https://www.pen.uem.br/site/public/cursos). Ele extrai as entradas presenciais por câmpus e o link para a EaD, sem acessar a rede ou gravar em `data/`.

```bash
python -m app.collectors.cursos \
  --html tests/fixtures/cursos_pen.html \
  --consultado-em 2026-09-25T12:00:00Z
```

Para comparar com uma captura anterior, acrescente `--html-anterior caminho/para/cursos-anteriores.html`. A prévia lista entradas removidas e adicionadas por câmpus, mostra as contagens antes e depois e sinaliza mudanças de nome ou no link da EaD. Sem esse arquivo, `comparacao.status` fica como `sem_captura_anterior` e a revisão manual continua necessária. O comando apenas lê os arquivos locais e imprime JSON.

A fixture é um exemplo para testes. Com uma cópia da página real, informe a hora em que ela foi capturada. A saída é uma prévia não publicável: cada entrada corresponde a um link da lista em um câmpus, e cursos de mesmo nome em câmpus diferentes permanecem separados. O coletor compara as seções de câmpus com a cobertura observada na PEN em 25 de setembro de 2026; se uma seção desaparecer ou surgir, a prévia falha e pede revisão. O coletor não usa o código da URL como ID institucional nem infere grau, centro ou departamento. Turnos e habilitações das páginas de detalhe e os cursos da EaD exigem uma etapa própria de revisão. As condições de reutilização da fonte também continuam pendentes.

## Prévia local do detalhe de um curso da PEN

O coletor de detalhe confere uma página salva com a entrada correspondente em uma cópia local do índice. O exemplo usa fixtures sintéticas, sem dados pessoais:

```bash
python -m app.collectors.curso_detalhes \
  --indice tests/fixtures/cursos_pen.html \
  --html tests/fixtures/curso_detalhe_pen.html \
  --campus sede \
  --url https://www.pen.uem.br/site/public/curso/1111111111111111111111111111111111111111 \
  --consultado-em 2026-09-26T12:00:00Z
```

O comando lê somente arquivos locais e imprime JSON. O título e o câmpus da página de detalhe devem coincidir com a entrada indicada no índice. Turnos, habilitações e graus são preservados em blocos conforme aparecem na seção acadêmica inicial; esses blocos ainda não representam ofertas independentes. O coletor separa valores por elementos HTML, não por quebras de linha do arquivo. Rótulos não acadêmicos encerram a captura; trechos ambíguos e contatos detectados em valores acadêmicos causam erro. Nomes, contatos e descrição do curso não são campos da prévia. O `id_candidato` combina o câmpus com o nome normalizado, mas muda se o nome mudar. Consulte a [decisão sobre unidade e IDs de cursos](docs/course-identity.md). O resultado permanece `publicavel: false` e não cria registros em `data/`.

## Prévia consolidada dos detalhes de cursos

Para conferir a cobertura do índice, associe cada página salva ao câmpus e à URL do curso em um manifesto JSON. Cada entrada contém `campus_id`, `url_detalhe`, `arquivo` e `consultado_em` com fuso horário. Caminhos relativos em `arquivo` são resolvidos a partir da pasta do manifesto. O [manifesto de exemplo](tests/fixtures/cursos_consolidados_manifesto.json) contém uma captura sintética; as demais entradas do índice aparecerão como `sem_captura`.

```bash
python -m app.collectors.cursos_consolidados \
  --indice tests/fixtures/cursos_pen.html \
  --manifesto tests/fixtures/cursos_consolidados_manifesto.json \
  --consultado-em-indice 2026-09-26T12:00:00Z
```

O comando não acessa a rede nem grava arquivos. Ele imprime uma prévia por curso validado e informa, separadamente, cursos `sem_captura`, `arquivo_ausente`, com `falha_leitura` ou `invalido`, além de capturas `fora_do_indice`. O resumo inclui contagens por câmpus. Uma falha em um detalhe não impede a conferência dos demais. Entradas malformadas, repetidas ou que reutilizem o mesmo arquivo para dois cursos interrompem a execução para evitar associação ambígua. `cobertura_completa` indica apenas que todas as entradas presenciais do índice tiveram um detalhe aceito e que não sobraram capturas no manifesto; não aprova os dados para publicação. O relatório não inclui o HTML bruto nem mensagens de erro com conteúdo da página. A saída permanece `publicavel: false` e não cria `cursos.json`.

## Prévia local dos departamentos da PLD

O coletor de departamentos lê uma cópia HTML local da página de um centro na [PLD](https://pld.uem.br/dvl/regulamentos/centros-de-ensino). Uma execução trata somente esse centro; a saída não comprova a cobertura completa de departamentos da UEM. O comando não acessa a rede nem grava arquivos.

```bash
python -m app.collectors.departamentos \
  --html tests/fixtures/departamentos_ctc.html \
  --centro CTC \
  --consultado-em 2026-09-26T12:00:00Z
```

`--centro` aceita `CCA`, `CCB`, `CCE`, `CCH`, `CCS`, `CSA` e `CTC`. A fixture é sintética e contém somente exemplos. Para uma captura real, informe a hora da captura com fuso horário. O coletor confere o título da página e a entrada do próprio centro, extrai sigla e nome dos rótulos de regulamentos e mantém os rótulos originais e links em `auditoria`. Entradas que não identificam departamentos aparecem em `excluidos` com motivo; sua classificação institucional ainda exige revisão.

A prévia usa a sigla em minúsculas como ID interno candidato, sem afirmar que seja um identificador institucional. Remove o sufixo de resolução do nome e mantém os demais parênteses. Reconhece a grafia `Deparamento de Engenharia Mecânica` na entrada `DEM`, preservando o nome e registrando uma observação para revisão. `campus_id` permanece `null` e `status` permanece `desconhecido`; a página de regulamentos não comprova esses campos. Os links dos regulamentos são preservados, mas seu conteúdo não é lido.

A captura deve conter o conteúdo principal da PLD (`article#content`, título `documentFirstHeading`, `div#content-core` e lista `div.entries` com `article.entry`). Cada entrada admite um único link textual no cabeçalho e, opcionalmente, um link de ícone para a mesma URL. Mudanças nessa estrutura, siglas ou URLs duplicadas, artigos aninhados, ausência de departamentos ou links fora da página institucional do centro interrompem a prévia. O coletor não possui uma lista completa de siglas esperadas: remoções de entradas e completude precisam de conferência manual. A origem do arquivo local não é autenticada, a cobertura dos demais centros e as condições de reutilização continuam pendentes, e `publicavel` permanece `false`.

## Prévia consolidada dos departamentos

O consolidado lê um manifesto JSON com `centro_sigla`, `arquivo` e `consultado_em` (ISO 8601 com fuso) para cada página local. Caminhos relativos são resolvidos a partir da pasta do manifesto. O [manifesto de exemplo](tests/fixtures/departamentos_consolidados_manifesto.json) lista os sete centros; somente a captura sintética de `CTC` está incluída nas fixtures. Os outros seis caminhos ilustram onde colocar capturas próprias e aparecerão como `arquivo_ausente` até existirem.

```bash
python -m app.collectors.departamentos_consolidados \
  --manifesto tests/fixtures/departamentos_consolidados_manifesto.json
```

O comando lê apenas arquivos locais e imprime JSON, sem acessar a rede nem gravar em `data/`. O relatório traz uma prévia individual para cada centro aceito, informa centros `sem_captura`, com `arquivo_ausente`, `falha_leitura` ou `invalido`, e identifica siglas de departamentos repetidas entre centros aceitos. Uma captura inválida não impede a análise das outras; manifestos ambíguos, com centro desconhecido, entrada duplicada, arquivo reutilizado ou horário sem fuso são rejeitados. `cobertura_fontes_completa` indica apenas que as sete páginas esperadas foram processadas. Ainda é preciso revisar cada página para verificar a completude e a atualidade de sua lista, resolver duplicidades e aprovar os dados e as condições de reutilização. A saída permanece `publicavel: false`.

## Revisão local de prévias

As prévias de câmpus e centros podem ser comparadas com capturas anteriores. O relatório destaca mudanças de registros e proveniência, informa decisões pendentes ou desatualizadas e oferece um modelo para registrar justificativas e evidências. Consulte o [procedimento de revisão](docs/review-workflow.md). A revisão não publica dados nem cria arquivos em `data/`.

```bash
python -m app.review.previews \
  --dataset campi \
  --atual caminho/para/campi-atual.json \
  --anterior caminho/para/campi-anterior.json
```

Na primeira revisão, omita `--anterior`. O mesmo comando aceita `--dataset centros` para as prévias do índice da PLD.

## Qualidade

```bash
python -m ruff check .
python -m ruff format --check .
python -m pytest
```

## Formato do snapshot

O diretório configurado deve conter `campi.json`, `centros.json`, `departamentos.json` e `cursos.json`. Cada arquivo contém uma lista JSON não vazia de registros do schema correspondente. Cada registro inclui `id`, `nome` e `fonte` com `source_id`, `url` e `consultado_em` com fuso horário. Os schemas em `app/schemas/` definem os demais campos. Todos os quatro arquivos são validados juntos; nenhum subconjunto é publicado isoladamente.

## Próximas etapas

1. Aplicar a revisão de prévias a capturas reais de câmpus e centros, registrando decisões e evidências.
2. Estender a revisão a departamentos e cursos; resolver cobertura da EaD, vínculos e IDs estáveis de cursos.
3. Verificar condições de reutilização das fontes e aprovar o snapshot completo antes de publicar os primeiros JSON reais.

O projeto não coleta dados pessoais, conteúdos restritos ou informações que exijam autenticação.
