# Kioskup — réplique statique

Réplique fidèle de [kioskup.be](https://www.kioskup.be/) en HTML/CSS/JS statique, sans dépendance
à Webflow. Le rendu a été vérifié identique à l'original (mêmes coordonnées au pixel près sur
l'ensemble des sections mesurées).

## Lancer le site

```bash
python3 serve.py     # http://127.0.0.1:8181
```

N'importe quel serveur de fichiers statiques convient (`npx serve`, Nginx, Netlify, GitHub Pages…).
Il n'y a ni build, ni dépendances à installer.

## Structure

```
index.html, les-editions.html, les-artistes.html,
le-projet.html, les-partenaires.html, contact.html   6 pages du menu principal
artistes/<slug>.html                                 70 fiches artistes
editions/<slug>.html                                 15 pages d'édition
assets/css/    kioskup.webflow.css (styles Webflow), splide-core.min.css
assets/fonts/  37 fichiers PP Fragment (.ttf)
assets/img/    675 images
assets/js/     jquery, webflow, luxy (parallax), splide (carrousel), finsweet, webfont
serve.py       serveur de prévisualisation local
```

Les URLs Webflow (`/les-editions`) sont devenues des fichiers (`les-editions.html`) ; les liens
internes ont été réécrits en conséquence. Si le site est déployé derrière un serveur capable de
réécrire les routes, ces liens peuvent être remis en URLs propres.

## Polices

Le site repose sur **PP Fragment** (Glare, Serif, Sans, Text — Pangram Pangram), une fonte
commerciale. Les fichiers proviennent du CDN Webflow du site d'origine et sont donc couverts par la
licence existante. Toute rediffusion publique doit rester dans le périmètre de cette licence.

## Écarts connus par rapport à l'original

Deux images sont cassées **sur le site en ligne lui-même** ; la réplique reproduit l'état tel quel :

- `background.jpg` sur la page Contact — hébergée sous un identifiant de site Webflow supprimé
  (`64cfe3ac…`), renvoie 403.
- `placeholder.60f9b1840c.svg` sur les pages d'édition — placeholder interne de Webflow, renvoie 403
  y compris depuis le navigateur.

Autres différences volontaires :

- **Google Analytics retiré** — une copie locale ne doit pas alimenter la propriété de mesure réelle.
  Le tag `G-47TZNXNLYP` peut être réinséré dans le `<head>` avant mise en production.
- **Liens externes conservés** — réseaux sociaux, sites d'artistes, embeds YouTube et Spotify
  pointent toujours vers leurs services d'origine.
- **Google Fonts** (PT Serif, Montserrat, Merriweather, Changa One, Inter) reste chargé depuis
  Google, comme sur l'original.
- Le formulaire de contact était géré par Webflow ; il s'affiche à l'identique mais n'a pas de
  backend et n'envoie rien. Il faut le brancher sur un service (Formspree, Netlify Forms…) avant
  toute mise en ligne.
