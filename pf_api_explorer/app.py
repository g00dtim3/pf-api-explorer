import streamlit as st
import requests
import pandas as pd

def main():
    with st.sidebar:
        st.header("Filtres")

        if st.button("🔄 Réinitialiser les filtres"):
            filter_keys = [
                "start_date", "end_date", "category", "subcategory", "brand",
                "country", "source", "market", "attributes",
                "attributes_positive", "attributes_negative",
                "apply_filters", "filters"
            ]
            for key in filter_keys:
                if key in st.session_state:
                    del st.session_state[key]
            st.toast("Filtres réinitialisés")
            st.experimental_rerun()

        if "start_date" not in st.session_state:
            st.session_state.start_date = pd.to_datetime("2022-01-01").date()
        if "end_date" not in st.session_state:
            st.session_state.end_date = pd.to_datetime("today").date()

        st.session_state.start_date = st.date_input("Date de début", value=st.session_state.start_date)
        st.session_state.end_date = st.date_input("Date de fin", value=st.session_state.end_date)

        st.session_state.category = st.selectbox("Catégorie", ["ALL"])
        st.session_state.subcategory = st.selectbox("Sous-catégorie", ["ALL"])
        st.session_state.brand = st.multiselect("Marques", [])
        st.session_state.country = st.multiselect("Pays", ["ALL"])
        st.session_state.source = st.multiselect("Sources", ["ALL"])
        st.session_state.market = st.multiselect("Markets", ["ALL"])

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
