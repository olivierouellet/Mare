# Mare: Setup Guide · Guide d’installation

**[English](#english) · [Français](#français)**

> *Mare* (pronounced **MAH-reh**, Latin for “sea”) comes from Canada’s motto, ***A mari usque ad mare***, “from sea to sea”.
> *Mare* (prononcé **MA-ré**, « mer » en latin) vient de la devise du Canada, ***A mari usque ad mare***, « d’un océan à l’autre ».

---

## English

### 1. Install the integration

**With HACS:** HACS → ⋮ → *Custom repositories* → add this repository with the type **Integration** → install **Mare** → restart Home Assistant.

**Manually:** copy the `custom_components/dfo_tides` folder into your Home Assistant configuration folder, then restart:

```text
config/
└── custom_components/
    └── dfo_tides/
        ├── __init__.py
        ├── api.py
        ├── config_flow.py
        ├── const.py
        ├── coordinator.py
        ├── manifest.json
        ├── sensor.py
        ├── strings.json
        └── translations/
            ├── en.json
            └── fr.json
```

### 2. Add a tide station

1. *Settings → Devices & services → Add integration* → search for **Mare**.
2. The map starts at your home location. Keep it, or move the pin to look for stations somewhere else, then submit.
3. Pick one of the **5 nearest stations** (each shows its code and distance), or tick *Search all stations instead* and type part of a name or code.

Repeat to add more stations.

**Sensors created** (entity IDs follow your Home Assistant language when the station is added):

| Sensor | State | Useful attributes |
|---|---|---|
| Tide level | Predicted level now, in metres | `trend`, `tide_data`, `tide_extremes`, `station_name` |
| Next high tide | Time of the next high tide | `height` |
| Next low tide | Time of the next low tide | `height` |

### 3. Change the station or the refresh rate

*Settings → Devices & services → Mare → Configure*

- **Recalculate the current level every**: how often the current level updates (default 5 minutes). Predictions themselves are downloaded once an hour.
- **Change station**: runs the same map → nearest stations → search steps. Your entity IDs stay the same, so cards and automations keep working.

### 4. Install the card

See [`card/README.md`](card/README.md): install it with HACS (type **Dashboard**) or copy `mare-tide-card.js` to `config/www/` and add it as a resource. Then add **Mare Tide Card** from the card picker and choose:

- **Home Assistant sensor (Mare integration)**: pick the *tide level* sensor, or
- **Directly from DFO (no integration)**: pick a station from the list (nearest to home, or use *Use my current position*, or search).

Example:

```yaml
type: custom:mare-tide-card
entity: sensor.halifax_tide_level
span: rolling
hours: 48
```

### Upgrading from the YAML version

The old version was configured in `configuration.yaml`:

```yaml
sensor:
  - platform: dfo_tides
    name: "Halifax Tides"
    station_id: "…"
```

After installing this version and restarting, that sensor is **imported automatically** into the UI and keeps its entity ID (e.g. `sensor.halifax_tides`). A repair notice then asks you to delete the `platform: dfo_tides` entry from `configuration.yaml` and restart.

> Note: the sample configuration in the previous version of this guide used the ID `5cebf1e33d0f4a073c4bc2d8`, which is **Sandy Beach (Gaspé, QC)**, not Halifax. Halifax is `5cebf1df3d0f4a073c4bbcbb`. With the new station picker you no longer need IDs at all.

The old ApexCharts card is in [`legacy/ApexChartsCard.yaml`](legacy/ApexChartsCard.yaml) for reference.

### Troubleshooting

- **Logs:** *Settings → System → Logs*, search for `dfo_tides`.
- **“Could not reach the DFO API”:** check that Home Assistant can reach `https://api-iwls.dfo-mpo.gc.ca`.
- **The card says the sensor has no tide data:** pick the *tide level* sensor, not *next high/low tide*.
- **Direct mode shows “Could not load tides from DFO”:** the browser must be able to reach `api-iwls.dfo-mpo.gc.ca` (some ad blockers or firewalls block it).
- **“Use my current position” isn’t available:** browsers only allow it over HTTPS or in the Home Assistant app.
- **Test the API yourself:** `https://api-iwls.dfo-mpo.gc.ca/api/v1/stations/5cebf1df3d0f4a073c4bbcbb/data?time-series-code=wlp-hilo&from=2026-09-27T00:00:00Z&to=2026-09-28T00:00:00Z`

---

## Français

### 1. Installer l’intégration

**Avec HACS :** HACS → ⋮ → *Dépôts personnalisés* → ajoutez ce dépôt avec le type **Intégration** → installez **Mare** → redémarrez Home Assistant.

**Manuellement :** copiez le dossier `custom_components/dfo_tides` dans le dossier de configuration de Home Assistant, puis redémarrez (voir l’arborescence dans la section anglaise ci-dessus).

### 2. Ajouter une station de marée

1. *Paramètres → Appareils et services → Ajouter une intégration* → cherchez **Mare**.
2. La carte s’ouvre sur l’emplacement de votre domicile. Gardez-le, ou déplacez l’épingle pour chercher des stations ailleurs, puis soumettez.
3. Choisissez l’une des **5 stations les plus proches** (chacune affiche son code et sa distance), ou cochez *Rechercher parmi toutes les stations* et tapez une partie d’un nom ou d’un code.

Recommencez pour ajouter d’autres stations.

**Capteurs créés** (les identifiants d’entité suivent la langue de Home Assistant au moment de l’ajout) :

| Capteur | État | Attributs utiles |
|---|---|---|
| Niveau de marée | Niveau prédit en ce moment, en mètres | `trend`, `tide_data`, `tide_extremes`, `station_name` |
| Prochaine marée haute | Heure de la prochaine marée haute | `height` (hauteur) |
| Prochaine marée basse | Heure de la prochaine marée basse | `height` (hauteur) |

### 3. Changer de station ou la fréquence de mise à jour

*Paramètres → Appareils et services → Mare → Configurer*

- **Recalculer le niveau actuel toutes les** : fréquence de mise à jour du niveau actuel (5 minutes par défaut). Les prédictions sont téléchargées une fois par heure.
- **Changer de station** : reprend les étapes carte → stations les plus proches → recherche. Vos identifiants d’entité ne changent pas : vos cartes et automatisations continuent de fonctionner.

### 4. Installer la carte

Voir [`card/README.md`](card/README.md#français) : installez-la avec HACS (type **Dashboard**) ou copiez `mare-tide-card.js` dans `config/www/` et ajoutez-la comme ressource. Ajoutez ensuite **Mare Tide Card** depuis le sélecteur de cartes et choisissez :

- **Capteur Home Assistant (intégration Mare)** : choisissez le capteur de *niveau de marée*, ou
- **Directement de MPO (sans intégration)** : choisissez une station dans la liste (les plus proches du domicile, *Utiliser ma position actuelle*, ou la recherche).

Exemple :

```yaml
type: custom:mare-tide-card
entity: sensor.halifax_niveau_de_maree
span: rolling
hours: 48
language: fr
```

### Mise à niveau depuis la version YAML

L’ancienne version se configurait dans `configuration.yaml` (`platform: dfo_tides`). Après l’installation de cette version et un redémarrage, ce capteur est **importé automatiquement** dans l’interface et garde son identifiant d’entité (p. ex. `sensor.halifax_tides`). Un avis de réparation vous demande ensuite de retirer l’entrée `platform: dfo_tides` de `configuration.yaml` et de redémarrer.

> Remarque : l’exemple de configuration de l’ancienne version de ce guide utilisait l’identifiant `5cebf1e33d0f4a073c4bc2d8`, qui correspond à **Sandy Beach (Gaspé, QC)** et non à Halifax. Halifax est `5cebf1df3d0f4a073c4bbcbb`. Avec le nouveau sélecteur de station, vous n’avez plus besoin des identifiants.

L’ancienne carte ApexCharts se trouve dans [`legacy/ApexChartsCard.yaml`](legacy/ApexChartsCard.yaml) à titre de référence.

### Dépannage

- **Journaux :** *Paramètres → Système → Journaux*, cherchez `dfo_tides`.
- **« Impossible de joindre l’API de MPO » :** vérifiez que Home Assistant peut joindre `https://api-iwls.dfo-mpo.gc.ca`.
- **La carte indique que le capteur n’a pas de données de marée :** choisissez le capteur de *niveau de marée*, pas celui de la prochaine marée haute ou basse.
- **Le mode direct affiche « Impossible de charger les marées de MPO » :** le navigateur doit pouvoir joindre `api-iwls.dfo-mpo.gc.ca` (certains bloqueurs de publicité ou pare-feu le bloquent).
- **« Utiliser ma position actuelle » n’est pas disponible :** les navigateurs ne le permettent qu’en HTTPS ou dans l’application Home Assistant.
