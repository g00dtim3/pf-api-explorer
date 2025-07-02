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
import time

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
    "filters": {},
    "export_strategy": None,
    "total_found": 0,
    "current_docs": []
}

for key, default_value in session_defaults.items():
    st.session_state.setdefault(key, default_value)

@st.cache_data(ttl=3600)
def fetch_cached(endpoint, params=None):
    """Fonction pour récupérer les données de l'API avec cache"""
    BASE_URL = "https://api-pf.ratingsandreviews-beauty.com"
    
    # Improved token handling with multiple fallback methods
    TOKEN = None
    try:
        # Try environment variable first
        TOKEN = os.getenv("API_TOKEN")
        if not TOKEN:
            # Try Streamlit secrets
            TOKEN = st.secrets.get("api", {}).get("token", "")
        if not TOKEN:
            # Try alternative secret structure
            TOKEN = st.secrets.get("API_TOKEN", "")
    except Exception:
        pass
    
    if not TOKEN:
        st.error("❌ ERREUR: Token API manquant. Veuillez configurer API_TOKEN dans les secrets.")
        return {}
    
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

    try:
        response = requests.get(url, headers={"Accept": "application/json"})
        if response.status_code == 200:
            return response.json().get("result", {})
        else:
            st.error(f"Erreur {response.status_code} sur {url}")
            st.error(f"Réponse: {response.text}")
            return {}
    except Exception as e:
        st.error(f"Erreur de connexion: {str(e)}")
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
    """Wrapper pour la fonction fetch_cached avec gestion améliorée des curseurs"""
    result = fetch_cached(endpoint, params)
    
    # Gestion spéciale pour les endpoints avec pagination
    if endpoint == "/reviews" and result:
        # Extraire le nextCursorMark si présent
        if "nextCursorMark" in result:
            next_cursor = result["nextCursorMark"]
            # Vérifier si le cursor a changé
            current_cursor = params.get("cursorMark", "*") if params else "*"
            if next_cursor != current_cursor:
                st.session_state.next_cursor = next_cursor
            else:
                # Fin de pagination atteinte
                st.session_state.next_cursor = None
        else:
            st.session_state.next_cursor = None
            
        # Stocker le nombre total de résultats
        if "numFound" in result:
            st.session_state.total_found = result["numFound"]
            
    return result

def postprocess_reviews(df):
    """Fonction de postprocessing des reviews"""
    if df.empty:
        return df
        
    df.rename(columns={
        'id': 'guid',
        'category': 'categories',
        'content trad': 'verbatim_content',
        'product': 'product_name_SEMANTIWEB'
    }, inplace=True)
    
    if 'date' in df.columns:
        df['date'] = pd.to_datetime(df['date'], errors='coerce')
        df['date'] = df['date'].dt.strftime('01/%m/%Y')

    if 'business indicator' in df.columns:
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
    available_columns = [col for col in final_columns if col in df.columns]
    return df[available_columns]

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
            st.metric("Volume utilisé", result.get('used volume', 'N/A'))
        with col2:
            st.metric("Volume restant", result.get('remaining volume', 'N/A'))
        with col3:
            st.metric("Quota total", result.get('quota', 'N/A'))
        with col4:
            st.metric("Valable jusqu'au", result.get('end date', 'N/A'))

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
        if "brand" in parsed:
            if isinstance(parsed["brand"], str):
                # Diviser par virgules et nettoyer
                brands = [b.strip() for b in parsed["brand"].split(",") if b.strip()]
                brand_list = brands
            elif isinstance(parsed["brand"], list):
                brand_list = [str(b).strip() for b in parsed["brand"] if str(b).strip()]
            parsed["brand"] = brand_list

        # Appliquer les filtres
        st.session_state.filters.update(parsed)
        st.session_state.apply_filters = True
        
        # Reset pagination when applying new filters
        reset_pagination()
        
        st.success("✅ Filtres chargés avec succès!")
        st.rerun()
        
    except Exception as e:
        st.error(f"❌ Erreur lors du chargement des filtres: {str(e)}")

def reset_pagination():
    """Réinitialise la pagination"""
    st.session_state.cursor_mark = "*"
    st.session_state.current_page = 1
    st.session_state.next_cursor = None
    st.session_state.all_docs = []
    st.session_state.current_docs = []

def apply_filters_and_fetch():
    """Applique les filtres et récupère les données avec pagination corrigée"""
    if not st.session_state.apply_filters:
        return
    
    filters = st.session_state.filters
    
    # Construire les paramètres pour l'API
    params = {}
    
    # Ajouter les filtres de base
    for key in ["start-date", "end-date", "brand", "category", "subcategory", "country"]:
        if key in filters and filters[key]:
            if key == "brand" and isinstance(filters[key], list):
                params[key] = ",".join(filters[key])
            else:
                params[key] = filters[key]
    
    # Ajouter les paramètres de pagination
    params["cursorMark"] = st.session_state.cursor_mark
    params["rows"] = 100  # Nombre de résultats par page
    
    # Récupérer les données
    result = fetch("/reviews", params)
    
    if result and "docs" in result:
        # Mettre à jour les données de la page actuelle
        st.session_state.current_docs = result["docs"]
        
        # Gérer la pagination : le next_cursor est déjà mis à jour dans fetch()
        
        # Mettre à jour le nombre total de résultats
        if "numFound" in result:
            st.session_state.total_found = result["numFound"]
    else:
        st.session_state.current_docs = []
        st.session_state.next_cursor = None

def go_to_next_page():
    """Va à la page suivante avec pagination corrigée"""
    if st.session_state.next_cursor:
        st.session_state.cursor_mark = st.session_state.next_cursor
        st.session_state.current_page += 1
        apply_filters_and_fetch()
        st.rerun()

def go_to_previous_page():
    """Va à la page précédente (limité car pagination cursor-based)"""
    if st.session_state.current_page > 1:
        # Pour la pagination cursor-based, on ne peut pas facilement revenir en arrière
        # On recommence depuis le début et on navigue jusqu'à la page précédente
        st.warning("⚠️ Retour à la première page (limitation de la pagination cursor-based)")
        reset_pagination()
        apply_filters_and_fetch()
        st.rerun()

def export_selected_products():
    """Exporte les produits sélectionnés avec gestion d'état améliorée"""
    if not st.session_state.selected_product_ids:
        st.error("❌ Aucun produit sélectionné pour l'export")
        return
    
    # Construire les paramètres d'export
    export_params = st.session_state.filters.copy()
    
    # CORRECTION: Utiliser les noms de produits sélectionnés pour filtrer
    export_params["product"] = ",".join(st.session_state.selected_product_ids)
    
    # Stocker les paramètres d'export
    st.session_state.export_params = export_params
    
    if st.session_state.is_preview_mode:
        # Mode aperçu - limiter à 1000 résultats
        export_params["rows"] = 1000
        export_params["cursorMark"] = "*"
        
        result = fetch("/reviews", export_params)
        
        if result and "docs" in result:
            df = pd.DataFrame(result["docs"])
            if not df.empty:
                processed_df = postprocess_reviews(df)
                
                # Générer le fichier CSV
                csv_buffer = io.StringIO()
                processed_df.to_csv(csv_buffer, index=False)
                csv_data = csv_buffer.getvalue()
                
                filename = generate_export_filename(export_params, mode="preview")
                
                st.download_button(
                    label=f"📥 Télécharger l'aperçu ({len(processed_df)} avis)",
                    data=csv_data,
                    file_name=filename,
                    mime="text/csv"
                )
                
                st.success(f"✅ Aperçu généré: {len(processed_df)} avis")
            else:
                st.warning("⚠️ Aucun avis trouvé pour les produits sélectionnés")
        else:
            st.error("❌ Erreur lors de la récupération des données")
    else:
        # Mode export complet
        st.session_state.export_strategy = "selected_products"
        st.info("🔄 Export complet des produits sélectionnés en cours...")
        perform_full_export()

def perform_full_export():
    """Effectue un export complet avec pagination cursor-based"""
    if not st.session_state.export_params:
        st.error("❌ Paramètres d'export manquants")
        return
    
    export_params = st.session_state.export_params.copy()
    all_reviews = []
    cursor = "*"
    page_count = 0
    max_pages = 100  # Limite de sécurité
    
    progress_bar = st.progress(0)
    status_text = st.empty()
    
    try:
        while cursor and page_count < max_pages:
            export_params["cursorMark"] = cursor
            export_params["rows"] = 1000  # Taille de lot pour l'export
            
            status_text.text(f"Récupération de la page {page_count + 1}...")
            result = fetch_cached("/reviews", export_params)  # Utiliser fetch_cached directement
            
            if not result or "docs" not in result:
                break
                
            docs = result["docs"]
            if not docs:
                break
                
            all_reviews.extend(docs)
            
            # Mettre à jour la barre de progression
            if "numFound" in result and result["numFound"] > 0:
                progress = min(len(all_reviews) / result["numFound"], 1.0)
                progress_bar.progress(progress)
            
            # CORRECTION: Vérifier le cursor suivant correctement
            next_cursor = result.get("nextCursorMark")
            if not next_cursor or next_cursor == cursor:
                # Fin de pagination atteinte
                break
                
            cursor = next_cursor
            page_count += 1
            
            # Pause pour éviter de surcharger l'API
            time.sleep(0.1)
            
        # Traitement des données
        status_text.text("Traitement des données...")
        if all_reviews:
            df = pd.DataFrame(all_reviews)
            processed_df = postprocess_reviews(df)
            
            # Générer le fichier CSV
            csv_buffer = io.StringIO()
            processed_df.to_csv(csv_buffer, index=False)
            csv_data = csv_buffer.getvalue()
            
            filename = generate_export_filename(export_params, mode="complete")
            
            # Nettoyer l'affichage
            progress_bar.empty()
            status_text.empty()
            
            st.download_button(
                label=f"📥 Télécharger l'export complet ({len(processed_df)} avis)",
                data=csv_data,
                file_name=filename,
                mime="text/csv"
            )
            
            st.success(f"✅ Export complet généré: {len(processed_df)} avis récupérés en {page_count + 1} pages")
        else:
            st.warning("⚠️ Aucun avis trouvé pour les critères spécifiés")
            progress_bar.empty()
            status_text.empty()
            
    except Exception as e:
        st.error(f"❌ Erreur lors de l'export: {str(e)}")
        progress_bar.empty()
        status_text.empty()

def display_sidebar_filters():
    """Affiche les filtres dans la sidebar"""
    with st.sidebar:
        st.header("Filtres")

        st.markdown("### 📎 Charger une configuration via JSON")
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

        # Appliquer les filtres
        if st.button("🔍 Appliquer les filtres"):
            st.session_state.filters = {
                "start-date": start_date,
                "end-date": end_date,
                "category": category if category != "ALL" else "",
                "subcategory": subcategory if subcategory != "ALL" else "",
                "brand": brand,
                "country": country[0] if country and country[0] != "ALL" else ""
            }
            st.session_state.apply_filters = True
            reset_pagination()
            st.rerun()

def display_filter_summary():
    """Affiche le résumé des filtres appliqués"""
    if st.session_state.apply_filters:
        filters = st.session_state.filters
        st.info("🔍 **Filtres actifs:**")
        
        filter_summary = []
        if filters.get("start-date"):
            filter_summary.append(f"Du {filters['start-date']}")
        if filters.get("end-date"):
            filter_summary.append(f"au {filters['end-date']}")
        if filters.get("category"):
            filter_summary.append(f"Catégorie: {filters['category']}")
        if filters.get("subcategory"):
            filter_summary.append(f"Sous-catégorie: {filters['subcategory']}")
        if filters.get("brand"):
            if isinstance(filters["brand"], list):
                filter_summary.append(f"Marques: {', '.join(filters['brand'])}")
            else:
                filter_summary.append(f"Marques: {filters['brand']}")
        if filters.get("country"):
            filter_summary.append(f"Pays: {filters['country']}")
        
        st.write(" | ".join(filter_summary))
        
        if st.button("🔄 Réinitialiser les filtres"):
            st.session_state.apply_filters = False
            st.session_state.filters = {}
            reset_pagination()
            st.rerun()

def load_product_list(filters):
    """Charge la liste des produits sans les métriques"""
    params = {}
    
    # Ajouter les filtres de base
    for key in ["start-date", "end-date", "brand", "category", "subcategory", "country"]:
        if key in filters and filters[key]:
            if key == "brand" and isinstance(filters[key], list):
                params[key] = ",".join(filters[key])
            else:
                params[key] = filters[key]
    
    result = fetch("/products", params)
    return result.get("products", [])

def display_product_selection():
    """Affiche la sélection de produits avec interface interactive"""
    st.header("🛍️ Sélection de produits")
    
    if not st.session_state.apply_filters:
        st.info("👈 Veuillez d'abord appliquer des filtres dans la barre latérale")
        return
    
    # Charger la liste des produits
    with st.spinner("Chargement des produits..."):
        products = load_product_list(st.session_state.filters)
    
    if not products:
        st.warning("⚠️ Aucun produit trouvé pour les filtres sélectionnés")
        return
    
    # Afficher le nombre de produits trouvés
    st.info(f"📊 {len(products)} produit(s) trouvé(s)")
    
    # Mode de sélection
    col1, col2 = st.columns(2)
    with col1:
        st.session_state.is_preview_mode = st.radio(
            "Mode d'export", 
            [True, False], 
            format_func=lambda x: "Aperçu (1000 avis max)" if x else "Export complet",
            index=0 if st.session_state.is_preview_mode else 1
        )
    
    with col2:
        if st.button("🗑️ Désélectionner tout"):
            st.session_state.selected_product_ids = []
            st.rerun()
    
    # Affichage des produits avec sélection
    st.subheader("Sélectionnez les produits à exporter:")
    
    for idx, product in enumerate(products):
        product_name = product.get("name", f"Produit {idx}")
        
        col1, col2, col3 = st.columns([0.5, 3, 2])
        
        with col1:
            is_selected = product_name in st.session_state.selected_product_ids
            if st.checkbox("", value=is_selected, key=f"product_{idx}"):
                if product_name not in st.session_state.selected_product_ids:
                    st.session_state.selected_product_ids.append(product_name)
            else:
                if product_name in st.session_state.selected_product_ids:
                    st.session_state.selected_product_ids.remove(product_name)
        
        with col2:
            st.write(f"**{product_name}**")
        with col3:
            nb_avis = product.get("nb_reviews", "N/A")
            st.write(f"{nb_avis} avis")
    
    # Actions d'export
    if st.session_state.selected_product_ids:
        st.success(f"✅ {len(st.session_state.selected_product_ids)} produit(s) sélectionné(s)")
        
        col1, col2 = st.columns(2)
        with col1:
            if st.button("📥 Exporter la sélection"):
                export_selected_products()
        with col2:
            if st.button("📋 Voir les produits sélectionnés"):
                st.write("**Produits sélectionnés:**")
                for product_id in st.session_state.selected_product_ids:
                    st.write(f"- {product_id}")

def display_reviews_results():
    """Affiche les résultats des reviews récupérées"""
    if not st.session_state.apply_filters:
        return
    
    st.header("📊 Résultats des avis")
    
    # Appliquer les filtres si nécessaire
    apply_filters_and_fetch()
    
    if not st.session_state.current_docs:
        st.warning("⚠️ Aucun avis trouvé pour les filtres sélectionnés")
        return
    
    # Informations de pagination
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("Total trouvé", st.session_state.total_found)
    with col2:
        st.write(f"**Page {st.session_state.current_page}** - {len(st.session_state.current_docs)} avis affichés")
    with col3:
        # Mode d'export
        st.session_state.is_preview_mode = st.toggle("Mode aperçu", st.session_state.is_preview_mode)
    
    # Contrôles de pagination
    col1, col2 = st.columns(2)
    with col1:
        if st.button("⬅️ Précédent", disabled=st.session_state.current_page <= 1):
            go_to_previous_page()
    with col2:
        if st.button("➡️ Suivant", disabled=not st.session_state.next_cursor):
            go_to_next_page()
    
    # Afficher les données
    df = pd.DataFrame(st.session_state.current_docs)
    if not df.empty:
        processed_df = postprocess_reviews(df)
        st.dataframe(processed_df, use_container_width=True)
        
        # Option d'export
        if st.button("📥 Exporter cette page"):
            csv_buffer = io.StringIO()
            processed_df.to_csv(csv_buffer, index=False)
            csv_data = csv_buffer.getvalue()
            
            filename = generate_export_filename(st.session_state.filters, mode="page", page=st.session_state.current_page)
            
            st.download_button(
                label=f"📥 Télécharger la page {st.session_state.current_page}",
                data=csv_data,
                file_name=filename,
                mime="text/csv"
            )

def main():
    """Fonction principale de l'application"""
    st.title("🔍 Explorateur API Ratings & Reviews")
    
    # Afficher les quotas
    display_quotas()
    
    # Sidebar avec filtres
    display_sidebar_filters()
    
    # Contenu principal
    display_filter_summary()
    
    # Onglets pour les différentes fonctionnalités
    tab1, tab2 = st.tabs(["📊 Résultats des avis", "🛍️ Sélection de produits"])
    
    with tab1:
        display_reviews_results()
    
    with tab2:
        display_product_selection()

if __name__ == "__main__":
    main()
