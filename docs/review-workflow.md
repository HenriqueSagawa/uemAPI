# Revisão local de prévias de câmpus e centros

As prévias produzidas pelos coletores são candidatas. O comando de revisão compara duas prévias do mesmo dataset, destaca mudanças e associa decisões registradas a versões específicas de cada registro. Ele não acessa a rede, não altera as prévias e não cria arquivos em `data/`.

## Preparar as prévias

Salve a saída de uma captura atual. Informe a data e a hora em que o HTML foi obtido, com fuso horário:

```bash
python -m app.collectors.campi \
  --html caminho/para/campi-atual.html \
  --consultado-em 2026-09-26T12:00:00-03:00 \
  > /tmp/campi-atual.json
```

Para centros, use `python -m app.collectors.centros` com os mesmos argumentos. Guarde a prévia anterior se quiser acompanhar o que mudou. Se não houver uma, a revisão tratará todos os registros atuais como candidatos novos.

Ao carregar uma prévia de centros, a revisão exige que cada `id` corresponda à `sigla` em minúsculas, conforme a regra do coletor. Uma divergência interrompe a análise antes de registrar aprovações.

## Comparar e criar um modelo de decisões

```bash
python -m app.review.previews \
  --dataset campi \
  --atual /tmp/campi-atual.json \
  --anterior caminho/para/campi-anterior.json \
  --modelo-decisoes /tmp/decisoes-campi.json \
  > /tmp/revisao-campi.json
```

Retire `--anterior` na primeira revisão. Para centros, troque `--dataset campi` por `--dataset centros` e use as prévias correspondentes. `--modelo-decisoes` cria um arquivo novo e recusa sobrescrever um existente. O relatório contém `comparacao.mudancas`, com inclusões, remoções e diferenças por campo, e `revisao.registros`, com a situação de cada decisão. Mudanças na proveniência da prévia aparecem em `comparacao.proveniencia_alterada`.

## Registrar e conferir decisões

Edite o modelo gerado. Para cada registro atual e cada remoção, preencha:

- `decisao`: `aprovado`, `rejeitado` ou `pendente`;
- `justificativa`: motivo da decisão;
- `evidencias`: lista de URLs ou caminhos de documentos conferidos;
- `data_decisao`: data e hora em ISO 8601 com fuso, para decisões finais.

Decisões finais exigem justificativa, pelo menos uma evidência e data. O Git registra quem alterou o manifesto; evite incluir nomes ou contatos pessoais nele. Depois, confira o relatório novamente:

```bash
python -m app.review.previews \
  --dataset campi \
  --atual /tmp/campi-atual.json \
  --anterior caminho/para/campi-anterior.json \
  --decisoes /tmp/decisoes-campi.json \
  > /tmp/revisao-campi-final.json
```

Cada decisão usa a `impressao` gerada para o registro e sua proveniência. Uma mudança de nome, ID, sigla, cidade, fonte, link de centro, status ou proveniência torna a decisão anterior `decisao_desatualizada`. Uma nova data de captura, sozinha, não a invalida. Registros removidos têm decisões próprias. Decisões que não correspondem a um registro atual ou a uma remoção aparecem em `decisoes_obsoletas`; IDs ausentes ou inesperados aparecem em `inconsistencias_cobertura`.

`todos_itens_aprovados` indica apenas que as decisões do relatório foram registradas e que não há inconsistências de cobertura. O relatório permanece `publicavel: false`: a origem dos arquivos locais não é autenticada, as condições de reutilização das fontes continuam pendentes e a API exige revisão do snapshot completo de quatro datasets antes de publicar dados.
