# Geração do snapshot revisado

O snapshot de `data/` é gerado apenas a partir dos lotes de revisão já registrados
em `reviews/`. O comando não acessa a rede e não altera as prévias, os relatórios
de revisão nem as capturas locais. O relatório do pipeline mantém
`publicavel: false` porque a geração é uma etapa técnica; a autorização de
publicação é registrada separadamente em
[`reviews/2026-11-20-publicacao/`](../reviews/2026-11-20-publicacao/README.md) e
conferida por `scripts/validate_publication.py`.

## Entradas

O manifesto [`reviews/snapshot-inputs.json`](../reviews/snapshot-inputs.json)
declara, para cada um dos quatro datasets, os pares de prévia e relatório de
revisão que entram no snapshot. Caminhos são resolvidos a partir da pasta do
manifesto. Para departamentos, cada centro tem seu próprio par; podem existir
vários pares no mesmo dataset.

O manifesto também aponta o documento de propostas de normalização. Uma proposta
só é aplicada depois de conferir:

- a `impressao_base` contra o registro e a proveniência da prévia;
- o `valor_observado` no registro carregado;
- se o campo pertence ao modelo canônico da v0.1.

Propostas para campos aninhados que não existem no contrato, como
`informacoes_academicas`, não alteram o snapshot e aparecem em
`normalizacoes_ignoradas`. Os valores extraídos e os lotes históricos permanecem
preservados.

## IDs estáveis de cursos

O manifesto também declara `ids_cursos`, que aponta para
[`reviews/course-ids.json`](../reviews/course-ids.json). O mapeamento é indexado
por `campus_id` e `url_detalhe` e define o `id` publicado de cada curso. A geração
recusa curso aceito sem ID, ID repetido ou ID fora do formato do contrato. IDs
presentes no mapeamento mas sem curso aceito correspondente aparecem em
`ids_cursos_nao_utilizados`; eles não são aplicados silenciosamente.

Mudar o nome de um curso não muda o ID. Uma URL nova exige uma nova entrada e uma
nova decisão de revisão. O ID candidato do coletor continua sendo apenas uma
proposta e não é usado diretamente em `cursos.json`.

## Portão de revisão

A geração é recusada quando qualquer relatório de revisão declarado no manifesto
tem decisões pendentes, decisões desatualizadas ou nenhuma decisão final. As
inconsistências de cobertura registradas nas revisões não bloqueiam a geração,
mas são reproduzidas no relatório para que a limitação continue visível.

## Inferência de grau

O grau de um curso só é preenchido quando há exatamente um bloco acadêmico com
exatamente um `graus_academicos`. Blocos múltiplos, valores ausentes ou mais de
um grau resultam em `grau: null` e em uma entrada em `grau_nao_inferido`. Nenhum
grau é deduzido a partir do nome do curso ou da habilitação.

## Comandos

Prévia sem escrita (padrão):

```bash
python scripts/update_data.py
```

A saída é um JSON com o diff contra `data/` (IDs criados, removidos e campos
alterados), as contagens por dataset, as normalizações aplicadas e ignoradas,
os graus não inferidos, os campos de prévia fora do contrato e as
inconsistências de cobertura. Nada é gravado.

Para verificar se `data/` corresponde exatamente à geração determinística:

```bash
python scripts/update_data.py --check
```

O comando falha se algum dos quatro arquivos estiver ausente ou divergente. Ele
não grava nada e é executado no CI antes da publicação.

Para substituir os quatro arquivos após validar o resultado:

```bash
python scripts/update_data.py --write
```

A escrita é atômica: o conteúdo final é validado pelo mesmo carregador usado
pela API antes de qualquer arquivo ser substituído. Se a geração ou a validação
falhar, o snapshot anterior permanece intacto. Use `--data-dir` e `--manifest`
para apontar outros caminhos. `--write` e `--check` são mutuamente exclusivos.

Para validar um snapshot já existente:

```bash
python scripts/validate_data.py
python scripts/validate_data.py --require
```

Sem arquivos, o comando informa que não há snapshot e termina com sucesso; com
`--require`, ele falha. Um snapshot incompleto ou inválido sempre falha e não
expõe os registros no relatório.

Para validar o catálogo de fontes:

```bash
python scripts/validate_sources.py
```

O comando confere a estrutura de `sources/registry.yaml`: datasets, HTTPS,
tipos, papéis, status, datas e condições de reutilização. Ele não acessa as URLs
nem altera o catálogo.

Para conferir a publicação completa:

```bash
python scripts/validate_publication.py
```

O comando valida o snapshot com o mesmo carregador da API, compara os quatro
arquivos com a geração do manifesto, exige que cada fonte efetivamente usada
esteja `approved` com `reuse_conditions: verified` e revisão dentro do intervalo,
e confere o registro estruturado de aprovação. Divergência de contagens, fontes,
data de captura ou conteúdo faz o comando falhar.

## Publicação

A v0.1.0 está publicada com o snapshot revisado de `data/`. O escopo, as fontes
aprovadas e as limitações estão em
[`reviews/2026-11-20-publicacao/`](../reviews/2026-11-20-publicacao/README.md).
A existência de arquivos válidos não substitui essa aprovação: mudanças de dados
exigem nova revisão e novo registro. Se o snapshot estiver ausente ou inválido, a
API responde 503.

O workflow de testes executa `scripts/validate_sources.py`,
`scripts/validate_data.py --require`, `scripts/update_data.py --check`,
`scripts/validate_publication.py`, a suíte de testes, a construção da imagem
Docker e um teste de fumaça do contêiner com `/v1/health` em `ready`.
