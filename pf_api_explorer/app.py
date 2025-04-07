import streamlit as st
import requests
import pandas as pd
import datetime

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
    st.title("Explorateur API Ratings & Reviews - Pierre Fabre")

    st.subheader("Quotas")
    if st.button("Afficher mes quotas"):
        result = fetch("/quotas", "")
        if result:
            st.metric("Volume utilisé", result['used volume'])
            st.metric("Volume restant", result['remaining volume'])
            st.metric("Quota total", result['quota'])
            st.metric("Valable jusqu'au", result['end date'])

   if st.sidebar.button("🔄 Réinitialiser les filtres"):
    st.experimental_rerun()
    return  # Stoppe proprement la fonction main()

    st.sidebar.header("Filtres")
    start_date = st.sidebar.date_input("Date de début", value=datetime.date(2024, 1, 1))
    end_date = st.sidebar.date_input("Date de fin", value=datetime.date(2024, 6, 30))

    params_base = []
    if start_date: params_base.append(f"start-date={start_date}")
    if end_date: params_base.append(f"end-date={end_date}")
    query_base = "&".join(params_base)

    categories = fetch("/categories")
    all_categories = [c["category"] for c in categories.get("categories", [])]
    category = st.sidebar.selectbox("Catégorie", all_categories)

    subcategory_options = []
    for cat in categories.get("categories", []):
        if cat["category"] == category:
            subcategory_options = cat["subcategories"]
    subcategory = st.sidebar.selectbox("Sous-catégorie", subcategory_options)

    brands = fetch("/brands", f"category={category}&subcategory={subcategory}")
    brand = st.sidebar.multiselect("Marques", brands.get("brands", []))

    products = fetch("/products", f"brand={brand[0]}&category={category}&subcategory={subcategory}" if brand else f"category={category}&subcategory={subcategory}")
    product_list = products.get("products", []) if products else []
    search_text = st.sidebar.text_input("🔍 Rechercher un produit")
    filtered_products = [p for p in product_list if search_text.lower() in p.lower()]
    selected_products = st.sidebar.multiselect("Produits", filtered_products)

    countries = fetch("/countries")
    country = st.sidebar.multiselect("Pays", countries.get("countries", []))

    sources = fetch("/sources", f"country={country[0]}" if country else "")
    source = st.sidebar.multiselect("Sources", sources.get("sources", []))

    markets = fetch("/markets")
    market = st.sidebar.multiselect("Markets", markets.get("markets", []))

    # Paramètres cumulés pour mise à jour dynamique
    params = params_base.copy()
    if category: params.append(f"category={category}")
    if subcategory: params.append(f"subcategory={subcategory}")
    if brand: params.append(f"brand={','.join(brand)}")
    if selected_products: params.append(f"product={','.join(selected_products)}")
    if country: params.append(f"country={','.join(country)}")
    if source: params.append(f"source={','.join(source)}")
    if market: params.append(f"market={','.join(market)}")

    query_string = "&".join(params)

    st.sidebar.markdown("---")
    st.sidebar.subheader("Disponibilité des données")
    dynamic_metrics = fetch("/metrics", query_string)
    if dynamic_metrics and dynamic_metrics.get("nbDocs"):
        st.sidebar.success(f"{dynamic_metrics['nbDocs']} reviews disponibles")
    else:
        st.sidebar.warning("Aucune review disponible pour cette combinaison")

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
