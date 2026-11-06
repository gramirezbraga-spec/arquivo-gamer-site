"""Sincroniza o site do Arquivo Gamer com os posts do Instagram.

Roda sozinho no GitHub Actions a cada 30 minutos (veja .github/workflows/sincronizar.yml)
e tambem pode ser rodado no seu PC:

    set IG_TOKEN=seu_token            (PowerShell: $env:IG_TOKEN = "seu_token")
    python sincronizar_instagram.py              sincroniza
    python sincronizar_instagram.py --dry-run    so mostra o que faria
    python sincronizar_instagram.py --renovar-token   pede um token novo (o atual vale ~60 dias)

O que faz:
  1. Pergunta ao Instagram quais sao os posts em video (Reels) mais recentes da sua conta.
  2. Para cada post ainda desconhecido, descobre de qual Arquivo ele e:
       a) pelo numero na legenda ("Arquivo #007", nas primeiras linhas), ou
       b) pela frase de gancho do calendario (a primeira frase da legenda), ou
       c) por um unico numero "Arquivo #NNN" em qualquer parte da legenda.
     Se nao tiver certeza, NAO publica nada e avisa no log.
  3. Baixa o video e a capa para site/videos e site/capas, grava a legenda postada e o link do post em site/dados.js.
Nunca apaga nada. O token so e lido da variavel de ambiente IG_TOKEN e nunca e impresso.

Usa so a biblioteca padrao do Python (nada para instalar).
"""
import argparse
import json
import os
import re
import sys
import time
import unicodedata
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

BASE = os.environ.get("IG_API_BASE", "https://graph.instagram.com").rstrip("/")
VERSAO = os.environ.get("IG_API_VERSION", "").strip("/")
CAMPOS = "id,caption,media_type,media_product_type,media_url,thumbnail_url,permalink,timestamp"
LOCAL = BASE.startswith("http://127.0.0.1") or BASE.startswith("http://localhost")  # so para testes
MAX_VIDEO_MB = 200


class ApiErro(Exception):
    def __init__(self, msg, codigo=None, status=None):
        super().__init__(msg)
        self.codigo, self.status = codigo, status


def url_api(caminho, **params):
    partes = [BASE] + ([VERSAO] if VERSAO else []) + [caminho.strip("/")]
    return "/".join(partes) + "?" + urllib.parse.urlencode(params)


def http_get(url, tentativas=3, timeout=40):
    """GET com tentativas. Nunca imprime a URL (ela leva o token)."""
    ultimo = None
    for t in range(tentativas):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "arquivo-gamer-sync/1.0"})
            return urllib.request.urlopen(req, timeout=timeout)
        except urllib.error.HTTPError as e:
            try:
                corpo = json.loads(e.read().decode("utf-8", "replace"))
                err = corpo.get("error", {})
            except Exception:
                err = {}
            ultimo = ApiErro(err.get("message", "HTTP %s" % e.code), err.get("code"), e.code)
            if e.code < 500 and e.code != 429:  # erro do pedido/token: nao adianta repetir
                raise ultimo
        except (urllib.error.URLError, TimeoutError, ConnectionError) as e:
            ultimo = ApiErro("falha de rede (%s)" % e.__class__.__name__)
        time.sleep(2 * (t + 1))
    raise ultimo


def api_json(url):
    with http_get(url) as r:
        return json.loads(r.read().decode("utf-8"))


def norm(s):
    s = unicodedata.normalize("NFD", s or "")
    s = "".join(c for c in s if unicodedata.category(c) != "Mn").lower()
    return re.sub(r"[^a-z0-9]+", " ", s).strip()


def linhas_uteis(caption):
    return [l.strip() for l in (caption or "").replace("\r", "").split("\n") if l.strip()]


RE_NUM = re.compile(r"arquivo\s*#\s*0*(\d{1,3})\b", re.I)


def confere(item, caption):
    """O numero sozinho nao basta: a legenda tambem precisa citar o gancho ou o nome do jogo."""
    nc = norm(caption)
    g = norm(item.get("gancho", ""))
    if len(g) >= 15 and g[:40] in nc:
        return True
    return any(len(w) >= 4 and w in nc for w in norm(item.get("jogo", "")).split())


def acha_arquivo(caption, itens):
    """Devolve (item, motivo) ou (None, explicacao). Na duvida, nao decide."""
    por_id = {i["id"]: i for i in itens}
    ls = linhas_uteis(caption)

    def por_numero(nums, onde):
        nums = {n for n in nums if n in por_id}
        if len(nums) > 1:
            return None, "ambiguo: a legenda cita " + ", ".join("#%03d" % n for n in sorted(nums)) + " " + onde
        if len(nums) == 1:
            n = next(iter(nums))
            if confere(por_id[n], caption):
                return por_id[n], "numero na legenda (#%03d)" % n
            return None, "a legenda diz #%03d mas nao cita o gancho nem o jogo (%s)" % (n, por_id[n]["jogo"])
        return False, ""

    # a) numero nas 2 primeiras linhas
    r = por_numero({int(n) for l in ls[:2] for n in RE_NUM.findall(l)}, "no comeco")
    if r[0] is not False:
        return r
    # b) frase de gancho do calendario (ja confirma o conteudo)
    nc = norm(" ".join(ls[:4]))
    achados = [i for i in itens if len(norm(i.get("gancho", ""))) >= 15 and norm(i["gancho"])[:50] in nc]
    if len(achados) == 1:
        return achados[0], "gancho do calendario"
    if len(achados) > 1:
        return None, "ambiguo: o gancho bate com " + ", ".join("#" + i["num"] for i in achados)
    # c) um unico numero em qualquer parte da legenda
    r = por_numero({int(n) for n in RE_NUM.findall(caption or "")}, "na legenda")
    if r[0] is not False:
        return r
    return None, "nao achei numero nem gancho conhecido"


def baixa(url, destino, assinatura, minimo_kb, limite_mb=MAX_VIDEO_MB):
    """Baixa para destino (so https; http so em teste local). Confere o tipo do arquivo."""
    if not (url.startswith("https://") or (LOCAL and url.startswith("http://127.0.0.1"))):
        raise ApiErro("endereco de download nao e https")
    destino = Path(destino)
    destino.parent.mkdir(parents=True, exist_ok=True)
    tmp = destino.with_suffix(destino.suffix + ".part")
    total = 0
    with http_get(url, timeout=120) as r, open(tmp, "wb") as f:
        while True:
            bloco = r.read(1 << 20)
            if not bloco:
                break
            total += len(bloco)
            if total > limite_mb * 1048576:
                f.close()
                tmp.unlink(missing_ok=True)
                raise ApiErro("arquivo maior que %d MB" % limite_mb)
            f.write(bloco)
    ok = total >= minimo_kb * 1024
    if ok:
        with open(tmp, "rb") as f:
            ok = assinatura(f.read(32))
    if not ok:
        tmp.unlink(missing_ok=True)
        raise ApiErro("o arquivo baixado nao parece valido")
    tmp.replace(destino)
    return total


def eh_mp4(b):
    return b[4:8] == b"ftyp"


def eh_imagem(b):
    return b[:3] == b"\xff\xd8\xff" or b[:8] == b"\x89PNG\r\n\x1a\n" or b[:4] == b"RIFF"


def le_dados(arq):
    m = re.match(r"^\s*window\.AG_DADOS\s*=\s*(.*?);?\s*$", Path(arq).read_text(encoding="utf-8"), re.S)
    if not m:
        sys.exit("Nao consegui ler %s (esperado: window.AG_DADOS = {...};)" % arq)
    return json.loads(m.group(1))


def grava_dados(arq, dados):
    js = json.dumps(dados, ensure_ascii=False).replace("\u2028", "\\u2028").replace("\u2029", "\\u2029")
    tmp = Path(str(arq) + ".tmp")
    tmp.write_text("window.AG_DADOS = " + js + ";\n", encoding="utf-8")
    tmp.replace(arq)


def posts_do_instagram(token, paginas):
    url = url_api("me/media", fields=CAMPOS, limit=25, access_token=token)
    posts = []
    for _ in range(paginas):
        d = api_json(url)
        posts += d.get("data", [])
        url = (d.get("paging") or {}).get("next")
        if not url:
            break
    return posts


def saida_github(**kv):
    f = os.environ.get("GITHUB_OUTPUT")
    if f:
        with open(f, "a", encoding="utf-8") as fh:
            for k, v in kv.items():
                fh.write("%s=%s\n" % (k, v))


def renovar(token):
    d = api_json(url_api("refresh_access_token", grant_type="ig_refresh_token", access_token=token))
    print("Token renovado. Vale por mais %d dias." % round(int(d.get("expires_in", 0)) / 86400))
    print("Troque o segredo IG_TOKEN no GitHub por este valor (nao compartilhe):")
    print(d.get("access_token", ""))


def main():
    ap = argparse.ArgumentParser(description="Sincroniza o site com os posts do Instagram")
    ap.add_argument("--pasta", default=str(Path(__file__).resolve().parent / "site"), help="pasta do site (com dados.js)")
    ap.add_argument("--dry-run", action="store_true", help="nao baixa nem grava nada")
    ap.add_argument("--paginas", type=int, default=2, help="paginas de 25 posts a consultar (padrao 2)")
    ap.add_argument("--renovar-token", action="store_true")
    ap.add_argument("--exigir-token", action="store_true", help="falha se IG_TOKEN nao existir")
    a = ap.parse_args()

    token = os.environ.get("IG_TOKEN", "").strip()
    if not token:
        msg = "IG_TOKEN nao esta configurado: nada foi sincronizado."
        print(("::warning::" if os.environ.get("GITHUB_ACTIONS") else "Aviso: ") + msg)
        saida_github(mudou="false")
        sys.exit(1 if a.exigir_token or a.renovar_token else 0)
    try:
        if a.renovar_token:
            renovar(token)
            return
        pasta = Path(a.pasta)
        arq = pasta / "dados.js"
        if not arq.exists():
            sys.exit("Nao achei %s. Gere o site antes (python gerar_site_publico.py)." % arq)
        dados = le_dados(arq)
        itens = dados["itens"]
        conhecidos = {i["ig_id"] for i in itens if i.get("ig_id")}
        posts = posts_do_instagram(token, a.paginas)
    except ApiErro as e:
        if e.codigo == 190 or e.status in (400, 401) and "token" in str(e).lower():
            print("::error::O token do Instagram expirou ou foi recusado (%s). Gere outro e atualize o segredo IG_TOKEN." % e)
        else:
            print("::error::Falha ao falar com o Instagram: %s" % e)
        saida_github(mudou="false")
        sys.exit(1)

    mudou, problemas = False, 0
    # refaz o download de videos que falharam numa rodada anterior (o endereco do video muda a cada consulta)
    por_ig = {i["ig_id"]: i for i in itens if i.get("ig_id")}
    for p in posts:
        it = por_ig.get(p.get("id"))
        if it and it.get("fonte") == "instagram" and it.get("postado") and not it.get("video") and p.get("media_url"):
            print("  ~ #%s: tentando baixar de novo o video que faltava" % it["num"])
            if a.dry_run:
                continue
            try:
                baixa(p["media_url"], Path(a.pasta) / "videos" / ("arquivo-%s.mp4" % it["num"]), eh_mp4, 20)
                it["video"] = "videos/arquivo-%s.mp4" % it["num"]
                if p.get("thumbnail_url") and not it.get("capa"):
                    baixa(p["thumbnail_url"], Path(a.pasta) / "capas" / ("arquivo-%s.jpg" % it["num"]), eh_imagem, 1)
                    it["capa"] = "capas/arquivo-%s.jpg" % it["num"]
                mudou = True
            except ApiErro as e:
                print("      continua sem video (%s)" % e)
    novos = [p for p in reversed(posts) if p.get("id") not in conhecidos]
    videos = [p for p in novos if p.get("media_type") == "VIDEO"]
    print("Posts consultados: %d | ja conhecidos: %d | videos novos: %d | outros (foto/carrossel) ignorados: %d" % (
        len(posts), len(posts) - len(novos), len(videos), len(novos) - len(videos)))
    for p in videos:
        link = p.get("permalink", "")
        link = link if re.match(r"^https://(www\.)?instagram\.com/", link) else ""
        item, motivo = acha_arquivo(p.get("caption", ""), itens)
        resumo = (linhas_uteis(p.get("caption", "")) or ["(sem legenda)"])[0][:60]
        if not item:
            print("  - Post %s sem correspondencia (%s): \"%s\"" % (p.get("id"), motivo, resumo))
            if os.environ.get("GITHUB_ACTIONS"):
                print("::warning::Post do Instagram nao associado a nenhum Arquivo: \"%s\" (%s)" % (resumo, motivo))
            problemas += 1
            continue
        if item.get("ig_id") and item["ig_id"] != p["id"]:
            print("  - #%s ja esta ligado a outro post do Instagram; ignorei o post %s (\"%s\")" % (item["num"], p.get("id"), resumo))
            problemas += 1
            continue
        ja_no_ar = bool(item.get("postado"))
        print("  + #%s %s <- post %s (%s)%s" % (item["num"], item["jogo"], p["id"], motivo, " [so vincula o link: ja estava no ar]" if ja_no_ar else ""))
        if a.dry_run:
            continue
        item["ig_id"], item["permalink"], item["publicado_em"] = p["id"], link, p.get("timestamp", "")
        if not ja_no_ar:
            item["postado"], item["fonte"] = True, "instagram"
            item["legenda"] = (p.get("caption") or "").strip()[:5000]
            try:
                if not p.get("media_url"):
                    raise ApiErro("o Instagram nao devolveu o endereco do video")
                mb = baixa(p["media_url"], pasta / "videos" / ("arquivo-%s.mp4" % item["num"]), eh_mp4, 20) / 1048576
                item["video"] = "videos/arquivo-%s.mp4" % item["num"]
                print("      video baixado (%.1f MB)" % mb)
            except ApiErro as e:
                print("      Aviso: video nao baixado (%s). O card vai apontar para o post no Instagram." % e)
            if p.get("thumbnail_url"):
                try:
                    baixa(p["thumbnail_url"], pasta / "capas" / ("arquivo-%s.jpg" % item["num"]), eh_imagem, 1)
                    item["capa"] = "capas/arquivo-%s.jpg" % item["num"]
                except ApiErro as e:
                    print("      Aviso: capa nao baixada (%s)." % e)
        elif not item.get("legenda"):
            item["legenda"] = (p.get("caption") or "").strip()[:5000]
        mudou = True
    if mudou and not a.dry_run:
        grava_dados(arq, dados)
        print("dados.js atualizado.")
    elif not mudou:
        print("Nada novo para publicar.")
    saida_github(mudou="true" if mudou and not a.dry_run else "false")


if __name__ == "__main__":
    main()
