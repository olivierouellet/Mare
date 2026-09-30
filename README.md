<p align="center">
  <img src="assets/icon.svg" alt="Mare logo" width="128" height="128">
</p>

<h1 align="center">Mare</h1>

<p align="center">Tide predictions for Home Assistant · Prédictions de marée pour Home Assistant</p>

<p align="center"><b><a href="#english">English</a> · <a href="#français">Français</a></b></p>

> ### 🌊 Why “Mare”? · Pourquoi « Mare » ?
>
> *Mare* is Latin for **sea**. The name comes from Canada’s motto, ***A mari usque ad mare*** (“from sea to sea”), where the project began. It is pronounced **MAH-reh** (/ˈma.re/).
>
> *Mare* signifie **mer** en latin. Le nom vient de la devise du Canada, ***A mari usque ad mare*** (« d’un océan à l’autre »), là où le projet a commencé. On le prononce **MA-ré** (/ˈma.re/).

---

## English

Mare brings official tide predictions into Home Assistant for **Canada, the United States, Mexico, the United Kingdom, Norway, the Netherlands and Ireland**, and shows them on a dashboard card that labels **every high and low tide**.

It has two parts:

| Part | Folder | What it does |
|---|---|---|
| **Mare integration** (`mare_tides`) | [`custom_components/mare_tides`](custom_components/mare_tides) | Adds a tide station from the UI (nearest stations suggested) and creates sensors: current tide level, next high tide, next low tide. |
| **Mare Tide Card** | [Mare-Tide-Card](https://github.com/olivierouellet/Mare-Tide-Card) | A Lovelace card with the tide curve, every high/low labelled with height and time, a span of up to 72 h, and a visual editor. English, French, Spanish, Dutch and Norwegian. |

The card works **with** the integration (it reads the tide level sensor) or **without** it (it downloads predictions directly from DFO for a station you pick in the card editor; Canadian stations only for now).

### Data sources

| Country | Service | Heights relative to |
|---|---|---|
| Canada | Fisheries and Oceans Canada (DFO), [IWLS API](https://api-iwls.dfo-mpo.gc.ca/) | Chart datum |
| United States (and its territories), Mexico | NOAA Tides and Currents, [CO-OPS API](https://api.tidesandcurrents.noaa.gov/api/prod/) | MLLW (mean lower low water) |
| United Kingdom | ADMIRALTY (UK Hydrographic Office), [UK Tidal API](https://admiraltyapi.portal.azure-api.net/) (free API key) | Chart datum |
| Norway | Kartverket (Norwegian Mapping Authority), [tide API](https://vannstand.kartverket.no/tideapi_en.html) | Chart datum |
| Netherlands | Rijkswaterstaat, [Waterwebservices](https://rijkswaterstaatdata.nl/waterdata/) | NAP (Normaal Amsterdams Peil) |
| Ireland | Marine Institute, [ERDDAP tide predictions](https://erddap.marine.ie/erddap/tabledap/imiTidePrediction.html) | OD Malin (Ordnance Datum Malin Head) |

**United Kingdom:** the service needs an API key. Sign up at the [ADMIRALTY developer portal](https://admiraltyapi.portal.azure-api.net/) and subscribe to *UK Tidal API - Discovery* (free for a year, renewable); Mare asks for the key when you pick the United Kingdom, and asks again if it expires. Discovery only publishes high and low waters for today and the next 6 days, so Mare draws the curve through them (`interpolated: true`) and has nothing before today's first tide until it has been running for a day.

Heights are measured from different references: chart datum and MLLW are near the lowest tides, while NAP and OD Malin are land survey levels, so lows are often negative. The tide level sensor has a `datum` attribute with the reference.

About 2,200 NOAA stations, including most Mexican ports, are *subordinate* stations: NOAA only publishes their high and low tides. Mare draws their curve through those highs and lows with a cosine, and sets the `interpolated` attribute to `true`. The high and low tides are official; the level between them is a close estimate.

### Integration features

- **Set up from the UI**: *Settings → Devices & services → Add integration → Mare*. Pick your country (the next step shows where its predictions come from), then the 5 stations nearest your home are listed with their distance; you can move the map pin or search every station by name or code.
- **Change the station later** under *Configure*. Entity IDs don’t change, so your cards and automations keep working.
- **Sensors**
  - `sensor.<station>_tide_level`: predicted level right now (m), with `trend` (`rising`/`falling`), `provider`, `datum`, `interpolated`, the whole curve (`tide_data`) and the official high/low points (`tide_extremes`) for yesterday through the next 3 days. The two large attributes are not written to the recorder database.
  - `sensor.<station>_next_high_tide` and `sensor.<station>_next_low_tide`: timestamps, with the `height` as an attribute. Handy for automations.
- Predictions are downloaded once an hour; the current level is recalculated every 5 minutes (configurable).
- Interface in English, French, Spanish (Spain and Latin America), Dutch and Norwegian Bokmål.

### Installation

**With HACS (recommended)**

[![Open your Home Assistant instance and open this repository in HACS.](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=olivierouellet&repository=Mare&category=integration)

1. In Home Assistant, open **HACS** → **⋮** (top right) → **Custom repositories**.
2. Repository: `https://github.com/olivierouellet/Mare`, type: **Integration**, then **Add**. (The button above does steps 1 and 2 for you.)
3. Search for **Mare**, open it and click **Download**.
4. Restart Home Assistant.
5. Add the integration: *Settings → Devices & services → Add integration → Mare*, then pick your station.

HACS then shows new versions as updates.

**Manually:** copy `custom_components/mare_tides` into your Home Assistant `config/custom_components/` folder, restart, and add the integration as in step 5.

**The card:** install the [Mare Tide Card](https://github.com/olivierouellet/Mare-Tide-Card) the same way, as a HACS custom repository of type **Dashboard**.

More details, including changing the station and troubleshooting, are in the **[Setup Guide](Setup%20Guide.md)**.

### Upgrading from 1.x

Version 2.0 renamed the integration from `dfo_tides` to `mare_tides` to make room for more countries, so existing stations must be added again:

1. **Before updating**, delete your Mare stations under *Settings → Devices & services → Mare*. This frees their entity IDs.
2. Update Mare in HACS and restart Home Assistant.
3. If a `config/custom_components/dfo_tides` folder is still there, delete it and restart again.
4. Add your stations again. Entity IDs come out the same (for example `sensor.halifax_tide_level`), so cards and automations keep working.

The YAML `platform: dfo_tides` sensor is no longer imported; add the station from the UI instead.

### Development

- Integration tests: `pytest` (needs `pytest-homeassistant-custom-component`, Python 3.13). They use recorded responses from every provider in `tests/fixtures`.
- The card lives in its own repository: [olivierouellet/Mare-Tide-Card](https://github.com/olivierouellet/Mare-Tide-Card).
- **Adding a country:** write a client that subclasses `TideClient` in `api.py` (implement `async_get_stations` and `_async_get_predictions`, plus `_async_get_extremes` if some stations only publish highs and lows; a key the user entered is in `self._api_key`), register it in `PROVIDERS` in `providers.py` with its countries (and `api_key_url` if it needs a key, which adds the key step to the setup), and add its label under `selector.provider` in `strings.json` and each translation. A test checks that every provider has a label in every language.
- The integration icon lives in `custom_components/mare_tides/brand/` (Home Assistant 2026.3 or later shows it automatically). Its source is `assets/icon.svg`; after editing it, export `icon@2x.png` at 512×512 and `icon.png` at 256×256.

Data: Fisheries and Oceans Canada, [Integrated Water Level System API](https://api-iwls.dfo-mpo.gc.ca/); NOAA Center for Operational Oceanographic Products and Services, [Tides and Currents](https://tidesandcurrents.noaa.gov/); UK Hydrographic Office, [ADMIRALTY UK Tidal API](https://admiraltyapi.portal.azure-api.net/); Kartverket, [Se havnivå](https://www.kartverket.no/en/at-sea/se-havniva) (CC BY 4.0); Rijkswaterstaat, [Waterinfo](https://waterinfo.rws.nl/); Marine Institute, [Irish National Tide Gauge Network](https://erddap.marine.ie/erddap/tabledap/imiTidePrediction.html). Predictions are not for navigation.

---

## Français

Mare intègre à Home Assistant les prédictions de marée officielles pour **le Canada, les États-Unis, le Mexique, le Royaume-Uni, la Norvège, les Pays-Bas et l’Irlande**, et les affiche dans une carte de tableau de bord qui indique **chaque marée haute et basse**.

Le projet comporte deux parties :

| Partie | Dossier | Rôle |
|---|---|---|
| **Intégration Mare** (`mare_tides`) | [`custom_components/mare_tides`](custom_components/mare_tides) | Ajoute une station de marée depuis l’interface (stations les plus proches suggérées) et crée des capteurs : niveau de marée actuel, prochaine marée haute, prochaine marée basse. |
| **Carte Mare Tide Card** | [Mare-Tide-Card](https://github.com/olivierouellet/Mare-Tide-Card#français) | Une carte Lovelace avec la courbe de marée, chaque marée haute et basse identifiée avec sa hauteur et son heure, une plage allant jusqu’à 72 h et un éditeur visuel. En français, anglais, espagnol, néerlandais et norvégien. |

La carte fonctionne **avec** l’intégration (elle lit le capteur de niveau de marée) ou **sans** elle (elle télécharge les prédictions directement de MPO pour une station choisie dans l’éditeur de la carte; stations canadiennes seulement pour l’instant).

### Sources de données

| Pays | Service | Hauteurs par rapport au |
|---|---|---|
| Canada | Pêches et Océans Canada (MPO), [API SINE](https://api-iwls.dfo-mpo.gc.ca/) | Zéro des cartes |
| États-Unis (et leurs territoires), Mexique | NOAA Tides and Currents, [API CO-OPS](https://api.tidesandcurrents.noaa.gov/api/prod/) | MLLW (moyenne des basses mers inférieures) |
| Royaume-Uni | ADMIRALTY (Service hydrographique du Royaume-Uni), [UK Tidal API](https://admiraltyapi.portal.azure-api.net/) (clé d’API gratuite) | Zéro des cartes |
| Norvège | Kartverket (Autorité cartographique norvégienne), [API des marées](https://vannstand.kartverket.no/tideapi_en.html) | Zéro des cartes |
| Pays-Bas | Rijkswaterstaat, [Waterwebservices](https://rijkswaterstaatdata.nl/waterdata/) | NAP (Normaal Amsterdams Peil) |
| Irlande | Marine Institute, [prédictions de marée ERDDAP](https://erddap.marine.ie/erddap/tabledap/imiTidePrediction.html) | OD Malin (niveau de référence de Malin Head) |

**Royaume-Uni :** le service demande une clé d’API. Inscrivez-vous sur le [portail des développeurs ADMIRALTY](https://admiraltyapi.portal.azure-api.net/) et abonnez-vous à *UK Tidal API - Discovery* (gratuit pendant un an, renouvelable); Mare demande la clé quand vous choisissez le Royaume-Uni, puis de nouveau si elle expire. Discovery ne publie que les pleines et basses mers d’aujourd’hui et des 6 prochains jours : Mare trace la courbe entre elles (`interpolated: true`) et n’a rien avant la première marée du jour tant qu’il n’a pas fonctionné une journée.

Les hauteurs n’ont pas toutes la même référence : le zéro des cartes et le MLLW sont près des plus basses marées, alors que le NAP et l’OD Malin sont des niveaux d’arpentage terrestres, où les basses mers sont souvent négatives. Le capteur de niveau de marée indique la référence dans l’attribut `datum`.

Environ 2 200 stations de la NOAA, dont la plupart des ports mexicains, sont des stations *secondaires* : la NOAA ne publie que leurs marées hautes et basses. Mare trace leur courbe entre ces marées hautes et basses avec un cosinus et met l’attribut `interpolated` à `true`. Les marées hautes et basses sont officielles; le niveau entre les deux est une bonne estimation.

### Fonctionnalités de l’intégration

- **Configuration dans l’interface** : *Paramètres → Appareils et services → Ajouter une intégration → Mare*. Choisissez votre pays (l’étape suivante indique la source de ses prédictions); les 5 stations les plus proches de votre domicile sont proposées avec leur distance; vous pouvez déplacer l’épingle sur la carte ou chercher parmi toutes les stations par nom ou par code.
- **Changer de station plus tard** avec *Configurer*. Les identifiants d’entité ne changent pas : vos cartes et automatisations continuent de fonctionner.
- **Capteurs**
  - `sensor.<station>_niveau_de_maree` (ou `_tide_level` en anglais) : niveau prédit en ce moment (m), avec `trend` (`rising`/`falling`, montante/descendante), `provider`, `datum`, `interpolated`, la courbe complète (`tide_data`) et les marées hautes et basses officielles (`tide_extremes`) d’hier jusqu’aux 3 prochains jours. Ces deux gros attributs ne sont pas enregistrés dans la base de données de l’historique.
  - Prochaine marée haute et prochaine marée basse : des horodatages, avec la hauteur (`height`) en attribut. Pratiques pour les automatisations.
- Les prédictions sont téléchargées une fois par heure; le niveau actuel est recalculé toutes les 5 minutes (réglable).
- Interface en français, anglais, espagnol (Espagne et Amérique latine), néerlandais et norvégien bokmål.

### Installation

**Avec HACS (recommandé)**

[![Ouvrir votre instance Home Assistant et ce dépôt dans HACS.](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=olivierouellet&repository=Mare&category=integration)

1. Dans Home Assistant, ouvrez **HACS** → **⋮** (en haut à droite) → **Dépôts personnalisés**.
2. Dépôt : `https://github.com/olivierouellet/Mare`, type : **Intégration**, puis **Ajouter**. (Le bouton ci-dessus fait les étapes 1 et 2 pour vous.)
3. Cherchez **Mare**, ouvrez-la et cliquez sur **Télécharger**.
4. Redémarrez Home Assistant.
5. Ajoutez l’intégration : *Paramètres → Appareils et services → Ajouter une intégration → Mare*, puis choisissez votre station.

HACS affiche ensuite les nouvelles versions comme des mises à jour.

**Manuellement :** copiez `custom_components/mare_tides` dans le dossier `config/custom_components/` de Home Assistant, redémarrez et ajoutez l’intégration comme à l’étape 5.

**La carte :** installez la [Mare Tide Card](https://github.com/olivierouellet/Mare-Tide-Card#français) de la même façon, comme dépôt personnalisé HACS de type **Dashboard** (tableau de bord).

Plus de détails, dont le changement de station et le dépannage, dans le **[guide d’installation](Setup%20Guide.md#français)**.

### Mise à jour depuis la version 1.x

La version 2.0 renomme l’intégration de `dfo_tides` à `mare_tides` pour faire place à d’autres pays; les stations existantes doivent donc être ajoutées de nouveau :

1. **Avant la mise à jour**, supprimez vos stations Mare dans *Paramètres → Appareils et services → Mare*. Cela libère leurs identifiants d’entité.
2. Mettez Mare à jour dans HACS et redémarrez Home Assistant.
3. Si un dossier `config/custom_components/dfo_tides` existe encore, supprimez-le et redémarrez de nouveau.
4. Ajoutez de nouveau vos stations. Les identifiants d’entité restent les mêmes (par exemple `sensor.halifax_niveau_de_maree`) : vos cartes et automatisations continuent de fonctionner.

Le capteur YAML `platform: dfo_tides` n’est plus importé; ajoutez plutôt la station depuis l’interface.

### Développement

- Tests de l’intégration : `pytest` (requiert `pytest-homeassistant-custom-component`, Python 3.13). Ils utilisent des réponses de chaque source enregistrées dans `tests/fixtures`.
- La carte a son propre dépôt : [olivierouellet/Mare-Tide-Card](https://github.com/olivierouellet/Mare-Tide-Card#français).
- **Ajouter un pays :** écrivez un client qui hérite de `TideClient` dans `api.py` (implémentez `async_get_stations` et `_async_get_predictions`, ainsi que `_async_get_extremes` si certaines stations ne publient que les marées hautes et basses; la clé saisie par l’utilisateur est dans `self._api_key`), inscrivez-le dans `PROVIDERS` de `providers.py` avec ses pays (et `api_key_url` s’il demande une clé, ce qui ajoute l’étape de la clé à la configuration), et ajoutez son libellé sous `selector.provider` dans `strings.json` et chaque traduction. Un test vérifie que chaque source a un libellé dans chaque langue.
- L’icône de l’intégration se trouve dans `custom_components/mare_tides/brand/` (Home Assistant 2026.3 ou plus récent l’affiche automatiquement). Sa source est `assets/icon.svg`; après une modification, exportez `icon@2x.png` en 512×512 et `icon.png` en 256×256.

Données : Pêches et Océans Canada, [API du Système intégré des niveaux d’eau](https://api-iwls.dfo-mpo.gc.ca/); NOAA Center for Operational Oceanographic Products and Services, [Tides and Currents](https://tidesandcurrents.noaa.gov/); UK Hydrographic Office, [ADMIRALTY UK Tidal API](https://admiraltyapi.portal.azure-api.net/); Kartverket, [Se havnivå](https://www.kartverket.no/en/at-sea/se-havniva) (CC BY 4.0); Rijkswaterstaat, [Waterinfo](https://waterinfo.rws.nl/); Marine Institute, [réseau national irlandais de marégraphes](https://erddap.marine.ie/erddap/tabledap/imiTidePrediction.html). Les prédictions ne doivent pas servir à la navigation.
