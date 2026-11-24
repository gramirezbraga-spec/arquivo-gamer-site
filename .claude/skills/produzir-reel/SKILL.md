---
name: produzir-reel
description: Monta o vídeo de um Reel do Arquivo Gamer a partir do roteiro aprovado, com o modelo de reel e a checagem de formato.
---
1. Leia o roteiro aprovado, fontes-e-licencas.md do jogo e arquivo-gamer/modelo de reel/guia-do-modelo.md.
2. Pasta do jogo: roteiros/<jogo>/video com textos_NNN.py, prep_voz.py (voz de personagem de jogo genérico, original) e build_video.py adaptado do modelo. Uma cena por frase; palavra-chave em amarelo; etiquetas curtas; fechamento fixo com créditos.
3. A nuvem não alcança o edge-tts: monte a prévia aqui e gere a voz final no PC (Remote Control), com ok do Guilherme para usar o computador.
4. Saída: 1080x1920, 30 fps, H.264 + AAC, cerca de 50 s, nome com versão (arquivo-NNN-<jogo>-reels-v2.mp4).
5. Confira com ffmpeg: duração, resolução e um quadro por segundo. Procure texto fora da área segura (13% a 78%), número do Arquivo errado e menções a datas que não valem na postagem.
6. Entregue ao analista para a checagem de IA antes do ok do Guilherme.
