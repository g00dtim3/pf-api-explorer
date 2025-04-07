import streamlit as st
import requests
import pandas as pd
import datetime
import io

st.set_page_config(page_title="Explorateur API Ratings & Reviews", layout="wide")

st.session_state.setdefault("apply_filters", False)

@st.cache_data(ttl=3600)
def fetch_cached(endpoint, params=""):
    BASE_URL = "https://api-pf.ratingsandreviews-beauty.com"
    TOKEN = "JbK3Iyxcw2EwKQKke0rAQJ6eEHaph1ifP5smlHIemlDmGqB5l3j997pcab92ty9r"
    url = f"{BASE_URL}{endpoint}?token={TOKEN}&{params}"
    response = requests.get(url, headers={"Accept": "application/json"})
    if response.status_code == 200:
        return response.json().get("result")
    else:
        st.error(f"Erreur {response.status_code} sur {url}")
        return {}

@st.cache_data(ttl=3600)
def fetch_products_by_brand(brand, category, subcategory, start_date, end_date):
    params = [f"brand={brand}", f"start-date={start_date}", f"end-date={end_date}"]
    if category != "ALL":
        params.append(f"category={category}")
    if subcategory != "ALL":
        params.append(f"subcategory={subcategory}")
    return fetch_cached("/products", "&".join(params))

@st.cache_data(ttl=3600)
def fetch_attributes_dynamic(category, subcategory, brand):
    filters = []
    if category != "ALL":
        filters.append(f"category={category}")
    if subcategory != "ALL":
        filters.append(f"subcategory={subcategory}")
    if brand:
        filters.append(f"brand={','.join(brand)}")
    return fetch_cached("/attributes", "&".join(filters))

# Utilisé uniquement pour requêtes non-cachables (avec refresh ou pagination)
def fetch(endpoint, params=""):
    return fetch_cached(endpoint, params)


def main():
    st.title("Explorateur API Ratings & Reviews")

    st.subheader("Quotas")
    if st.button("Afficher mes quotas"):
        result = fetch("/quotas", "")
        if result:
            st.metric("Volume utilisé", result['used volume'])
            st.metric("Volume restant", result['remaining volume'])
            st.metric("Quota total", result['quota'])
            st.metric("Valable jusqu'au", result['end date'])

    with st.sidebar:
        st.header("Filtres")
        if st.button("🔄 Réinitialiser les filtres"):
            st.session_state.clear()
            st.experimental_rerun()

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

        brands_params = []
        if category != "ALL":
            brands_params.append(f"category={category}")
        if subcategory != "ALL":
            brands_params.append(f"subcategory={subcategory}")
        brands = fetch("/brands", "&".join(brands_params))
        brand = st.multiselect("Marques", brands.get("brands", []))

        countries = fetch("/countries")
        all_countries = ["ALL"] + countries.get("countries", [])
        country = st.multiselect("Pays", all_countries)

        sources = fetch("/sources", f"country={country[0]}" if country and country[0] != "ALL" else "")
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
    start_date = filters["start_date"]
    end_date = filters["end_date"]
    category = filters["category"]
    subcategory = filters["subcategory"]
    brand = filters["brand"]
    country = filters["country"]
    source = filters["source"]
    market = filters["market"]
    attributes = filters.get("attributes", [])
    attributes_positive = filters.get("attributes_positive", [])
    attributes_negative = filters.get("attributes_negative", [])

    st.markdown("## 🧾 Résumé des filtres appliqués")
    st.markdown(f"- **Dates** : du `{start_date}` au `{end_date}`")
    st.markdown(f"- **Catégorie** : `{category}` | **Sous-catégorie** : `{subcategory}`")
    st.markdown(f"- **Marques** : `{', '.join(brand) if brand else 'Toutes'}`")
    st.markdown(f"- **Pays** : `{', '.join(country) if country and 'ALL' not in country else 'Tous'}`")
    st.markdown(f"- **Sources** : `{', '.join(source) if source and 'ALL' not in source else 'Toutes'}`")
    st.markdown(f"- **Markets** : `{', '.join(market) if market and 'ALL' not in market else 'Tous'}`")
    st.markdown(f"- **Attributs** : `{', '.join(attributes)}`")
    st.markdown(f"- **Attributs positifs** : `{', '.join(attributes_positive)}`")
    st.markdown(f"- **Attributs négatifs** : `{', '.join(attributes_negative)}`")

    params = [f"start-date={start_date}", f"end-date={end_date}"]
    if category != "ALL": params.append(f"category={category}")
    if subcategory != "ALL": params.append(f"subcategory={subcategory}")
    if brand: params.append(f"brand={','.join(brand)}")
    if country and "ALL" not in country: params.append(f"country={','.join(country)}")
    if source and "ALL" not in source: params.append(f"source={','.join(source)}")
    if market and "ALL" not in market: params.append(f"market={','.join(market)}")
    if attributes: params.append(f"attribute={','.join(attributes)}")
    if attributes_positive: params.append(f"attribute-positive={','.join(attributes_positive)}")
    if attributes_negative: params.append(f"attribute-negative={','.join(attributes_negative)}")

    query_string = "&".join(params)

    st.subheader("📈 Vue des métriques par attribut")
    if attributes:
        metric_rows = []
        for attr in attributes:
            attr_param = f"{query_string}&attribute={attr}"
            result = fetch("/metrics", attr_param)
            count = result.get("nbDocs", 0) if result else 0
            metric_rows.append({"Attribut": attr, "Reviews": count})
        df_metrics = pd.DataFrame(metric_rows)
        st.dataframe(df_metrics)
        csv = df_metrics.to_csv(index=False)
        st.download_button("📥 Télécharger les métriques (CSV)", csv, file_name="metrics_par_attribut.csv", mime="text/csv")

    st.success("Filtrage appliqué. Ajoute une section d'affichage ou d'export ici si besoin.")
