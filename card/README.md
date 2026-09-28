# Mare Tide Card

**[English](#english) · [Français](#français)**

> ### 🌊 Why “Mare”? · Pourquoi « Mare » ?
>
> *Mare* is Latin for **sea**. The name comes from Canada’s motto, ***A mari usque ad mare*** (“from sea to sea”, Psalm 72:8), because the card covers tide stations on every Canadian coast. It is pronounced **MAH-reh** (/ˈma.re/), two syllables: not the English *mare* (a horse), and not the French *mare* (a pond).
>
> *Mare* signifie **mer** en latin. Le nom vient de la devise du Canada, ***A mari usque ad mare*** (« d’un océan à l’autre », Psaume 72:8), puisque la carte couvre les stations de marée de toutes les côtes canadiennes. On le prononce **MA-ré** (/ˈma.re/), en deux syllabes : ce n’est ni la *mare* aux canards, ni le mot anglais *mare* (une jument).

---

## English

A Home Assistant dashboard card for Canadian tides from **Fisheries and Oceans Canada (DFO)**.

- The tide curve with **every high and low tide labelled** with its height and time.
- A time range of 6 to 72 hours, starting at midnight or around now.
- Current level, rising/falling trend, and the next high and low in the header.
- A marker for the current time, and a tooltip when you hover or drag across the chart.
- A visual editor, including a **station picker** that lists the stations nearest your home, can use your device’s position, and searches every station.
- **English and French**, following Home Assistant’s language or set per card.
- Follows your theme (light and dark) and your 12/24-hour setting.

### Two ways to get the data

1. **From the Mare integration (recommended).** Install the [Mare integration](../README.md) and pick its *tide level* sensor. Tides are downloaded once by Home Assistant, and you also get sensors for automations. To change the station, use *Configure* on the integration.
2. **Directly from DFO.** Pick a station in the card editor; no integration needed. Each open dashboard downloads the predictions itself (cached for 6 hours).

### Installation

**HACS (custom repository)**
1. HACS → ⋮ → *Custom repositories* → add this repository with the type **Dashboard**.
2. Install **Mare Tide Card**, then reload your browser.

**Manual**
1. Download `mare-tide-card.js` from the latest release (or build it: `yarn install && yarn build`, then use `dist/mare-tide-card.js`).
2. Copy it to `config/www/`.
3. *Settings → Dashboards → ⋮ → Resources → Add resource*: URL `/local/mare-tide-card.js`, type **JavaScript module**.

Then add the card from the card picker (search for “Mare”).

### Options

| Option | Default | Description |
|---|---|---|
| `entity` | — | Tide level sensor from the Mare integration. Use this **or** `station_id`. |
| `station_id` | — | DFO station ID, for direct mode (set by the editor’s station picker). |
| `station_name` | — | Station name shown as the title in direct mode (set by the editor). |
| `title` | station name | Card title. |
| `show_header` | `true` | Show the title, current level and next tides. |
| `show_current` | `true` | Show the current level, trend and next high/low in the header. |
| `span` | `day` | `day`: start at midnight today. `rolling`: start `hours_before` hours before now. |
| `hours` | `24` | Hours shown, from 6 to 72. |
| `hours_before` | `6` | With `span: rolling`, hours shown before now (0 to 24). |
| `height` | `220` | Chart height in pixels. |
| `color` | theme primary | Curve colour: a theme colour name (`blue`, `teal`, `accent`…) or any CSS colour. |
| `show_extremes` | `true` | Mark and label high and low tides. |
| `extreme_label` | `height_time` | `height_time`, `height` or `time`. With long spans on narrow cards, labels automatically shorten to the height, and any that still overlap are hidden. |
| `show_now` | `true` | Show the current time on the chart. |
| `precision` | `2` | Decimals for heights (0 to 3). |
| `language` | `auto` | `auto` (Home Assistant’s language), `en` or `fr`. |

### Examples

```yaml
type: custom:mare-tide-card
entity: sensor.halifax_tide_level
```

```yaml
type: custom:mare-tide-card
station_id: 5cebf1df3d0f4a073c4bbcbb
station_name: Halifax
span: rolling
hours: 48
hours_before: 6
extreme_label: height
color: teal
language: fr
```

### Development

- `yarn install`, then `yarn build` (lint, type check, bundle to `dist/`).
- `yarn start` rebuilds on change and serves on port 5050 (not 5000, which macOS uses for AirPlay):
  - `http://localhost:5050/` is a test page with a mock Home Assistant: several configurations, light/dark, EN/FR, phone width and the editor. URL options: `?dark&lang=fr&tf=24&width=320&direct&only=editor`.
  - Add `http://<your-computer>:5050/mare-tide-card.js` as a dashboard resource to try the live build in Home Assistant.
- Scaffolded from [custom-cards/boilerplate-card](https://github.com/custom-cards/boilerplate-card).

Data: Fisheries and Oceans Canada. Predictions are not for navigation.

---

## Français

Une carte de tableau de bord Home Assistant pour les marées canadiennes de **Pêches et Océans Canada (MPO)**.

- La courbe de marée avec **chaque marée haute et basse identifiée** par sa hauteur et son heure.
- Une plage de 6 à 72 heures, à partir de minuit ou autour de maintenant.
- Le niveau actuel, la tendance (montante ou descendante) et les prochaines marées haute et basse dans l’en-tête.
- Un repère pour l’heure actuelle et une infobulle au survol ou en glissant le doigt sur le graphique.
- Un éditeur visuel, avec un **sélecteur de station** qui propose les stations les plus proches de votre domicile, peut utiliser la position de votre appareil et permet de chercher parmi toutes les stations.
- **Français et anglais**, selon la langue de Home Assistant ou choisi pour chaque carte.
- Respecte votre thème (clair ou sombre) et votre format d’heure (12 h ou 24 h).

### Deux façons d’obtenir les données

1. **Avec l’intégration Mare (recommandé).** Installez l’[intégration Mare](../README.md#français) et choisissez son capteur de *niveau de marée*. Home Assistant télécharge les marées une seule fois, et vous obtenez aussi des capteurs pour vos automatisations. Pour changer de station, utilisez *Configurer* sur l’intégration.
2. **Directement de MPO.** Choisissez une station dans l’éditeur de la carte; aucune intégration requise. Chaque tableau de bord ouvert télécharge lui-même les prédictions (conservées en cache 6 heures).

### Installation

**HACS (dépôt personnalisé)**
1. HACS → ⋮ → *Dépôts personnalisés* → ajoutez ce dépôt avec le type **Dashboard** (tableau de bord).
2. Installez **Mare Tide Card**, puis rechargez votre navigateur.

**Manuelle**
1. Téléchargez `mare-tide-card.js` depuis la dernière version publiée (ou compilez-le : `yarn install && yarn build`, puis prenez `dist/mare-tide-card.js`).
2. Copiez-le dans `config/www/`.
3. *Paramètres → Tableaux de bord → ⋮ → Ressources → Ajouter une ressource* : URL `/local/mare-tide-card.js`, type **Module JavaScript**.

Ajoutez ensuite la carte depuis le sélecteur de cartes (cherchez « Mare »).

### Options

| Option | Défaut | Description |
|---|---|---|
| `entity` | — | Capteur de niveau de marée de l’intégration Mare. Utilisez ceci **ou** `station_id`. |
| `station_id` | — | Identifiant de station de MPO, pour le mode direct (rempli par le sélecteur de station de l’éditeur). |
| `station_name` | — | Nom de la station affiché comme titre en mode direct (rempli par l’éditeur). |
| `title` | nom de la station | Titre de la carte. |
| `show_header` | `true` | Afficher le titre, le niveau actuel et les prochaines marées. |
| `show_current` | `true` | Afficher le niveau actuel, la tendance et les prochaines marées dans l’en-tête. |
| `span` | `day` | `day` : à partir de minuit aujourd’hui. `rolling` : à partir de `hours_before` heures avant maintenant. |
| `hours` | `24` | Heures affichées, de 6 à 72. |
| `hours_before` | `6` | Avec `span: rolling`, heures affichées avant maintenant (0 à 24). |
| `height` | `220` | Hauteur du graphique en pixels. |
| `color` | couleur principale du thème | Couleur de la courbe : un nom de couleur du thème (`blue`, `teal`, `accent`…) ou toute couleur CSS. |
| `show_extremes` | `true` | Marquer et identifier les marées hautes et basses. |
| `extreme_label` | `height_time` | `height_time` (hauteur et heure), `height` (hauteur) ou `time` (heure). Pour les longues plages sur des cartes étroites, les étiquettes se réduisent automatiquement à la hauteur, et celles qui se chevauchent encore sont masquées. |
| `show_now` | `true` | Afficher l’heure actuelle sur le graphique. |
| `precision` | `2` | Décimales des hauteurs (0 à 3). |
| `language` | `auto` | `auto` (langue de Home Assistant), `en` ou `fr`. |

### Exemples

```yaml
type: custom:mare-tide-card
entity: sensor.halifax_niveau_de_maree
```

```yaml
type: custom:mare-tide-card
station_id: 5cebf1df3d0f4a073c4bbcbb
station_name: Halifax
span: rolling
hours: 48
hours_before: 6
extreme_label: height
color: teal
language: fr
```

### Développement

- `yarn install`, puis `yarn build` (analyse, vérification des types et paquet dans `dist/`).
- `yarn start` recompile à chaque modification et sert les fichiers sur le port 5050 (pas 5000, utilisé par AirPlay sur macOS) :
  - `http://localhost:5050/` est une page de test avec un Home Assistant simulé : plusieurs configurations, clair/sombre, FR/EN, largeur de téléphone et l’éditeur. Options d’URL : `?dark&lang=fr&tf=24&width=320&direct&only=editor`.
  - Ajoutez `http://<votre-ordinateur>:5050/mare-tide-card.js` comme ressource de tableau de bord pour essayer la version en développement dans Home Assistant.
- Basée sur [custom-cards/boilerplate-card](https://github.com/custom-cards/boilerplate-card).

Données : Pêches et Océans Canada. Les prédictions ne doivent pas servir à la navigation.
