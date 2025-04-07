import streamlit as st
import requests
import pandas as pd
import datetime

st.set_page_config(page_title="Explorateur PF API", layout="wide")

st.session_state.setdefault("apply_filters", False)


def fetch(endpoint, params=""):
    BASE_URL = "https://api-pf.ratingsandreviews-beauty.com"
    TOKEN = "JbK3Iyxcw2EwKQKke0rAQJ6eEHaph1ifP5smlHIemlDmGqB5l3j997pcab92ty9r"
    url = f"{BASE_URL}{endpoint}?token={TOKEN}&{params}"
    response = requests.get(url, headers={"Accept": "application/json"})
    if response.status_code == 200:
        return response.json().get("result")
    else:
        st.error(f"Erreur {response.status_code} sur {url}")
        return {}


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
                "market": market
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

    params = [f"start-date={start_date}", f"end-date={end_date}"]
    if category != "ALL": params.append(f"category={category}")
    if subcategory != "ALL": params.append(f"subcategory={subcategory}")
    if brand: params.append(f"brand={','.join(brand)}")
    if country and "ALL" not in country: params.append(f"country={','.join(country)}")
    if source and "ALL" not in source: params.append(f"source={','.join(source)}")
    if market and "ALL" not in market: params.append(f"market={','.join(market)}")

    query_string = "&".join(params)

    # Produits groupés par marque + compteur de reviews
    product_info = {}
    product_data = []
    for b in brand:
        product_params = [f"brand={b}", f"start-date={start_date}", f"end-date={end_date}"]
        if category != "ALL":
            product_params.append(f"category={category}")
        if subcategory != "ALL":
            product_params.append(f"subcategory={subcategory}")
        product_query = "&".join(product_params)
        products = fetch("/products", product_query)
        if products and products.get("products"):
            for p in products["products"]:
                metric_param = f"brand={b}&product={p}&start-date={start_date}&end-date={end_date}"
                metric = fetch("/metrics", metric_param)
                volume = metric.get("nbDocs", 0) if metric else 0
                label = f"{b} > {p} ({volume})"
                product_info[label] = p
                product_data.append({"Marque": b, "Produit": p, "Reviews": volume})

    if product_data:
        st.subheader("📊 Produits disponibles")
        df_products = pd.DataFrame(product_data).sort_values(by="Reviews", ascending=False)
        st.dataframe(df_products)

        st.markdown("**Top 5 produits les plus populaires**")
        st.table(df_products.head(5))

    search_text = st.text_input("🔍 Rechercher un produit")
    display_list = [k for k in product_info if search_text.lower() in k.lower()]
    selected_display = st.multiselect("Produits", display_list)
    selected_products = [product_info[label] for label in selected_display]

    if selected_products:
        params.append(f"product={','.join(selected_products)}")

    query_string = "&".join(params)

    st.markdown("---")
    st.subheader("Disponibilité des données")
    dynamic_metrics = fetch("/metrics", query_string)
    if dynamic_metrics and dynamic_metrics.get("nbDocs"):
        st.success(f"{dynamic_metrics['nbDocs']} reviews disponibles")
    else:
        st.warning("Aucune review disponible pour cette combinaison")

    mode = st.radio("Afficher", ["Métriques (metrics)", "Reviews"])

    if st.button("Lancer la requête"):
        if mode == "Métriques (metrics)":
            result = fetch("/metrics", query_string)
            st.json(result)
        else:
            query_string += "&rows=100"
            result = fetch("/reviews", query_string)
            docs = result.get("docs", []) if result else []
            if docs:
                df = pd.DataFrame(docs)
                st.dataframe(df)
                st.download_button("📂 Télécharger en CSV", df.to_csv(index=False), file_name="reviews.csv", mime="text/csv")
                st.download_button("📄 Télécharger en Excel", df.to_excel(index=False, engine='openpyxl'), file_name="reviews.xlsx", mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
            else:
                st.warning("Aucune review trouvée pour ces critères.")

if __name__ == "__main__":
    main()
