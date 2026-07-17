#!/usr/bin/env python3
"""Compare la base Airtable aux fiches artistes publiées. Ne modifie rien.

Le journal des Actions n'étant pas lisible publiquement, toute erreur est
écrite dans rapport-artistes.md, qui est committé quoi qu'il arrive.

Le dépôt est public : le rapport ne contient que des informations déjà
publiées (noms d'artistes). Les statuts ne sont donnés qu'en totaux, jamais
individuellement, et les champs internes (e-mail, fiches techniques,
commentaires) ne sont ni lus ni exposés.
"""
import json
import os
import pathlib
import re
import traceback
import unicodedata
import urllib.error
import urllib.parse
import urllib.request

BASE = "appUbHPkquG7bXSxJ"
TABLE = "tblvRWQHFtKwcfcpn"
RAPPORT = pathlib.Path("rapport-artistes.md")

CHAMPS_URL = [
    "web", "instagram", "Tik Tok", "youtube", "spotify",
    "Linkedin", "facebook", "soundcloud", "video youtube ou autre",
]


def ecrire(lignes):
    RAPPORT.write_text("\n".join(lignes) + "\n", encoding="utf-8")
    print("\n".join(lignes))


def echouer(msg):
    ecrire(["# Audit Airtable / site", "", "## Échec", "", "```", msg, "```"])
    raise SystemExit(0)  # 0 : on veut que l'étape suivante committe le rapport


def slug(s):
    """Reproduit la forme des URLs Webflow : sans accent, en minuscules."""
    s = unicodedata.normalize("NFKD", s or "")
    s = "".join(c for c in s if not unicodedata.combining(c))
    return re.sub(r"[^a-zA-Z0-9]+", "-", s).strip("-").lower()


def statut(fields):
    """Le champ Statut peut être un choix simple (chaîne) ou multiple (liste)
    selon la façon dont la colonne a été créée : on accepte les deux."""
    v = fields.get("Statut")
    if isinstance(v, list):
        return v[0].strip() if v else ""
    return (v or "").strip()


def sans_accent(s):
    """« Validé » peut arriver en Unicode composé (é) ou décomposé (e + accent) :
    visuellement identiques, mais différents à la comparaison. On compare donc
    des formes dépouillées."""
    s = unicodedata.normalize("NFKD", s or "")
    return "".join(c for c in s if not unicodedata.combining(c)).strip().lower()


def est_valide(fields):
    return sans_accent(statut(fields)) == "valide"


def lire_base(token):
    records, offset = [], None
    while True:
        url = f"https://api.airtable.com/v0/{BASE}/{TABLE}?pageSize=100"
        if offset:
            url += "&offset=" + urllib.parse.quote(offset)
        req = urllib.request.Request(url, headers={"Authorization": f"Bearer {token}"})
        with urllib.request.urlopen(req, timeout=30) as r:
            data = json.load(r)
        records += data.get("records", [])
        offset = data.get("offset")
        if not offset:
            return records


def main():
    token = os.environ.get("AIRTABLE_TOKEN")
    if not token:
        echouer("Secret AIRTABLE_TOKEN absent du dépôt.")

    try:
        records = lire_base(token)
    except urllib.error.HTTPError as e:
        echouer(f"Airtable a répondu {e.code}\n{e.read().decode('utf-8', 'replace')[:600]}")

    # Statuts : totaux seulement.
    statuts = {}
    for rec in records:
        v = statut(rec["fields"]) or "(vide)"
        statuts[v] = statuts.get(v, 0) + 1

    pages = {p.stem for p in pathlib.Path("artistes").glob("*.html")}

    valides, sans_nom = [], 0
    for rec in records:
        f = rec["fields"]
        if not est_valide(f):
            continue
        nom = (f.get("Nom artiste") or "").strip()
        if nom:
            valides.append(nom)
        else:
            sans_nom += 1

    slugs = {slug(n): n for n in valides}
    manquants = {s: n for s, n in slugs.items() if s not in pages}
    orphelins = sorted(pages - set(slugs))

    # Qualité des liens : ce qui produirait un lien mort sur la fiche.
    soucis = []
    for rec in records:
        f = rec["fields"]
        if not est_valide(f):
            continue
        nom = (f.get("Nom artiste") or "?").strip() or "?"
        for champ in CHAMPS_URL:
            v = (f.get(champ) or "").strip()
            if not v:
                continue
            if v.startswith("@") or not re.match(r"^https?://", v):
                soucis.append((nom, champ, v, "pas une URL complète — corrigeable"))
            elif champ != "web" and re.match(r"^https?://(www\.)?[^/]+/?$", v):
                soucis.append((nom, champ, v, "mène à l'accueil du service, pas à un profil"))

    L = ["# Audit Airtable / site", ""]
    L.append(f"- Entrées dans la base : **{len(records)}**")
    L.append(f"- Fiches publiées sur le site : **{len(pages)}**")
    L.append(f"- Validées exploitables : **{len(valides)}**")
    L += ["", "## Statuts (totaux)", ""]
    for k, v in sorted(statuts.items(), key=lambda x: -x[1]):
        L.append(f"- {k} : **{v}**")

    # Forme brute des valeurs : deux chaînes peuvent s'afficher pareil et différer
    # (accent composé ou non, espace en trop). Sans ça, un filtre qui ne retient
    # rien reste inexplicable.
    if not valides and records:
        brut = {repr(rec["fields"].get("Statut")) for rec in records}
        L += ["", "### Diagnostic", "",
              "Aucune entrée validée alors que la base en compte. Valeurs brutes :", ""]
        for b in sorted(brut):
            L.append(f"- `{b}`")
        champs = sorted({c for rec in records for c in rec["fields"]})
        L += ["", "Champs réellement présents :", "", "```", ", ".join(champs), "```"]
    if sans_nom:
        L += ["", f"⚠️ **{sans_nom}** entrée(s) validée(s) sans « Nom artiste » : "
              "aucune fiche ne peut être générée pour elles."]

    L += ["", f"## Validés absents du site : {len(manquants)}", ""]
    L.append("La génération **créerait** ces fiches." if manquants else "_Aucun._")
    for s, n in sorted(manquants.items(), key=lambda x: x[1].lower()):
        L.append(f"- {n} → `artistes/{s}.html`")

    L += ["", f"## Fiches en ligne absentes de la base : {len(orphelins)}", ""]
    L.append("⚠️ La génération les **supprimerait**." if orphelins else "_Aucune._")
    for s in orphelins:
        L.append(f"- `artistes/{s}.html`")

    # Correspondance nom Airtable -> page du site. Sert à savoir quels artistes
    # manquent réellement, pour ne leur livrer que ceux-là : une fusion
    # écraserait leurs données Tally par celles, moins bonnes, du site.
    L += ["", "## Correspondance Airtable → site", "",
          "Noms tels que saisis dans la base, et page correspondante.", ""]
    for n in sorted(valides, key=str.lower):
        s = slug(n)
        etat = f"`{s}.html`" if s in pages else "**aucune page**"
        L.append(f"- {n} → {etat}")

    L += ["", f"## Liens douteux : {len(soucis)}", ""]
    L.append("_Aucun._" if not soucis else "")
    for nom, champ, v, why in sorted(soucis):
        L.append(f"- **{nom}** / {champ} : `{v}` — {why}")

    ecrire(L)


if __name__ == "__main__":
    try:
        main()
    except SystemExit:
        raise
    except Exception:
        echouer(traceback.format_exc())
