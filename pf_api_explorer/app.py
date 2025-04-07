import streamlit as st
import requests
import pandas as pd
import altair as alt

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

def main():
    with st.sidebar:
        st.header("Filtres")

        start_date = st.date_input("Date de début", pd.to_datetime("2022-01-01").date())
        end_date = st.date_input("Date de fin", pd.to_datetime("today").date())

        categories_data = fetch("/categories")
        all_categories = ["ALL"] + [c["category"] for c in categories_data.get("categories", [])]
        category = st.selectbox("Catégorie", all_categories)

        subcategory_options = ["ALL"]
        if category != "ALL":
            for c in categories_data.get("categories", []):
                if c["category"] == category:
                    subcategory_options += c["subcategories"]
        subcategory = st.selectbox("Sous-catégorie", subcategory_options)

        product_filters = [f"start-date={start_date}", f"end-date={end_date}"]
        if category != "ALL":
            product_filters.append(f"category={category}")
        if subcategory != "ALL":
            product_filters.append(f"subcategory={subcategory}")

        products_data = fetch("/products", "&".join(product_filters))
        products = products_data.get("products", []) if products_data else []

        if len(products) == 1:
            selected_products = [products[0]]
        else:
            selected_products = st.multiselect("Produits", products, default=products[:10])

        if not selected_products:
            st.info("Veuillez sélectionner des produits pour afficher les résultats.")
        return

    st.subheader("📊 Nombre de reviews par produit")
    rows = []
    for p in selected_products:
        res = fetch("/metrics", f"product={p}&start-date={start_date}&end-date={end_date}")
        rows.append({"Produit": p, "Reviews": res.get("nbDocs", 0) if res else 0})
    df_reviews = pd.DataFrame(rows)
    st.dataframe(df_reviews)

    st.subheader("📊 Sentiments par attribut pour chaque produit")
    attributes_data = fetch("/attributes")
    attributes = attributes_data.get("attributes", []) if attributes_data else []

    sentiments = []
    for p in selected_products:
        for attr in attributes:
            pos = fetch("/metrics", f"product={p}&attribute-positive={attr}&start-date={start_date}&end-date={end_date}")
            neg = fetch("/metrics", f"product={p}&attribute-negative={attr}&start-date={start_date}&end-date={end_date}")
            sentiments.append({
                "Produit": p,
                "Attribut": attr,
                "Positifs": pos.get("nbDocs", 0) if pos else 0,
                "Négatifs": neg.get("nbDocs", 0) if neg else 0
            })

    df_sentiments = pd.DataFrame(sentiments)
    st.dataframe(df_sentiments)

    if not df_sentiments.empty:
        df_melted = df_sentiments.melt(id_vars=["Produit", "Attribut"], value_vars=["Positifs", "Négatifs"],
                                       var_name="Sentiment", value_name="Count")
        heatmap = alt.Chart(df_melted).mark_rect().encode(
            x=alt.X("Attribut:N", title="Attribut"),
            y=alt.Y("Produit:N", title="Produit"),
            color=alt.Color("Count:Q", scale=alt.Scale(scheme='redblue'), title="# Reviews"),
            tooltip=["Produit", "Attribut", "Sentiment", "Count"]
        ).properties(
            width=600,
            height=400,
            title="Heatmap Sentiments par Attribut et Produit"
        )
        st.altair_chart(heatmap, use_container_width=True)

if __name__ == "__main__":
    main()
