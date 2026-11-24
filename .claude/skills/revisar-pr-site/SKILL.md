---
name: revisar-pr-site
description: Revisão de mudanças no site, no robô sincronizar_instagram.py e nos workflows antes de pedir o ok do Guilherme.
---
1. Leia o diff completo. Confira que nenhum segredo aparece em código, log ou mensagem.
2. Workflows: "Publicar Reel (com confirmacao)" continua exigindo confirmar=PUBLICAR e o ambiente instagram-publicar; o robô de sincronia continua sem postar nada.
3. Robô: ligação por "Arquivo #NNN" na legenda; roda a cada 30 min; não quebra com post sem número.
4. Site: abre sem erro, dados.js válido, vídeos e capas existem, nada com crédito faltando.
5. Rode o que for possível localmente (sintaxe Python, validação do YAML). Relate o que NÃO foi testado.
6. Entregue resumo simples e deixe o merge para o Guilherme.
