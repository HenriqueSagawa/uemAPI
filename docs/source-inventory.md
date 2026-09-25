# Inventário inicial de fontes da uemAPI

Revisão: 25 de setembro de 2026. Este inventário avalia as sete URLs já propostas em `sources/registry.yaml`. Todas permanecem **candidatas**. Acesso público à página confirma que ela pode ser lida sem login; não confirma permissão para coleta automatizada ou redistribuição de um dataset.

| Fonte | Dados observados | Uso proposto | Limite encontrado |
| --- | --- | --- | --- |
| [Câmpus da UEM](https://www.uem.br/a-uem/campus) | Sede em Maringá e seis câmpus regionais, com seus municípios. | Nomes e cidades de câmpus. | O texto não traz siglas, identificadores ou endereços de cada unidade. |
| [Organograma](https://www.npd.uem.br/transparencia/organograma/index.html) | Hierarquia de câmpus regionais, centros e departamentos. | Confrontar vínculos institucionais. | É uma página de apresentação; nomes e relações exigem conferência em fontes específicas. |
| [Centros de ensino da PLD](https://pld.uem.br/dvl/regulamentos/centros-de-ensino) | Índice de sete centros com siglas; páginas vinculadas listam departamentos e resoluções. | Fonte inicial para centros e departamentos. | A estrutura das sete páginas vinculadas e a atualidade de cada lista ainda precisam ser conferidas. |
| [Base de Dados da PLD](https://pld.uem.br/lni/base) | Índice HTML de relatórios anuais em PDF. O [relatório 2025](https://pld.uem.br/lni/v05-base-de-dados-2024-2025.pdf) usa ano base 2024 e inclui uma lista de siglas. | Verificação histórica de nomes e siglas. | Não é um PDF único nem uma fonte corrente. O relatório informa direitos reservados; reutilização precisa de revisão específica. |
| [Cursos de graduação da PEN](https://www.pen.uem.br/site/public/cursos) | Lista cursos presenciais por câmpus; páginas de curso apresentam turno, habilitação e grau. A modalidade a distância remete ao NEAD. | Candidata a fonte principal de cursos presenciais. | Não informa centro e departamento nessa lista; é preciso conferir a cobertura da EaD, definir o que constitui uma oferta e validar os identificadores das URLs de detalhe. |
| [Portal de graduação](https://www.uem.br/estude-na-uem/graduacao) | Resumo que informa 80 cursos e distribuição por local e modalidade. | Conferência de cobertura da PEN e da EaD. | É preciso identificar a unidade dessa contagem antes de compará-la com as listas de cursos por câmpus. |
| [SIGAA público](https://sigs.uem.br/sigaa/public/home.jsf) | Links públicos para consultas de centros, departamentos e cursos. | Fonte adicional de validação. | A página inicial é pública, mas o acesso automatizado aos resultados e seu formato ainda não foram verificados. |

## Decisões antes do primeiro coletor

1. **Identificadores e siglas de câmpus.** A [regra de IDs](campus-identifiers.md) usa as seis siglas regionais registradas pela UEM e `sede` como ID interno para Maringá. A sede permanece sem sigla institucional no schema; a aplicação dessa regra aos dados reais ainda exige revisão antes da publicação.
2. **Unidade de curso.** A PEN lista cursos por câmpus e encaminha a modalidade a distância ao NEAD; o portal informa 80 cursos. O catálogo da CPR, consultado anteriormente, mostrava 57 resultados. Não tratar essas contagens como equivalentes sem entender se contam cursos, ofertas, turnos ou modalidades. Um curso com ofertas distintas não deve ser mesclado por nome.
3. **Reutilização e frequência.** Não foi identificada uma licença geral de dados para essas páginas. O relatório anual declara direitos reservados. Antes de automatizar ou redistribuir, revisar as condições aplicáveis a cada fonte e definir frequência prudente de acesso. `review_interval_days` permanece sem valor no registro até essa decisão.
4. **Cobertura dos vínculos.** Conferir os sete centros e suas páginas de departamentos. Vínculos curso–departamento não devem ser inferidos apenas por semelhança de nome ou pelo centro do curso.

Um protótipo do coletor de câmpus agora lê HTML local, valida a lista de municípios e gera uma prévia em JSON para revisão. Ele não busca páginas automaticamente nem cria um dataset de produção. As condições de reutilização e o snapshot completo continuam pendentes antes da publicação.
