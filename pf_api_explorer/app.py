import streamlit as st
import requests
import pandas as pd

def main():
    with st.sidebar:
        st.header("Filtres")

        if "start_date" not in st.session_state:
            st.session_state.start_date = pd.to_datetime("2022-01-01").date()
        if "end_date" not in st.session_state:
            st.session_state.end_date = pd.to_datetime("today").date()

        st.session_state.start_date = st.date_input("Date de début", value=st.session_state.start_date)
        st.session_state.end_date = st.date_input("Date de fin", value=st.session_state.end_date)

        categories_data = fetch("/categories")
        all_categories = ["ALL"] + [c["category"] for c in categories_data.get("categories", [])]
        st.session_state.category = st.selectbox("Catégorie", all_categories)
        subcategory_options = ["ALL"]
        if st.session_state.category != "ALL":
            for c in categories_data.get("categories", []):
                if c["category"] == st.session_state.category:
                    subcategory_options += c["subcategories"]
        st.session_state.subcategory = st.selectbox("Sous-catégorie", subcategory_options)
        brand_filters = []
        if st.session_state.category != "ALL":
            brand_filters.append(f"category={st.session_state.category}")
        if st.session_state.subcategory != "ALL":
            brand_filters.append(f"subcategory={st.session_state.subcategory}")
        brands_data = fetch("/brands", "&".join(brand_filters))
        st.session_state.brand = st.multiselect("Marques", brands_data.get("brands", []))
        countries_data = fetch("/countries")
        st.session_state.country = st.multiselect("Pays", ["ALL"] + countries_data.get("countries", []))
        sources_data = fetch("/sources", f"country={st.session_state.country[0]}" if st.session_state.country and st.session_state.country[0] != "ALL" else "")
        st.session_state.source = st.multiselect("Sources", ["ALL"] + sources_data.get("sources", []))
        markets_data = fetch("/markets")
        st.session_state.market = st.multiselect("Markets", ["ALL"] + markets_data.get("markets", []))

        st.session_state.attributes = st.multiselect("Attributs", [])
        st.session_state.attributes_positive = st.multiselect("Attributs positifs", [])
        st.session_state.attributes_negative = st.multiselect("Attributs négatifs", [])

        if st.button("✅ Appliquer les filtres"):
            st.session_state.apply_filters = True
            st.session_state.filters = {
                "start_date": st.session_state.start_date,
                "end_date": st.session_state.end_date,
                "category": st.session_state.category,
                "subcategory": st.session_state.subcategory,
                "brand": st.session_state.brand,
                "country": st.session_state.country,
                "source": st.session_state.source,
                "market": st.session_state.market,
                "attributes": st.session_state.attributes,
                "attributes_positive": st.session_state.attributes_positive,
                "attributes_negative": st.session_state.attributes_negative,
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

    # 🔍 Sélection interactive de produits après sélection des marques
    if brand:
        product_labels = []
        product_map = {}
        for b in brand:
            product_list = fetch("/products", f"brand={b}&start-date={start_date}&end-date={end_date}")
            if product_list and "products" in product_list:
                for p in product_list["products"]:
                    label = f"{b} > {p}"
                    product_labels.append(label)
                    product_map[label] = {"brand": b, "product": p}

        selected_products_display = st.multiselect("🎯 Filtrer les produits à analyser", product_labels)
        selected_products = [product_map[label] for label in selected_products_display]
    else:
        selected_products = []

    # Écran supplémentaire : nombre de reviews par produit
    st.subheader("📊 Nombre de reviews par produit")
    if selected_products:
    with st.spinner("🔄 Récupération des reviews par produit..."):
        product_rows = []
        for entry in selected_products:
            b = entry["brand"]
            p = entry["product"]
            metric = fetch("/metrics", f"brand={b}&product={p}&start-date={start_date}&end-date={end_date}")
            count = metric.get("nbDocs", 0) if metric else 0
            product_rows.append({"Marque": b, "Produit": p, "Reviews": count})



    # Écran supplémentaire : répartition positif / négatif par attribut et produit
    if attributes and selected_products:
    with st.spinner("🔄 Analyse des sentiments par attribut..."):
        sentiment_rows = []
        for entry in selected_products:
            b = entry["brand"]
            p = entry["product"]
            for attr in attributes:
                pos = fetch("/metrics", f"brand={b}&product={p}&attribute-positive={attr}&start-date={start_date}&end-date={end_date}")
                neg = fetch("/metrics", f"brand={b}&product={p}&attribute-negative={attr}&start-date={start_date}&end-date={end_date}")
                sentiment_rows.append({
                    "Marque": b,
                    "Produit": p,
                    "Attribut": attr,
                    "Positifs": pos.get("nbDocs", 0) if pos else 0,
                    "Négatifs": neg.get("nbDocs", 0) if neg else 0
                })

        df_sentiments = pd.DataFrame(sentiment_rows)
        st.dataframe(df_sentiments)
        csv_sent = df_sentiments.to_csv(index=False)
        st.download_button("📥 Exporter répartition attributs", csv_sent, file_name="repartition_attributs.csv", mime="text/csv")

        # 🔥 Heatmap
        if not df_sentiments.empty:
            import altair as alt
            df_melted = df_sentiments.melt(id_vars=["Produit", "Attribut"], value_vars=["Positifs", "Négatifs"], var_name="Sentiment", value_name="Count")
            heatmap = alt.Chart(df_melted).mark_rect().encode(
                x=alt.X("Attribut:N", title="Attribut"),
                y=alt.Y("Produit:N", title="Produit"),
                color=alt.Color("Count:Q", scale=alt.Scale(scheme='blues'), title="Nombre de reviews"),
                tooltip=["Produit", "Attribut", "Sentiment", "Count"]
            ).properties(
                width=600,
                height=400,
                title="Heatmap des reviews Positifs / Négatifs par Attribut"
            )
            st.altair_chart(heatmap, use_container_width=True)

@st.cache_data(ttl=3600)
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

if __name__ == "__main__":
    main()
