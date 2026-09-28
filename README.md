# Mare

**[English](#english) · [Français](#français)**

> ### 🌊 Why “Mare”? · Pourquoi « Mare » ?
>
> *Mare* is Latin for **sea**. The name comes from Canada’s motto, ***A mari usque ad mare*** (“from sea to sea”, Psalm 72:8), because this project covers tide stations on every Canadian coast. It is pronounced **MAH-reh** (/ˈma.re/), two syllables: not the English *mare* (a horse), and not the French *mare* (a pond).
>
> *Mare* signifie **mer** en latin. Le nom vient de la devise du Canada, ***A mari usque ad mare*** (« d’un océan à l’autre », Psaume 72:8), puisque ce projet couvre les stations de marée de toutes les côtes canadiennes. On le prononce **MA-ré** (/ˈma.re/), en deux syllabes : ce n’est ni la *mare* aux canards, ni le mot anglais *mare* (une jument).

---

## English

Mare brings Canadian tide predictions from **Fisheries and Oceans Canada (DFO)** into Home Assistant, and shows them on a dashboard card that labels **every high and low tide**.

It has two parts:

| Part | Folder | What it does |
|---|---|---|
| **Mare integration** (`dfo_tides`) | [`custom_components/dfo_tides`](custom_components/dfo_tides) | Adds a tide station from the UI (nearest stations suggested) and creates sensors: current tide level, next high tide, next low tide. |
| **Mare Tide Card** | [`card/`](card) | A Lovelace card with the tide curve, every high/low labelled with height and time, a span of up to 72 h, and a visual editor. English and French. |

The card works **with** the integration (it reads the tide level sensor) or **without** it (it downloads predictions directly from DFO for a station you pick in the card editor).

### Integration features

- **Set up from the UI**: *Settings → Devices & services → Add integration → Mare*. The 5 stations nearest your home are listed with their distance; you can move the map pin or search every station by name or code.
- **Change the station later** under *Configure*. Entity IDs don’t change, so your cards and automations keep working.
- **Sensors**
  - `sensor.<station>_tide_level`: predicted level right now (m), with `trend` (`rising`/`falling`), the whole 15-minute curve (`tide_data`) and the official high/low points (`tide_extremes`) for yesterday through the next 3 days. The two large attributes are not written to the recorder database.
  - `sensor.<station>_next_high_tide` and `sensor.<station>_next_low_tide`: timestamps, with the `height` as an attribute. Handy for automations.
- Predictions are downloaded once an hour; the current level is recalculated every 5 minutes (configurable).
- English and French interface.
- An old `platform: dfo_tides` YAML sensor is imported automatically and keeps its entity ID. Then remove the YAML entry.

### Installation

See the **[Setup Guide](Setup%20Guide.md)**. In short:

1. Copy `custom_components/dfo_tides` into your Home Assistant `config/custom_components/` folder (or add this repository to HACS as a custom *Integration* repository), then restart.
2. Add the **Mare** integration from *Settings → Devices & services*.
3. Install the card: see [`card/README.md`](card/README.md).

### Development

- Integration tests: `pytest` (needs `pytest-homeassistant-custom-component`, Python 3.13). They use recorded DFO responses in `tests/fixtures`.
- Card: `cd card && yarn install && yarn build`. `yarn start` serves a live dev build and a test page on port 5050.
- The integration and the card are meant to become two HACS repositories: this folder for the integration, `card/` for the card.

Data: Fisheries and Oceans Canada, [Integrated Water Level System API](https://api-iwls.dfo-mpo.gc.ca/). Predictions are not for navigation.

---

## Français

Mare intègre à Home Assistant les prédictions de marée de **Pêches et Océans Canada (MPO)** et les affiche dans une carte de tableau de bord qui indique **chaque marée haute et basse**.

Le projet comporte deux parties :

| Partie | Dossier | Rôle |
|---|---|---|
| **Intégration Mare** (`dfo_tides`) | [`custom_components/dfo_tides`](custom_components/dfo_tides) | Ajoute une station de marée depuis l’interface (stations les plus proches suggérées) et crée des capteurs : niveau de marée actuel, prochaine marée haute, prochaine marée basse. |
| **Carte Mare Tide Card** | [`card/`](card) | Une carte Lovelace avec la courbe de marée, chaque marée haute et basse identifiée avec sa hauteur et son heure, une plage allant jusqu’à 72 h et un éditeur visuel. En français et en anglais. |

La carte fonctionne **avec** l’intégration (elle lit le capteur de niveau de marée) ou **sans** elle (elle télécharge les prédictions directement de MPO pour une station choisie dans l’éditeur de la carte).

### Fonctionnalités de l’intégration

- **Configuration dans l’interface** : *Paramètres → Appareils et services → Ajouter une intégration → Mare*. Les 5 stations les plus proches de votre domicile sont proposées avec leur distance; vous pouvez déplacer l’épingle sur la carte ou chercher parmi toutes les stations par nom ou par code.
- **Changer de station plus tard** avec *Configurer*. Les identifiants d’entité ne changent pas : vos cartes et automatisations continuent de fonctionner.
- **Capteurs**
  - `sensor.<station>_niveau_de_maree` (ou `_tide_level` en anglais) : niveau prédit en ce moment (m), avec `trend` (`rising`/`falling`, montante/descendante), la courbe complète aux 15 minutes (`tide_data`) et les marées hautes et basses officielles (`tide_extremes`) d’hier jusqu’aux 3 prochains jours. Ces deux gros attributs ne sont pas enregistrés dans la base de données de l’historique.
  - Prochaine marée haute et prochaine marée basse : des horodatages, avec la hauteur (`height`) en attribut. Pratiques pour les automatisations.
- Les prédictions sont téléchargées une fois par heure; le niveau actuel est recalculé toutes les 5 minutes (réglable).
- Interface en français et en anglais.
- Un ancien capteur YAML `platform: dfo_tides` est importé automatiquement et garde son identifiant d’entité. Retirez ensuite l’entrée YAML.

### Installation

Consultez le **[guide d’installation](Setup%20Guide.md#français)**. En bref :

1. Copiez `custom_components/dfo_tides` dans le dossier `config/custom_components/` de Home Assistant (ou ajoutez ce dépôt à HACS comme dépôt personnalisé de type *Intégration*), puis redémarrez.
2. Ajoutez l’intégration **Mare** depuis *Paramètres → Appareils et services*.
3. Installez la carte : voir [`card/README.md`](card/README.md#français).

### Développement

- Tests de l’intégration : `pytest` (requiert `pytest-homeassistant-custom-component`, Python 3.13). Ils utilisent des réponses de MPO enregistrées dans `tests/fixtures`.
- Carte : `cd card && yarn install && yarn build`. `yarn start` sert une version de développement et une page de test sur le port 5050.
- L’intégration et la carte deviendront deux dépôts HACS : ce dossier pour l’intégration, `card/` pour la carte.

Données : Pêches et Océans Canada, [API du Système intégré des niveaux d’eau](https://api-iwls.dfo-mpo.gc.ca/). Les prédictions ne doivent pas servir à la navigation.
