---
name: checar-sinais-de-ia
description: Análise profunda de um vídeo/roteiro do Arquivo Gamer para achar sinais óbvios de conteúdo gerado por IA.
---
Faça a checagem completa, por critérios, e devolva nota (0-10 de "parece humano"), evidências e ajustes:
- Voz: ritmo uniforme demais, pausas erradas, pronúncia de nomes, respiração, emoção plana, volume constante.
- Texto/roteiro: frases-padrão ("você sabia que"), listas de três, adjetivos vazios, estrutura repetida entre Arquivos, conclusões genéricas.
- Imagem: mãos/textos/logos deformados, brilho plástico, movimento "derretido", estilo sem consistência, fotos de banco sem origem.
- Edição: cortes mecânicos no mesmo intervalo, animações iguais em todo Reel, legenda sem sincronia, música sem intenção.
- Veracidade: afirmação sem fonte ou "alucinada" é sinal forte de IA; cheque cada fato.
Como olhar o vídeo: extraia quadros com ffmpeg (ex.: 1 por segundo), veja os quadros, ouça/leia a transcrição e compare com Arquivos anteriores.
Diga o grau de certeza; é análise de riscos, não detector perfeito. A decisão final é do Guilherme.
