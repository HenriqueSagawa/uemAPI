# Unidade e identificadores de cursos na prévia

## Unidade observada

O índice da PEN fornece um link de curso sob um câmpus. A prévia trata esse par como uma unidade candidata. Mesmo que duas entradas tenham o mesmo nome, elas permanecem separadas quando pertencem a câmpus diferentes. A página de detalhe pode descrever turnos, habilitações e graus múltiplos; ainda não há base suficiente para tratá-los como registros independentes da API.

## ID candidato

O coletor de detalhe monta `id_candidato` como `<campus_id>-<nome-normalizado>`: letras minúsculas sem acentos e grupos de outros caracteres substituídos por hífens. Ele verifica se há colisões entre todas as entradas do índice local. O código hexadecimal da URL da PEN é preservado como referência da fonte e não é tratado como ID institucional.

Esse ID é apenas uma proposta interna. Uma mudança de nome pode mudá-lo, e duas denominações parecidas podem colidir. Antes de publicar `cursos.json`, é preciso aprovar e registrar um mapeamento persistente dos IDs e revisar mudanças de nome ou URL sem trocar IDs automaticamente.

## Limites da página de detalhe

Os blocos de informações acadêmicas seguem a ordem de `Turno`, `Habilitação/Habilitações` e `Grau Acadêmico` na página. Uma lista de habilitações sob um turno permanece no mesmo bloco; o coletor não deduz qual grau corresponde a cada habilitação nem interpreta “matutino ou noturno” como duas ofertas. Páginas como Ciências Biológicas, Letras e Música mostram por que essa revisão é necessária.

O detalhe é conferido com o título e o câmpus do índice salvo. A origem dos arquivos não é autenticada. O coletor não lê conteúdo de documentos vinculados e não extrai dados de coordenação, contatos ou textos descritivos. A cobertura da EaD, os vínculos com centro e departamento, a completude e as condições de reutilização continuam pendentes. Nenhum resultado desta etapa é publicável.
