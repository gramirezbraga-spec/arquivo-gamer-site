"""Publica CARROSSEL, IMAGEM UNICA ou STORY (imagem) no Instagram do Arquivo Gamer, so com confirmacao.

    python publicar_imagens.py --tipo carrossel --imagens site/publicar/bf/01.jpg,site/publicar/bf/02.jpg --legenda site/publicar/bf/legenda.txt
        -> ENSAIO (padrao): confere os links e mostra a legenda. NAO posta nada.
    python publicar_imagens.py ... --confirmar PUBLICAR
        -> posta de verdade.

Tipos: carrossel (2 a 10 imagens, com legenda) | imagem (1 imagem, com legenda) | story (1 imagem por vez, SEM legenda).
Limites da API do Instagram: so JPEG; stories pela API nao aceitam figurinhas (enquete, quiz, link, musica);
a imagem do story deve ser 9:16 (1080x1920). Carrossel/imagem: 4:5 (1080x1350) funciona.
O token vem so da variavel IG_TOKEN e nunca e impresso. Mesmas regras de token do publicar_reel.py.
As imagens precisam estar em site/publicar/ (viram link publico no GitHub Pages).
"""
import argparse
import json
import os
import struct
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

BASE_SITE = os.environ.get("SITE_URL", "https://gramirezbraga-spec.github.io/arquivo-gamer-site").rstrip("/")
IG_USER_ID = os.environ.get("IG_USER_ID", "").strip()
_TOKEN_IG = os.environ.get("IG_TOKEN", "").strip().startswith("IG")
USA_FACEBOOK = bool(IG_USER_ID) and not _TOKEN_IG
API = "https://graph.facebook.com/v23.0" if USA_FACEBOOK else "https://graph.instagram.com/v23.0"
CONTA = IG_USER_ID if USA_FACEBOOK else "me"
PERMISSAO = "instagram_content_publish" if USA_FACEBOOK else "instagram_business_content_publish"


def chamada(metodo, caminho, token, **params):
    params["access_token"] = token
    dados = urllib.parse.urlencode(params).encode()
    url = API + "/" + caminho.strip("/")
    if metodo == "GET":
        req = urllib.request.Request(url + "?" + dados.decode())
    else:
        req = urllib.request.Request(url, data=dados, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            return json.loads(r.read().decode())
    except urllib.error.HTTPError as e:
        try:
            err = json.loads(e.read().decode()).get("error", {})
        except Exception:
            err = {}
        msg = err.get("message", "HTTP %s" % e.code)
        dica = ""
        if err.get("code") in (10, 200, 190) or "permission" in msg.lower():
            dica = " -> Falta a permissao %s no token (gere um token novo marcando-a)." % PERMISSAO
        sys.exit("Erro do Instagram (codigo %s): %s%s" % (err.get("code"), msg, dica))


def tamanho_jpeg(dados):
    """Le largura x altura de um JPEG (so biblioteca padrao)."""
    i = 2
    while i + 9 < len(dados):
        if dados[i] != 0xFF:
            i += 1
            continue
        marca = dados[i + 1]
        if marca in (0xC0, 0xC1, 0xC2):
            alt, larg = struct.unpack(">HH", dados[i + 5:i + 9])
            return larg, alt
        i += 2 + struct.unpack(">H", dados[i + 2:i + 4])[0]
    return None


def confere_link(url):
    """O Instagram baixa a imagem sozinho: link publico, direto, JPEG, proporcao aceita."""
    try:
        with urllib.request.urlopen(urllib.request.Request(url), timeout=60) as r:
            final = r.geturl()
            dados = r.read()
    except urllib.error.URLError as e:
        sys.exit("O link da imagem nao abre (%s): %s" % (e, url))
    if final != url:
        print("Aviso: o link redireciona; o Instagram pode recusar:", url)
    if dados[:2] != b"\xff\xd8":
        sys.exit("Nao e JPEG (a API so aceita .jpg). O deploy do site ja terminou? %s" % url)
    if len(dados) > 8 * 1024 * 1024:
        sys.exit("Imagem maior que 8 MB: %s" % url)
    return tamanho_jpeg(dados)


def espera(cont, token):
    for _ in range(12):
        st = chamada("GET", cont, token, fields="status_code").get("status_code")
        if st == "FINISHED":
            return
        if st in ("ERROR", "EXPIRED"):
            sys.exit("O Instagram recusou a midia (%s). Nada foi postado." % st)
        time.sleep(5)
    sys.exit("Demorou demais para processar. Nada foi postado; tente de novo.")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--tipo", required=True, choices=["carrossel", "imagem", "story"])
    ap.add_argument("--imagens", required=True, help="caminhos .jpg em site/publicar/, separados por virgula, na ordem dos slides")
    ap.add_argument("--legenda", default="", help="arquivo .txt com a legenda (nao vale para story)")
    ap.add_argument("--confirmar", default="", help="digite exatamente PUBLICAR para postar de verdade")
    a = ap.parse_args()

    imgs = [Path(x.strip()).as_posix() for x in a.imagens.split(",") if x.strip()]
    for p in imgs:
        if not p.startswith("site/publicar/") or not p.lower().endswith((".jpg", ".jpeg")) or ".." in p:
            sys.exit("Cada imagem precisa estar em site/publicar/ e ser .jpg: %s" % p)
    if a.tipo == "carrossel" and not 2 <= len(imgs) <= 10:
        sys.exit("Carrossel precisa de 2 a 10 imagens (recebi %d)." % len(imgs))
    if a.tipo in ("imagem", "story") and len(imgs) != 1:
        sys.exit("O tipo %s leva exatamente 1 imagem por execucao (recebi %d)." % (a.tipo, len(imgs)))

    legenda = ""
    if a.tipo == "story":
        if a.legenda:
            print("Aviso: story nao aceita legenda pela API; a legenda sera ignorada.")
    else:
        if not a.legenda:
            sys.exit("Informe o arquivo de legenda.")
        legenda = Path(a.legenda).read_text(encoding="utf-8").strip()
        if not legenda or len(legenda) > 2200:
            sys.exit("Legenda vazia ou maior que 2200 caracteres (%d)." % len(legenda))

    urls = [BASE_SITE + "/" + p[len("site/"):] for p in imgs]
    print("=" * 60)
    print("TIPO:", a.tipo, "| %d imagem(ns)" % len(urls))
    if legenda:
        print("LEGENDA (%d caracteres):\n%s" % (len(legenda), legenda))
    print("=" * 60)
    for i, u in enumerate(urls, 1):
        dim = confere_link(u)
        print("Imagem %d OK: %s  tamanho=%s" % (i, u, "%dx%d" % dim if dim else "?"))
        if dim and a.tipo == "story" and abs(dim[0] / dim[1] - 9 / 16) > 0.02:
            print("  AVISO: story deveria ser 9:16 (1080x1920).")
        if dim and a.tipo != "story" and not 0.79 <= dim[0] / dim[1] <= 1.92:
            sys.exit("Proporcao fora do aceito pelo Instagram (4:5 a 1.91:1).")

    if a.confirmar != "PUBLICAR":
        print("\nENSAIO: nada foi postado. Para postar, rode de novo com a confirmacao PUBLICAR.")
        return

    token = os.environ.get("IG_TOKEN", "").strip()
    if not token:
        sys.exit("IG_TOKEN nao configurado.")
    print("Confirmado. Criando a publicacao...")
    if a.tipo == "carrossel":
        filhos = []
        for u in urls:
            c = chamada("POST", CONTA + "/media", token, image_url=u, is_carousel_item="true")["id"]
            espera(c, token)
            filhos.append(c)
        cont = chamada("POST", CONTA + "/media", token, media_type="CAROUSEL", children=",".join(filhos), caption=legenda)["id"]
    elif a.tipo == "imagem":
        cont = chamada("POST", CONTA + "/media", token, image_url=urls[0], caption=legenda)["id"]
    else:
        cont = chamada("POST", CONTA + "/media", token, image_url=urls[0], media_type="STORIES")["id"]
    espera(cont, token)
    media = chamada("POST", CONTA + "/media_publish", token, creation_id=cont)["id"]
    info = chamada("GET", media, token, fields="permalink")
    print("POSTADO:", info.get("permalink", media))


if __name__ == "__main__":
    main()
