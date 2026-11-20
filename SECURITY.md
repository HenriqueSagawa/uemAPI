# Política de Segurança

## Versões suportadas

A versão `0.1.x` recebe correções de segurança. Versões antigas podem não receber
atualizações.

## Como relatar uma vulnerabilidade

**Não abra uma issue pública para vulnerabilidades.**

Use o canal privado de
[GitHub Security Advisories](https://github.com/HenriqueSagawa/uemAPI/security/advisories/new)
para relatar o problema. Se não for possível usar esse canal, envie um e-mail
para henriquetutomusagawa@gmail.com com o assunto `[uemAPI] Vulnerabilidade`.

Inclua, quando possível:

- versão, commit ou URL afetada;
- rota, arquivo ou componente envolvido;
- passos para reproduzir;
- impacto observado ou potencial;
- ambiente (local, Docker ou produção);
- sugestão de correção, se houver.

Não inclua dados pessoais, credenciais ou conteúdo de terceiros no relato.

## Escopo

São considerados problemas de segurança:

- execução não autorizada de código;
- exposição de segredos, credenciais ou variáveis de ambiente;
- falhas de validação que permitam contornar o contrato da API;
- negação de serviço causada por entrada malformada;
- inclusão acidental de dados pessoais ou conteúdo restrito no repositório ou na
  API;
- vulnerabilidades em dependências usadas pela aplicação.

Não são tratados como vulnerabilidade de segurança:

- incorreções de dados institucionais (use o
  [modelo de correção de dados](.github/ISSUE_TEMPLATE/data_correction.yml));
- indisponibilidade de páginas de terceiros;
- divergências porque a API é comunitária e não oficial;
- falta de uma funcionalidade.

## Processo

O relato será analisado em caráter privado. Quando aplicável, será preparada uma
correção, uma nova versão e uma divulgação coordenada. O projeto é mantido de
forma voluntária e não oferece prazo garantido de resposta ou recompensa
financeira.

## Boas práticas para contribuidores

- Nunca faça commit de `.env`, tokens, chaves ou credenciais.
- Use variáveis de ambiente e os exemplos em `.env.example`.
- Remova dados pessoais de logs, issues e capturas.
- Se uma credencial for exposta, revogue-a imediatamente e avise o mantenedor.
