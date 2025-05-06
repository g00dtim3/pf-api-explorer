import streamlit as st
import requests
import pandas as pd
import datetime
import io
import altair as alt
import urllib.parse
from functools import partial

st.set_page_config(page_title="Explorateur API Ratings & Reviews", layout="wide")

st.session_state.setdefault("apply_filters", False)

@st.cache_data(ttl=3600)
def fetch_cached(endpoint, params=None):
    BASE_URL = "https://api-pf.ratingsandreviews-beauty.com"
    TOKEN = st.secrets["api"]["token"]
    show_debug = False

    if params is None:
        params = {}
    elif isinstance(params, str):
        st.error("❌ ERREUR: `params` doit être un dict ou une liste de tuples, pas une chaîne.")
        return {}

    def quote_strict(string, safe='/', encoding=None, errors=None):
        return urllib.parse.quote(string, safe='', encoding=encoding, errors=errors)

    if isinstance(params, dict):
        params["token"] = TOKEN
        query_string = urllib.parse.urlencode(params, doseq=True, quote_via=quote_strict)
    else:
        params.append(("token", TOKEN))
        query_string = urllib.parse.urlencode(params, doseq=True, quote_via=quote_strict)

    url = f"{BASE_URL}{endpoint}?{query_string}"

    if show_debug:
        st.write("🔎 URL générée:", url)
        st.write("Paramètres analysés:", params)

    response = requests.get(url, headers={"Accept": "application/json"})
    if response.status_code == 200:
        return response.json().get("result")
    else:
        st.error(f"Erreur {response.status_code} sur {url}")
        st.error(f"Réponse: {response.text}")
        return {}

@st.cache_data(ttl=3600)
def fetch_products_by_brand(brand, category, subcategory, start_date, end_date):
    params = {
        "brand": brand,
        "start-date": start_date,
        "end-date": end_date
    }
    if category != "ALL":
        params["category"] = category
    if subcategory != "ALL":
        params["subcategory"] = subcategory
    return fetch_cached("/products", params)

@st.cache_data(ttl=3600)
def fetch_attributes_dynamic(category, subcategory, brand):
    params = {}
    if category != "ALL":
        params["category"] = category
    if subcategory != "ALL":
        params["subcategory"] = subcategory
    if brand:
        params["brand"] = ",".join(brand)
    return fetch_cached("/attributes", params)

def fetch(endpoint, params=None):
    return fetch_cached(endpoint, params)


def main():
    st.title("Explorateur API Ratings & Reviews")

    st.subheader("Quotas")
    if st.button("Afficher mes quotas"):
        result = fetch("/quotas")
        if result:
            st.metric("Volume utilisé", result['used volume'])
            st.metric("Volume restant", result['remaining volume'])
            st.metric("Quota total", result['quota'])
            st.metric("Valable jusqu'au", result['end date'])

    with st.sidebar:
        st.header("Filtres")

        start_date = st.date_input("Date de début", value=datetime.date(2022, 1, 1))
        end_date = st.date_input("Date de fin", value=datetime.date.today())

        categories = fetch("/categories")
        all_categories = ["ALL"] + [c["category"] for c in categories.get("categories", [])]
        category = st.selectbox("Catégorie", all_categories)

        subcategory_options = ["ALL"]
        if category != "ALL":
            for cat in categories.get("categories", []):
                if cat["category"] == category:
                    subcategory_options += cat["subcategories"]
        subcategory = st.selectbox("Sous-catégorie", subcategory_options)

        brands_params = {}
        if category != "ALL":
            brands_params["category"] = category
        if subcategory != "ALL":
            brands_params["subcategory"] = subcategory
        brands = fetch("/brands", brands_params)
        brand = st.multiselect("Marques", brands.get("brands", []))

        countries = fetch("/countries")
        all_countries = ["ALL"] + countries.get("countries", [])
        country = st.multiselect("Pays", all_countries)

        source_params = {}
        if country and country[0] != "ALL":
            source_params["country"] = country[0]
        sources = fetch("/sources", source_params)
        all_sources = ["ALL"] + sources.get("sources", [])
        source = st.multiselect("Sources", all_sources)

        markets = fetch("/markets")
        all_markets = ["ALL"] + markets.get("markets", [])
        market = st.multiselect("Markets", all_markets)

        attribute_data = fetch_attributes_dynamic(category, subcategory, brand)
        attribute_options = attribute_data.get("attributes", [])
        attributes = st.multiselect("Attributs", attribute_options)
        attributes_positive = st.multiselect("Attributs positifs", attribute_options)
        attributes_negative = st.multiselect("Attributs négatifs", attribute_options)

        if st.button("✅ Appliquer les filtres"):
            st.session_state.apply_filters = True
            st.session_state.filters = {
                "start_date": start_date,
                "end_date": end_date,
                "category": category,
                "subcategory": subcategory,
                "brand": brand,
                "country": country,
                "source": source,
                "market": market,
                "attributes": attributes,
                "attributes_positive": attributes_positive,
                "attributes_negative": attributes_negative
            }

    if not st.session_state.get("apply_filters") or "filters" not in st.session_state:
        st.info("Appliquez les filtres pour afficher les données.")
        return

    filters = st.session_state.filters
    params = {
        "start-date": filters["start_date"],
        "end-date": filters["end_date"]
    }
    if filters["category"] != "ALL": params["category"] = filters["category"]
    if filters["subcategory"] != "ALL": params["subcategory"] = filters["subcategory"]
    if filters["brand"]: params["brand"] = ",".join(filters["brand"])
    if filters["country"] and "ALL" not in filters["country"]: params["country"] = ",".join(filters["country"])
    if filters["source"] and "ALL" not in filters["source"]: params["source"] = ",".join(filters["source"])
    if filters["market"] and "ALL" not in filters["market"]: params["market"] = ",".join(filters["market"])
    if filters["attributes"]: params["attribute"] = ",".join(filters["attributes"])
    if filters["attributes_positive"]: params["attribute-positive"] = ",".join(filters["attributes_positive"])
    if filters["attributes_negative"]: params["attribute-negative"] = ",".join(filters["attributes_negative"])

    st.markdown("## 🧾 Résumé des filtres appliqués")
    st.markdown(f"- **Dates** : du `{filters['start_date']}` au `{filters['end_date']}`")
    st.markdown(f"- **Catégorie** : `{filters['category']}` | **Sous-catégorie** : `{filters['subcategory']}`")
    st.markdown(f"- **Marques** : `{', '.join(filters['brand']) if filters['brand'] else 'Toutes'}`")
    st.markdown(f"- **Pays** : `{', '.join(filters['country']) if filters['country'] and 'ALL' not in filters['country'] else 'Tous'}`")
    st.markdown(f"- **Sources** : `{', '.join(filters['source']) if filters['source'] and 'ALL' not in filters['source'] else 'Toutes'}`")
    st.markdown(f"- **Markets** : `{', '.join(filters['market']) if filters['market'] and 'ALL' not in filters['market'] else 'Tous'}`")
    st.markdown(f"- **Attributs** : `{', '.join(filters['attributes'])}`")
    st.markdown(f"- **Attributs positifs** : `{', '.join(filters['attributes_positive'])}`")
    st.markdown(f"- **Attributs négatifs** : `{', '.join(filters['attributes_negative'])}`")

    product_info = {}
    product_data = []

    if filters["brand"]:
        with st.spinner("Chargement des produits par marque..."):
            for i, b in enumerate(filters["brand"]):
                st.write(f"🔎 {i+1}/{len(filters['brand'])} : {b}")
                products = fetch_products_by_brand(b, filters["category"], filters["subcategory"], filters["start_date"], filters["end_date"])
                if products and products.get("products"):
                    for p in products["products"]:
                        label = f"{b} > {p}"
                        product_info[label] = p
                        product_data.append({"Marque": b, "Produit": p})

    if product_data:
        st.subheader("📊 Produits disponibles")
        
        # Initialiser la sélection dans session_state si nécessaire
        if "selected_product_ids" not in st.session_state:
            st.session_state.selected_product_ids = []
        
        # Ajouter une recherche pour filtrer les produits
        search_text = st.text_input("🔍 Filtrer les produits")
        
        # Récupérer le nombre d'avis par produit
        with st.spinner("Récupération du nombre d'avis par produit..."):
            for i, row in enumerate(product_data):
                product_name = row["Produit"]
                brand_name = row["Marque"]
                product_params = {
                    "product": product_name,
                    "brand": brand_name,
                    "start-date": filters["start_date"],
                    "end-date": filters["end_date"]
                }
                metrics = fetch("/metrics", product_params)
                nb_reviews = metrics.get("nbDocs", 0) if metrics else 0
                product_data[i]["Nombre d'avis"] = nb_reviews
        
        # Créer un DataFrame avec les données
        df_products = pd.DataFrame(product_data)
        
        # Filtrer selon la recherche
        if search_text:
            mask = df_products["Produit"].str.contains(search_text, case=False) | df_products["Marque"].str.contains(search_text, case=False)
            filtered_df = df_products[mask]
        else:
            filtered_df = df_products
        
        # Trier le DataFrame (par défaut par nombre d'avis, décroissant)
        if "sort_column" not in st.session_state:
            st.session_state.sort_column = "Nombre d'avis"
            st.session_state.sort_ascending = False
            
        # Boutons de tri
        col1, col2, col3 = st.columns([2, 2, 2])
        with col1:
            if st.button("Trier par marque"):
                st.session_state.sort_column = "Marque"
                st.session_state.sort_ascending = not st.session_state.sort_ascending if st.session_state.sort_column == "Marque" else True
        with col2:
            if st.button("Trier par produit"):
                st.session_state.sort_column = "Produit"
                st.session_state.sort_ascending = not st.session_state.sort_ascending if st.session_state.sort_column == "Produit" else True
        with col3:
            if st.button("Trier par nb d'avis"):
                st.session_state.sort_column = "Nombre d'avis"
                st.session_state.sort_ascending = not st.session_state.sort_ascending if st.session_state.sort_column == "Nombre d'avis" else False
        
        # Appliquer le tri
        filtered_df = filtered_df.sort_values(by=st.session_state.sort_column, ascending=st.session_state.sort_ascending)
        
        # Afficher le tableau avec les cases à cocher
        st.write(f"Nombre de produits: {len(filtered_df)} | Tri actuel: {st.session_state.sort_column} ({'croissant' if st.session_state.sort_ascending else 'décroissant'})")
        
        # En-têtes du tableau
        header_col1, header_col2, header_col3, header_col4 = st.columns([0.5, 2, 2, 1])
        with header_col1:
            st.write("**Sélect.**")
        with header_col2:
            st.write("**Marque**")
        with header_col3:
            st.write("**Produit**")
        with header_col4:
            st.write("**Nombre d'avis**")
        
        # Stocker temporairement les modifications actuelles
        temp_selected = set(st.session_state.selected_product_ids)
        
        # Créer un sélecteur pour chaque ligne
        for index, row in filtered_df.iterrows():
            product_id = row["Produit"]
            col1, col2, col3, col4 = st.columns([0.5, 2, 2, 1])
            with col1:
                is_selected = st.checkbox("", value=product_id in st.session_state.selected_product_ids, key=f"check_{product_id}")
            with col2:
                st.write(row["Marque"])
            with col3:
                st.write(row["Produit"])
            with col4:
                st.write(f"{row['Nombre d\'avis']}")
            
            # Mettre à jour la sélection temporaire
            if is_selected:
                temp_selected.add(product_id)
            elif product_id in temp_selected:
                temp_selected.remove(product_id)
        
        # Mettre à jour la liste des produits sélectionnés
        st.session_state.selected_product_ids = list(temp_selected)
        selected_products = st.session_state.selected_product_ids
        
        st.write("---")
        st.write(f"**{len(selected_products)} produits sélectionnés** : {', '.join(selected_products) if selected_products else 'Aucun'}")
    else:
        st.warning("Aucun produit disponible pour les filtres sélectionnés.")
        selected_products = []
    
    st.markdown("---")
    st.subheader("Disponibilité des données")
    
    # Mise à jour des paramètres avec les produits sélectionnés
    if selected_products:
        params["product"] = ",".join(selected_products)
    
    # Requête pour obtenir les métriques avec les produits sélectionnés
    dynamic_metrics = fetch("/metrics", params)
    if dynamic_metrics and dynamic_metrics.get("nbDocs"):
        st.success(f"{dynamic_metrics['nbDocs']} reviews disponibles")
    else:
        st.warning("Aucune review disponible pour cette combinaison")

    st.markdown("## ⚙️ Paramètres d’export des reviews")

    import os
    from pathlib import Path
    
    log_path = Path("review_exports_log.csv")
    if log_path.exists():
        with st.expander("📁 Consulter le journal des exports précédents", expanded=False):
            export_log_df = pd.read_csv(log_path)
            st.dataframe(export_log_df)
            st.download_button("⬇️ Télécharger le journal des exports", export_log_df.to_csv(index=False), file_name="review_exports_log.csv", mime="text/csv")
    
    with st.expander("🔧 Options d’export", expanded=True):
        col1, col2 = st.columns(2)
    
        with col1:
            rows_per_page = st.number_input(
                "Nombre de reviews à récupérer par page (max 1000)",
                min_value=10,
                max_value=1000,
                value=100,
                step=10
            )
    
        with col2:
            use_random = st.checkbox("Randomiser les résultats")
            if use_random:
                random_seed = st.number_input("Seed aléatoire (1-9999)", min_value=1, max_value=9999, value=42)
            else:
                random_seed = None
    
        st.markdown("### 📊 Quotas API")
        quotas = fetch("/quotas")
        if quotas:
            st.metric("Quota utilisé", quotas['used volume'])
            st.metric("Quota restant", quotas['remaining volume'])
            st.metric("Quota total", quotas['quota'])
            st.metric("Valable jusqu’au", quotas['end date'])
    
        if "cursor_mark" not in st.session_state:
            st.session_state.cursor_mark = "*"
        if "current_page" not in st.session_state:
            st.session_state.current_page = 1
        if "all_docs" not in st.session_state:
            st.session_state.all_docs = []
        if "next_cursor" not in st.session_state:
            st.session_state.next_cursor = None
    
        # ✅ Vérification d’export déjà réalisé, englobant ou identique
        potential_duplicates = []
        if log_path.exists():
            try:
                export_log_df = pd.read_csv(log_path)
                export_log_df["start_date"] = pd.to_datetime(export_log_df["start_date"])
                export_log_df["end_date"] = pd.to_datetime(export_log_df["end_date"])
    
                product_names = params.get("product", "").split(",")
                start = pd.to_datetime(str(params.get("start-date")))
                end = pd.to_datetime(str(params.get("end-date")))
    
                for prod in product_names:
                    overlapping = export_log_df[
                        (export_log_df["product"] == prod) &
                        (export_log_df["start_date"] <= end) &
                        (export_log_df["end_date"] >= start)
                    ]
                    if not overlapping.empty:
                        potential_duplicates.append(prod)
            except Exception as e:
                st.warning(f"Erreur de lecture du fichier log : {e}")
    
        if potential_duplicates:
            st.warning(f"🚫 Les produits suivants ont déjà été exportés pour une période qui recouvre partiellement ou totalement celle sélectionnée : {', '.join(potential_duplicates)}")
    
       # Fonction pour générer un nom de fichier basé sur les filtres
def generate_export_filename(params, mode="complete", page=None, extension="csv"):
    """
    Génère un nom de fichier basé sur les paramètres de filtre
    
    Args:
        params: Dictionnaire contenant les paramètres de filtrage
        mode: Type d'export ('preview', 'page', 'complete')
        page: Numéro de page (pour mode='page')
        extension: Extension du fichier ('csv' ou 'xlsx')
    
    Returns:
        Nom du fichier formaté avec les filtres
    """
    # Base du nom de fichier
    filename_parts = ["reviews"]
    
    # Ajouter le pays s'il est spécifié
    country = params.get("country", "").strip()
    if country:
        filename_parts.append(country.lower())
    
    # Ajouter les produits (limité à 2 pour éviter des noms trop longs)
    products = params.get("product", "").split(",")
    if products and products[0]:
        # Nettoyer et limiter la longueur des noms de produits
        clean_products = []
        for p in products[:2]:  # Limiter à 2 produits maximum
            # Simplifier le nom du produit pour le filename
            clean_p = p.strip().lower()
            clean_p = clean_p.replace(" ", "_").replace("/", "-")
            # Limiter la longueur
            if len(clean_p) > 15:
                clean_p = clean_p[:15]
            clean_products.append(clean_p)
        
        if clean_products:
            filename_parts.append("-".join(clean_products))
            if len(products) > 2:
                filename_parts[-1] += "-plus"  # Indiquer s'il y a plus de produits
    
    # Ajouter les dates
    start_date = params.get("start-date")
    end_date = params.get("end-date")
    
    if start_date and end_date:
        # Formater les dates en format compact
        start_date_str = start_date.replace("-", "")
        end_date_str = end_date.replace("-", "")
        
        # Si l'année est la même, ne pas répéter
        if start_date_str[:4] == end_date_str[:4]:
            # Format: 2023_0101-0630 (pour jan-juin 2023)
            date_str = f"{start_date_str[:4]}_{start_date_str[4:8]}-{end_date_str[4:8]}"
        else:
            # Format: 20220101-20230630 (pour différentes années)
            date_str = f"{start_date_str}-{end_date_str}"
        
        filename_parts.append(date_str)
    
    # Ajouter le mode d'export
    if mode == "preview":
        filename_parts.append("apercu")
    elif mode == "page":
        filename_parts.append(f"page{page}")
    
    # Joindre toutes les parties avec des underscores
    filename = "_".join(filename_parts)
    
    # Ajouter l'extension
    filename += f".{extension}"
    
    # S'assurer que le nom n'est pas trop long (limite à 100 caractères)
    if len(filename) > 100:
        base, ext = filename.rsplit(".", 1)
        filename = base[:96] + "..." + "." + ext
    
    return filename

# Initialiser les variables de session si elles n'existent pas encore
if 'is_preview_mode' not in st.session_state:
    st.session_state.is_preview_mode = True
if 'current_page' not in st.session_state:
    st.session_state.current_page = 1
if 'all_docs' not in st.session_state:
    st.session_state.all_docs = []
if 'export_params' not in st.session_state:
    st.session_state.export_params = {}
if 'switch_to_full_export' not in st.session_state:
    st.session_state.switch_to_full_export = False

# Ajouter des options pour l'aperçu et l'export complet
st.header("🔍 Options d'export")

# Déterminer l'index du mode d'export (basé sur le mode actuel)
export_mode_index = 0 if st.session_state.is_preview_mode else 1

# Si l'utilisateur a demandé le passage en mode complet depuis l'aperçu
if st.session_state.switch_to_full_export:
    export_mode_index = 1
    st.session_state.switch_to_full_export = False  # Réinitialiser le flag
    
export_mode = st.radio(
    "Mode d'export",
    ["Aperçu rapide (50 reviews max)", "Export complet (toutes les reviews)"],
    index=export_mode_index
)

# Mettre à jour le mode d'aperçu en fonction du choix utilisateur
st.session_state.is_preview_mode = export_mode == "Aperçu rapide (50 reviews max)"

preview_limit = 50  # Nombre maximum de reviews pour l'aperçu

if st.button("📅 Lancer " + ("l'aperçu" if st.session_state.is_preview_mode else "l'export complet")):
    # Réinitialiser la session pour le chargement
    st.session_state.cursor_mark = "*"
    st.session_state.current_page = 1
    st.session_state.all_docs = []
    # Le mode est déjà défini par le radio button
    st.session_state.export_params = params.copy()  # Stocker les paramètres pour les noms de fichiers
    
    params_with_rows = params.copy()
    
    # En mode aperçu, on limite le nombre de lignes
    if st.session_state.is_preview_mode:
        params_with_rows["rows"] = min(int(rows_per_page), preview_limit)
    else:
        params_with_rows["rows"] = int(rows_per_page)
        
    if use_random and random_seed:
        params_with_rows["random"] = str(random_seed)
    
    metrics_result = fetch("/metrics", params)
    total_api_results = metrics_result.get("nbDocs", 0) if metrics_result else 0
    
    if total_api_results == 0:
        st.warning("Aucune review disponible pour cette combinaison")
    else:
        # En mode aperçu, ne récupérer qu'une page
        if st.session_state.is_preview_mode:
            expected_total_pages = 1
            max_reviews = min(preview_limit, total_api_results)
            st.info(f"📊 Mode aperçu : Chargement de {max_reviews} reviews maximum sur {total_api_results} disponibles")
        else:
            # Calculer le nombre total de pages attendues pour l'export complet
            expected_total_pages = (total_api_results + int(rows_per_page) - 1) // int(rows_per_page)
            st.info(f"🔄 Export complet : Chargement de toutes les {total_api_results} reviews...")
        
        # Afficher une barre de progression
        progress_bar = st.progress(0)
        status_text = st.empty()
        
        cursor_mark = "*"
        all_docs = []
        page_count = 0
        
        # Boucle pour récupérer les pages via cursor pagination
        while True:
            page_count += 1
            status_text.text(f"Chargement de la page {page_count}/{expected_total_pages if not st.session_state.is_preview_mode else 1}...")
            
            # Ajouter le cursor_mark aux paramètres
            current_params = params_with_rows.copy()
            current_params["cursorMark"] = cursor_mark
            
            # Récupérer la page courante
            result = fetch("/reviews", current_params)
            
            if not result or not result.get("docs"):
                break
                
            # Ajouter les documents à notre collection
            docs = result.get("docs", [])
            all_docs.extend(docs)
            
            # Mettre à jour la barre de progression
            progress_percent = min(page_count / expected_total_pages, 1.0)
            progress_bar.progress(progress_percent)
            
            # En mode aperçu, on s'arrête après la première page
            if st.session_state.is_preview_mode:
                break
                
            # Vérifier si nous avons un nouveau cursor_mark
            next_cursor = result.get("nextCursorMark")
            
            # Si pas de nouveau cursor ou même valeur que précédent, on a terminé
            if not next_cursor or next_cursor == cursor_mark:
                break
                
            # Mise à jour du cursor pour la prochaine itération
            cursor_mark = next_cursor
            
            # Si nous avons atteint le nombre maximal de reviews en mode aperçu, on s'arrête
            if st.session_state.is_preview_mode and len(all_docs) >= preview_limit:
                break
        
        # Stocker tous les documents récupérés
        st.session_state.all_docs = all_docs
        
        # 🔒 Génération du log d'export local (uniquement pour l'export complet)
        if not st.session_state.is_preview_mode:
            export_date = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            export_country = params.get("country", "Tous")
            
            product_names = params.get("product", "").split(",")
            brand_names = params.get("brand", "").split(",")
            
            log_entries = []
            for product in product_names:
                if not product.strip():
                    continue
                brand = next((b for b in brand_names if b and b.lower() in product.lower()), brand_names[0] if brand_names and brand_names[0] else "")
                log_entries.append({
                    "product": product,
                    "brand": brand,
                    "start_date": params.get("start-date"),
                    "end_date": params.get("end-date"),
                    "country": export_country,
                    "rows": rows_per_page,
                    "random_seed": random_seed if use_random else None,
                    "nb_reviews": len(all_docs),
                    "export_timestamp": export_date
                })
            
            if log_entries:
                new_log_df = pd.DataFrame(log_entries)
                if log_path.exists():
                    existing_log_df = pd.read_csv(log_path)
                    log_df = pd.concat([existing_log_df, new_log_df], ignore_index=True)
                else:
                    log_df = new_log_df
                log_df.to_csv(log_path, index=False)
                
                st.info("📝 Log d'export mis à jour dans 'review_exports_log.csv'")
        
        mode_text = "aperçu" if st.session_state.is_preview_mode else "export complet"
        status_text.text(f"✅ {mode_text.capitalize()} terminé! {len(all_docs)} reviews récupérées sur {page_count} pages.")

# Affichage des reviews si dispo
if st.session_state.all_docs:
    docs = st.session_state.all_docs
    total_results = len(docs)
    rows_per_page = int(rows_per_page)
    total_pages = max(1, (total_results + rows_per_page - 1) // rows_per_page)
    
    # S'assurer que la page actuelle est dans les limites valides
    if st.session_state.current_page > total_pages:
        st.session_state.current_page = total_pages
    if st.session_state.current_page < 1:
        st.session_state.current_page = 1
    
    current_page = st.session_state.current_page
    
    start_idx = (current_page - 1) * rows_per_page
    end_idx = min(start_idx + rows_per_page, total_results)
    page_docs = docs[start_idx:end_idx]
    
    # Afficher un bandeau différent selon le mode
    if st.session_state.is_preview_mode:
        st.warning("⚠️ Vous êtes en mode aperçu - Seulement un échantillon des données est affiché")
    
    st.markdown(f"""
    ### 📋 Résultats
    - **Total récupéré** : `{total_results}`
    - **Affichés sur cette page** : `{end_idx - start_idx}`
    - **Page actuelle** : `{current_page}` / `{total_pages}`
    """)
    
    df = pd.json_normalize(page_docs)
    df = df.applymap(lambda x: str(x) if isinstance(x, (dict, list)) else x)
    st.dataframe(df)
    
    # Pagination avec gestion d'état par callbacks pour éviter les experimental_rerun
    col1, col2 = st.columns(2)
    
    def prev_page():
        if st.session_state.current_page > 1:
            st.session_state.current_page -= 1
    
    def next_page():
        if st.session_state.current_page < total_pages:
            st.session_state.current_page += 1
    
    with col1:
        st.button("⬅️ Page précédente", on_click=prev_page, disabled=current_page <= 1)
    with col2:
        st.button("➡️ Page suivante", on_click=next_page, disabled=current_page >= total_pages)
    
    # Utiliser les params stockés pour les noms de fichiers
    export_params = st.session_state.export_params
    
    # Générer des noms de fichiers basés sur les filtres
    page_csv_filename = generate_export_filename(export_params, mode="page", page=current_page, extension="csv")
    page_excel_filename = generate_export_filename(export_params, mode="page", page=current_page, extension="xlsx")
    
    full_csv_filename = generate_export_filename(export_params, 
                                               mode="preview" if st.session_state.is_preview_mode else "complete", 
                                               extension="csv")
    full_excel_filename = generate_export_filename(export_params, 
                                                 mode="preview" if st.session_state.is_preview_mode else "complete", 
                                                 extension="xlsx")
    
    # Export de la page actuelle
    all_csv = df.to_csv(index=False)
    excel_buffer = io.BytesIO()
    with pd.ExcelWriter(excel_buffer, engine='openpyxl') as writer:
        df.to_excel(writer, index=False)
    excel_data = excel_buffer.getvalue()
    
    st.success(f"**Téléchargement prêt !** {len(page_docs)} résultats affichés.")
    col1, col2 = st.columns(2)
    with col1:
        st.download_button("📂 Télécharger la page en CSV", all_csv, file_name=page_csv_filename, mime="text/csv")
    with col2:
        st.download_button("📄 Télécharger la page en Excel", excel_data, file_name=page_excel_filename, mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
    
    # Export de toutes les données stockées
    st.markdown("---")
    st.subheader("📦 Exporter toutes les pages")
    full_df = pd.json_normalize(st.session_state.all_docs)
    full_df = full_df.applymap(lambda x: str(x) if isinstance(x, (dict, list)) else x)
    all_csv_full = full_df.to_csv(index=False)
    excel_buffer_full = io.BytesIO()
    with pd.ExcelWriter(excel_buffer_full, engine='openpyxl') as writer:
        full_df.to_excel(writer, index=False)
    excel_data_full = excel_buffer_full.getvalue()
    
    colf1, colf2 = st.columns(2)
    with colf1:
        st.download_button("📂 Télécharger toutes les reviews (CSV)", all_csv_full, file_name=full_csv_filename, mime="text/csv")
    with colf2:
        st.download_button("📄 Télécharger toutes les reviews (Excel)", excel_data_full, file_name=full_excel_filename, mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
    
    # Si on est en mode aperçu, proposer de passer à l'export complet
    if st.session_state.is_preview_mode:
        st.markdown("---")
        st.subheader("🚀 Passer à l'export complet")
        
        def switch_to_full_export():
            st.session_state.is_preview_mode = False
            st.session_state.switch_to_full_export = True
            # Pas de experimental_rerun nécessaire ici car la page se recharge naturellement
        
        st.button("📊 Récupérer toutes les reviews disponibles", on_click=switch_to_full_export)


if __name__ == "__main__":
    main()
