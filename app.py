import os
import re
import unicodedata
import textwrap
from io import BytesIO

import streamlit as st
import pandas as pd

from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas
from reportlab.lib.utils import ImageReader

# --- Chemins des fichiers ---
EXCEL_PATH = "PCP.xlsx"
PROTOCOLE_PDF_PATH = "Protocole_repartition.pdf"  # renomme ton PDF avec ce nom
PDF_LIBRARY_DIR = "pdf_competences"  # dossier pour stocker tes PDF par compétence
LOGO_PATH = "logo_academie_versailles.png"        # logo à placer à côté de app.py

# --- Constantes de mise en page PDF ---
PAGE_WIDTH, PAGE_HEIGHT = A4
LEFT_MARGIN = 40
RIGHT_MARGIN = 40
TOP_MARGIN = 40
BOTTOM_MARGIN = 40
LINE_HEIGHT = 15
TEXT_WIDTH = PAGE_WIDTH - LEFT_MARGIN - RIGHT_MARGIN


# --- Fonctions utilitaires pour Excel ---

@st.cache_data
def load_class_list():
    """
    Liste des classes depuis l'onglet 'Continuité pédagogique'.
    On suppose que la première colonne contient les noms de classes.
    """
    df = pd.read_excel(EXCEL_PATH, sheet_name="Continuité pédagogique")
    col = df.columns[0]  # ex : "Choix de la classe"
    return df[col].dropna().tolist()


@st.cache_data
def load_competences_for_class(classe: str) -> pd.DataFrame:
    """
    Charge les compétences pour une classe (PS, MS, GS, CP, CE1...).
    On suppose que chaque onglet porte le nom de la classe.
    """
    df = pd.read_excel(EXCEL_PATH, sheet_name=classe)
    expected_cols = ["Domaine", "Sous domaine", "Compétence", "Activité proposée"]
    df = df[expected_cols]
    return df


# --- Fiche texte (structure commune) ---

def build_fiche_text(
    ecole,
    classe,
    enseignant_absent,
    date_debut,
    date_fin,
    duree_type,
    domaine,
    sous_domaine,
    competence,
    activites,
    organisation,
    logistique,
    communication_familles,
):
    """Construit le contenu texte de la fiche pédagogique."""
    fiche = f"""FICHE DE CONTINUITÉ PÉDAGOGIQUE

École : {ecole}
Classe concernée : {classe}
Enseignant absent : {enseignant_absent}
Période : {date_debut} -> {date_fin}
Durée de l'absence : {duree_type}

1. MISE EN ŒUVRE / ORGANISATION
--------------------------------
Organisation de la classe / des groupes :
{organisation}

Logistique / matériel / ressources :
{logistique}

2. CONTENUS D'APPRENTISSAGE
----------------------------
Domaine : {domaine}
Sous-domaine : {sous_domaine}
Compétence travaillée :
{competence}

Activités prévues :
{activites}

3. COMMUNICATION
-----------------
Message / éléments de communication aux familles :
{communication_familles}

"""
    return fiche


# --- Outils pour la bibliothèque de PDF par compétence ---

def slugify_filename(value: str) -> str:
    """
    Transforme un texte libre (compétence) en nom de fichier safe :
    - supprime les accents,
    - remplace les espaces par des underscores,
    - enlève les caractères spéciaux.
    """
    value = str(value)
    value = unicodedata.normalize("NFKD", value).encode("ascii", "ignore").decode("ascii")
    value = re.sub(r"[^\w\s-]", "", value).strip().lower()
    value = re.sub(r"[\s-]+", "_", value)
    return value


def get_pdf_from_library(competence: str):
    """
    Cherche un PDF dans le dossier PDF_LIBRARY_DIR correspondant à la compétence.
    Si trouvé -> renvoie les bytes.
    Sinon -> renvoie None (on passera à la génération d'un PDF d'exemple).
    """
    if not competence:
        return None

    safe_name = slugify_filename(competence)
    os.makedirs(PDF_LIBRARY_DIR, exist_ok=True)  # garantit que le dossier existe

    candidate_path = os.path.join(PDF_LIBRARY_DIR, f"{safe_name}.pdf")

    if os.path.exists(candidate_path):
        with open(candidate_path, "rb") as f:
            return f.read()

    return None


# --- Outils texte -> PDF (mise en page propre) ---

def wrap_text_to_width(text, font="Helvetica", font_size=11):
    """
    Coupe automatiquement les lignes trop longues selon la largeur autorisée.
    Retourne une liste de lignes prêtes à être écrites.
    """
    lines = []
    for paragraph in text.split("\n"):
        if paragraph.strip() == "":
            lines.append("")  # ligne vide
            continue

        # Estimation du nombre max de caractères par ligne (approx mais efficace)
        max_chars = int(TEXT_WIDTH / (font_size * 0.55))
        wrapped = textwrap.wrap(paragraph, width=max_chars)
        if not wrapped:
            lines.append("")
        else:
            lines.extend(wrapped)

    return lines


def draw_logo_top_right(c):
    """
    Dessine le logo en haut à droite de la page PDF si le fichier existe.
    """
    if not os.path.exists(LOGO_PATH):
        return

    try:
        logo = ImageReader(LOGO_PATH)
        # Taille du logo (en points)
        logo_width = 90
        logo_height = 60
        x = PAGE_WIDTH - RIGHT_MARGIN - logo_width
        y = PAGE_HEIGHT - TOP_MARGIN - logo_height + 20  # un peu plus haut
        c.drawImage(logo, x, y, width=logo_width, height=logo_height, mask='auto')
    except Exception:
        # Si problème de lecture du logo, on ne bloque pas la génération du PDF
        pass


def build_example_pdf(fiche_texte: str, competence: str = None) -> bytes:
    """
    Génère un PDF d'exemple propre, paginé, avec retours à la ligne
    et logo en haut à droite.
    """
    buffer = BytesIO()
    c = canvas.Canvas(buffer, pagesize=A4)

    # Première page : logo en haut à droite
    draw_logo_top_right(c)

    y = PAGE_HEIGHT - TOP_MARGIN - 10

    # --- TITRE ---
    if competence:
        c.setFont("Helvetica-Bold", 14)
        title_lines = wrap_text_to_width(f"Compétence : {competence}", font_size=14)
        for line in title_lines:
            c.drawString(LEFT_MARGIN, y, line)
            y -= LINE_HEIGHT
        y -= LINE_HEIGHT
    else:
        c.setFont("Helvetica-Bold", 14)
        c.drawString(LEFT_MARGIN, y, "Fiche de continuité pédagogique")
        y -= LINE_HEIGHT * 2

    # --- TEXTE PRINCIPAL ---
    c.setFont("Helvetica", 11)

    for line in wrap_text_to_width(fiche_texte):
        if y < BOTTOM_MARGIN:
            # Nouvelle page : logo + reset Y
            c.showPage()
            draw_logo_top_right(c)
            c.setFont("Helvetica", 11)
            y = PAGE_HEIGHT - TOP_MARGIN - 10

        c.drawString(LEFT_MARGIN, y, line)
        y -= LINE_HEIGHT

    c.save()
    pdf = buffer.getvalue()
    buffer.close()
    return pdf


def build_pdf_for_competence(competence: str, fiche_texte: str) -> bytes:
    """
    1) Cherche un PDF dans la bibliothèque `pdf_competences`
    2) Sinon génère un PDF d’exemple (correctement mis en page + logo)
    """
    if competence:
        pdf_from_lib = get_pdf_from_library(competence)
        if pdf_from_lib:
            # On suppose que les PDF de la bibliothèque ont déjà leur propre mise en forme
            return pdf_from_lib

    # Fallback : PDF avec mise en page + logo
    return build_example_pdf(fiche_texte, competence)


# --- Mise en page générale Streamlit ---

st.set_page_config(
    page_title="Continuité pédagogique - Absence enseignant",
    layout="wide",
)

# Bandeau haut : titre à gauche / logo à droite
top_col1, top_col2 = st.columns([4, 1])

with top_col1:
    st.title("🧑‍🏫 Continuité pédagogique en cas d'absence d'un enseignant")

with top_col2:
    if os.path.exists(LOGO_PATH):
        st.image(LOGO_PATH, width=160)  # Ajuste la taille si nécessaire
    else:
        st.write("")  # pas de logo si fichier absent

st.markdown(
    """
Cette application accompagne le directeur (ou un parent référent) en **3 étapes** :

1. **Mise en œuvre** : informations pratiques et organisation.  
2. **Contenu** : choix des compétences et des activités.  
3. **Communication** : message aux familles / à l’équipe.

Sélectionne d’abord la **durée de l’absence** :
"""
)

duree_type = st.radio(
    "Durée de l’absence",
    ["1 à 5 jours", "Plus de 5 jours"],
    horizontal=True,
)

st.divider()

# --- Infos générales communes ---

st.subheader("Informations générales")

col1, col2, col3 = st.columns(3)

with col1:
    ecole = st.text_input("Nom de l'école", value="")
    enseignant_absent = st.text_input("Enseignant absent", value="")

with col2:
    date_debut = st.date_input("Date de début de l'absence")
    date_fin = st.date_input("Date de fin de l'absence")

with col3:
    try:
        classes_disponibles = load_class_list()
    except Exception as e:
        st.error(f"Erreur lors du chargement des classes depuis {EXCEL_PATH} : {e}")
        classes_disponibles = []
    classe = st.selectbox("Classe concernée", classes_disponibles)


st.divider()

# ----------------- CAS 1 : ABSENCE COURTE (1 à 5 jours) -----------------

if duree_type == "1 à 5 jours":
    st.header("Absence de 1 à 5 jours : répartition des élèves")

    st.markdown(
        """
Pour une absence courte, le protocole prévoit généralement une **répartition des élèves dans les autres classes** 
en s’appuyant sur un document de référence (PDF de protocole de répartition).
"""
    )

    # Étape 1 - Mise en œuvre
    st.subheader("Étape 1 • Mise en œuvre / Organisation")

    organisation_courte = st.text_area(
        "Comment les élèves de la classe absente vont-ils être répartis ? \
(par niveau, par groupes, par demi-journées, etc.)",
        height=120,
    )

    logistique_courte = st.text_area(
        "Logistique / points de vigilance \
(accueil, cantine, PAI, APC, services, corrections…)",
        height=120,
    )

    # Protocole PDF à télécharger
    st.markdown("### Protocole de répartition entre les classes")

    try:
        with open(PROTOCOLE_PDF_PATH, "rb") as f:
            pdf_bytes_protocole = f.read()
        st.download_button(
            "📄 Télécharger le protocole de répartition (PDF)",
            data=pdf_bytes_protocole,
            file_name="Protocole_repartition.pdf",
            mime="application/pdf",
        )
        st.caption(
            "Le fichier PDF de protocole doit s'appeler `Protocole_repartition.pdf` "
            "dans le même dossier que `app.py`."
        )
    except FileNotFoundError:
        st.warning(
            f"Le fichier `{PROTOCOLE_PDF_PATH}` est introuvable. "
            "Place-le dans le même dossier que `app.py` ou modifie PROTOCOLE_PDF_PATH."
        )

    # Étape 2 - Contenu (consolidation / révisions)
    st.subheader("Étape 2 • Contenu proposé aux élèves")

    contenu_courte = st.text_area(
        "Activités prévues (consolidation, révisions, lecture, problèmes, production d'écrits, etc.)",
        height=140,
    )

    # Étape 3 - Communication
    st.subheader("Étape 3 • Communication")

    message_familles_courte = st.text_area(
        "Message aux familles ou à l’ENT (modèle) :",
        value=(
            "Madame, Monsieur,\n\n"
            f"L’enseignant(e) de la classe {classe} est absent(e) du {date_debut} au {date_fin}. "
            "Les élèves seront répartis dans les autres classes selon le protocole de continuité pédagogique. "
            "Les apprentissages seront assurés sous forme d’activités de consolidation.\n\n"
            "Cordialement,\nLa direction."
        ),
        height=160,
    )

    # Génération de la fiche (texte + PDF générique, pas lié à une compétence)
    st.subheader("Récapitulatif")

    fiche_texte = build_fiche_text(
        ecole=ecole,
        classe=classe,
        enseignant_absent=enseignant_absent,
        date_debut=str(date_debut),
        date_fin=str(date_fin),
        duree_type=duree_type,
        domaine="(non spécifié – absence courte)",
        sous_domaine="",
        competence="",
        activites=contenu_courte,
        organisation=organisation_courte,
        logistique=logistique_courte,
        communication_familles=message_familles_courte,
    )

    st.text_area("Prévisualisation de la fiche", fiche_texte, height=300)

    # Ici pas de compétence -> PDF d'exemple générique (avec logo)
    pdf_bytes = build_pdf_for_competence(None, fiche_texte)

    st.download_button(
        "💾 Télécharger la fiche (PDF)",
        data=pdf_bytes,
        file_name="fiche_continuite_absence_courte.pdf",
        mime="application/pdf",
    )

# ----------------- CAS 2 : ABSENCE LONGUE (>5 jours) -----------------

else:
    st.header("Absence de plus de 5 jours : fiche de travail par compétences")

    st.markdown(
        """
Pour une absence longue, on s’appuie sur le fichier **PCP.xlsx** pour choisir :

- la **classe**,
- le **domaine**,
- le **sous-domaine**,
- puis la **compétence** actuellement travaillée.

👉 Le PDF généré doit, à terme, s'appuyer sur une **bibliothèque de PDF par compétence**  
(dossier `pdf_competences/`).  
Tant que cette bibliothèque n’est pas remplie, l’application génère un **PDF d’exemple** correspondant à la compétence (avec le logo en haut à droite).
"""
    )

    # Chargement des compétences pour la classe choisie
    if classe:
        try:
            df_comp = load_competences_for_class(classe)
        except Exception as e:
            st.error(f"Erreur lors du chargement des compétences pour {classe} : {e}")
            df_comp = None
    else:
        df_comp = None

    if df_comp is not None and not df_comp.empty:
        # Filtrage par domaine / sous-domaine
        st.subheader("Étape 2 • Choix de la compétence")

        domaines = sorted(df_comp["Domaine"].dropna().unique())
        domaine = st.selectbox("Domaine", domaines)

        sous_df = df_comp[df_comp["Domaine"] == domaine]
        sous_domaines = sorted(sous_df["Sous domaine"].dropna().unique())
        sous_domaine = st.selectbox("Sous-domaine", sous_domaines)

        comp_df = sous_df[sous_df["Sous domaine"] == sous_domaine]
        competences = comp_df["Compétence"].dropna().tolist()
        competence = st.selectbox("Compétence travaillée", competences)

        # Activité proposée éventuellement présente dans le fichier
        activite_proposee = ""
        if competence:
            ligne = comp_df[comp_df["Compétence"] == competence]
            if not ligne.empty:
                activite_proposee = str(ligne["Activité proposée"].iloc[0] or "")

        st.markdown("### Activités prévues")

        activites = st.text_area(
            "Décrire les activités prévues pour cette compétence "
            "(tu peux partir de la colonne 'Activité proposée' si elle est renseignée) :",
            value=activite_proposee,
            height=160,
        )

        # Étape 1 & 3 : organisation + communication
        st.subheader("Étape 1 • Mise en œuvre / Organisation")

        organisation_longue = st.text_area(
            "Organisation de la continuité pédagogique \
(groupes, plan de travail, cahier de texte, supports envoyés, etc.)",
            height=140,
        )

        logistique_longue = st.text_area(
            "Logistique / matériel (manuels, photocopies, ENT, tablette, ressources en ligne…)",
            height=140,
        )

        st.subheader("Étape 3 • Communication")

        message_familles_longue = st.text_area(
            "Message aux familles (modèle) :",
            value=(
                "Madame, Monsieur,\n\n"
                f"Suite à l'absence prolongée de l’enseignant(e) de la classe {classe}, "
                "une continuité pédagogique est mise en place du "
                f"{date_debut} au {date_fin}. "
                "Les élèves travailleront notamment la compétence suivante :\n"
                f"- {competence}\n\n"
                "Vous trouverez ci-joint / dans le cahier les activités prévues.\n\n"
                "Cordialement,\nLa direction."
            ),
            height=180,
        )

        # Génération de la fiche
        st.subheader("Fiche pédagogique générée")

        fiche_texte = build_fiche_text(
            ecole=ecole,
            classe=classe,
            enseignant_absent=enseignant_absent,
            date_debut=str(date_debut),
            date_fin=str(date_fin),
            duree_type=duree_type,
            domaine=domaine,
            sous_domaine=sous_domaine,
            competence=competence,
            activites=activites,
            organisation=organisation_longue,
            logistique=logistique_longue,
            communication_familles=message_familles_longue,
        )

        st.text_area("Prévisualisation de la fiche", fiche_texte, height=350)

        # PDF basé sur bibliothèque si dispo, sinon exemple (avec logo)
        pdf_bytes = build_pdf_for_competence(competence, fiche_texte)

        st.download_button(
            "💾 Télécharger la fiche (PDF)",
            data=pdf_bytes,
            file_name=f"fiche_continuite_{slugify_filename(classe)}_{slugify_filename(competence)}.pdf",
            mime="application/pdf",
        )

    else:
        st.warning(
            "Impossible de charger les compétences pour cette classe. "
            f"Vérifie le fichier {EXCEL_PATH} et le nom des onglets."
        )
