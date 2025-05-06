# Documentation de l'Explorateur API Ratings & Reviews

## 📖 Présentation générale

L'Explorateur API Ratings & Reviews est une application web développée avec Streamlit qui permet d'accéder, de filtrer et d'exporter facilement des données d'avis et de notations provenant de l'API Ratings & Reviews pour les produits Beauty. Cette application facilite l'analyse des avis clients et offre une interface intuitive pour explorer les données disponibles.

## 🚀 Fonctionnalités principales

- Consultation des quotas d'API disponibles
- Filtrage multicritère des données (dates, catégories, marques, pays, etc.)
- Sélection et recherche de produits spécifiques
- Aperçu des données avec pagination
- Export de données au format CSV et Excel
- Journalisation des exports pour éviter les duplications

## 💻 Installation et prérequis

### Dépendances requises

L'application nécessite les bibliothèques Python suivantes, qui sont définies dans le fichier `requirements.txt` :

```
streamlit
pandas
requests
openpyxl
altair
```

Pour installer ces dépendances, exécutez la commande :

```bash
pip install -r requirements.txt
```

## 🛠️ Guide d'utilisation

### 1. Configuration initiale

L'application nécessite un token d'API valide, qui doit être configuré dans le fichier `.streamlit/secrets.toml` avec la structure suivante :

```toml
[api]
token = "votre_token_api_ici"
```

### 2. Filtres disponibles

Le panneau latéral (sidebar) permet de définir des filtres précis pour votre recherche :

| Filtre | Description |
|--------|-------------|
| Date de début | Date à partir de laquelle rechercher les avis |
| Date de fin | Date jusqu'à laquelle rechercher les avis |
| Catégorie | Catégorie principale de produits (ex: "Maquillage") |
| Sous-catégorie | Sous-catégorie de produits (ex: "Mascara") |
| Marques | Sélection multiple des marques à inclure |
| Pays | Sélection multiple des pays d'origine des avis |
| Sources | Sélection multiple des sources d'avis (ex: sites e-commerce) |
| Markets | Sélection multiple des marchés concernés |
| Attributs | Attributs spécifiques mentionnés dans les avis |

Pour appliquer les filtres, cliquez sur le bouton "**✅ Appliquer les filtres**".

### 3. Consultation des produits disponibles

Une fois les filtres appliqués, l'application affiche la liste des produits correspondants :

- Les produits sont affichés avec leur marque et le nombre d'avis disponibles
- Vous pouvez filtrer cette liste avec la barre de recherche
- Le tri peut être effectué par marque, produit ou nombre d'avis
- Sélectionnez les produits souhaités en cochant les cases correspondantes

### 4. Options d'export

L'application propose deux modes d'export :

1. **Aperçu rapide** : Récupère un maximum de 50 avis pour une consultation rapide
2. **Export complet** : Récupère toutes les reviews correspondant aux critères

Paramètres configurables :
- **Nombre de reviews par page** : Contrôle la pagination (10-1000)
- **Randomiser les résultats** : Option permettant d'obtenir un échantillon aléatoire
- **Seed aléatoire** : Définit une graine pour garantir la reproductibilité des résultats aléatoires

### 5. Consultation et téléchargement des résultats

Après le chargement des données, vous pouvez :

- Visualiser les avis dans un tableau interactif
- Naviguer entre les différentes pages de résultats
- Télécharger uniquement la page actuelle en CSV ou Excel
- Télécharger l'ensemble des résultats en CSV ou Excel

L'application génère automatiquement des noms de fichiers significatifs incluant les informations sur les produits, les dates et le type d'export.

### 6. Journal des exports

L'application maintient un journal des exports précédents dans le fichier `review_exports_log.csv`. Ce journal permet :

- De consulter l'historique des exports effectués
- D'identifier les potentielles duplications d'exports (l'application vous avertit si vous tentez d'exporter à nouveau des données déjà exportées)
- De télécharger l'historique complet des exports

> **Important** : Pour que le journal des exports fonctionne correctement, le chemin d'accès au fichier log (`log_path = Path("review_exports_log.csv")`) doit être défini correctement dans le code. Assurez-vous que l'application a les droits d'écriture dans le répertoire spécifié. Si vous déployez l'application dans un environnement différent, veillez à adapter ce chemin pour maintenir l'historique des exports.

## 📊 Quotas API

L'application affiche les informations sur vos quotas API :
- Volume utilisé
- Volume restant
- Quota total
- Date de validité du quota

Ces informations sont essentielles pour gérer votre consommation d'API et éviter les dépassements de quota.

## 🔍 Fonctionnalités avancées

### Cursor Pagination

L'application utilise le mécanisme de cursor pagination pour récupérer efficacement de grands volumes de données, en permettant de parcourir l'ensemble des résultats par pages sans perdre ni dupliquer d'informations.

### Cache des requêtes

Les requêtes API sont mises en cache pendant une heure (`@st.cache_data(ttl=3600)`), ce qui permet d'optimiser les performances et de réduire la consommation de quota API.

### Gestion des URL codées

L'application utilise un encodage strict des paramètres URL pour garantir la compatibilité avec l'API, notamment pour les caractères spéciaux.

## 🚀 Démarrage de l'application

Pour lancer l'application, exécutez la commande suivante dans le répertoire du projet :

```bash
streamlit run app.py
```

Si vous avez modifié le nom du fichier principal, remplacez `app.py` par le nom correct.

Par défaut, l'application sera accessible à l'adresse http://localhost:8501 dans votre navigateur web.

Pour un déploiement en production, consultez la [documentation officielle de Streamlit](https://docs.streamlit.io/knowledge-base/deploy).

## ⚠️ Limites et précautions

- **Quotas API** : Surveillez votre consommation pour éviter d'atteindre les limites
- **Exports volumineux** : Les exports très volumineux peuvent prendre du temps et consommer beaucoup de mémoire
- **Nombre maximal de pages** : Un mécanisme de sécurité limite à 100 le nombre maximal de pages récupérables en une seule fois pour éviter les boucles infinies
- **Noms de fichiers** : Les noms de fichiers très longs sont automatiquement tronqués à 100 caractères
- **Journal des exports** : Pour que la fonctionnalité de journal fonctionne, assurez-vous que le chemin du fichier log est accessible en écriture pour l'application

## 🔧 Dépannage

| Problème | Solution |
|----------|----------|
| Erreur d'authentification | Vérifiez que votre token API est correct et à jour dans le fichier secrets.toml |
| Aucun produit affiché | Élargissez vos critères de recherche ou vérifiez que les filtres ne sont pas trop restrictifs |
| Export lent | Réduisez la plage de dates ou le nombre de produits sélectionnés |
| Erreur de quota dépassé | Attendez le renouvellement de votre quota ou contactez votre administrateur API |
| Erreur de module manquant | Vérifiez que toutes les dépendances sont installées avec `pip install -r requirements.txt` |
| Problème d'accès au fichier journal | Vérifiez les permissions d'écriture dans le répertoire où le fichier log est sauvegardé |

## 📑 Structure du code

L'application est structurée autour des fonctions principales suivantes :

- `fetch_cached` : Récupération des données API avec mise en cache
- `fetch_products_by_brand` : Récupération des produits par marque
- `fetch_attributes_dynamic` : Récupération dynamique des attributs disponibles
- `generate_export_filename` : Génération de noms de fichiers cohérents pour les exports
- `main` : Fonction principale qui gère l'interface utilisateur et le flux de l'application

Ces fonctions sont conçues pour être modulaires et réutilisables, facilitant ainsi la maintenance et l'extension de l'application.
