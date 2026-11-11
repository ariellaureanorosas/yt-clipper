# Política de Segurança

## Versões suportadas

Apenas a versão mais recente publicada é suportada com correções de segurança.

| Versão | Suporte |
|--------|---------|
| 1.1.x  | ✅ |
| < 1.1  | ❌ |

## Como relatar uma vulnerabilidade

**Não abra uma issue pública** para vulnerabilidades de segurança.

Reporte de forma privada usando o recurso
[**Report a vulnerability**](../../security/advisories/new) do GitHub
(Security → Advisories → Report a vulnerability). Se não conseguir, envie um
e-mail para **ariellaureanorosas@users.noreply.github.com**.

Inclua, se possível:

- descrição do problema e impacto;
- passos para reproduzir ou prova de conceito;
- versão do aplicativo e do sistema operacional;
- sugestão de correção, se tiver.

### O que esperar

- Confirmação de recebimento em até **5 dias úteis**.
- Avaliação e, se confirmado, correção na versão mais recente.
- Crédito pelo relato no aviso de segurança (se você quiser ser creditado).

Por favor, não divulgue publicamente o problema até que uma correção esteja
disponível.

## Escopo

Este projeto é um aplicativo desktop que executa `yt-dlp` e `ffmpeg` como
subprocessos. Vulnerabilidades relevantes incluem, por exemplo:

- execução de comandos arbitrários a partir de entradas do usuário;
- escrita/leitura indevida de arquivos fora da pasta de trabalho;
- dependências desatualizadas com CVEs conhecidas (o Dependabot monitora isso).

Problemas que dependem exclusivamente de serviços de terceiros (YouTube,
`yt-dlp`, `ffmpeg`) devem ser reportados aos projetos correspondentes.
