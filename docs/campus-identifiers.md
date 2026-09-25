# Identificadores dos câmpus

Revisão: 25 de setembro de 2026. Esta é uma regra da **uemAPI**, não uma tabela oficial de IDs da UEM. A [página de câmpus da UEM](https://www.uem.br/a-uem/campus) informa a sede em Maringá e seis câmpus regionais. O [relatório Base de Dados 2025](https://pld.uem.br/lni/v05-base-de-dados-2024-2025.pdf), com ano base 2024, registra as seis siglas regionais e apresenta a sede sem sigla.

| ID da uemAPI | Nome | Município | Sigla institucional |
| --- | --- | --- | --- |
| `sede` | Câmpus Sede | Maringá | `null` |
| `crc` | Câmpus Regional de Cianorte | Cianorte | `CRC` |
| `crg` | Câmpus Regional de Goioerê | Goioerê | `CRG` |
| `car` | Câmpus Regional do Arenito | Cidade Gaúcha | `CAR` |
| `crn` | Câmpus Regional do Noroeste | Diamante do Norte | `CRN` |
| `cau` | Câmpus Regional de Umuarama | Umuarama | `CAU` |
| `crv` | Câmpus Regional do Vale do Ivaí | Ivaiporã | `CRV` |

Os vínculos entre nomes, siglas e municípios são corroborados pelo [glossário da UEM](https://cpr.uem.br/glossario/), pela [Carta de Serviços do CRN](https://cpr.uem.br/index.php/pesquisar-carta/3547-gre-crn) e pelo [contato do CRV](https://crv.uem.br/contato). O relatório anual é usado aqui para conferir a nomenclatura; suas condições de reutilização ainda precisam de revisão antes de compor um dataset publicado.

## Regra da API

- `id` é a chave estável usada por `/v1/campi/{id}` e nas referências `campus_id` de cursos e departamentos.
- Para câmpus regionais, o ID é a sigla institucional em minúsculas. Para a sede, o ID interno é `sede`.
- `sigla` é um campo obrigatório que contém a sigla institucional verificada ou `null` para a sede; `SEDE` não deve ser apresentado como sigla oficial.
- A consulta por ID ignora diferenças entre maiúsculas e minúsculas. Assim, `/v1/campi/CRC` e `/v1/campi/crc` identificam o mesmo registro.
- O coletor usa esta tabela explícita e interrompe a prévia quando os municípios da página não correspondem aos esperados. Não cria IDs automaticamente a partir do nome da cidade.

Nenhum registro real foi publicado. A fonte permanece como `candidate` até a revisão de reutilização e do snapshot completo.
