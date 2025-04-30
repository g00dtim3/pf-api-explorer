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

    st.markdown("## ⚙️ Paramètres d’export des reviews")

    import os
    from pathlib import Path
    
    log_path = Path("review_exports_log.csv")
    if log_path.exists():
        with st.expander("📁 Consulter le journal des exports précédents", expanded=False):
            export_log_df = pd.read_csv(log_path)
            st.dataframe(export_log_df)
            st.download_button("⬇️ Télécharger le journal des exports", export_log_df.to_csv(index=False), file_name="review_exports_log.csv", mime="text/csv")
    
    with st.expander("🔧 Options d’export", expanded=True):
        col1, col2 = st.columns(2)
    
        with col1:
            rows_per_page = st.number_input(
                "Nombre de reviews à récupérer par page (max 1000)",
                min_value=10,
                max_value=1000,
                value=100,
                step=10
            )
    
        with col2:
            use_random = st.checkbox("Randomiser les résultats")
            if use_random:
                random_seed = st.number_input("Seed aléatoire (1-9999)", min_value=1, max_value=9999, value=42)
            else:
                random_seed = None
    
        st.markdown("### 📊 Quotas API")
        quotas = fetch("/quotas")
        if quotas:
            st.metric("Quota utilisé", quotas['used volume'])
            st.metric("Quota restant", quotas['remaining volume'])
            st.metric("Quota total", quotas['quota'])
            st.metric("Valable jusqu’au", quotas['end date'])
    
        if "cursor_mark" not in st.session_state:
            st.session_state.cursor_mark = "*"
        if "current_page" not in st.session_state:
            st.session_state.current_page = 1
        if "all_docs" not in st.session_state:
            st.session_state.all_docs = []
        if "next_cursor" not in st.session_state:
            st.session_state.next_cursor = None
    
        # ✅ Vérification d’export déjà réalisé, englobant ou identique
        potential_duplicates = []
        if log_path.exists():
            try:
                export_log_df = pd.read_csv(log_path)
                export_log_df["start_date"] = pd.to_datetime(export_log_df["start_date"])
                export_log_df["end_date"] = pd.to_datetime(export_log_df["end_date"])
    
                product_names = params.get("product", "").split(",")
                start = pd.to_datetime(str(params.get("start-date")))
                end = pd.to_datetime(str(params.get("end-date")))
    
                for prod in product_names:
                    overlapping = export_log_df[
                        (export_log_df["product"] == prod) &
                        (export_log_df["start_date"] <= end) &
                        (export_log_df["end_date"] >= start)
                    ]
                    if not overlapping.empty:
                        potential_duplicates.append(prod)
            except Exception as e:
                st.warning(f"Erreur de lecture du fichier log : {e}")
    
        if potential_duplicates:
            st.warning(f"🚫 Les produits suivants ont déjà été exportés pour une période qui recouvre partiellement ou totalement celle sélectionnée : {', '.join(potential_duplicates)}")

        if selected_products:
            params["product"] = ",".join(selected_products)
    
        if st.button("📅 Lancer l’export des reviews"):
            # Réinitialiser la session
            st.session_state.cursor_mark = "*"
            st.session_state.current_page = 1
            st.session_state.all_docs = []
            st.session_state.next_cursor = None
        
            params_with_rows = params.copy()
            params_with_rows["rows"] = int(rows_per_page)
            if use_random and random_seed:
                params_with_rows["random"] = str(random_seed)

            st.write("📤 Paramètres envoyés à l’API:", params_with_rows)
        
            with st.spinner("🔄 Chargement des reviews depuis l'API..."):
                result = fetch("/reviews", params_with_rows)
                if result and result.get("docs"):
                    docs = result.get("docs", [])
                    st.session_state.all_docs = docs.copy()
                    st.session_state.next_cursor = result.get("nextCursorMark")
                    st.success(f"✅ {len(docs)} reviews chargées avec succès.")
                else:
                    st.warning("Aucune donnée retournée par l’API.")
    
                    # 🔒 Génération du log d'export local (changer le chemin si besoin)
                    export_date = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

                    export_country = params.get("country", "Tous")
    
                    product_names = params.get("product", "").split(",")
                    brand_names = params.get("brand", "").split(",")
    
                    log_entries = []
                    for product in product_names:
                        brand = next((b for b in brand_names if b.lower() in product.lower()), brand_names[0] if brand_names else "")
                        log_entries.append({
                            "product": product,
                            "brand": brand,
                            "start_date": params.get("start-date"),
                            "end_date": params.get("end-date"),
                            "country": export_country,
                            "rows": rows_per_page,
                            "random_seed": random_seed if use_random else None,
                            "nb_reviews": len(st.session_state.all_docs),
                            "export_timestamp": export_date
                        })
    
                    new_log_df = pd.DataFrame(log_entries)
                    if log_path.exists():
                        existing_log_df = pd.read_csv(log_path)
                        log_df = pd.concat([existing_log_df, new_log_df], ignore_index=True)
                    else:
                        log_df = new_log_df
                    log_df.to_csv(log_path, index=False)
    
                    st.info("📝 Log d'export mis à jour dans 'review_exports_log.csv' (fichier local - modifiez le chemin pour autre stockage)")
    
        # Affichage des reviews si dispo
        if st.session_state.all_docs:
            docs = st.session_state.all_docs
            total_results = len(docs)
            rows_per_page = int(rows_per_page)
            total_pages = (total_results + rows_per_page - 1) // rows_per_page
            current_page = st.session_state.current_page

            start_idx = (current_page - 1) * rows_per_page
            end_idx = start_idx + rows_per_page

            # Si la page suivante est demandée et non encore chargée
            if end_idx > len(docs) and st.session_state.next_cursor:
                params_with_rows = params.copy()
                params_with_rows["rows"] = rows_per_page
                if use_random and random_seed:
                    params_with_rows["random"] = str(random_seed)
                params_with_rows["cursorMark"] = st.session_state.next_cursor

                result = fetch("/reviews", params_with_rows)
                if result and result.get("docs"):
                    new_docs = result.get("docs", [])
                    st.session_state.all_docs.extend(new_docs)
                    st.session_state.next_cursor = result.get("nextCursorMark")
                    total_results = len(st.session_state.all_docs)
                    total_pages = (total_results + rows_per_page - 1) // rows_per_page
                    docs = st.session_state.all_docs  # refresh local ref

            page_docs = docs[start_idx:end_idx]

            st.markdown(f"""
            ### 📋 Résultats
            - **Total stocké** : `{total_results}`
            - **Affichés sur cette page** : `{len(page_docs)}`
            - **Page actuelle** : `{current_page}` / environ `{total_pages}`
            """)

            df = pd.json_normalize(page_docs)
            df = df.applymap(lambda x: str(x) if isinstance(x, (dict, list)) else x)
            st.dataframe(df)

            col1, col2 = st.columns(2)
            with col1:
                if st.button("⬅️ Page précédente") and st.session_state.current_page > 1:
                    st.session_state.current_page -= 1
            with col2:
                if st.button("➡️ Page suivante") and st.session_state.current_page < total_pages:
                    st.session_state.current_page += 1

            # Export de la page actuelle
            all_csv = df.to_csv(index=False)
            excel_buffer = io.BytesIO()
            with pd.ExcelWriter(excel_buffer, engine='openpyxl') as writer:
                df.to_excel(writer, index=False)
            excel_data = excel_buffer.getvalue()

            st.success(f"**Téléchargement prêt !** {len(page_docs)} résultats affichés.")
            col1, col2 = st.columns(2)
            with col1:
                st.download_button("📂 Télécharger en CSV", all_csv, file_name="reviews_export.csv", mime="text/csv")
            with col2:
                st.download_button("📄 Télécharger en Excel", excel_data, file_name="reviews_export.xlsx", mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")

            # Export de toutes les données stockées
            st.markdown("---")
            st.subheader("📦 Exporter toutes les pages")

            if st.button("🔄 Charger toutes les pages depuis l'API"):
                with st.spinner("Chargement de toutes les reviews..."):
                    while st.session_state.next_cursor:
                        params_with_rows = params.copy()
                        params_with_rows["rows"] = rows_per_page
                        if use_random and random_seed:
                            params_with_rows["random"] = str(random_seed)
                        params_with_rows["cursorMark"] = st.session_state.next_cursor

                        result = fetch("/reviews", params_with_rows)
                        if result and result.get("docs"):
                            new_docs = result.get("docs", [])
                            st.session_state.all_docs.extend(new_docs)
                            st.session_state.next_cursor = result.get("nextCursorMark")
                        else:
                            break
                    st.success("✅ Toutes les pages disponibles ont été chargées.")

            full_df = pd.json_normalize(st.session_state.all_docs)
            full_df = full_df.applymap(lambda x: str(x) if isinstance(x, (dict, list)) else x)
            all_csv_full = full_df.to_csv(index=False)
            excel_buffer_full = io.BytesIO()
            with pd.ExcelWriter(excel_buffer_full, engine='openpyxl') as writer:
                full_df.to_excel(writer, index=False)
            excel_data_full = excel_buffer_full.getvalue()

            colf1, colf2 = st.columns(2)
            with colf1:
                st.download_button("📂 Télécharger toutes les reviews (CSV)", all_csv_full, file_name="all_reviews_export.csv", mime="text/csv")
            with colf2:
                st.download_button("📄 Télécharger toutes les reviews (Excel)", excel_data_full, file_name="all_reviews_export.xlsx", mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")





if __name__ == "__main__":
    main()
