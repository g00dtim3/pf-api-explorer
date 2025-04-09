import streamlit as st
import requests
import pandas as pd
import datetime
import io
import altair as alt
import urllib.parse

st.set_page_config(page_title="Explorateur API Ratings & Reviews", layout="wide")

# 🔧 Mode debug
show_debug = st.sidebar.toggle("Afficher les URLs (mode debug)", value=False)

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

    if isinstance(params, dict):
        params["token"] = TOKEN
        query_string = urllib.parse.urlencode(params, doseq=True, quote_via=lambda x, safe: urllib.parse.quote(x, safe=''))
    else:
        params.append(("token", TOKEN))
        query_string = urllib.parse.urlencode(params, doseq=True, quote_via=lambda x, safe: urllib.parse.quote(x, safe=''))

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
        df_products = pd.DataFrame(product_data)
        st.dataframe(df_products)

    search_text = st.text_input("🔍 Rechercher un produit")
    display_list = [k for k in product_info if search_text.lower() in k.lower()]
    selected_display = st.multiselect("Produits", display_list)
    selected_products = [product_info[label] for label in selected_display]

    if selected_products:
        params["product"] = ",".join(selected_products)

    st.markdown("---")
    st.subheader("Disponibilité des données")
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
