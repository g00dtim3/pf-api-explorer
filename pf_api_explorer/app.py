import streamlit as st
import requests
import pandas as pd

def main():
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

if __name__ == "__main__":
    main()
