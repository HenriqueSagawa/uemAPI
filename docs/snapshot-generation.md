# Geração do snapshot revisado

O snapshot de `data/` é gerado apenas a partir dos lotes de revisão já registrados
em `reviews/`. O comando não acessa a rede e não altera as prévias, os relatórios
de revisão nem as capturas locais. A revisão humana continua sendo a etapa que
autoriza a publicação: um snapshot gerado mantém `publicavel: false`.

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

Para substituir os quatro arquivos após validar o resultado:

```bash
python scripts/update_data.py --write
```

A escrita é atômica: o conteúdo final é validado pelo mesmo carregador usado
pela API antes de qualquer arquivo ser substituído. Se a geração ou a validação
falhar, o snapshot anterior permanece intacto. Use `--data-dir` e `--manifest`
para apontar outros caminhos.

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
nem promove uma fonte candidata a aprovada.

## Publicação

`data/` permanece vazio neste repositório até que o snapshot completo e as
condições de reutilização das fontes sejam aprovados em revisão separada. A
existência de arquivos válidos em `data/` não substitui essa aprovação. Enquanto
não houver snapshot aprovado, a API responde 503.

O workflow de testes executa `scripts/validate_sources.py`, `scripts/validate_data.py`
e a suíte de testes. `validate_data.py` não exige `data/` preenchido, de modo que
o CI também falha se um snapshot commitado ficar inválido ou incompleto.
