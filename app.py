# app.py — Plan de continuité pédagogique (version complète, propre, à jour)
# Dépendances (requirements.txt) :
# streamlit
# pandas
# openpyxl
# reportlab
# pypdf

import os
import re
import glob
import unicodedata
import textwrap
import hashlib
import difflib
from io import BytesIO
from datetime import date
from pathlib import Path

import streamlit as st
import pandas as pd

from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas
from reportlab.lib.utils import ImageReader

from pypdf import PdfReader, PdfWriter


# =========================
# CONFIG / FICHIERS
# =========================

EXCEL_PATH = "PCP.xlsx"
LOGO_PATH = "logo_academie_versailles.png"

# PDF téléchargeable (à la racine du projet)
PROTOCOLE_CONTINUITE_PDF = "Protocole de continuité pédagogique.pdf"

# Bibliothèques PDF
PDF_COMPETENCES_DIR = "pdf_competences"  # exercices
PDF_CORRECTION_DIR = "pdf_correction"    # corrections

# Ressource en ligne
GENIALLY_URL = "https://view.genially.com/693ad2fee4adee9eefd9d637/interactive-content-plan-de-continuite-pedagogique"

# Images (si présentes à la racine)
INCIDENCES_HINTS = ["incidence", "incidences", "niveau"]
SLIDE_KEYWORDS = ["contexte", "anticipation", "mise", "oeuvre", "mise_en_oeuvre", "mise-oeuvre"]

# Tailles d’images (Streamlit : utiliser width=...)
SLIDE_WIDTH_PX = 820
INCIDENCE_IMG_WIDTH_PX = 520
LOGO_WIDTH_PX = 110

# PDF fallback : mise en page
PAGE_WIDTH, PAGE_HEIGHT = A4
LEFT_MARGIN = 40
RIGHT_MARGIN = 40
TOP_MARGIN = 40
BOTTOM_MARGIN = 40
LINE_HEIGHT = 15
TEXT_WIDTH = PAGE_WIDTH - LEFT_MARGIN - RIGHT_MARGIN


# =========================
# UTILITAIRES
# =========================

def ensure_dirs():
    os.makedirs(PDF_COMPETENCES_DIR, exist_ok=True)
    os.makedirs(PDF_CORRECTION_DIR, exist_ok=True)


def slugify_filename(value: str) -> str:
    value = str(value)
    value = unicodedata.normalize("NFKD", value).encode("ascii", "ignore").decode("ascii")
    value = re.sub(r"[^\w\s-]", "", value).strip().lower()
    value = re.sub(r"[\s-]+", "_", value)
    return value


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


def build_text_pdf(title: str, body_text: str, subtitle: str | None = None) -> bytes:
    """
    Génère un PDF propre (fallback) : titres + retours à la ligne + pagination + logo.
    """
    buffer = BytesIO()
    c = canvas.Canvas(buffer, pagesize=A4)
    draw_logo_top_right(c)

    y = PAGE_HEIGHT - TOP_MARGIN - 10

    c.setFont("Helvetica-Bold", 14)
    for line in wrap_text_to_width(title, font_size=14):
        c.drawString(LEFT_MARGIN, y, line)
        y -= LINE_HEIGHT
    y -= LINE_HEIGHT

    if subtitle:
        c.setFont("Helvetica-Bold", 12)
        for line in wrap_text_to_width(subtitle, font_size=12):
            c.drawString(LEFT_MARGIN, y, line)
            y -= LINE_HEIGHT
        y -= LINE_HEIGHT

    c.setFont("Helvetica", 11)
    for line in wrap_text_to_width(body_text, font_size=11):
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


def merge_pdfs(pdf_bytes_list: list[bytes]) -> bytes:
    """
    Fusionne une liste de PDF (bytes) en un seul PDF (bytes).
    """
    writer = PdfWriter()
    for pdf_bytes in pdf_bytes_list:
        reader = PdfReader(BytesIO(pdf_bytes))
        for page in reader.pages:
            writer.add_page(page)
    out = BytesIO()
    writer.write(out)
    return out.getvalue()

ILLUSTRATIONS_DIR = "illustrations"

def list_illustrations() -> list[str]:
    exts = (".png", ".jpg", ".jpeg", ".webp", ".pdf")
    if not os.path.exists(ILLUSTRATIONS_DIR):
        return []
    files = []
    for fn in os.listdir(ILLUSTRATIONS_DIR):
        if fn.lower().endswith(exts):
            files.append(os.path.join(ILLUSTRATIONS_DIR, fn))
    return sorted(files)


def pick_illustration_for_livret(illustrations: list[str], livret_num: str, fallback_seed: str = "") -> str | None:
    """
    Même numéro de livret = même illustration.
    Si numéro vide, fallback sur classe.
    """
    if not illustrations:
        return None

    seed = (livret_num or "").strip()
    if not seed:
        seed = (fallback_seed or "default").strip()

    h = hashlib.md5(seed.encode("utf-8")).hexdigest()
    idx = int(h, 16) % len(illustrations)
    return illustrations[idx]


def build_illustration_pdf(image_path: str) -> bytes:
    buffer = BytesIO()
    c = canvas.Canvas(buffer, pagesize=A4)

    try:
        img = ImageReader(image_path)
        iw, ih = img.getSize()

        # zone utilisable
        x0, y0 = 20, 20
        w0, h0 = PAGE_WIDTH - 40, PAGE_HEIGHT - 40

        scale = min(w0 / iw, h0 / ih)
        w = iw * scale
        h = ih * scale
        x = x0 + (w0 - w) / 2
        y = y0 + (h0 - h) / 2

        c.drawImage(img, x, y, width=w, height=h, preserveAspectRatio=True, mask="auto")

    except Exception:
        c.setFont("Helvetica-Bold", 16)
        c.drawString(LEFT_MARGIN, PAGE_HEIGHT - 80, "Illustration")
        c.setFont("Helvetica", 11)
        c.drawString(LEFT_MARGIN, PAGE_HEIGHT - 110, f"Image introuvable : {image_path}")

    draw_logo_top_right(c)

    c.save()
    pdf = buffer.getvalue()
    buffer.close()
    return pdf


def find_first_image_by_hints(hints: list[str]) -> str | None:
    exts = (".png", ".jpg", ".jpeg", ".webp")
    for fn in sorted(glob.glob("*")):
        low = fn.lower()
        if low.endswith(exts) and any(h in low for h in hints):
            return fn
    return None


def build_slides_list() -> list[str]:
    """
    Diaporama : images contenant des mots-clés (contexte/anticipation/mise en oeuvre).
    """
    exts = (".png", ".jpg", ".jpeg", ".webp")
    images = [f for f in glob.glob("*") if f.lower().endswith(exts)]
    slides = []
    for f in images:
        low = f.lower()
        if any(k in low for k in SLIDE_KEYWORDS):
            slides.append(f)
    return sorted(slides)


# =========================
# EXCEL
# =========================

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


# =========================
# RECHERCHE PDF (ROBUSTE CLOUD)
# =========================

@st.cache_data
def build_pdf_index(directory: str) -> dict:
    """
    Indexe tous les PDFs du dossier :
    {slug(nom_sans_extension) -> nom_fichier_original}
    """
    if not os.path.exists(directory):
        return {}
    idx = {}
    for fn in os.listdir(directory):
        if fn.lower().endswith(".pdf"):
            base = os.path.splitext(fn)[0]
            idx[slugify_filename(base)] = fn
    return idx


import difflib  # en haut du fichier

def normalize_for_match(s: str) -> str:
    s = str(s or "")
    s = unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode("ascii")
    s = s.lower()
    s = re.sub(r"[\(\)\[\]\{\}]", " ", s)
    s = re.sub(r"[^\w\s]", " ", s)
    s = re.sub(r"\s+", " ", s).strip()
    return s


def read_pdf_by_competence(directory: str, competence: str) -> tuple[bytes | None, str | None]:
    """
    Cherche un pdf dans directory correspondant à competence.
    - ne plante jamais
    - tolère accents, majuscules, (1), espaces
    - choisit le meilleur match
    """
    if not competence or not os.path.exists(directory):
        return None, None

    target = normalize_for_match(competence)

    pdf_files = [fn for fn in os.listdir(directory) if fn.lower().endswith(".pdf")]
    if not pdf_files:
        return None, None

    candidates = []
    for fn in pdf_files:
        stem = os.path.splitext(fn)[0]
        norm = normalize_for_match(stem)
        candidates.append((fn, norm))

    # 1) exact normalisé
    for fn, norm in candidates:
        if norm == target:
            path = os.path.join(directory, fn)
            try:
                with open(path, "rb") as f:
                    return f.read(), fn
            except FileNotFoundError:
                # au cas où (rare) : on continue
                break

    # 2) contains
    contains_hits = []
    for fn, norm in candidates:
        if target in norm or norm in target:
            score = difflib.SequenceMatcher(None, target, norm).ratio()
            contains_hits.append((score, fn))

    if contains_hits:
        contains_hits.sort(reverse=True, key=lambda x: x[0])
        best_fn = contains_hits[0][1]
        path = os.path.join(directory, best_fn)
        try:
            with open(path, "rb") as f:
                return f.read(), best_fn
        except FileNotFoundError:
            pass

    # 3) meilleur score global
    scored = []
    for fn, norm in candidates:
        score = difflib.SequenceMatcher(None, target, norm).ratio()
        scored.append((score, fn))
    scored.sort(reverse=True, key=lambda x: x[0])

    best_score, best_fn = scored[0]
    if best_score >= 0.62:
        path = os.path.join(directory, best_fn)
        try:
            with open(path, "rb") as f:
                return f.read(), best_fn
        except FileNotFoundError:
            pass

    return None, None


# =========================
# NIVEAU D'INCIDENCE (3 niveaux)
# =========================

INCIDENCE_OPTIONS = ["Faible", "Modéré", "Élevé"]


def message_selon_incidence(level: str) -> str:
    # ⚠️ L'incidence ne doit pas apparaître dans la fiche récap.
    if level == "Faible":
        return "Information simple aux familles dans le carnet de liaison et sur l'ENT."
    if level == "Modéré":
        return "Rencontre de l'équipe pédagogique avec une délégation de parents."
    return "Rencontre entre l'équipe de circonscription et les représentants des parents élus."


# =========================
# MODÈLES DE COMMUNICATION
# =========================

COMM_TEMPLATES = {
    "Modèle 1 — Information simple": (
        "Madame, Monsieur,\n\n"
        "Dans le cadre du plan de continuité pédagogique, des supports de travail sont mis à disposition "
        "afin de poursuivre les apprentissages.\n\n"
        "Cordialement,\nLa direction."
    ),
    "Modèle 2 — Rappel organisation (supports + retour)": (
        "Madame, Monsieur,\n\n"
        "Afin d’assurer la continuité pédagogique, un livret d’exercices est transmis. "
        "Merci de le faire réaliser régulièrement et de conserver les productions.\n\n"
        "Cordialement,\nLa direction."
    ),
    "Modèle 3 — Absence prolongée (supports adaptés)": (
        "Madame, Monsieur,\n\n"
        "Suite à l’absence, des supports de travail sont mis à disposition afin de poursuivre les apprentissages. "
        "Les consignes et les supports seront précisés au fur et à mesure.\n\n"
        "Cordialement,\nLa direction."
    ),
}


# =========================
# FICHE RÉCAP (TEXTE)
# =========================

def build_recap_text(
    livret_num: str,
    ecole: str,
    classe: str,
    enseignant_absent: str,
    dispositif: list[str],
    duree_label: str,
    periode_label: str,
    competences: list[tuple[str, str, str]],
    communication: str | None,
) -> str:
    """
    competences : liste de tuples (Domaine, Sous-domaine, Compétence)
    """
    lines = []
    lines.append("FICHE RÉCAPITULATIVE — PLAN DE CONTINUITÉ PÉDAGOGIQUE")
    lines.append("")
    if livret_num:
        lines.append(f"N° de livret : {livret_num}")
    if ecole:
        lines.append(f"École : {ecole}")
    if classe:
        lines.append(f"Classe concernée : {classe}")
    if enseignant_absent:
        lines.append(f"Enseignant absent : {enseignant_absent}")
    if dispositif:
        lines.append("Dispositif choisi : " + ", ".join(dispositif))
    lines.append(f"Durée : {duree_label}")
    lines.append(f"Période : {periode_label}")
    lines.append("")
    lines.append("CONTENU DU LIVRET (pour 2 jours sans remplacement) :")
    if competences:
        for dom, sous, comp in competences:
            lines.append(f"• {dom} > {sous} > {comp}")
    else:
        lines.append("• (Aucune compétence sélectionnée)")
    if communication:
        lines.append("")
        lines.append("COMMUNICATION (modèle) :")
        lines.append(communication)
    lines.append("")
    return "\n".join(lines)


# =========================
# UI
# =========================

st.set_page_config(page_title="Plan de continuité pédagogique", layout="wide")
ensure_dirs()

# ----- Bannière -----
banner_left, banner_right = st.columns([1, 7], vertical_alignment="center")
with banner_left:
    if os.path.exists(LOGO_PATH):
        st.image(LOGO_PATH, width=LOGO_WIDTH_PX)
with banner_right:
    st.markdown("## Plan de continuité pédagogique")
    st.markdown(
        "<div style='margin-top:-8px; font-size:14px; color:#555;'>"
        "Direction des services départementaux de l’Education Nationale du Val d’Oise"
        "</div>",
        unsafe_allow_html=True,
    )

# ----- Accueil : Diaporama (flèches) -----
slides = build_slides_list()
if "slide_idx" not in st.session_state:
    st.session_state.slide_idx = 0

if slides:
    nav_l, nav_c, nav_r = st.columns([1, 6, 1], vertical_alignment="center")
    with nav_l:
        if st.button("◀", use_container_width=True):
            st.session_state.slide_idx = (st.session_state.slide_idx - 1) % len(slides)
    with nav_r:
        if st.button("▶", use_container_width=True):
            st.session_state.slide_idx = (st.session_state.slide_idx + 1) % len(slides)
    with nav_c:
        st.image(slides[st.session_state.slide_idx], width=SLIDE_WIDTH_PX)
else:
    st.info(
        "Diaporama indisponible : aucune image trouvée.\n\n"
        "Ajoute des images à la racine nommées par exemple :\n"
        "- contexte.png\n- anticipation.jpg\n- mise_en_oeuvre.png"
    )

# ----- Ressources sous le diaporama -----
st.divider()
st.subheader("Ressources")

st.markdown(
    """
**AVANT LA RENTRÉE :**  
Afin de pouvoir bénéficier d’un accompagnement optimum à la continuité pédagogique,
il est nécessaire, au préalable et en équipe, d’avoir désigné une personne ressource
et d’avoir complété le dossier comprenant :

- la fiche « PCP » renseignée,  
- les programmations communes,  
- les répartitions d’élèves.  

Le plan de continuité pédagogique aide le conseil des maîtres à déterminer l’organisation
la plus adaptée à la situation de l’école (*répartition, accueil dans une classe du même niveau, regroupement*).
"""
)

st.link_button(
    "🔗 Consulter le Genially – Plan de continuité pédagogique",
    GENIALLY_URL,
    use_container_width=True,
)

if os.path.exists(PROTOCOLE_CONTINUITE_PDF):
    with open(PROTOCOLE_CONTINUITE_PDF, "rb") as f:
        st.download_button(
            "📄 Télécharger le Protocole de continuité pédagogique (PDF)",
            data=f.read(),
            file_name=PROTOCOLE_CONTINUITE_PDF,
            mime="application/pdf",
            use_container_width=True,
        )
else:
    st.warning(f"Fichier introuvable : {PROTOCOLE_CONTINUITE_PDF}")

st.markdown(
    """
**EN CAS D’ABSENCE D’UN ENSEIGNANT :**  
Le directeur ou la directrice de l’école est invité(e) à utiliser cet outil afin de :

- suivre le protocole de continuité pédagogique pas à pas,
- identifier la durée de l’absence et le niveau d’incidence,
- sélectionner les compétences à travailler,
- générer les livrets d’exercices et les supports de communication adaptés.

Cet outil vise à faciliter la prise de décision collective et à garantir la continuité des apprentissages pour tous les élèves.
"""
)

st.divider()

# ----- Informations générales -----
st.subheader("Informations générales")

livret_num = st.text_input("Numéro de livret (reporté sur les PDF)", value="")
enseignant_absent = st.text_input("Enseignant absent", value="")

row1 = st.columns([2, 2, 3, 3])
with row1[0]:
    ecole = st.text_input("Nom de l'école", value="")
with row1[1]:
    try:
        classes_disponibles = load_class_list()
    except Exception as e:
        st.error(f"Erreur chargement classes depuis {EXCEL_PATH} : {e}")
        classes_disponibles = []
    classe = st.selectbox("Classe concernée", classes_disponibles)
with row1[2]:
    DISPOSITIFS = [
        "Répartition dans les autres classes",
        "Répartition dans une classe d'un même niveau",
        "Répartition dans une classe d'un même niveau + regroupement",
        "Co-intervention / renfort interne",
        "Continuité à distance",
    ]
    dispositif = st.multiselect("Dispositif choisi", options=DISPOSITIFS, default=[])
with row1[3]:
    duree_base = st.radio(
        "Durée de l'absence",
        options=["Inférieur ou égal à 5 jours", "Supérieur à 5 jours"],
        horizontal=False,
    )

# Dates + “fin indéterminée” => “À partir de”
st.markdown("#### Période")
dcol1, dcol2, dcol3 = st.columns([2, 2, 2])
with dcol1:
    fin_indet = st.checkbox("Fin d'absence indéterminée", value=False)
with dcol2:
    date_debut = st.date_input("Début", value=date.today())
with dcol3:
    if fin_indet:
        st.markdown("**Fin :** indéterminée")
        date_fin = None
    else:
        date_fin = st.date_input("Fin", value=date.today())

if fin_indet:
    periode_label = f"À partir du {date_debut}"
else:
    periode_label = f"Du {date_debut} au {date_fin}"

duree_label = duree_base

# ----- Niveau d'incidence : image AU DESSUS du choix + pas de mot "tension" -----
st.markdown("#### Niveau d'incidence")

inc_img = find_first_image_by_hints([h.lower() for h in INCIDENCES_HINTS])
if inc_img and os.path.exists(inc_img):
    st.image(inc_img, width=INCIDENCE_IMG_WIDTH_PX)

incidence = st.selectbox("Choisir un niveau", options=INCIDENCE_OPTIONS, index=0)
incidence_msg = message_selon_incidence(incidence)

st.caption("Suggestion (adaptée au niveau sélectionné) :")
st.info(incidence_msg)

st.divider()

# ----- Communication (modèle modifiable) -----
st.subheader("Communication (modèle modifiable)")

st.info(
    "Vous pouvez insérer un modèle et/ou ajouter la suggestion liée au niveau d’incidence. "
    "Vous pouvez aussi choisir d’inclure (ou non) ce texte dans la fiche récap."
)

comm_row = st.columns([2, 1, 2])
with comm_row[0]:
    chosen_template = st.selectbox("Choisir un modèle", options=list(COMM_TEMPLATES.keys()))
with comm_row[1]:
    if st.button("Insérer le modèle", use_container_width=True):
        st.session_state["communication_text"] = COMM_TEMPLATES[chosen_template]
with comm_row[2]:
    if st.button("Ajouter la suggestion (niveau d'incidence)", use_container_width=True):
        base = st.session_state.get("communication_text", "")
        if base.strip():
            st.session_state["communication_text"] = base.strip() + "\n\n" + incidence_msg
        else:
            st.session_state["communication_text"] = incidence_msg

include_comm_in_recap = st.checkbox("Inclure la communication dans la fiche récap", value=True)

if "communication_text" not in st.session_state:
    st.session_state["communication_text"] = COMM_TEMPLATES[list(COMM_TEMPLATES.keys())[0]]

communication = st.text_area(
    "Message aux familles / ENT",
    value=st.session_state["communication_text"],
    height=150,
)

st.session_state["communication_text"] = communication

st.divider()

# ----- Contenu du livret : domaines + sous-domaines + compétences (mix possible) -----
st.subheader("Contenu du livret (pour 2 jours sans remplacement)")

if not classe:
    st.warning("Sélectionne une classe.")
    st.stop()

try:
    df_comp = load_competences_for_class(classe)
except Exception as e:
    st.error(f"Erreur chargement compétences pour {classe} : {e}")
    st.stop()

# Domaines (multi)
domaines_dispo = sorted(df_comp["Domaine"].dropna().unique().tolist())
domaines_selected = st.multiselect(
    "1) Domaines (sélection multiple)",
    options=domaines_dispo,
    default=[],
)

df_dom = df_comp[df_comp["Domaine"].isin(domaines_selected)] if domaines_selected else df_comp.copy()

# Sous-domaines (multi) basés sur domaines sélectionnés
sous_dispo = sorted(df_dom["Sous domaine"].dropna().unique().tolist())
sous_selected = st.multiselect(
    "2) Sous-domaines (sélection multiple)",
    options=sous_dispo,
    default=[],
)

df_sous = df_dom[df_dom["Sous domaine"].isin(sous_selected)] if sous_selected else df_dom.copy()

# Compétences disponibles (avec contexte dom/sous)
df_sous = df_sous.dropna(subset=["Domaine", "Sous domaine", "Compétence"])
df_sous["__label__"] = (
    df_sous["Domaine"].astype(str)
    + " > "
    + df_sous["Sous domaine"].astype(str)
    + " > "
    + df_sous["Compétence"].astype(str)
)

labels = sorted(df_sous["__label__"].unique().tolist())

if duree_base == "Inférieur ou égal à 5 jours":
    chosen_label = st.selectbox("3) Compétence (1 seule pour ≤ 5 jours)", options=labels)
    selected_labels = [chosen_label] if chosen_label else []
else:
    selected_labels = st.multiselect("3) Compétences (sélection multiple)", options=labels, default=[])

# Transformer les labels en tuples (dom, sous, comp) et liste de comp seules pour chercher les PDFs
selected_triplets: list[tuple[str, str, str]] = []
selected_competences_only: list[str] = []
for lab in selected_labels:
    parts = [p.strip() for p in lab.split(">")]
    if len(parts) >= 3:
        dom, sous = parts[0], parts[1]
        comp = ">".join(parts[2:]).strip()
        selected_triplets.append((dom, sous, comp))
        selected_competences_only.append(comp)

# ----- Fiche récap (toujours affichée) -----
comm_for_recap = communication if include_comm_in_recap else None
recap_text = build_recap_text(
    livret_num=livret_num,
    ecole=ecole,
    classe=classe,
    enseignant_absent=enseignant_absent,
    dispositif=dispositif,
    duree_label=duree_label,
    periode_label=periode_label,
    competences=selected_triplets,
    communication=comm_for_recap,
)

st.subheader("Fiche récap (toujours affichée)")
st.text_area("Prévisualisation", recap_text, height=240)

st.divider()

# =========================
# TÉLÉCHARGEMENTS
# - Livret d’exercices = Fiche récap + PDFs exercices
# - Livret de corrections = Fiche récap + PDFs corrections
# - Pas de PDF "page infos" en trop
# =========================

st.subheader("Téléchargements")
st.caption("💡 Conseil : téléchargez directement le livret d’exercices ET le livret de corrections pour tout avoir au même moment.")

if not selected_competences_only:
    st.info("Sélectionne au moins une compétence pour générer les livrets.")
    st.stop()

# PDF récap (utilisé comme 1ère partie du livret)
recap_pdf = build_text_pdf(
    title="Fiche récapitulative — Plan de continuité pédagogique",
    body_text=recap_text,
    subtitle=f"N° de livret : {livret_num}" if livret_num else None,
)

# Collecte PDFs exercices + corrections (bibliothèque ou fallback)
exercices_pdfs = []
corrections_pdfs = []
diag_ex = []
diag_corr = []

for cpt in selected_competences_only:
    ex_bytes, ex_name = read_pdf_by_competence(PDF_COMPETENCES_DIR, cpt)
    if ex_bytes is None:
        ex_bytes = build_text_pdf(
            title="Exercices (fallback)",
            body_text="Aucun PDF d'exercices n’a été trouvé dans la bibliothèque.\n\nCompétence : " + cpt,
            subtitle=f"N° de livret : {livret_num}" if livret_num else None,
        )
        diag_ex.append((cpt, None))
    else:
        diag_ex.append((cpt, ex_name))
    exercices_pdfs.append(ex_bytes)

    corr_bytes, corr_name = read_pdf_by_competence(PDF_CORRECTION_DIR, cpt)
    if corr_bytes is None:
        corr_bytes = build_text_pdf(
            title="Corrections (fallback)",
            body_text="Aucun PDF de corrections n’a été trouvé dans la bibliothèque.\n\nCompétence : " + cpt,
            subtitle=f"N° de livret : {livret_num}" if livret_num else None,
        )
        diag_corr.append((cpt, None))
    else:
        diag_corr.append((cpt, corr_name))
    corrections_pdfs.append(corr_bytes)

# Fusion : RÉCAP + compétences
# --- Illustration déterminée par numéro de livret ---
illus = list_illustrations()
chosen_illustration = pick_illustration_for_livret(illus, livret_num, fallback_seed=classe)

if chosen_illustration:
    if chosen_illustration.lower().endswith(".pdf"):
        # Si c'est déjà un PDF, on l'intègre directement
        with open(chosen_illustration, "rb") as f:
            illus_pdf = f.read()
    else:
        # Sinon c'est une image → on génère une page PDF
        illus_pdf = build_illustration_pdf(chosen_illustration)
else:
    illus_pdf = build_text_pdf(
        "Illustration",
        "Aucune illustration trouvée."
    )

# Ordre final : Fiche récap -> Illustration -> Exercices / Corrections
livret_exercices = merge_pdfs([recap_pdf, illus_pdf] + exercices_pdfs)
livret_corrections = merge_pdfs([recap_pdf, illus_pdf] + corrections_pdfs)

dl1, dl2 = st.columns(2)
with dl1:
    st.download_button(
        "📘 Télécharger le livret d’exercices (PDF)",
        data=livret_exercices,
        file_name=f"livret_exercices_{slugify_filename(classe)}_{slugify_filename(livret_num) if livret_num else 'livret'}.pdf",
        mime="application/pdf",
        use_container_width=True,
        help="Recommandé : télécharge aussi le livret de corrections."
    )
with dl2:
    st.download_button(
        "📕 Télécharger le livret de corrections (PDF)",
        data=livret_corrections,
        file_name=f"livret_corrections_{slugify_filename(classe)}_{slugify_filename(livret_num) if livret_num else 'livret'}.pdf",
        mime="application/pdf",
        use_container_width=True,
        help="Recommandé : télécharge aussi le livret d’exercices."
    )

with st.expander("Diagnostic (PDF trouvés dans les bibliothèques)"):
    st.markdown("### Exercices")
    for cpt, name in diag_ex:
        if name:
            st.success(f"✅ {cpt} → {name}")
        else:
            st.warning(f"⚠️ {cpt} → introuvable (fallback généré)")
    st.markdown("### Corrections")
    for cpt, name in diag_corr:
        if name:
            st.success(f"✅ {cpt} → {name}")
        else:
            st.warning(f"⚠️ {cpt} → introuvable (fallback généré)")
