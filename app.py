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
PROTOCOLE_PDF_PATH = "Protocole_repartition.pdf"
LOGO_PATH = "logo_academie_versailles.png"

# Bibliothèques PDF
PDF_COMPETENCES_DIR = "pdf_competences"  # PDF exercices
PDF_CORRECTION_DIR = "pdf_correction"    # PDF corrections


# --- Constantes de mise en page PDF ---
PAGE_WIDTH, PAGE_HEIGHT = A4
LEFT_MARGIN = 40
RIGHT_MARGIN = 40
TOP_MARGIN = 40
BOTTOM_MARGIN = 40
LINE_HEIGHT = 15
TEXT_WIDTH = PAGE_WIDTH - LEFT_MARGIN - RIGHT_MARGIN


# -------------------- Excel --------------------

@st.cache_data
def load_class_list():
    df = pd.read_excel(EXCEL_PATH, sheet_name="Continuité pédagogique")
    col = df.columns[0]
    return df[col].dropna().tolist()


@st.cache_data
def load_competences_for_class(classe: str) -> pd.DataFrame:
    df = pd.read_excel(EXCEL_PATH, sheet_name=classe)
    expected_cols = ["Domaine", "Sous domaine", "Compétence", "Activité proposée"]
    return df[expected_cols]


# -------------------- Fiche texte --------------------

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
    return f"""FICHE DE CONTINUITÉ PÉDAGOGIQUE

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


# -------------------- PDF : utilitaires --------------------

def slugify_filename(value: str) -> str:
    value = str(value)
    value = unicodedata.normalize("NFKD", value).encode("ascii", "ignore").decode("ascii")
    value = re.sub(r"[^\w\s-]", "", value).strip().lower()
    value = re.sub(r"[\s-]+", "_", value)
    return value


def ensure_dirs():
    os.makedirs(PDF_COMPETENCES_DIR, exist_ok=True)
    os.makedirs(PDF_CORRECTION_DIR, exist_ok=True)


def wrap_text_to_width(text: str, font_size: int = 11):
    lines = []
    for paragraph in text.split("\n"):
        if paragraph.strip() == "":
            lines.append("")
            continue
        max_chars = int(TEXT_WIDTH / (font_size * 0.55))
        wrapped = textwrap.wrap(paragraph, width=max_chars)
        lines.extend(wrapped if wrapped else [""])
    return lines


def draw_logo_top_right(c: canvas.Canvas):
    if not os.path.exists(LOGO_PATH):
        return
    try:
        logo = ImageReader(LOGO_PATH)
        logo_w = 90
        logo_h = 60
        x = PAGE_WIDTH - RIGHT_MARGIN - logo_w
        y = PAGE_HEIGHT - TOP_MARGIN - logo_h + 20
        c.drawImage(logo, x, y, width=logo_w, height=logo_h, mask="auto")
    except Exception:
        pass


def build_example_pdf(title: str, fiche_texte: str, competence: str | None = None) -> bytes:
    """
    PDF fallback (bien mis en page + logo) si un PDF de bibliothèque manque.
    """
    buffer = BytesIO()
    c = canvas.Canvas(buffer, pagesize=A4)

    draw_logo_top_right(c)
    y = PAGE_HEIGHT - TOP_MARGIN - 10

    # Titre
    c.setFont("Helvetica-Bold", 14)
    for line in wrap_text_to_width(title, font_size=14):
        c.drawString(LEFT_MARGIN, y, line)
        y -= LINE_HEIGHT
    y -= LINE_HEIGHT

    # Sous-titre compétence
    if competence:
        c.setFont("Helvetica-Bold", 12)
        for line in wrap_text_to_width(f"Compétence : {competence}", font_size=12):
            c.drawString(LEFT_MARGIN, y, line)
            y -= LINE_HEIGHT
        y -= LINE_HEIGHT

    # Corps
    c.setFont("Helvetica", 11)
    for line in wrap_text_to_width(fiche_texte, font_size=11):
        if y < BOTTOM_MARGIN:
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


def read_pdf_if_exists(directory: str, competence: str) -> bytes | None:
    """
    Cherche un PDF nommé comme le slug de la compétence dans le dossier donné.
    Exemple : pdf_competences/lire_un_texte_court.pdf
    """
    if not competence:
        return None

    ensure_dirs()
    safe = slugify_filename(competence)
    path = os.path.join(directory, f"{safe}.pdf")
    if os.path.exists(path):
        with open(path, "rb") as f:
            return f.read()
    return None


def get_exercice_pdf(competence: str, fiche_texte: str) -> tuple[bytes, bool]:
    """
    Renvoie (pdf_bytes, found_in_library)
    """
    pdf = read_pdf_if_exists(PDF_COMPETENCES_DIR, competence)
    if pdf is not None:
        return pdf, True
    # fallback
    return build_example_pdf("Fiche d'exercices (exemple)", fiche_texte, competence), False


def get_correction_pdf(competence: str, fiche_texte: str) -> tuple[bytes, bool]:
    """
    Renvoie (pdf_bytes, found_in_library)
    """
    pdf = read_pdf_if_exists(PDF_CORRECTION_DIR, competence)
    if pdf is not None:
        return pdf, True
    # fallback
    return build_example_pdf("Fiche de corrections (exemple)", fiche_texte, competence), False


# -------------------- Streamlit UI --------------------

st.set_page_config(page_title="Continuité pédagogique - Absence enseignant", layout="wide")

# Bandeau haut : titre à gauche / logo à droite
top_col1, top_col2 = st.columns([4, 1])
with top_col1:
    st.title("🧑‍🏫 Continuité pédagogique en cas d'absence d'un enseignant")
with top_col2:
    if os.path.exists(LOGO_PATH):
        st.image(LOGO_PATH, width=160)

st.markdown(
    """
Cette application accompagne le directeur (ou un parent référent) en **3 étapes** :

1. **Mise en œuvre** : informations pratiques et organisation  
2. **Contenu** : choix des compétences et des activités  
3. **Communication** : message aux familles / à l’équipe  

Sélectionne d’abord la **durée de l’absence** :
"""
)

duree_type = st.radio("Durée de l’absence", ["1 à 5 jours", "Plus de 5 jours"], horizontal=True)
st.divider()

# Infos générales
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
        st.error(f"Erreur chargement classes depuis {EXCEL_PATH} : {e}")
        classes_disponibles = []
    classe = st.selectbox("Classe concernée", classes_disponibles)

st.divider()

# ----------------- ABSENCE COURTE -----------------
if duree_type == "1 à 5 jours":
    st.header("Absence de 1 à 5 jours : répartition des élèves")

    st.subheader("Étape 1 • Mise en œuvre / Organisation")
    organisation = st.text_area(
        "Répartition des élèves (niveau, groupes, demi-journées, etc.)",
        height=120,
    )
    logistique = st.text_area(
        "Logistique / points de vigilance (PAI, cantine, services, matériel…)",
        height=120,
    )

    st.markdown("### Protocole de répartition entre les classes")
    try:
        with open(PROTOCOLE_PDF_PATH, "rb") as f:
            protocole_bytes = f.read()
        st.download_button(
            "📄 Télécharger le protocole de répartition (PDF)",
            data=protocole_bytes,
            file_name="Protocole_repartition.pdf",
            mime="application/pdf",
        )
    except FileNotFoundError:
        st.warning(
            f"Le fichier `{PROTOCOLE_PDF_PATH}` est introuvable. "
            "Place-le à la racine du projet (même dossier que app.py)."
        )

    st.subheader("Étape 2 • Contenu proposé aux élèves")
    activites = st.text_area(
        "Activités prévues (consolidation, révisions, lecture, problèmes...)",
        height=140,
    )

    st.subheader("Étape 3 • Communication")
    communication = st.text_area(
        "Message aux familles (modèle) :",
        value=(
            "Madame, Monsieur,\n\n"
            f"L’enseignant(e) de la classe {classe} est absent(e) du {date_debut} au {date_fin}. "
            "Les élèves seront répartis dans les autres classes selon le protocole de continuité pédagogique. "
            "Les apprentissages seront assurés sous forme d’activités de consolidation.\n\n"
            "Cordialement,\nLa direction."
        ),
        height=160,
    )

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
        activites=activites,
        organisation=organisation,
        logistique=logistique,
        communication_familles=communication,
    )

    st.text_area("Prévisualisation de la fiche", fiche_texte, height=300)

    # PDF unique (fallback généré)
    pdf_bytes = build_example_pdf("Fiche de continuité (absence courte)", fiche_texte)
    st.download_button(
        "💾 Télécharger la fiche (PDF)",
        data=pdf_bytes,
        file_name="fiche_continuite_absence_courte.pdf",
        mime="application/pdf",
    )

# ----------------- ABSENCE LONGUE -----------------
else:
    st.header("Absence de plus de 5 jours : exercices + corrections par compétence")

    st.markdown(
        f"""
**Bibliothèques attendues :**
- Exercices : `{PDF_COMPETENCES_DIR}/<competence>.pdf`
- Corrections : `{PDF_CORRECTION_DIR}/<competence>.pdf`

Le nom de fichier doit correspondre au *slug* de la compétence (accents supprimés, espaces remplacés par `_`).
"""
    )

    if classe:
        try:
            df_comp = load_competences_for_class(classe)
        except Exception as e:
            st.error(f"Erreur chargement compétences pour {classe} : {e}")
            df_comp = None
    else:
        df_comp = None

    if df_comp is not None and not df_comp.empty:
        st.subheader("Étape 2 • Choix de la compétence")

        domaines = sorted(df_comp["Domaine"].dropna().unique())
        domaine = st.selectbox("Domaine", domaines)

        sous_df = df_comp[df_comp["Domaine"] == domaine]
        sous_domaines = sorted(sous_df["Sous domaine"].dropna().unique())
        sous_domaine = st.selectbox("Sous-domaine", sous_domaines)

        comp_df = sous_df[sous_df["Sous domaine"] == sous_domaine]
        competences = comp_df["Compétence"].dropna().tolist()
        competence = st.selectbox("Compétence travaillée", competences)

        # activité proposée
        activite_proposee = ""
        if competence:
            ligne = comp_df[comp_df["Compétence"] == competence]
            if not ligne.empty:
                activite_proposee = str(ligne["Activité proposée"].iloc[0] or "")

        st.markdown("### Activités prévues")
        activites = st.text_area(
            "Décrire / compléter les activités prévues (base Excel si renseignée) :",
            value=activite_proposee,
            height=160,
        )

        st.subheader("Étape 1 • Mise en œuvre / Organisation")
        organisation = st.text_area(
            "Organisation (groupes, plan de travail, supports, ENT...)",
            height=140,
        )
        logistique = st.text_area(
            "Logistique / matériel (manuels, photocopies, ressources...)",
            height=140,
        )

        st.subheader("Étape 3 • Communication")
        communication = st.text_area(
            "Message aux familles (modèle) :",
            value=(
                "Madame, Monsieur,\n\n"
                f"Suite à l'absence prolongée de l’enseignant(e) de la classe {classe}, "
                f"une continuité pédagogique est mise en place du {date_debut} au {date_fin}. "
                "Les élèves travailleront notamment la compétence suivante :\n"
                f"- {competence}\n\n"
                "Vous trouverez ci-joint les exercices (et éventuellement les corrections) associés.\n\n"
                "Cordialement,\nLa direction."
            ),
            height=180,
        )

        st.subheader("Fiche de continuité (récap)")
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
            organisation=organisation,
            logistique=logistique,
            communication_familles=communication,
        )
        st.text_area("Prévisualisation", fiche_texte, height=320)

        # Nom de fichier attendu
        expected_ex = os.path.join(PDF_COMPETENCES_DIR, f"{slugify_filename(competence)}.pdf")
        expected_corr = os.path.join(PDF_CORRECTION_DIR, f"{slugify_filename(competence)}.pdf")
        st.caption(f"Nom attendu exercices : {expected_ex}")
        st.caption(f"Nom attendu corrections : {expected_corr}")

        # Génération / récupération des deux PDF
        ex_pdf, ex_found = get_exercice_pdf(competence, fiche_texte)
        corr_pdf, corr_found = get_correction_pdf(competence, fiche_texte)

        if not ex_found:
            st.warning("PDF d'exercices introuvable dans la bibliothèque → un PDF d’exemple a été généré.")
        if not corr_found:
            st.info("PDF de correction introuvable dans la bibliothèque → un PDF d’exemple a été généré.")

        # Téléchargements séparés
        c1, c2 = st.columns(2)
        with c1:
            st.download_button(
                "📄 Télécharger le PDF d’exercices",
                data=ex_pdf,
                file_name=f"exercices_{slugify_filename(classe)}_{slugify_filename(competence)}.pdf",
                mime="application/pdf",
            )
        with c2:
            st.download_button(
                "✅ Télécharger le PDF avec corrections",
                data=corr_pdf,
                file_name=f"corrections_{slugify_filename(classe)}_{slugify_filename(competence)}.pdf",
                mime="application/pdf",
            )

    else:
        st.warning(
            f"Impossible de charger les compétences pour cette classe. Vérifie `{EXCEL_PATH}` et le nom des onglets."
        )
