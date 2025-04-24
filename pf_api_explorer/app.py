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
    show_debug = True

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

    mode = st.radio("Afficher", ["Métriques (metrics)", "Reviews"])

    if st.button("Lancer la requête"):
        if mode == "Métriques (metrics)":
            result = fetch("/metrics", params)
            st.json(result)
        else:
            params_with_rows = params.copy()
            params_with_rows["rows"] = 100
            result = fetch("/reviews", params_with_rows)
            docs = result.get("docs", []) if result else []
            if docs:
                df = pd.json_normalize(docs)
                df = df.applymap(lambda x: str(x) if isinstance(x, (dict, list)) else x)
                st.dataframe(df)
                csv = df.to_csv(index=False)

                excel_buffer = io.BytesIO()
                with pd.ExcelWriter(excel_buffer, engine='openpyxl') as writer:
                    df.to_excel(writer, index=False)
                excel_data = excel_buffer.getvalue()

                st.download_button("📂 Télécharger en CSV", csv, file_name="reviews.csv", mime="text/csv")
                st.download_button("📄 Télécharger en Excel", excel_data, file_name="reviews.xlsx", mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
            else:
                st.warning("Aucune review trouvée pour ces critères.")

if __name__ == "__main__":
    main()
