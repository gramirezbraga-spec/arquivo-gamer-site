"""Publica UM Reel no Instagram do Arquivo Gamer, so com confirmacao explicita.

    python publicar_reel.py --video site/videos/arquivo-013.mp4 --legenda site/publicar/arquivo-013.txt
        -> ENSAIO (padrao): confere tudo e mostra a legenda. NAO posta nada.
    python publicar_reel.py ... --confirmar PUBLICAR
        -> posta de verdade.

O token vem so da variavel IG_TOKEN e nunca e impresso.
Dois tipos de token (igual ao sincronizar_instagram.py):
  - comeca com "IG"  -> login do Instagram (graph.instagram.com), permissao instagram_business_content_publish
  - outro (ex. "EAA") -> login com Facebook (graph.facebook.com), precisa de IG_USER_ID e da
                         permissao instagram_content_publish (conta ligada a uma Pagina do Facebook)
O video precisa estar num link publico (o site no GitHub Pages serve: /videos/... ou /publicar/...).
Usa so a biblioteca padrao do Python.
"""
import argparse
import json
import os
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


def confere_link(url):
    """O Instagram baixa o video sozinho: o link tem que ser publico, direto (sem redirecionar) e ser MP4."""
    req = urllib.request.Request(url, headers={"Range": "bytes=0-1023"})
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            tipo = r.headers.get("Content-Type", "")
            final = r.geturl()
            primeiro = r.read(12)
    except urllib.error.URLError as e:
        sys.exit("O link do video nao abre (%s): %s" % (e, url))
    if final != url:
        print("Aviso: o link redireciona para outro endereco; o Instagram pode recusar.")
    if primeiro[4:8] != b"ftyp":
        sys.exit("O link nao entrega um MP4 valido (tipo %s). O deploy do site ja terminou?" % tipo)
    print("Link do video OK (publico, MP4).")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--video", required=True, help="caminho do mp4 dentro de site/videos/ ou site/publicar/")
    ap.add_argument("--legenda", required=True, help="arquivo .txt com a legenda")
    ap.add_argument("--confirmar", default="", help='digite exatamente PUBLICAR para postar de verdade')
    a = ap.parse_args()

    video = Path(a.video).as_posix()
    if not (video.startswith("site/publicar/") or video.startswith("site/videos/")) or not video.endswith(".mp4") or ".." in video:
        sys.exit("O video precisa estar em site/videos/ ou site/publicar/ e ser .mp4")
    legenda = Path(a.legenda).read_text(encoding="utf-8").strip()
    if not legenda or len(legenda) > 2200:
        sys.exit("Legenda vazia ou maior que 2200 caracteres (%d)." % len(legenda))
    url = BASE_SITE + "/" + video[len("site/"):]

    print("=" * 60)
    print("VIDEO:", url)
    print("LEGENDA (%d caracteres):\n%s" % (len(legenda), legenda))
    print("=" * 60)
    confere_link(url)

    if a.confirmar != "PUBLICAR":
        print("\nENSAIO: nada foi postado. Para postar, rode de novo com a confirmacao PUBLICAR.")
        return

    token = os.environ.get("IG_TOKEN", "").strip()
    if not token:
        sys.exit("IG_TOKEN nao configurado.")
    print("Confirmado. Criando o Reel...")
    cont = chamada("POST", CONTA + "/media", token, media_type="REELS", video_url=url, caption=legenda)["id"]
    for _ in range(12):  # ate ~6 min
        time.sleep(30)
        st = chamada("GET", cont, token, fields="status_code").get("status_code")
        print("  processando:", st)
        if st == "FINISHED":
            break
        if st in ("ERROR", "EXPIRED"):
            sys.exit("O Instagram recusou o video (%s). Nada foi postado." % st)
    else:
        sys.exit("Demorou demais para processar. Nada foi postado; tente de novo.")
    media = chamada("POST", CONTA + "/media_publish", token, creation_id=cont)["id"]
    info = chamada("GET", media, token, fields="permalink")
    print("POSTADO:", info.get("permalink", media))


if __name__ == "__main__":
    main()
