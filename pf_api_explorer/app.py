st.markdown("## ⚙️ Paramètres d’export des reviews")

import os
from pathlib import Path

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

        metrics_result = fetch("/metrics", params)
        total_results = metrics_result.get("nbDocs", 0) if metrics_result else 0

        if total_results == 0:
            st.warning("Aucune review disponible pour cette combinaison")
        else:
            total_pages = (total_results + rows_per_page - 1) // rows_per_page
            result = fetch("/reviews", params_with_rows)

            if result and result.get("docs"):
                docs = result.get("docs", [])
                st.session_state.all_docs = docs.copy()
                st.session_state.next_cursor = result.get("nextCursorMark")

                # 🔒 Génération du log d'export local (changer le chemin si besoin)
                log_path = Path("review_exports_log.csv")
                export_date = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

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
                        "rows": rows_per_page,
                        "random_seed": random_seed if use_random else None,
                        "nb_reviews": len(docs),
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
