import streamlit as st
from streamlit.components.v1 import html
import pandas as pd

# Fonction pour améliorer l'accessibilité des composants Streamlit
def create_accessible_checkbox(label, key, value=False, help_text=None):
    """Crée une case à cocher accessible avec label explicite et texte d'aide"""
    col1, col2 = st.columns([4, 1])
    with col1:
        if help_text:
            st.markdown(f"""<div class="checkbox-container">
                <label for="{key}" aria-describedby="{key}_help">{label}</label>
                <div id="{key}_help" class="help-text">{help_text}</div>
            </div>""", unsafe_allow_html=True)
        else:
            st.markdown(f'<label for="{key}">{label}</label>', unsafe_allow_html=True)
    with col2:
        return st.checkbox("", value=value, key=key)

# Ajouter du CSS personnalisé pour l'accessibilité
def add_accessibility_styles():
    st.markdown("""
    <style>
    /* Amélioration du contraste et de la visibilité */
    .stButton > button {
        border: 2px solid #4CAF50 !important;
        color: #FFFFFF !important;
        background-color: #3A5E40 !important;
        font-weight: bold !important;
    }
    
    .stButton > button:hover {
        background-color: #4CAF50 !important;
        box-shadow: 0 0 10px rgba(76, 175, 80, 0.5) !important;
    }
    
    .stButton > button:focus {
        outline: 3px solid #4CAF50 !important;
        outline-offset: 2px !important;
    }
    
    .stButton > button:disabled {
        opacity: 0.6 !important;
        cursor: not-allowed !important;
        background-color: #767676 !important;
        border-color: #767676 !important;
    }
    
    /* Amélioration focus pour tous les éléments interactifs */
    input:focus, select:focus, textarea:focus, button:focus, a:focus, 
    .stSelectbox:focus, .stMultiSelect:focus, .stDateInput:focus {
        outline: 3px solid #4CAF50 !important;
        outline-offset: 2px !important;
    }
    
    /* Meilleure visibilité des étiquettes */
    label, .stLabel {
        font-weight: 500 !important;
        margin-bottom: 5px !important;
        display: block !important;
    }
    
    /* Notifications et alertes accessibles */
    .accessibility-alert {
        padding: 15px;
        border-radius: 5px;
        margin: 10px 0;
        position: relative;
        padding-left: 50px;
    }
    
    .accessibility-alert:before {
        position: absolute;
        left: 15px;
        top: 50%;
        transform: translateY(-50%);
        font-size: 24px;
    }
    
    .accessibility-alert.info {
        background-color: #e8f4f8;
        border-left: 5px solid #2196F3;
        color: #0b3c5d;
    }
    
    .accessibility-alert.info:before {
        content: "ℹ️";
    }
    
    .accessibility-alert.warning {
        background-color: #fff8e1;
        border-left: 5px solid #FFC107;
        color: #663c00;
    }
    
    .accessibility-alert.warning:before {
        content: "⚠️";
    }
    
    .accessibility-alert.success {
        background-color: #e8f5e9;
        border-left: 5px solid #4CAF50;
        color: #1b5e20;
    }
    
    .accessibility-alert.success:before {
        content: "✅";
    }
    
    .accessibility-alert.error {
        background-color: #fdecea;
        border-left: 5px solid #F44336;
        color: #921616;
    }
    
    .accessibility-alert.error:before {
        content: "❌";
    }
    
    /* Indication visuelle pour les éléments requis */
    .required-field label:after {
        content: " *";
        color: #F44336;
    }
    
    /* Amélioration de la visibilité des tableaux */
    .dataframe {
        border-collapse: collapse !important;
        width: 100% !important;
    }
    
    .dataframe th {
        background-color: #f1f1f1 !important;
        color: #333 !important;
        font-weight: bold !important;
        text-align: left !important;
        padding: 10px !important;
    }
    
    .dataframe td {
        padding: 10px !important;
        border-bottom: 1px solid #ddd !important;
    }
    
    .dataframe tr:nth-child(even) {
        background-color: #f9f9f9 !important;
    }
    
    .dataframe tr:hover {
        background-color: #f1f1f1 !important;
    }
    
    /* Style des onglets d'étapes */
    .step-tabs {
        display: flex;
        margin-bottom: 20px;
    }
    
    .step-tab {
        flex: 1;
        padding: 15px 20px;
        text-align: center;
        background-color: #f1f1f1;
        border-right: 1px solid #ddd;
        cursor: pointer;
        position: relative;
    }
    
    .step-tab:first-child {
        border-radius: 5px 0 0 5px;
    }
    
    .step-tab:last-child {
        border-radius: 0 5px 5px 0;
        border-right: none;
    }
    
    .step-tab.active {
        background-color: #4CAF50;
        color: white;
        font-weight: bold;
    }
    
    .step-tab.complete {
        background-color: #81C784;
        color: white;
    }
    
    .step-tab.complete:after {
        content: "✓";
        margin-left: 5px;
    }
    
    .step-indicator {
        display: block;
        font-size: 12px;
        margin-top: 5px;
        color: #555;
    }
    
    .active .step-indicator {
        color: #e0e0e0;
    }
    
    /* Skip link pour la navigation au clavier */
    .skip-link {
        position: absolute;
        top: -40px;
        left: 0;
        background: #4CAF50;
        color: white;
        padding: 8px;
        z-index: 100;
        transition: top 0.3s;
    }
    
    .skip-link:focus {
        top: 0;
    }
    
    /* Carte de produit */
    .product-card {
        border: 1px solid #ddd;
        border-radius: 5px;
        padding: 15px;
        margin-bottom: 15px;
        transition: box-shadow 0.3s;
        display: flex;
        align-items: center;
    }
    
    .product-card:hover {
        box-shadow: 0 5px 15px rgba(0,0,0,0.1);
    }
    
    .product-card-checkbox {
        margin-right: 15px;
    }
    
    .product-card-content {
        flex-grow: 1;
    }
    
    .product-card-brand {
        font-weight: bold;
        color: #555;
    }
    
    .product-card-name {
        font-size: 16px;
        margin: 5px 0;
    }
    
    .product-card-reviews {
        background-color: #f1f1f1;
        padding: 3px 8px;
        border-radius: 10px;
        font-size: 14px;
    }
    
    /* Amélioration de la visibilité du focus pour le mode sombre */
    @media (prefers-color-scheme: dark) {
        input:focus, select:focus, textarea:focus, button:focus, a:focus {
            outline: 3px solid #81C784 !important;
        }
    }
    </style>
    
    <a href="#main-content" class="skip-link">Aller au contenu principal</a>
    """, unsafe_allow_html=True)

# Fonction pour créer des notifications accessibles
def accessible_notification(message, type="info"):
    """Affiche une notification accessible avec type: info, success, warning, error"""
    st.markdown(f'<div class="accessibility-alert {type}" role="alert">{message}</div>', unsafe_allow_html=True)

# Interface par étapes pour améliorer le flux utilisateur
def step_navigation(current_step):
    steps = [
        {"id": 1, "name": "Filtres", "aria": "Configuration des filtres"},
        {"id": 2, "name": "Produits", "aria": "Sélection des produits"},
        {"id": 3, "name": "Paramètres", "aria": "Paramètres d'export"},
        {"id": 4, "name": "Résultats", "aria": "Résultats et téléchargement"}
    ]
    
    html_steps = '<div class="step-tabs" role="tablist">'
    
    for step in steps:
        status = ""
        if step["id"] < current_step:
            status = "complete"
        elif step["id"] == current_step:
            status = "active"
            
        html_steps += f"""
        <div class="step-tab {status}" role="tab" 
             aria-selected="{'true' if status == 'active' else 'false'}" 
             id="step-{step['id']}" 
             aria-controls="step-panel-{step['id']}">
            {step["name"]}
            <span class="step-indicator" aria-hidden="true">Étape {step["id"]}/{len(steps)}</span>
        </div>
        """
    
    html_steps += '</div>'
    st.markdown(html_steps, unsafe_allow_html=True)

# Exemple d'utilisation des cartes de produit au lieu d'un simple tableau
def product_card_list(products_df, on_select_callback=None):
    """Affiche les produits sous forme de cartes interactives"""
    if products_df.empty:
        st.write("Aucun produit disponible pour ces critères.")
        return []
    
    selected_products = []
    
    for _, row in products_df.iterrows():
        product_id = row["Produit"]
        
        # Créer une carte pour chaque produit
        cols = st.columns([1, 10])
        
        with cols[0]:
            is_selected = st.checkbox("", key=f"prod_{product_id}", 
                               label_visibility="collapsed",
                               help=f"Sélectionner {product_id}")
            if is_selected:
                selected_products.append(product_id)
        
        with cols[1]:
            st.markdown(f"""
            <div class="product-card">
                <div class="product-card-content">
                    <div class="product-card-brand">{row["Marque"]}</div>
                    <div class="product-card-name">{row["Produit"]}</div>
                    <div class="product-card-reviews">{row["Nombre d'avis"]} avis</div>
                </div>
            </div>
            """, unsafe_allow_html=True)
    
    return selected_products

# Création d'un composant résumé des filtres toujours visible
def filters_summary(filters):
    """Affiche un résumé des filtres appliqués"""
    with st.expander("📌 Résumé des filtres appliqués", expanded=True):
        col1, col2 = st.columns(2)
        
        with col1:
            st.markdown("**📅 Période**")
            st.markdown(f"Du {filters['start_date']} au {filters['end_date']}")
            
            st.markdown("**🏷️ Catégories**")
            st.markdown(f"Catégorie: {filters['category']}")
            st.markdown(f"Sous-catégorie: {filters['subcategory']}")
            
            st.markdown("**🏢 Marques**")
            brands = ", ".join(filters['brand']) if filters['brand'] else "Toutes"
            st.markdown(f"{brands}")
            
        with col2:
            st.markdown("**🌎 Localisation**")
            countries = ", ".join(filters['country']) if filters['country'] and 'ALL' not in filters['country'] else "Tous"
            st.markdown(f"Pays: {countries}")
            
            markets = ", ".join(filters['market']) if filters['market'] and 'ALL' not in filters['market'] else "Tous"
            st.markdown(f"Marchés: {markets}")
            
            st.markdown("**🔍 Attributs**")
            attributes = ", ".join(filters['attributes']) if filters['attributes'] else "Aucun"
            st.markdown(f"Attributs: {attributes}")
            
            pos_attrs = ", ".join(filters['attributes_positive']) if filters['attributes_positive'] else "Aucun"
            neg_attrs = ", ".join(filters['attributes_negative']) if filters['attributes_negative'] else "Aucun"
            st.markdown(f"Positifs: {pos_attrs}")
            st.markdown(f"Négatifs: {neg_attrs}")

# Amélioration de la pagination avec indicateurs d'accessibilité
def accessible_pagination(current_page, total_pages, page_change_callback):
    """Crée une pagination avec des contrôles accessibles"""
    col1, col2, col3 = st.columns([2, 3, 2])
    
    with col1:
        prev_disabled = current_page <= 1
        if st.button("⬅️ Page précédente", 
                    disabled=prev_disabled,
                    help="Aller à la page précédente",
                    key="prev_page_btn"):
            if not prev_disabled:
                page_change_callback(current_page - 1)
    
    with col2:
        st.markdown(f"""
        <div style="text-align: center;">
            <span aria-live="polite" aria-atomic="true">
                Page <strong>{current_page}</strong> sur <strong>{total_pages}</strong>
            </span>
        </div>
        """, unsafe_allow_html=True)
        
        # Ajouter un slider de navigation rapide si beaucoup de pages
        if total_pages > 5:
            page = st.slider("Aller à la page", 1, total_pages, current_page, 
                           key="page_slider", label_visibility="collapsed")
            if page != current_page:
                page_change_callback(page)
    
    with col3:
        next_disabled = current_page >= total_pages
        if st.button("➡️ Page suivante", 
                    disabled=next_disabled,
                    help="Aller à la page suivante",
                    key="next_page_btn"):
            if not next_disabled:
                page_change_callback(current_page + 1)

def main():
    # Appliquer les styles d'accessibilité
    add_accessibility_styles()
    
    st.title("Explorateur API Ratings & Reviews")
    st.markdown('<span id="main-content"></span>', unsafe_allow_html=True)
    
    # Intégrer un composant d'aide et d'accessibilité dans l'en-tête
    with st.expander("ℹ️ Aide et accessibilité"):
        st.markdown("""
        ### Raccourcis clavier
        - **Tab** : Naviguer entre les éléments
        - **Entrée** : Activer un bouton ou sélectionner une option
        - **Espace** : Cocher/décocher une case
        - **Flèches** : Naviguer dans les listes déroulantes
        
        ### Accessibilité
        Cette application est optimisée pour les lecteurs d'écran et la navigation au clavier.
        Si vous rencontrez des problèmes d'accessibilité, merci de nous contacter.
        """)
    
    # Démonstration de l'interface par étapes
    if "current_step" not in st.session_state:
        st.session_state.current_step = 1
        
    step_navigation(st.session_state.current_step)
    
    # Exemple d'utilisation des notifications accessibles
    accessible_notification(
        "Cette version inclut des améliorations d'accessibilité. Utilisez la touche Tab pour naviguer.", 
        type="info"
    )
    
    # Démonstration d'un composant de filtre accessible
    st.subheader("Démonstration de composants accessibles")
    
    # Exemple de champ requis avec indication visuelle
    st.markdown('<div class="required-field">', unsafe_allow_html=True)
    date_from = st.date_input("Date de début", help="Sélectionnez la date de début pour filtrer les résultats")
    st.markdown('</div>', unsafe_allow_html=True)
    
    # Exemple de case à cocher accessible
    use_random = create_accessible_checkbox(
        "Randomiser les résultats", 
        "use_random_accessible",
        help_text="Activez cette option pour obtenir un échantillon aléatoire des résultats."
    )
    
    # Exemple de carte produit accessible
    st.subheader("Exemple de cartes produit")
    # Créer des données d'exemple
    sample_data = {
        "Marque": ["L'Oréal", "Garnier", "Maybelline"],
        "Produit": ["Mascara Volume", "Crème Hydratante", "Rouge à Lèvres Mat"],
        "Nombre d'avis": [128, 245, 89]
    }
    df_sample = pd.DataFrame(sample_data)
    
    # Afficher les cartes produit
    selected = product_card_list(df_sample)
    
    # Exemple d'un résumé de filtres
    st.subheader("Résumé des filtres")
    example_filters = {
        "start_date": "2022-01-01",
        "end_date": "2023-01-01",
        "category": "Maquillage",
        "subcategory": "Lèvres",
        "brand": ["L'Oréal", "Maybelline"],
        "country": ["France", "Allemagne"],
        "market": ["Europe"],
        "attributes": ["Longue tenue", "Hydratant"],
        "attributes_positive": ["Pigmentation"],
        "attributes_negative": []
    }
    filters_summary(example_filters)
    
    # Exemple de pagination accessible
    st.subheader("Pagination accessible")
    
    def change_page(new_page):
        st.session_state.demo_page = new_page
        
    if "demo_page" not in st.session_state:
        st.session_state.demo_page = 1
        
    accessible_pagination(st.session_state.demo_page, 10, change_page)

if __name__ == "__main__":
    main()
