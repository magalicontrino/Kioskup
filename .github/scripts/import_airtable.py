#!/usr/bin/env python3
"""Complète la base Airtable : corrige les slugs et ajoute les artistes absents.

Les extensions Airtable étant réservées aux forfaits payants, l'import CSV
fusionné est impossible ; on passe donc par l'API.

Deux opérations, et deux seulement :
  1. renseigner `slug` sur les lignes existantes, en les retrouvant par leur nom
  2. créer les artistes publiés que la base ignore

Rien n'est jamais supprimé, et aucun autre champ des lignes existantes n'est
touché : leurs données viennent de Tally, saisies par les artistes eux-mêmes,
et valent mieux que ce qu'on extrait du HTML.

Simulation par défaut. Il faut ECRIRE=oui pour que quoi que ce soit parte.
"""
import json
import os
import pathlib
import sys
import traceback
import urllib.error
import re
import unicodedata
import urllib.parse
import urllib.request

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from extraction import toutes_les_fiches  # noqa: E402

BASE = "appUbHPkquG7bXSxJ"
TABLE = "tblvRWQHFtKwcfcpn"
RAPPORT = pathlib.Path("rapport-import.md")
ECRIRE = os.environ.get("ECRIRE", "").strip().lower() in ("oui", "true", "1")

# Nom tel que saisi dans Airtable -> page publiée correspondante.
# Le nom seul ne suffit pas : « Captain » contre « Captaine », ou une adresse
# figée sur l'ancien nom (Odile Poireau publiée sous elodie-kempenaer).
CORRESPONDANCE = {
    "Agojie": "agojie",
    "ALCHEME": "alcheme",
    "Angatu Eleyê": "angatu-eleye",
    "Anna Winkin": "anna-winkin",
    "Camina Dance School": "camina",
    "Captain Frakas": "captaine-frakas",
    "Cassiof": "cassiof",
    "Clémence en flammes": "clemence-en-flammes",
    "Comtesse Florette": "comtesse-florette",
    "Eric Lang / Easygoprod": "eric-lang",
    "Fuego dance": "fuego-dance",
    "Gaélane": "gaelane",
    "Gerard Spencer": "gerard-spencer",
    "Hicham": "hicham",
    "JoBee Project": "jobee-project",
    "Johara": "johara",
    "Legoattini": "",           # jamais publié : reste sans page
    "Marie Darah": "marie-darah",
    "Mike & Tenzen - Acoustic shamanic folk music project": "mike-tenzen",
    "moonmood": "moonmood",
    "Nadjad": "nadjad-bacar-2",
    "Nina Morales": "nina-morales",
    "Nonante2": "nonante-2",
    "Nousssss": "nousssss",
    "Odile Poireau": "elodie-kempenaer",
    "ramythologie": "ramythologie",
    "Rogine": "rogine",
    "Saint December": "saint-december",
    "Talip": "talip",
    "Trio Audelia": "trio-audelia",
    "WI$E NIGG": "wi-e-nigg",
}

# Champs de la base qu'on sait remplir depuis une page.
CHAMPS = [
    "slug", "Nom artiste", "Genre", "miniphrase de présentation", "bio",
    "Email", "web", "instagram", "Tik Tok", "youtube", "spotify",
    "Linkedin", "facebook", "soundcloud", "source couverture",
]

# Nom du champ côté Airtable quand il diffère du nôtre. La colonne
# « miniphrase de présentation » a été créée avec une espace initiale : l'API
# est littérale et rejette tout le lot si le nom ne correspond pas au caractère
# près.
NOMS_AIRTABLE = {
    "miniphrase de présentation": " miniphrase de présentation",
}

# `Genre` est une liste de choix : la valeur doit être un tableau.
MULTI = {"Genre"}


def ecrire_rapport(lignes):
    RAPPORT.write_text("\n".join(lignes) + "\n", encoding="utf-8")
    print("\n".join(lignes))


def echouer(msg):
    ecrire_rapport(["# Import Airtable", "", "## Échec", "", "```", msg, "```"])
    raise SystemExit(0)  # 0 : l'étape suivante doit committer le rapport


def api(url, token, methode="GET", corps=None):
    data = json.dumps(corps).encode() if corps is not None else None
    req = urllib.request.Request(url, data=data, method=methode)
    req.add_header("Authorization", f"Bearer {token}")
    if data:
        req.add_header("Content-Type", "application/json")
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.load(r)


def lire_base(token):
    records, offset = [], None
    while True:
        url = f"https://api.airtable.com/v0/{BASE}/{TABLE}?pageSize=100"
        if offset:
            url += "&offset=" + urllib.parse.quote(offset)
        d = api(url, token)
        records += d.get("records", [])
        offset = d.get("offset")
        if not offset:
            return records


GENRES_AIRTABLE = ["musique", "slam", "poésie", "danse", "stand up",
                   "conte", "théâtre", "cirque"]


def _forme(s):
    """Rapproche « Stand-up » de « stand up » : minuscules, sans accent, et
    tirets ramenés à des espaces."""
    s = unicodedata.normalize("NFKD", s or "")
    s = "".join(c for c in s if not unicodedata.combining(c))
    return re.sub(r"[\s_-]+", " ", s).strip().lower()


_INDEX = {_forme(g): g for g in GENRES_AIRTABLE}


def valeur_genre(v):
    """Le Genre du site est une chaîne (« Slam ») ; Airtable attend une liste,
    et n'accepte que les choix déjà définis — au caractère près. On rapproche
    donc chaque valeur d'un choix existant, sans jamais en inventer."""
    trouves, ignores = [], []
    for brut in str(v).split(","):
        brut = brut.strip()
        if not brut:
            continue
        choix = _INDEX.get(_forme(brut))
        (trouves if choix else ignores).append(choix or brut)
    return trouves, ignores


def main():
    token = os.environ.get("AIRTABLE_WRITE_TOKEN")
    if not token:
        echouer("Secret AIRTABLE_WRITE_TOKEN absent du dépôt.")

    fiches = toutes_les_fiches()
    try:
        records = lire_base(token)
    except urllib.error.HTTPError as e:
        echouer(f"Airtable a répondu {e.code}\n{e.read().decode('utf-8', 'replace')[:600]}")

    # 1. Slugs à corriger sur les lignes existantes.
    corrections, inconnus = [], []
    for rec in records:
        nom = (rec["fields"].get("Nom artiste") or "").strip()
        actuel = (rec["fields"].get("slug") or rec["fields"].get("Slug") or "").strip()
        if nom not in CORRESPONDANCE:
            inconnus.append(nom or "(sans nom)")
            continue
        attendu = CORRESPONDANCE[nom]
        if actuel != attendu:
            corrections.append((rec["id"], nom, actuel, attendu))

    # 2. Artistes publiés que la base ignore.
    couverts = {s for s in CORRESPONDANCE.values() if s}
    a_creer = [fiches[s] for s in sorted(fiches) if s not in couverts]

    L = ["# Import Airtable", ""]
    L.append(f"Mode : **{'ÉCRITURE' if ECRIRE else 'simulation — rien ne sera modifié'}**")
    L += ["", f"- Lignes dans la base : **{len(records)}**",
          f"- Fiches publiées : **{len(fiches)}**", ""]

    L += [f"## Slugs à corriger : {len(corrections)}", ""]
    for _, nom, actuel, attendu in sorted(corrections, key=lambda x: x[1].lower()):
        L.append(f"- {nom} : `{actuel or '(vide)'}` → `{attendu or '(vide)'}`")

    if inconnus:
        L += ["", f"⚠️ **Noms inconnus de la correspondance : {len(inconnus)}**", "",
              "Ces lignes seront laissées telles quelles.", ""]
        L += [f"- {n}" for n in sorted(inconnus)]

    L += ["", f"## Artistes à créer : {len(a_creer)}", ""]
    for d in a_creer:
        L.append(f"- {d.get('Nom artiste')} → `{d['slug']}`")

    if not ECRIRE:
        L += ["", "---", "",
              "Simulation : aucune modification envoyée. "
              "Relancer avec `ECRIRE=oui` pour appliquer."]
        ecrire_rapport(L)
        return

    # --- Écriture ---
    faits, erreurs = 0, []

    for i in range(0, len(corrections), 10):   # l'API accepte 10 lignes par appel
        lot = corrections[i:i + 10]
        corps = {"records": [{"id": rid, "fields": {"slug": attendu}}
                             for rid, _, _, attendu in lot]}
        try:
            api(f"https://api.airtable.com/v0/{BASE}/{TABLE}", token, "PATCH", corps)
            faits += len(lot)
        except urllib.error.HTTPError as e:
            erreurs.append(f"correction: {e.code} {e.read().decode('utf-8', 'replace')[:200]}")

    crees = 0
    genres_ignores = []
    for i in range(0, len(a_creer), 10):
        lot = a_creer[i:i + 10]
        corps = {"records": []}
        for d in lot:
            f = {}
            for c in CHAMPS:
                v = d.get(c)
                if not v:
                    continue
                if c in MULTI:
                    ok, inconnus_g = valeur_genre(v)
                    if inconnus_g:
                        genres_ignores.append(f"{d.get('Nom artiste')} : {', '.join(inconnus_g)}")
                    if not ok:
                        continue
                    f[NOMS_AIRTABLE.get(c, c)] = ok
                else:
                    f[NOMS_AIRTABLE.get(c, c)] = v
            f["slug"] = d["slug"]
            # Une création n'est jamais publiée d'office : c'est vous qui validez.
            f["Statut"] = ["À vérifier"]
            corps["records"].append({"fields": f})
        try:
            api(f"https://api.airtable.com/v0/{BASE}/{TABLE}", token, "POST", corps)
            crees += len(lot)
        except urllib.error.HTTPError as e:
            erreurs.append(f"création: {e.code} {e.read().decode('utf-8', 'replace')[:300]}")

    L += ["", "---", "", "## Résultat", "",
          f"- Slugs corrigés : **{faits}** / {len(corrections)}",
          f"- Artistes créés : **{crees}** / {len(a_creer)}"]
    if genres_ignores:
        L += ["", "### Genres non reconnus (champ laissé vide)", ""]
        L += [f"- {g}" for g in genres_ignores]
    if erreurs:
        L += ["", "### Erreurs", ""] + [f"- `{e}`" for e in erreurs]
    ecrire_rapport(L)


if __name__ == "__main__":
    try:
        main()
    except SystemExit:
        raise
    except Exception:
        echouer(traceback.format_exc())
