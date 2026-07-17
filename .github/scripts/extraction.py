#!/usr/bin/env python3
"""Extrait le contenu des fiches artistes publiées.

Les 40 artistes absents d'Airtable ne sont jamais passés par Tally : ils
venaient du CMS Webflow. Leurs données ne sont pas perdues pour autant, elles
sont dans les pages du site — c'est ici qu'on les récupère.

Le CSV équivalent est tenu hors du dépôt car il agrège les adresses des
artistes. On relit donc les pages directement : même contenu, rien de plus
exposé que ce qui est déjà publié.
"""
import html
import re
from html.parser import HTMLParser
from pathlib import Path

RACINE = Path(__file__).resolve().parents[2]
BASE_URL = "https://kioskup.be"

# L'icône d'un lien dit à quelle plateforme il mène.
ICONES = {
    "linkedin": "Linkedin",
    "tiktok": "Tik Tok",
    "facebook": "facebook",
    "spotify": "spotify",
    "deezer": "deezer",
    "mail": "Email",
    "soundcloud": "soundcloud",
    "youtube": "youtube",
    "frame-656": "instagram",       # l'icône Instagram est exportée sous ce nom
    "web-social-logo": "web",
}

CLASSES = {
    "titre z": "Nom artiste",
    "style-musical stylepageartistes": "Genre",
    "text-block-24": "miniphrase de présentation",
    "source-pic-couv": "source couverture",
    "txt w-richtext": "bio",
}


class Fiche(HTMLParser):
    """Un parseur plutôt qu'une expression régulière : l'ordre des attributs
    varie d'une page à l'autre."""

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.slug = ""
        self.champs = {}
        self.couverture = ""
        self.liens = {}
        self._cible = None
        self._tampon = []
        self._profondeur = 0
        self._lien = None

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)

        if tag == "html" and a.get("data-wf-item-slug"):
            self.slug = a["data-wf-item-slug"]
        if tag == "meta" and a.get("property") == "og:image":
            self.couverture = a.get("content", "")

        cls = (a.get("class") or "").strip()

        if tag == "a" and "link-block-11" in cls:
            self._lien = a.get("href", "")
        if tag == "img" and self._lien is not None:
            fichier = (a.get("src") or "").split("/")[-1].lower()
            fichier = re.sub(r"^[0-9a-f]{6}_", "", fichier).rsplit(".", 1)[0]
            champ = ICONES.get(fichier)
            # href="#" : Webflow rend l'icône même quand le champ est vide.
            if champ and self._lien and self._lien != "#":
                self.liens[champ] = html.unescape(self._lien)
            self._lien = None

        if self._cible:
            self._profondeur += 1
            if self._cible == "bio" and tag in ("p", "br"):
                self._tampon.append("\n")
            return

        if cls in CLASSES:
            self._cible = CLASSES[cls]
            self._tampon = []
            self._profondeur = 0

    def handle_endtag(self, tag):
        if not self._cible:
            return
        if self._profondeur == 0:
            texte = "".join(self._tampon)
            texte = re.sub(r"[ \t]+", " ", texte)
            texte = re.sub(r"\n\s*\n+", "\n\n", texte).strip()
            self.champs.setdefault(self._cible, texte)
            self._cible = None
        else:
            self._profondeur -= 1

    def handle_data(self, data):
        if self._cible:
            self._tampon.append(data)


def lire_fiche(p: Path) -> dict:
    f = Fiche()
    f.feed(p.read_text(encoding="utf-8", errors="replace"))

    d = {"slug": f.slug or p.stem}
    d.update(f.champs)
    d.update(f.liens)

    if d.get("Email", "").startswith("mailto:"):
        d["Email"] = d["Email"][7:]
    if f.couverture:
        d["couverture"] = BASE_URL + f.couverture.replace("../", "/")

    return {k: v for k, v in d.items() if v}


def toutes_les_fiches() -> dict:
    """slug -> champs, pour les 70 pages publiées."""
    return {
        d["slug"]: d
        for d in (lire_fiche(p) for p in sorted((RACINE / "artistes").glob("*.html")))
    }


if __name__ == "__main__":
    fiches = toutes_les_fiches()
    print(f"{len(fiches)} fiches extraites")
    for s, d in list(fiches.items())[:3]:
        print(f"  {s}: {d.get('Nom artiste')} — {len(d)} champs")
