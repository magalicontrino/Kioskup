#!/usr/bin/env python3
"""Met à jour les fiches artistes à partir d'Airtable.

On **modifie** les pages existantes, on ne les régénère pas : chaque fiche
contient des éléments qu'Airtable ignore — le lien vers l'édition où l'artiste
s'est produit, sa vignette, une vidéo intégrée. Les régénérer les effacerait.

Seuls les champs connus de la base sont réécrits. Le reste n'est pas touché.

Simulation par défaut : il faut ECRIRE=oui pour modifier les fichiers.
"""
import html
import json
import os
import pathlib
import re
import sys
import traceback
import unicodedata
import urllib.error
import urllib.parse
import urllib.request

RACINE = pathlib.Path(__file__).resolve().parents[2]
BASE = "appUbHPkquG7bXSxJ"
TABLE = "tblvRWQHFtKwcfcpn"
RAPPORT = pathlib.Path("rapport-generation.md")
ECRIRE = os.environ.get("ECRIRE", "").strip().lower() in ("oui", "true", "1")

MINIPHRASE = " miniphrase de présentation"   # espace initiale : nom réel du champ

# Icône du lien -> champ Airtable qui l'alimente.
ICONES = {
    "linkedin": "Linkedin",
    "tiktok": "Tik Tok",
    "facebook": "facebook",
    "spotify": "spotify",
    "deezer": "deezer",
    "mail": "Email",
    "soundcloud": "soundcloud",
    "youtube": "youtube",
    "frame-656": "instagram",
    "web-social-logo": "web",
}

# Un profil ne vit jamais à la racine du service : une telle URL est un lien mort.
RACINES_MORTES = re.compile(
    r"^https?://(www\.)?(instagram\.com|facebook\.com|youtube\.com|tiktok\.com|"
    r"soundcloud\.com|open\.spotify\.com|linkedin\.com)/?$", re.I)


def ecrire_rapport(lignes):
    RAPPORT.write_text("\n".join(lignes) + "\n", encoding="utf-8")
    print("\n".join(lignes))


def echouer(msg):
    ecrire_rapport(["# Génération des fiches", "", "## Échec", "", "```", msg, "```"])
    raise SystemExit(0)


def sans_accent(s):
    s = unicodedata.normalize("NFKD", s or "")
    return "".join(c for c in s if not unicodedata.combining(c)).strip().lower()


def est_valide(f):
    v = f.get("Statut")
    v = (v[0] if v else "") if isinstance(v, list) else (v or "")
    return sans_accent(v) == "valide"


def lire_base(token):
    records, offset = [], None
    while True:
        url = f"https://api.airtable.com/v0/{BASE}/{TABLE}?pageSize=100"
        if offset:
            url += "&offset=" + urllib.parse.quote(offset)
        req = urllib.request.Request(url, headers={"Authorization": f"Bearer {token}"})
        with urllib.request.urlopen(req, timeout=30) as r:
            d = json.load(r)
        records += d.get("records", [])
        offset = d.get("offset")
        if not offset:
            return records


def normaliser_lien(v, champ):
    """Les artistes saisissent ce qu'ils veulent dans Tally. On rattrape ce qui
    est rattrapable et on écarte ce qui mènerait dans le vide — mieux vaut pas
    d'icône qu'une icône morte."""
    v = (v or "").strip()
    if not v:
        return ""
    if champ == "Email":
        return v
    if v.startswith("@"):   # « @fuegodance.be » : un pseudo, pas une adresse
        service = {"instagram": "https://www.instagram.com/",
                   "Tik Tok": "https://www.tiktok.com/@",
                   "facebook": "https://www.facebook.com/"}.get(champ)
        return service + v.lstrip("@") if service else ""
    if not re.match(r"^https?://", v):
        if "." not in v.split("/")[0]:   # « nadjad.slam » n'est pas un domaine
            service = {"instagram": "https://www.instagram.com/",
                       "Tik Tok": "https://www.tiktok.com/@",
                       "facebook": "https://www.facebook.com/"}.get(champ)
            return service + v if service else ""
        v = "https://" + v
    if RACINES_MORTES.match(v):
        return ""
    return v


def champ(f, nom):
    v = f.get(nom)
    if isinstance(v, list):
        v = ", ".join(str(x) for x in v)
    return (v or "").strip()


def maj_texte(t, classe, valeur):
    """Remplace le contenu d'un <div class="..."> par une valeur échappée."""
    motif = re.compile(r'(<div class="' + re.escape(classe) + r'">)([^<]*)(</div>)')
    return motif.sub(lambda m: m.group(1) + html.escape(valeur) + m.group(3), t, count=1)


def maj_liens(t, f):
    """Réécrit chaque bloc de lien selon la valeur du champ correspondant.
    Webflow masque un lien vide par la classe w-condition-invisible ; on
    reproduit exactement ce comportement."""
    def remplacer(m):
        bloc = m.group(0)
        icone = re.search(r'src="[^"]*?/(?:[0-9a-f]{6}_)?([^"/]+?)\.svg"', bloc, re.I)
        if not icone:
            return bloc
        nom_champ = ICONES.get(icone.group(1).lower())
        if not nom_champ:
            return bloc

        brut = champ(f, nom_champ)
        url = normaliser_lien(brut, nom_champ)
        if nom_champ == "Email" and url:
            url = "mailto:" + url

        if url:
            ouvre = (f'<a href="{html.escape(url, quote=True)}"'
                     + ('' if nom_champ == "Email" else ' target="_blank"')
                     + ' class="link-block-11 w-inline-block">')
        else:
            ouvre = '<a href="#" class="link-block-11 w-inline-block w-condition-invisible">'
        return re.sub(r"^<a[^>]*>", ouvre, bloc, count=1)

    return re.sub(r'<a [^>]*class="link-block-11[^"]*"[^>]*>.*?</a>', remplacer, t, flags=re.S)


def maj_bio(t, bio):
    """La bio est du texte riche : chaque paragraphe devient un <p>."""
    if not bio:
        return t
    corps = "".join(f"<p>{html.escape(p.strip())}</p>"
                    for p in re.split(r"\n\s*\n", bio) if p.strip())
    return re.sub(r'(<div class="txt w-richtext">)(.*?)(</div>)',
                  lambda m: m.group(1) + corps + m.group(3), t, count=1, flags=re.S)


def maj_metas(t, nom, mini):
    # [^"]* et non .*? : le document tient sur une seule ligne, et une capture
    # permissive traverse les guillemets pour avaler les balises voisines.
    for motif, val in [
        (r'(<title>)([^<]*)(</title>)', nom),
        (r'(<meta content=")([^"]*)(" name="description"/>)', mini),
        (r'(<meta content=")([^"]*)(" property="og:title"/>)', nom),
        (r'(<meta content=")([^"]*)(" property="og:description"/>)', mini),
        (r'(<meta content=")([^"]*)(" name="twitter:title"/>)', nom),
        (r'(<meta content=")([^"]*)(" name="twitter:description"/>)', mini),
    ]:
        t = re.sub(motif, lambda m, v=val: m.group(1) + html.escape(v) + m.group(3),
                   t, count=1)
    return t


def appliquer(page: pathlib.Path, f: dict):
    avant = page.read_text(encoding="utf-8")
    t = avant

    nom = champ(f, "Nom artiste")
    genre = champ(f, "Genre")
    mini = champ(f, MINIPHRASE) or champ(f, "miniphrase de présentation")
    source = champ(f, "source couverture")
    bio = champ(f, "bio")

    if nom:
        t = maj_texte(t, "titre z", nom)
        t = maj_texte(t, "text-block-54", nom)
    if genre:
        t = maj_texte(t, "style-musical stylepageartistes", genre)
    if mini:
        t = maj_texte(t, "text-block-24", mini)
    if source:
        t = maj_texte(t, "source-pic-couv", source)
    t = maj_bio(t, bio)
    t = maj_liens(t, f)
    if nom and mini:
        t = maj_metas(t, nom, mini)

    return avant, t


def main():
    token = os.environ.get("AIRTABLE_TOKEN")
    if not token:
        echouer("Secret AIRTABLE_TOKEN absent du dépôt.")

    try:
        records = lire_base(token)
    except urllib.error.HTTPError as e:
        echouer(f"Airtable a répondu {e.code}\n{e.read().decode('utf-8', 'replace')[:600]}")

    modifiees, inchangees, sans_page = [], [], []
    for rec in records:
        f = rec["fields"]
        if not est_valide(f):
            continue
        s = (f.get("slug") or f.get("Slug") or "").strip()
        if not s:
            continue
        page = RACINE / "artistes" / f"{s}.html"
        if not page.exists():
            sans_page.append((champ(f, "Nom artiste"), s))
            continue

        avant, apres = appliquer(page, f)
        if avant == apres:
            inchangees.append(s)
        else:
            modifiees.append(s)
            if ECRIRE:
                page.write_text(apres, encoding="utf-8")

    L = ["# Génération des fiches", ""]
    L.append(f"Mode : **{'ÉCRITURE' if ECRIRE else 'simulation — aucun fichier modifié'}**")
    L += ["", f"- Fiches validées traitées : **{len(modifiees) + len(inchangees)}**",
          f"- Modifiées : **{len(modifiees)}**",
          f"- Déjà conformes : **{len(inchangees)}**"]
    if sans_page:
        L += ["", f"## Validés sans page : {len(sans_page)}", "",
              "Une fiche neuve reste à créer pour eux — non couvert à ce stade.", ""]
        L += [f"- {n} → `{s}`" for n, s in sans_page]
    if modifiees:
        L += ["", "## Fiches modifiées", ""] + [f"- `{s}.html`" for s in sorted(modifiees)]
    if not ECRIRE:
        L += ["", "---", "", "Simulation. Relancer avec `ECRIRE=oui` pour appliquer."]
    ecrire_rapport(L)


if __name__ == "__main__":
    try:
        main()
    except SystemExit:
        raise
    except Exception:
        echouer(traceback.format_exc())
