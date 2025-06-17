import streamlit as st
import requests
import pandas as pd
import datetime
import io
import altair as alt
import urllib.parse
from functools import partial
import ast
import json
import os
from pathlib import Path

st.set_page_config(page_title="Explorateur API Ratings & Reviews", layout="wide")

# Initialisation des variables de session
session_defaults = {
    "apply_filters": False,
    "cursor_mark": "*",
    "current_page": 1,
    "all_docs": [],
    "next_cursor": None,
    "selected_product_ids": [],
    "is_preview_mode": True,
    "export_params": {},
    "switch_to_full_export": False,
    "sort_column": "Nombre d'avis",
    "sort_ascending": False,
    "filters": {}
}

for key, default_value in session_defaults.items():
    st.session_state.setdefault(key, default_value)

@st.cache_data(ttl=3600)
def fetch_cached(endpoint, params=None):
    """Fonction pour récupérer les données de l'API avec cache"""
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
    """Récupère les produits pour une marque donnée avec filtres"""
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
    """Récupère les attributs dynamiquement selon les filtres"""
    params = {}
    if category != "ALL":
        params["category"] = category
    if subcategory != "ALL":
        params["subcategory"] = subcategory
    if brand:
        params["brand"] = ",".join(brand)
    return fetch_cached("/attributes", params)

def fetch(endpoint, params=None):
    """Wrapper pour la fonction fetch_cached"""
    return fetch_cached(endpoint, params)

def postprocess_reviews(df):
    """Fonction de postprocessing des reviews"""
    df.rename(columns={
        'id': 'guid',
        'category': 'categories',
        'content trad': 'verbatim_content',
        'product': 'product_name_SEMANTIWEB'
    }, inplace=True)
    
    if 'date' in df.columns:
        df['date'] = pd.to_datetime(df['date'], errors='coerce')
        df['date'] = df['date'].dt.strftime('01/%m/%Y')

    df['Sampling'] = df['business indicator'].apply(lambda x: 1 if 'Sampling Rate' in str(x) else 0)
    df = df.drop(columns=['content origin'], errors='ignore')

    predefined_attributes = [
        'Composition', 'Efficiency', 'Packaging', 'Price', 
        'Quality', 'Safety', 'Scent', 'Taste', 'Texture'
    ]
    attribute_columns = {attr: f"attribute_{attr}" for attr in predefined_attributes}
    for col_name in attribute_columns.values():
        df[col_name] = '0'

    pos_attributes_by_row = {}
    neg_attributes_by_row = {}
    all_attributes_by_row = {}

    for idx, row in df.iterrows():
        pos_attrs_set = set()
        neg_attrs_set = set()
        all_attrs_set = set()
        
        if pd.notna(row.get('attributes')):
            try:
                all_attrs = ast.literal_eval(row['attributes'])
                all_attrs_set = {attr for attr in all_attrs if attr in predefined_attributes}
            except (ValueError, SyntaxError):
                pass
                
        if pd.notna(row.get('attributes positive')):
            try:
                pos_attrs = ast.literal_eval(row['attributes positive'])
                pos_attrs_set = {attr for attr in pos_attrs if attr in predefined_attributes}
            except (ValueError, SyntaxError):
                pass
                
        if pd.notna(row.get('attributes negative')):
            try:
                neg_attrs = ast.literal_eval(row['attributes negative'])
                neg_attrs_set = {attr for attr in neg_attrs if attr in predefined_attributes}
            except (ValueError, SyntaxError):
                pass
                
        pos_attributes_by_row[idx] = pos_attrs_set
        neg_attributes_by_row[idx] = neg_attrs_set
        all_attributes_by_row[idx] = all_attrs_set

    for idx in all_attributes_by_row:
        all_attrs = all_attributes_by_row[idx]
        pos_attrs = pos_attributes_by_row[idx]
        neg_attrs = neg_attributes_by_row[idx]
        neutral_attrs = pos_attrs.intersection(neg_attrs)
        only_pos_attrs = pos_attrs - neutral_attrs
        only_neg_attrs = neg_attrs - neutral_attrs
        implicit_neutral_attrs = all_attrs - pos_attrs - neg_attrs
        
        for attr in neutral_attrs:
            df.at[idx, attribute_columns[attr]] = 'neutre'
        for attr in only_pos_attrs:
            df.at[idx, attribute_columns[attr]] = 'positive'
        for attr in only_neg_attrs:
            df.at[idx, attribute_columns[attr]] = 'negative'
        for attr in implicit_neutral_attrs:
            df.at[idx, attribute_columns[attr]] = 'neutre'

    original_columns = [col for col in df.columns if col not in ['attributes', 'attributes positive', 'attributes negative']]
    original_columns = [col for col in original_columns if not col.startswith('attribute_')]

    df['safety'] = '0'
    for idx in all_attributes_by_row:
        pos_attrs = pos_attributes_by_row[idx]
        neg_attrs = neg_attributes_by_row[idx]
        all_attrs = all_attributes_by_row[idx]
        safety_attrs = {'Safety', 'Composition'}
        safety_neutral = any(attr in (all_attrs - pos_attrs - neg_attrs) for attr in safety_attrs)
        safety_positive = any(attr in pos_attrs for attr in safety_attrs)
        safety_negative = any(attr in neg_attrs for attr in safety_attrs)
        
        if safety_positive and safety_negative:
            df.at[idx, 'safety'] = 'neutre'
        elif safety_positive:
            df.at[idx, 'safety'] = 'positive'
        elif safety_negative:
            df.at[idx, 'safety'] = 'negative'
        elif safety_neutral:
            df.at[idx, 'safety'] = 'neutre'

    final_columns = original_columns + list(attribute_columns.values()) + ['safety']
    return df[final_columns]

def generate_export_filename(params, mode="complete", page=None, extension="csv"):
    """Génère un nom de fichier basé sur les paramètres d'export"""
    filename_parts = ["reviews"]
    country = params.get("country", "").strip() if isinstance(params.get("country"), str) else ""
    if country:
        filename_parts.append(country.lower())

    products = params.get("product", "").split(",") if isinstance(params.get("product"), str) else []
    if products and products[0]:
        clean_products = []
        for p in products[:2]:
            clean_p = p.strip().lower().replace(" ", "_").replace("/", "-")
            if len(clean_p) > 15:
                clean_p = clean_p[:15]
            clean_products.append(clean_p)
        if clean_products:
            filename_parts.append("-".join(clean_products))
            if len(products) > 2:
                filename_parts[-1] += "-plus"

    start_date = params.get("start-date")
    end_date = params.get("end-date")
    
    if start_date is not None and end_date is not None:
        start_date_str = str(start_date).replace("-", "")
        end_date_str = str(end_date).replace("-", "")
        
        if len(start_date_str) >= 8 and len(end_date_str) >= 8:
            if start_date_str[:4] == end_date_str[:4]:
                date_str = f"{start_date_str[:4]}_{start_date_str[4:8]}-{end_date_str[4:8]}"
            else:
                date_str = f"{start_date_str}-{end_date_str}"
            filename_parts.append(date_str)

    if mode == "preview":
        filename_parts.append("apercu")
    elif mode == "page":
        filename_parts.append(f"page{page}")

    filename = "_".join(filename_parts) + f".{extension}"
    if len(filename) > 100:
        base, ext = filename.rsplit(".", 1)
        filename = base[:96] + "..." + "." + ext

    return filename

def display_quotas():
    """Affiche les quotas API"""
    result = fetch("/quotas")
    if result:
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            st.metric("Volume utilisé", result['used volume'])
        with col2:
            st.metric("Volume restant", result['remaining volume'])
        with col3:
            st.metric("Quota total", result['quota'])
        with col4:
            st.metric("Valable jusqu'au", result['end date'])

def load_filters_from_json(json_input):
    """Charge les filtres depuis un JSON"""
    try:
        # Nettoyer l'input avant parsing
        cleaned_input = json_input.strip()
        
        # Tenter de corriger automatiquement quelques erreurs courantes
        if not cleaned_input.startswith('{'):
            st.error("❌ Le JSON doit commencer par '{'")
            return
        
        # Essayer de parser d'abord tel quel
        try:
            parsed = json.loads(cleaned_input)
        except json.JSONDecodeError as e:
            st.error(f"❌ Erreur JSON à la ligne {e.lineno}, position {e.colno}: {e.msg}")
            st.error("Vérifiez que :")
            st.error("- Toutes les clés et valeurs sont entre guillemets")
            st.error("- Il y a des virgules entre chaque paire clé-valeur")
            st.error("- Les dates sont au format 'YYYY-MM-DD' entre guillemets")
            st.error("- Pas de virgule après le dernier élément")
            
            # Afficher un exemple corrigé
            st.info("📝 Exemple de JSON valide :")
            example_json = {
                "start-date": "2025-01-01",
                "end-date": "2025-04-30", 
                "brand": "AVÈNE,aderma,arthrodont,BIODERMA",
                "category": "bodycare",
                "subcategory": "body creams & milks",
                "country": "France",
                "token": "YOUR_TOKEN"
            }
            st.code(json.dumps(example_json, indent=2), language="json")
            return
        
        # Cast start/end-date si c'est une string
        for k in ["start-date", "end-date"]:
            if isinstance(parsed.get(k), str):
                date_str = parsed[k]
                # Gérer les différents formats de date
                if date_str.startswith("datetime.date("):
                    # Extraire les valeurs du format datetime.date(2025, 1, 1)
                    import re
                    match = re.search(r'datetime\.date\((\d+),\s*(\d+),\s*(\d+)\)', date_str)
                    if match:
                        year, month, day = match.groups()
                        parsed[k] = datetime.date(int(year), int(month), int(day))
                    else:
                        st.warning(f"Format de date non reconnu pour {k}: {date_str}")
                        parsed[k] = datetime.date.today()
                else:
                    try:
                        parsed[k] = pd.to_datetime(date_str).date()
                    except:
                        st.warning(f"Impossible de parser la date {k}: {date_str}")
                        parsed[k] = datetime.date.today()

        # Nettoyer et valider les marques
        brand_list = []
        if parsed.get("brand"):
            brand_str = parsed["brand"]
            if isinstance(brand_str, str):
                # Nettoyer les marques (enlever espaces superflus)
                brand_list = [brand.strip() for brand in brand_str.split(",") if brand.strip()]
            elif isinstance(brand_str, list):
                brand_list = brand_str

        # Nettoyer les autres listes
        country_list = []
        if parsed.get("country"):
            if isinstance(parsed["country"], str):
                country_list = [c.strip() for c in parsed["country"].split(",") if c.strip()]
            elif isinstance(parsed["country"], list):
                country_list = parsed["country"]

        source_list = []
        if parsed.get("source"):
            if isinstance(parsed["source"], str):
                source_list = [s.strip() for s in parsed["source"].split(",") if s.strip()]
            elif isinstance(parsed["source"], list):
                source_list = parsed["source"]

        market_list = []
        if parsed.get("market"):
            if isinstance(parsed["market"], str):
                market_list = [m.strip() for m in parsed["market"].split(",") if m.strip()]
            elif isinstance(parsed["market"], list):
                market_list = parsed["market"]

        # Injecter dans les filtres
        st.session_state.apply_filters = True
        st.session_state.filters = {
            "start_date": parsed.get("start-date", datetime.date(2022, 1, 1)),
            "end_date": parsed.get("end-date", datetime.date.today()),
            "category": parsed.get("category", "ALL"),
            "subcategory": parsed.get("subcategory", "ALL"),
            "brand": brand_list,
            "country": country_list,
            "source": source_list,
            "market": market_list,
            "attributes": parsed.get("attributes", []) if isinstance(parsed.get("attributes"), list) else [],
            "attributes_positive": parsed.get("attributes_positive", []) if isinstance(parsed.get("attributes_positive"), list) else [],
            "attributes_negative": parsed.get("attributes_negative", []) if isinstance(parsed.get("attributes_negative"), list) else []
        }
        
        # Afficher un résumé de ce qui a été chargé
        st.success("✅ Paramètres chargés avec succès.")
        st.info(f"📊 Résumé : {len(brand_list)} marque(s), du {parsed.get('start-date')} au {parsed.get('end-date')}")
        
    except Exception as e:
        st.error(f"❌ Erreur lors du parsing : {e}")
        st.error("💡 Astuce : Vérifiez que votre JSON est valide sur jsonlint.com")

def display_sidebar_filters():
    """Affiche les filtres dans la sidebar"""
    with st.sidebar:
        st.header("Filtres")

        st.markdown("### 📎 Charger une configuration via URL ou JSON")
        json_input = st.text_area("📥 Collez ici vos paramètres (JSON)", height=150, 
                                 help="Collez une chaîne JSON valide")

        if st.button("🔄 Charger les paramètres"):
            load_filters_from_json(json_input)

        # Filtres de base
        start_date = st.date_input("Date de début", value=datetime.date(2022, 1, 1))
        end_date = st.date_input("Date de fin", value=datetime.date.today())

        # Catégories
        categories = fetch("/categories")
        all_categories = ["ALL"] + [c["category"] for c in categories.get("categories", [])]
        category = st.selectbox("Catégorie", all_categories)

        # Sous-catégories
        subcategory_options = ["ALL"]
        if category != "ALL":
            for cat in categories.get("categories", []):
                if cat["category"] == category:
                    subcategory_options += cat["subcategories"]
        subcategory = st.selectbox("Sous-catégorie", subcategory_options)

        # Marques
        brands_params = {}
        if category != "ALL":
            brands_params["category"] = category
        if subcategory != "ALL":
            brands_params["subcategory"] = subcategory
        brands = fetch("/brands", brands_params)
        brand = st.multiselect("Marques", brands.get("brands", []))

        # Pays
        countries = fetch("/countries")
        all_countries = ["ALL"] + countries.get("countries", [])
        country = st.multiselect("Pays", all_countries)

        # Sources
        source_params = {}
        if country and country[0] != "ALL":
            source_params["country"] = country[0]
        sources = fetch("/sources", source_params)
        all_sources = ["ALL"] + sources.get("sources", [])
        source = st.multiselect("Sources", all_sources)

        # Markets
        markets = fetch("/markets")
        all_markets = ["ALL"] + markets.get("markets", [])
        market = st.multiselect("Markets", all_markets)

        # Attributs
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

        # Switch pour le type d'export - APRÈS l'application des filtres
        if st.session_state.get("apply_filters") and st.session_state.get("filters", {}).get("brand"):
            st.markdown("---")
            st.markdown("### 🔀 Mode d'export")
            
            export_strategy = st.radio(
                "Stratégie d'export",
                [
                    "🚀 Export en masse par marque (recommandé pour beaucoup de produits)",
                    "🎯 Export par sélection de produits (précis)"
                ],
                key="export_strategy_choice",
                help="Choisissez dès maintenant pour éviter le chargement inutile de listes de produits"
            )
            
            st.session_state.export_strategy = export_strategy
            
            # Affichage d'informations selon la stratégie
            if "🚀 Export en masse" in export_strategy:
                st.success("⚡ Mode rapide sélectionné : Pas de chargement de liste de produits")
                st.info(f"Exportera toutes les reviews pour : {', '.join(st.session_state.filters['brand'])}")
            else:
                st.info("🔍 Mode précis sélectionné : La liste des produits va être chargée")
                
                # Estimation du nombre de produits à charger
                total_products_estimate = 0
                with st.spinner("Estimation du nombre de produits..."):
                    for brand in st.session_state.filters["brand"][:3]:  # Échantillon des 3 premières marques
                        products = fetch_products_by_brand(
                            brand, 
                            st.session_state.filters["category"], 
                            st.session_state.filters["subcategory"], 
                            st.session_state.filters["start_date"], 
                            st.session_state.filters["end_date"]
                        )
                        if products and products.get("products"):
                            total_products_estimate += len(products["products"])
                
                # Extrapoler pour toutes les marques
                if len(st.session_state.filters["brand"]) > 3:
                    avg_products_per_brand = total_products_estimate / min(3, len(st.session_state.filters["brand"]))
                    total_products_estimate = int(avg_products_per_brand * len(st.session_state.filters["brand"]))
                
                if total_products_estimate > 500:
                    st.warning(f"⚠️ Estimation : ~{total_products_estimate} produits à charger. Cela peut prendre du temps et consommer du quota API.")
                    if st.button("🔄 Changer pour l'export en masse", key="switch_to_bulk"):
                        st.session_state.export_strategy = "🚀 Export en masse par marque (recommandé pour beaucoup de produits)"
                        st.experimental_rerun()
                else:
                    st.success(f"✅ Estimation : ~{total_products_estimate} produits à charger")

def display_export_interface():
    """Affiche l'interface d'export selon la stratégie choisie"""
    if not st.session_state.get("export_strategy"):
        st.warning("⚠️ Veuillez d'abord choisir une stratégie d'export dans la sidebar")
        return
    
    strategy = st.session_state.export_strategy
    
    if "🚀 Export en masse" in strategy:
        # Export en masse direct
        st.markdown("---")
        st.header("🚀 Export en masse par marque")
        display_bulk_export_interface()
        
    else:
        # Export par sélection de produits
        st.markdown("---")
        st.header("🎯 Sélection de produits")
        
        # Afficher un récapitulatif avant le chargement
        filters = st.session_state.filters
        st.info(f"📊 Chargement des produits pour {len(filters['brand'])} marque(s) : {', '.join(filters['brand'])}")
        
        if st.button("▶️ Charger la liste des produits", key="load_products_list"):
            with st.spinner("Chargement en cours..."):
                selected_products = display_product_selection()
                
                # Interface d'export classique
                st.markdown("---")
                display_reviews_export_interface(st.session_state.filters, selected_products)
        else:
            st.markdown("""
            💡 **Conseil** : Cliquez sur "▶️ Charger la liste des produits" pour voir tous les produits disponibles.
            
            ⚠️ **Attention** : Avec beaucoup de marques, cela peut prendre plusieurs minutes et consommer votre quota API.
            """)

def main():
    """Fonction principale de l'application"""
    st.title("🔍 Explorateur API Ratings & Reviews")
    
    # Affichage des quotas en header
    with st.expander("📊 Quotas API", expanded=False):
        display_quotas()
    
    # Sidebar avec filtres
    display_sidebar_filters()
    
    # Interface principale
    if st.session_state.get("apply_filters") and st.session_state.get("filters"):
        # Affichage du résumé des filtres
        display_filter_summary()
        
        # Affichage des produits par marque (optionnel)
        display_products_by_brand()
        
        # Interface d'export selon la stratégie
        display_export_interface()
        
        # Affichage des résultats si disponibles
        if st.session_state.all_docs:
            st.markdown("---")
            display_reviews_results()
        
        # Configuration d'export réutilisable
        display_export_configuration()
        
    else:
        st.markdown("""
        ## 👋 Bienvenue dans l'Explorateur API Ratings & Reviews
        
        Pour commencer :
        1. **Configurez vos filtres** dans la barre latérale gauche
        2. **Appliquez les filtres** en cliquant sur "✅ Appliquer les filtres"
        3. **Choisissez votre stratégie d'export** :
           - 🚀 **Export en masse** : Rapide, idéal pour beaucoup de produits
           - 🎯 **Export par sélection** : Précis, pour des choix spécifiques
        4. **Exportez vos reviews** avec les options disponibles
        
        💡 **Astuce** : Vous pouvez charger une configuration existante en collant un JSON dans la zone de configuration.
        """)

if __name__ == "__main__":
    main()
    """Affiche le résumé des filtres appliqués"""
    filters = st.session_state.filters
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

def display_products_by_brand():
    """Affiche les produits filtrés par marque"""
    filters = st.session_state.filters
    
    st.markdown("---")
    st.header("📦 Produits par marque selon les filtres appliqués")
    
    if st.checkbox("📋 Afficher les produits filtrés par marque"):
        with st.spinner("Chargement des produits par marque avec les filtres..."):
            product_rows = []
            load_reviews_count = st.checkbox("📈 Inclure le nombre d'avis par produit", value=False)

            for i, brand in enumerate(filters["brand"]):
                st.write(f"🔍 {i+1}/{len(filters['brand'])} : {brand}")
                params = {
                    "brand": brand,
                    "start-date": filters["start_date"],
                    "end-date": filters["end_date"]
                }
                if filters["category"] != "ALL":
                    params["category"] = filters["category"]
                if filters["subcategory"] != "ALL":
                    params["subcategory"] = filters["subcategory"]
                if filters["country"] and "ALL" not in filters["country"]:
                    params["country"] = ",".join(filters["country"])
                if filters["source"] and "ALL" not in filters["source"]:
                    params["source"] = ",".join(filters["source"])
                if filters["market"] and "ALL" not in filters["market"]:
                    params["market"] = ",".join(filters["market"])

                products_data = fetch_cached("/products", params)

                for product in products_data.get("products", []):
                    product_info = {"Marque": brand, "Produit": product}

                    if load_reviews_count:
                        metric_params = params.copy()
                        metric_params["product"] = product
                        metrics = fetch("/metrics", metric_params)
                        nb_reviews = metrics.get("nbDocs", 0) if metrics else 0
                        product_info["Nombre d'avis"] = nb_reviews

                    product_rows.append(product_info)

            if product_rows:
                df_filtered_products = pd.DataFrame(product_rows)
                st.dataframe(df_filtered_products)
                st.download_button(
                    "⬇️ Télécharger la liste filtrée",
                    df_filtered_products.to_csv(index=False),
                    file_name="produits_filtrés_par_marque.csv",
                    mime="text/csv"
                )
            else:
                st.warning("Aucun produit trouvé avec ces filtres.")

def display_product_selection():
    """Affiche la sélection de produits avec interface interactive"""
    filters = st.session_state.filters
    product_info = {}
    product_data = []
    
    if filters["brand"]:
        with st.spinner("Chargement des produits par marque..."):
            for i, b in enumerate(filters["brand"]):
                st.write(f"🔎 {i+1}/{len(filters['brand'])} : {b}")
                products = fetch_products_by_brand(b, filters["category"], filters["subcategory"], 
                                                 filters["start_date"], filters["end_date"])
                if products and products.get("products"):
                    for p in products["products"]:
                        label = f"{b} > {p}"
                        product_info[label] = p
                        product_data.append({"Marque": b, "Produit": p})

    if product_data:
        st.subheader("📊 Produits disponibles")
        
        # Option pour charger le nombre d'avis
        load_reviews_count = st.checkbox(
            "📈 Charger le nombre d'avis par produit", 
            value=False,
            help="Cette option peut prendre du temps à charger"
        )
        
        # Ajouter une recherche pour filtrer les produits
        search_text = st.text_input("🔍 Filtrer les produits")
        
        # Récupérer le nombre d'avis par produit seulement si demandé
        if load_reviews_count:
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
        else:
            for i, row in enumerate(product_data):
                product_data[i]["Nombre d'avis"] = "Non chargé"
        
        # Créer un DataFrame avec les données
        df_products = pd.DataFrame(product_data)
        
        # Filtrer selon la recherche
        if search_text:
            mask = df_products["Produit"].str.contains(search_text, case=False) | df_products["Marque"].str.contains(search_text, case=False)
            filtered_df = df_products[mask]
        else:
            filtered_df = df_products
        
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
        if st.session_state.sort_column in filtered_df.columns:
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

        # Liste des produits visibles à l'écran
        visible_product_ids = list(filtered_df["Produit"].values)
        
        # Interface de sélection groupée
        col_sel_all, col_apply_sel, col_deselect_all = st.columns([1, 2, 2])
        with col_sel_all:
            select_all = st.checkbox("✅ Tout sélectionner les produits affichés", key="select_all_toggle")
        
        with col_apply_sel:
            if st.button("🎯 Appliquer la sélection visible"):
                if select_all:
                    for pid in visible_product_ids:
                        if pid not in st.session_state.selected_product_ids:
                            st.session_state.selected_product_ids.append(pid)
                else:
                    st.session_state.selected_product_ids = [
                        pid for pid in st.session_state.selected_product_ids if pid not in visible_product_ids
                    ]
        
        with col_deselect_all:
            if st.button("❌ Tout désélectionner"):
                st.session_state.selected_product_ids = []

        # Affichage ligne par ligne avec checkbox
        for index, row in filtered_df.iterrows():
            product_id = row["Produit"]
            
            col1, col2, col3, col4 = st.columns([0.5, 2, 2, 1])
            with col1:
                is_selected = st.checkbox(
                    "", 
                    value=product_id in st.session_state.selected_product_ids,
                    key=f"check_{index}_{product_id}"
                )
            with col2:
                st.write(row["Marque"])
            with col3:
                st.write(row["Produit"])
            with col4:
                st.write(f"{row['Nombre d\'avis']}")
        
            # Mise à jour à la volée
            if is_selected and product_id not in st.session_state.selected_product_ids:
                st.session_state.selected_product_ids.append(product_id)
            elif not is_selected and product_id in st.session_state.selected_product_ids:
                st.session_state.selected_product_ids.remove(product_id)

        # Résumé sélection
        st.write("---")
        selected_products = st.session_state.selected_product_ids
        if selected_products:
            st.write(f"**{len(selected_products)} produits sélectionnés** : {', '.join(selected_products)}")
        else:
            st.write("**Aucun produit sélectionné.**")
            
        return selected_products
    
    return []

def display_reviews_export_interface(filters, selected_products):
    """Affiche l'interface d'export des reviews"""
    # Construction des paramètres d'export
    params = {
        "start-date": filters["start_date"],
        "end-date": filters["end_date"]
    }
    
    if filters["category"] != "ALL":
        params["category"] = filters["category"]
    if filters["subcategory"] != "ALL":
        params["subcategory"] = filters["subcategory"]
    if filters["brand"]:
        params["brand"] = ",".join(filters["brand"])
    if filters["country"] and "ALL" not in filters["country"]:
        params["country"] = ",".join(filters["country"])
    if filters["source"] and "ALL" not in filters["source"]:
        params["source"] = ",".join(filters["source"])
    if filters["market"] and "ALL" not in filters["market"]:
        params["market"] = ",".join(filters["market"])
    if filters["attributes"]:
        params["attribute"] = ",".join(filters["attributes"])
    if filters["attributes_positive"]:
        params["attribute-positive"] = ",".join(filters["attributes_positive"])
    if filters["attributes_negative"]:
        params["attribute-negative"] = ",".join(filters["attributes_negative"])
    if selected_products:
        params["product"] = ",".join(selected_products)
    
    # Affichage des métriques
    dynamic_metrics = fetch("/metrics", params)
    if dynamic_metrics and dynamic_metrics.get("nbDocs"):
        st.success(f"{dynamic_metrics['nbDocs']} reviews disponibles")
    else:
        st.warning("Aucune review disponible pour cette combinaison")

    st.markdown("## ⚙️ Paramètres d'export des reviews")

    # Journal des exports
    log_path = Path("review_exports_log.csv")
    if log_path.exists():
        with st.expander("📁 Consulter le journal des exports précédents", expanded=False):
            export_log_df = pd.read_csv(log_path)
            st.dataframe(export_log_df)
            st.download_button("⬇️ Télécharger le journal des exports", export_log_df.to_csv(index=False), file_name="review_exports_log.csv", mime="text/csv")
    
    with st.expander("🔧 Options d'export", expanded=True):
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
            col1, col2, col3, col4 = st.columns(4)
            with col1:
                st.metric("Volume utilisé", quotas['used volume'])
            with col2:
                st.metric("Volume restant", quotas['remaining volume'])
            with col3:
                st.metric("Quota total", quotas['quota'])
            with col4:
                st.metric("Valable jusqu'au", quotas['end date'])
    
        # ✅ Vérification d'export déjà réalisé, englobant ou identique
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
                        
                
                status_text = st.empty()                  # ✅ Toujours défini
            
                # Afficher une barre de progression seulement en mode export complet
                progress_bar = None if st.session_state.is_preview_mode else st.progress(0)
                
                cursor_mark = "*"
                page_count = 0
                all_docs = []
                
                # Ajout d'un mécanisme de sécurité pour éviter les boucles infinies
                max_iterations = min(100, expected_total_pages + 5)  # Limite raisonnable
                
                # Boucle pour récupérer les pages via cursor pagination
                try:
                    while page_count < max_iterations:
                        page_count += 1
                        status_text.text(f"Chargement de la page {page_count}/{expected_total_pages if not st.session_state.is_preview_mode else 1}...")
                        
                        # Ajouter le cursor_mark aux paramètres
                        current_params = params_with_rows.copy()
                        current_params["cursorMark"] = cursor_mark
                        
                        # Récupérer la page courante
                        result = fetch("/reviews", current_params)
                        
                        # Vérifier si le résultat est valide et contient des documents
                        if not result or not result.get("docs") or len(result.get("docs", [])) == 0:
                            break
                            
                        # Ajouter les documents à notre collection
                        docs = result.get("docs", [])
                        all_docs.extend(docs)
                        
                        # Mettre à jour la barre de progression uniquement en mode export complet
                        if progress_bar is not None:
                            progress_percent = min(page_count / expected_total_pages, 1.0) if expected_total_pages > 0 else 1.0
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
                            
                except Exception as e:
                    st.error(f"Erreur lors de la récupération des données: {str(e)}")
                    
                # Stocker tous les documents récupérés
                st.session_state.all_docs = all_docs
                
                # 🔒 Génération du log d'export local (uniquement pour l'export complet)
                if not st.session_state.is_preview_mode and all_docs:
                    try:
                        export_date = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                        export_country = params.get("country", "Tous")
                        
                        product_names = params.get("product", "").split(",") if params.get("product") else []
                        brand_names = params.get("brand", "").split(",") if params.get("brand") else []
                        
                        log_entries = []
                        for product in product_names:
                            if not product.strip():
                                continue
                            brand = ""
                            if brand_names and brand_names[0]:
                                for b in brand_names:
                                    if b and b.lower() in product.lower():
                                        brand = b
                                        break
                                if not brand and brand_names[0]:
                                    brand = brand_names[0]
                                    
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
                    except Exception as e:
                        st.warning(f"Erreur lors de la mise à jour du journal d'export: {str(e)}")
                
                mode_text = "aperçu" if st.session_state.is_preview_mode else "export complet"
                if all_docs:
                    status_text.text(f"✅ {mode_text.capitalize()} terminé! {len(all_docs)} reviews récupérées sur {page_count} pages.")
                else:
                    status_text.text(f"⚠️ Aucune review récupérée. Vérifiez vos filtres.")

def display_reviews_results():
    """Affiche les résultats des reviews récupérées"""
    if st.session_state.all_docs:
        docs = st.session_state.all_docs
        total_results = len(docs)
        
        # Utiliser un nombre de lignes par page par défaut si pas encore défini
        rows_per_page = 100  # Valeur par défaut
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
        col1, col2, col3 = st.columns(3)
        with col1:
            st.download_button("📂 Télécharger la page en CSV", all_csv, file_name=page_csv_filename, mime="text/csv")
        with col2:
            st.download_button("📄 Télécharger la page en Excel", excel_data, file_name=page_excel_filename, mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
        with col3:
            try:
                df_flat_page = postprocess_reviews(df.copy())
                flat_csv_page = df_flat_page.to_csv(index=False, sep=';', encoding='utf-8-sig')
                flat_page_filename = generate_export_filename(export_params, mode="page", page=current_page, extension="plat.csv")
                st.download_button("📃 Télécharger le format à plat", flat_csv_page, file_name=flat_page_filename, mime="text/csv")
            except Exception as e:
                st.warning(f"Erreur format plat : {e}")

        # Export de toutes les données stockées
        st.markdown("---")
        st.subheader("📦 Exporter " + ("l'aperçu actuel" if st.session_state.is_preview_mode else "toutes les pages"))
        
        if st.session_state.is_preview_mode:
            st.info("⚠️ Vous êtes en mode aperçu. Ce téléchargement contient uniquement un échantillon limité des données (max 50 reviews).")
        else:
            st.success("✅ Ce téléchargement contient l'ensemble des reviews correspondant à vos filtres.")
        
        # Afficher le nom du fichier pour transparence
        st.markdown(f"**Nom de fichier généré :** `{full_csv_filename}`")
        
        full_df = pd.json_normalize(st.session_state.all_docs)
        full_df = full_df.applymap(lambda x: str(x) if isinstance(x, (dict, list)) else x)
        all_csv_full = full_df.to_csv(index=False, encoding="utf-8-sig")
        
        excel_buffer_full = io.BytesIO()
        with pd.ExcelWriter(excel_buffer_full, engine='openpyxl') as writer:
            full_df.to_excel(writer, index=False)
        excel_data_full = excel_buffer_full.getvalue()
        
        colf1, colf2, colf3 = st.columns(3)
        with colf1:
            st.download_button("📂 Télécharger les reviews en CSV", all_csv_full, file_name=full_csv_filename, mime="text/csv")
        with colf2:
            st.download_button("📄 Télécharger les reviews en Excel", excel_data_full, file_name=full_excel_filename, mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
        with colf3:
            try:
                df_flat_full = postprocess_reviews(full_df.copy())
                flat_csv_full = df_flat_full.to_csv(index=False, sep=';', encoding='utf-8-sig')
                flat_full_filename = generate_export_filename(export_params, mode="preview" if st.session_state.is_preview_mode else "complete", extension="plat.csv")
                st.download_button("📃 Télécharger le format à plat", flat_csv_full, file_name=flat_full_filename, mime="text/csv")
            except Exception as e:
                st.warning(f"Erreur format plat : {e}")

def display_export_configuration():
    """Affiche la configuration d'export réutilisable"""
    if st.session_state.get("filters"):
        st.markdown("---")
        st.markdown("### 📋 Configuration réutilisable")
        st.markdown("Vous pouvez copier ce bloc et le coller dans la barre de configuration pour relancer cet export plus tard.")
        
        import json
        export_token = st.secrets["api"]["token"] if "api" in st.secrets else "YOUR_TOKEN"
        export_preset = {
            "start-date": str(st.session_state.filters["start_date"]),
            "end-date": str(st.session_state.filters["end_date"]),
            "brand": ",".join(st.session_state.filters["brand"]),
            "category": st.session_state.filters.get("category", "ALL"),
            "subcategory": st.session_state.filters.get("subcategory", "ALL"),
            "token": export_token
        }
        
        # Ajouter les autres filtres s'ils sont définis
        if st.session_state.filters.get("country") and "ALL" not in st.session_state.filters["country"]:
            export_preset["country"] = ",".join(st.session_state.filters["country"])
        if st.session_state.filters.get("source") and "ALL" not in st.session_state.filters["source"]:
            export_preset["source"] = ",".join(st.session_state.filters["source"])
        if st.session_state.filters.get("market") and "ALL" not in st.session_state.filters["market"]:
            export_preset["market"] = ",".join(st.session_state.filters["market"])
        if st.session_state.filters.get("attributes"):
            export_preset["attributes"] = st.session_state.filters["attributes"]
        if st.session_state.filters.get("attributes_positive"):
            export_preset["attributes_positive"] = st.session_state.filters["attributes_positive"]
        if st.session_state.filters.get("attributes_negative"):
            export_preset["attributes_negative"] = st.session_state.filters["attributes_negative"]
        
        st.code(json.dumps(export_preset, indent=2), language="json")

def main():
    """Fonction principale de l'application"""
    st.title("🔍 Explorateur API Ratings & Reviews")
    
    # Affichage des quotas en header
    with st.expander("📊 Quotas API", expanded=False):
        display_quotas()
    
    # Sidebar avec filtres
    display_sidebar_filters()
    
    # Interface principale
    if st.session_state.get("apply_filters") and st.session_state.get("filters"):
        # Affichage du résumé des filtres
        display_filter_summary()
        
        # Affichage des produits par marque
        display_products_by_brand()
        
def display_bulk_export_interface():
    """Interface d'export en masse par marque"""
    st.markdown("---")
    st.header("🚀 Export en masse par marque")
    
    filters = st.session_state.filters
    
    # Options d'export en masse
    with st.expander("📦 Options d'export en masse", expanded=True):
        st.markdown("""
        **Export en masse** : Récupère toutes les reviews pour les marques sélectionnées **sans** avoir besoin de sélectionner les produits individuellement.
        
        ⚡ **Avantages :**
        - Pas d'appels API pour chaque produit individuel
        - Export rapide de milliers de reviews
        - Idéal pour des analyses globales par marque
        """)
        
        col1, col2 = st.columns(2)
        
        with col1:
            bulk_rows_per_page = st.number_input(
                "Reviews par page (bulk)",
                min_value=10,
                max_value=1000,
                value=500,
                step=50,
                help="Plus élevé = moins d'appels API mais plus de mémoire"
            )
        
        with col2:
            bulk_use_random = st.checkbox("Randomiser les résultats (bulk)")
            if bulk_use_random:
                bulk_random_seed = st.number_input(
                    "Seed aléatoire (bulk)", 
                    min_value=1, 
                    max_value=9999, 
                    value=42
                )
            else:
                bulk_random_seed = None
        
        # Mode d'export
        bulk_mode = st.radio(
            "Mode d'export en masse",
            ["Aperçu rapide (100 reviews max)", "Export complet par marque"],
            key="bulk_export_mode"
        )
        
        # Estimation du volume
        if filters.get("brand"):
            st.markdown("### 📊 Estimation du volume")
            total_estimated = 0
            
            with st.spinner("Estimation du volume total..."):
                for brand in filters["brand"]:
                    brand_params = {
                        "brand": brand,
                        "start-date": filters["start_date"],
                        "end-date": filters["end_date"]
                    }
                    
                    # Ajouter les autres filtres
                    if filters["category"] != "ALL":
                        brand_params["category"] = filters["category"]
                    if filters["subcategory"] != "ALL":
                        brand_params["subcategory"] = filters["subcategory"]
                    if filters["country"] and "ALL" not in filters["country"]:
                        brand_params["country"] = ",".join(filters["country"])
                    if filters["source"] and "ALL" not in filters["source"]:
                        brand_params["source"] = ",".join(filters["source"])
                    if filters["market"] and "ALL" not in filters["market"]:
                        brand_params["market"] = ",".join(filters["market"])
                    
                    metrics = fetch("/metrics", brand_params)
                    brand_count = metrics.get("nbDocs", 0) if metrics else 0
                    total_estimated += brand_count
                    
                    st.write(f"• **{brand}** : {brand_count:,} reviews")
            
            st.success(f"**Total estimé : {total_estimated:,} reviews** pour {len(filters['brand'])} marque(s)")
            
            if bulk_mode == "Aperçu rapide (100 reviews max)":
                actual_export = min(100, total_estimated)
                st.info(f"Mode aperçu : {actual_export} reviews seront exportées")
            else:
                st.info(f"Export complet : {total_estimated:,} reviews seront exportées")
        
        # Bouton de lancement
        if st.button("🚀 Lancer l'export en masse", key="launch_bulk_export"):
            if not filters.get("brand"):
                st.error("❌ Aucune marque sélectionnée pour l'export en masse")
                return
            
            # Construire les paramètres pour l'export en masse
            bulk_params = {
                "start-date": filters["start_date"],
                "end-date": filters["end_date"],
                "brand": ",".join(filters["brand"])  # Toutes les marques en une fois
            }
            
            # Ajouter les autres filtres
            if filters["category"] != "ALL":
                bulk_params["category"] = filters["category"]
            if filters["subcategory"] != "ALL":
                bulk_params["subcategory"] = filters["subcategory"]
            if filters["country"] and "ALL" not in filters["country"]:
                bulk_params["country"] = ",".join(filters["country"])
            if filters["source"] and "ALL" not in filters["source"]:
                bulk_params["source"] = ",".join(filters["source"])
            if filters["market"] and "ALL" not in filters["market"]:
                bulk_params["market"] = ",".join(filters["market"])
            if filters["attributes"]:
                bulk_params["attribute"] = ",".join(filters["attributes"])
            if filters["attributes_positive"]:
                bulk_params["attribute-positive"] = ",".join(filters["attributes_positive"])
            if filters["attributes_negative"]:
                bulk_params["attribute-negative"] = ",".join(filters["attributes_negative"])
            
            # Paramètres de pagination
            is_bulk_preview = bulk_mode == "Aperçu rapide (100 reviews max)"
            
            if is_bulk_preview:
                bulk_params["rows"] = min(bulk_rows_per_page, 100)
            else:
                bulk_params["rows"] = bulk_rows_per_page
            
            if bulk_use_random and bulk_random_seed:
                bulk_params["random"] = str(bulk_random_seed)
            
            # Stocker les paramètres pour les noms de fichiers
            st.session_state.export_params = bulk_params.copy()
            st.session_state.is_preview_mode = is_bulk_preview
            
            # Lancer l'export
            execute_bulk_export(bulk_params, is_bulk_preview)

def execute_bulk_export(params, is_preview):
    """Exécute l'export en masse"""
    st.markdown("### 🔄 Export en cours...")
    
    # Obtenir les métriques totales
    metrics_result = fetch("/metrics", params)
    total_api_results = metrics_result.get("nbDocs", 0) if metrics_result else 0
    
    if total_api_results == 0:
        st.warning("❌ Aucune review disponible pour cette combinaison")
        return
    
    # Configuration selon le mode
    if is_preview:
        expected_total_pages = 1
        max_reviews = min(100, total_api_results)
        st.info(f"📊 Mode aperçu : Chargement de {max_reviews} reviews maximum sur {total_api_results} disponibles")
    else:
        rows_per_page = params.get("rows", 500)
        expected_total_pages = (total_api_results + rows_per_page - 1) // rows_per_page
        st.info(f"🔄 Export complet : Chargement de toutes les {total_api_results:,} reviews sur {expected_total_pages} pages...")
    
    # Interface de progression
    status_text = st.empty()
    progress_bar = None if is_preview else st.progress(0)
    
    cursor_mark = "*"
    page_count = 0
    all_docs = []
    max_iterations = min(200, expected_total_pages + 10)  # Sécurité
    
    # Boucle de récupération
    try:
        while page_count < max_iterations:
            page_count += 1
            status_text.text(f"📥 Chargement page {page_count}/{expected_total_pages if not is_preview else 1}...")
            
            # Paramètres avec cursor
            current_params = params.copy()
            current_params["cursorMark"] = cursor_mark
            
            # Appel API
            result = fetch("/reviews", current_params)
            
            if not result or not result.get("docs"):
                st.warning(f"⚠️ Pas de données à la page {page_count}")
                break
            
            docs = result.get("docs", [])
            all_docs.extend(docs)
            
            # Mise à jour progression
            if progress_bar is not None:
                progress_percent = min(page_count / expected_total_pages, 1.0) if expected_total_pages > 0 else 1.0
                progress_bar.progress(progress_percent)
            
            # En mode aperçu, on s'arrête après la première page
            if is_preview:
                break
            
            # Vérifier le cursor suivant
            next_cursor = result.get("nextCursorMark")
            if not next_cursor or next_cursor == cursor_mark:
                break
            
            cursor_mark = next_cursor
            
            # Limite aperçu
            if is_preview and len(all_docs) >= 100:
                break
    
    except Exception as e:
        st.error(f"❌ Erreur lors de l'export : {str(e)}")
        return
    
    # Stocker les résultats
    st.session_state.all_docs = all_docs
    st.session_state.current_page = 1
    
    # Messages finaux
    mode_text = "aperçu en masse" if is_preview else "export complet en masse"
    if all_docs:
        status_text.text(f"✅ {mode_text.capitalize()} terminé! {len(all_docs):,} reviews récupérées")
        st.balloons()  # Célébration pour les gros exports !
        
        # Log pour export complet
        if not is_preview:
            log_bulk_export(params, len(all_docs))
        
    else:
        status_text.text(f"⚠️ Aucune review récupérée.")

def log_bulk_export(params, nb_reviews):
    """Enregistre l'export en masse dans le log"""
    try:
        log_path = Path("review_exports_log.csv")
        export_date = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        brands = params.get("brand", "").split(",") if params.get("brand") else []
        
        log_entry = {
            "product": "BULK_EXPORT_ALL_PRODUCTS",
            "brand": params.get("brand", ""),
            "start_date": params.get("start-date"),
            "end_date": params.get("end-date"),
            "country": params.get("country", "Tous"),
            "rows": params.get("rows", 500),
            "random_seed": params.get("random", None),
            "nb_reviews": nb_reviews,
            "export_timestamp": export_date,
            "export_type": "BULK_BY_BRAND"
        }
        
        new_log_df = pd.DataFrame([log_entry])
        
        if log_path.exists():
            existing_log_df = pd.read_csv(log_path)
            log_df = pd.concat([existing_log_df, new_log_df], ignore_index=True)
        else:
            log_df = new_log_df
            
        log_df.to_csv(log_path, index=False)
        st.success("📝 Export en masse enregistré dans le journal")
        
    except Exception as e:
        st.warning(f"⚠️ Erreur lors de l'enregistrement du log : {str(e)}")
        
        # Affichage des résultats si disponibles
        if st.session_state.all_docs:
            st.markdown("---")
            display_reviews_results()
        
        # Configuration d'export réutilisable
        display_export_configuration()
        
    else:
        st.markdown("""
        ## 👋 Bienvenue dans l'Explorateur API Ratings & Reviews
        
        Pour commencer :
        1. **Configurez vos filtres** dans la barre latérale gauche
        2. **Appliquez les filtres** en cliquant sur "✅ Appliquer les filtres"
        3. **Sélectionnez vos produits** dans la liste qui s'affichera
        4. **Exportez vos reviews** avec les options disponibles
        
        💡 **Astuce** : Vous pouvez charger une configuration existante en collant un JSON dans la zone de configuration.
        """)

if __name__ == "__main__":
    main()
