<p align="center">
  <img src="assets/icon.svg" alt="Mare logo" width="128" height="128">
</p>

<h1 align="center">Mare</h1>

<p align="center">Canadian tide predictions from DFO · Prédictions de marée canadiennes du MPO</p>

<p align="center"><b><a href="#english">English</a> · <a href="#français">Français</a></b></p>

> ### 🌊 Why “Mare”? · Pourquoi « Mare » ?
>
> *Mare* is Latin for **sea**. The name comes from Canada’s motto, ***A mari usque ad mare*** (“from sea to sea”). It is pronounced **MAH-reh** (/ˈma.re/).
>
> *Mare* signifie **mer** en latin. Le nom vient de la devise du Canada, ***A mari usque ad mare*** (« d’un océan à l’autre »). On le prononce **MA-ré** (/ˈma.re/).

---

## English

Mare brings Canadian tide predictions from **Fisheries and Oceans Canada (DFO)** into Home Assistant, and shows them on a dashboard card that labels **every high and low tide**.

It has two parts:

| Part | Folder | What it does |
|---|---|---|
| **Mare integration** (`dfo_tides`) | [`custom_components/dfo_tides`](custom_components/dfo_tides) | Adds a tide station from the UI (nearest stations suggested) and creates sensors: current tide level, next high tide, next low tide. |
| **Mare Tide Card** | [Mare-Tide-Card](https://github.com/olivierouellet/Mare-Tide-Card) | A Lovelace card with the tide curve, every high/low labelled with height and time, a span of up to 72 h, and a visual editor. English and French. |

The card works **with** the integration (it reads the tide level sensor) or **without** it (it downloads predictions directly from DFO for a station you pick in the card editor).

### Integration features

- **Set up from the UI**: *Settings → Devices & services → Add integration → Mare*. The 5 stations nearest your home are listed with their distance; you can move the map pin or search every station by name or code.
- **Change the station later** under *Configure*. Entity IDs don’t change, so your cards and automations keep working.
- **Sensors**
  - `sensor.<station>_tide_level`: predicted level right now (m), with `trend` (`rising`/`falling`), the whole 15-minute curve (`tide_data`) and the official high/low points (`tide_extremes`) for yesterday through the next 3 days. The two large attributes are not written to the recorder database.
  - `sensor.<station>_next_high_tide` and `sensor.<station>_next_low_tide`: timestamps, with the `height` as an attribute. Handy for automations.
- Predictions are downloaded once an hour; the current level is recalculated every 5 minutes (configurable).
- English and French interface.

### Installation

**With HACS (recommended)**

[![Open your Home Assistant instance and open this repository in HACS.](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=olivierouellet&repository=Mare&category=integration)

1. In Home Assistant, open **HACS** → **⋮** (top right) → **Custom repositories**.
2. Repository: `https://github.com/olivierouellet/Mare`, type: **Integration**, then **Add**. (The button above does steps 1 and 2 for you.)
3. Search for **Mare**, open it and click **Download**.
4. Restart Home Assistant.
5. Add the integration: *Settings → Devices & services → Add integration → Mare*, then pick your station.

HACS then shows new versions as updates.

**Manually:** copy `custom_components/dfo_tides` into your Home Assistant `config/custom_components/` folder, restart, and add the integration as in step 5.

**The card:** install the [Mare Tide Card](https://github.com/olivierouellet/Mare-Tide-Card) the same way, as a HACS custom repository of type **Dashboard**.

More details, including changing the station and troubleshooting, are in the **[Setup Guide](Setup%20Guide.md)**.

### Development

- Integration tests: `pytest` (needs `pytest-homeassistant-custom-component`, Python 3.13). They use recorded DFO responses in `tests/fixtures`.
- The card lives in its own repository: [olivierouellet/Mare-Tide-Card](https://github.com/olivierouellet/Mare-Tide-Card).
- The integration icon lives in `custom_components/dfo_tides/brand/` (Home Assistant 2026.3 or later shows it automatically). Its source is `assets/icon.svg`; after editing it, export `icon@2x.png` at 512×512 and `icon.png` at 256×256.

Data: Fisheries and Oceans Canada, [Integrated Water Level System API](https://api-iwls.dfo-mpo.gc.ca/). Predictions are not for navigation.

---

## Français

Mare intègre à Home Assistant les prédictions de marée de **Pêches et Océans Canada (MPO)** et les affiche dans une carte de tableau de bord qui indique **chaque marée haute et basse**.

Le projet comporte deux parties :

| Partie | Dossier | Rôle |
|---|---|---|
| **Intégration Mare** (`dfo_tides`) | [`custom_components/dfo_tides`](custom_components/dfo_tides) | Ajoute une station de marée depuis l’interface (stations les plus proches suggérées) et crée des capteurs : niveau de marée actuel, prochaine marée haute, prochaine marée basse. |
| **Carte Mare Tide Card** | [Mare-Tide-Card](https://github.com/olivierouellet/Mare-Tide-Card#français) | Une carte Lovelace avec la courbe de marée, chaque marée haute et basse identifiée avec sa hauteur et son heure, une plage allant jusqu’à 72 h et un éditeur visuel. En français et en anglais. |

La carte fonctionne **avec** l’intégration (elle lit le capteur de niveau de marée) ou **sans** elle (elle télécharge les prédictions directement de MPO pour une station choisie dans l’éditeur de la carte).

### Fonctionnalités de l’intégration

- **Configuration dans l’interface** : *Paramètres → Appareils et services → Ajouter une intégration → Mare*. Les 5 stations les plus proches de votre domicile sont proposées avec leur distance; vous pouvez déplacer l’épingle sur la carte ou chercher parmi toutes les stations par nom ou par code.
- **Changer de station plus tard** avec *Configurer*. Les identifiants d’entité ne changent pas : vos cartes et automatisations continuent de fonctionner.
- **Capteurs**
  - `sensor.<station>_niveau_de_maree` (ou `_tide_level` en anglais) : niveau prédit en ce moment (m), avec `trend` (`rising`/`falling`, montante/descendante), la courbe complète aux 15 minutes (`tide_data`) et les marées hautes et basses officielles (`tide_extremes`) d’hier jusqu’aux 3 prochains jours. Ces deux gros attributs ne sont pas enregistrés dans la base de données de l’historique.
  - Prochaine marée haute et prochaine marée basse : des horodatages, avec la hauteur (`height`) en attribut. Pratiques pour les automatisations.
- Les prédictions sont téléchargées une fois par heure; le niveau actuel est recalculé toutes les 5 minutes (réglable).
- Interface en français et en anglais.

### Installation

**Avec HACS (recommandé)**

[![Ouvrir votre instance Home Assistant et ce dépôt dans HACS.](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=olivierouellet&repository=Mare&category=integration)

1. Dans Home Assistant, ouvrez **HACS** → **⋮** (en haut à droite) → **Dépôts personnalisés**.
2. Dépôt : `https://github.com/olivierouellet/Mare`, type : **Intégration**, puis **Ajouter**. (Le bouton ci-dessus fait les étapes 1 et 2 pour vous.)
3. Cherchez **Mare**, ouvrez-la et cliquez sur **Télécharger**.
4. Redémarrez Home Assistant.
5. Ajoutez l’intégration : *Paramètres → Appareils et services → Ajouter une intégration → Mare*, puis choisissez votre station.

HACS affiche ensuite les nouvelles versions comme des mises à jour.

**Manuellement :** copiez `custom_components/dfo_tides` dans le dossier `config/custom_components/` de Home Assistant, redémarrez et ajoutez l’intégration comme à l’étape 5.

**La carte :** installez la [Mare Tide Card](https://github.com/olivierouellet/Mare-Tide-Card#français) de la même façon, comme dépôt personnalisé HACS de type **Dashboard** (tableau de bord).

Plus de détails, dont le changement de station et le dépannage, dans le **[guide d’installation](Setup%20Guide.md#français)**.

### Développement

- Tests de l’intégration : `pytest` (requiert `pytest-homeassistant-custom-component`, Python 3.13). Ils utilisent des réponses de MPO enregistrées dans `tests/fixtures`.
- La carte a son propre dépôt : [olivierouellet/Mare-Tide-Card](https://github.com/olivierouellet/Mare-Tide-Card#français).
- L’icône de l’intégration se trouve dans `custom_components/dfo_tides/brand/` (Home Assistant 2026.3 ou plus récent l’affiche automatiquement). Sa source est `assets/icon.svg`; après une modification, exportez `icon@2x.png` en 512×512 et `icon.png` en 256×256.

Données : Pêches et Océans Canada, [API du Système intégré des niveaux d’eau](https://api-iwls.dfo-mpo.gc.ca/). Les prédictions ne doivent pas servir à la navigation.
