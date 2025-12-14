# Application de Télémétrie F1 25

Une application Python modulaire pour capturer, parser et visualiser les données de télémétrie du jeu F1 25 en temps réel.

## Fonctionnalités

- **Capture UDP** : Réception des paquets de télémétrie F1 25
- **Parsing des données** : Extraction des informations (vitesse, RPM, contrôles, etc.)
- **Interface graphique** : Affichage en temps réel avec Tkinter
- **Graphiques temps réel** : Visualisation des données avec Matplotlib
- **Logs détaillés** : Suivi des paquets reçus

## Structure du projet

```
telemetry_app/
├── main.py              # Point d'entrée principal
├── config.py            # Configuration de l'application
├── telemetry.py         # Capture des paquets UDP
├── data_parser.py       # Parsing des données F1
├── gui.py               # Interface graphique
├── test_telemetry.py    # Script de test
└── telemetry_capture.py # Script original (conservé)
```

## Installation

1. Créer un environnement virtuel :
```bash
python -m venv .venv
```

2. Activer l'environnement :
```bash
# Windows
.venv\Scripts\activate

# Linux/Mac
source .venv/bin/activate
```

3. Installer les dépendances :
```bash
pip install matplotlib
```

## Configuration F1 25

1. Lancer F1 25
2. Aller dans les paramètres → Télémétrie
3. Activer la télémétrie UDP
4. Configurer :
   - IP : `127.0.0.1`
   - Port : `20777`

## Utilisation

1. Lancer l'application :
```bash
python main.py
```

2. Dans l'interface :
   - Cliquer "Démarrer la capture"
   - Lancer une session F1 25 (course, qualifications)
   - Observer les données en temps réel

## Test sans F1 25

Pour tester l'application sans le jeu :

1. Lancer l'application principale
2. Démarrer la capture
3. Dans un autre terminal, exécuter :
```bash
python test_telemetry.py
```

Cela enverra des paquets de test simulés.

## Fonctionnalités des graphiques

- **Vitesse** : Évolution de la vitesse en km/h
- **RPM** : Régime moteur en temps réel
- **Contrôles** : Position de l'accélérateur et du frein
- **Position** : Coordonnées mondiales (réservé pour évolution future)

## Dépannage

- **Aucun paquet reçu** : Vérifier la configuration réseau et le pare-feu
- **Erreur de parsing** : Les offsets peuvent varier selon la version de F1
- **Graphiques vides** : S'assurer que matplotlib est installé

## Développement

L'application est modulaire pour faciliter les extensions :
- Ajouter de nouveaux types de graphiques
- Sauvegarder les données dans des fichiers
- Intégrer d'autres sources de données
- Améliorer le parsing pour d'autres versions de F1

## Licence

Ce projet est fourni tel quel pour usage éducatif et personnel.