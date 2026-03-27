# app.py — Plan de continuité pédagogique
# Dépendances (requirements.txt) :
# streamlit
# pandas
# openpyxl
# reportlab
# pypdf

import os
import re
import glob
import difflib
import unicodedata
import textwrap
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

BASE_DIR = Path(__file__).resolve().parent

EXCEL_PATH = BASE_DIR / "PCP.xlsx"
LOGO_PATH = BASE_DIR / "logo_academie_versailles.png"

PROTOCOLE_CONTINUITE_PDF = BASE_DIR / "Protocole de continuité pédagogique.pdf"

PDF_COMPETENCES_DIR = BASE_DIR / "pdf_competences"
PDF_CORRECTION_DIR = BASE_DIR / "pdf_correction"
ILLUSTRATIONS_DIR = BASE_DIR / "illustrations"
SLIDES_DIR = BASE_DIR / "slides"

GENIALLY_URL = "https://view.genially.com/693ad2fee4adee9eefd9d637/interactive-content-plan-de-continuite-pedagogique"

SLIDE_WIDTH_PX = 900
LOGO_WIDTH_PX = 160

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
    PDF_COMPETENCES_DIR.mkdir(parents=True, exist_ok=True)
    PDF_CORRECTION_DIR.mkdir(parents=True, exist_ok=True)
    ILLUSTRATIONS_DIR.mkdir(parents=True, exist_ok=True)
    SLIDES_DIR.mkdir(parents=True, exist_ok=True)


def slugify_filename(value: str) -> str:
    value = str(value)
    value = unicodedata.normalize("NFKD", value).encode("ascii", "ignore").decode("ascii")
    value = re.sub(r"[^\w\s-]", "", value).strip().lower()
    value = re.sub(r"[\s-]+", "_", value)
    return value


def normalize_for_match(s: str) -> str:
    s = str(s or "")
    s = unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode("ascii")
    s = s.lower()
    s = re.sub(r"[\(\)\[\]\{\}]", " ", s)
    s = re.sub(r"[^\w\s]", " ", s)
    s = re.sub(r"\s+", " ", s).strip()
    return s


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
    if not LOGO_PATH.exists():
        return
    try:
        logo = ImageReader(str(LOGO_PATH))
        logo_w = 90
        logo_h = 60
        x = PAGE_WIDTH - RIGHT_MARGIN - logo_w
        y = PAGE_HEIGHT - TOP_MARGIN - logo_h + 20
        c.drawImage(logo, x, y, width=logo_w, height=logo_h, mask="auto")
    except Exception:
        pass


def build_text_pdf(title: str, body_text: str, subtitle: str | None = None) -> bytes:
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
    writer = PdfWriter()
    for pdf_bytes in pdf_bytes_list:
        reader = PdfReader(BytesIO(pdf_bytes))
        for page in reader.pages:
            writer.add_page(page)
    out = BytesIO()
    writer.write(out)
    return out.getvalue()


def natural_key(name: str):
    parts = re.split(r"(\d+)", name.lower())
    key = []
    for p in parts:
        key.append(int(p) if p.isdigit() else p)
    return key


def build_slides_list() -> list[str]:
    exts = (".png", ".jpg", ".jpeg", ".webp")
    slides = []

    if SLIDES_DIR.exists():
        slides = [
            str(p) for p in SLIDES_DIR.iterdir()
            if p.is_file() and p.suffix.lower() in exts
        ]
        slides.sort(key=lambda p: natural_key(Path(p).name))
        if slides:
            return slides

    root_candidates = [
        str(p) for p in BASE_DIR.iterdir()
        if p.is_file() and p.suffix.lower() in exts and "slide" in p.stem.lower()
    ]
    root_candidates.sort(key=lambda p: natural_key(Path(p).name))
    return root_candidates


def build_pdf_index(directory: Path) -> dict:
    if not directory.exists():
        return {}
    idx = {}
    for fn in directory.iterdir():
        if fn.is_file() and fn.suffix.lower() == ".pdf":
            idx[slugify_filename(fn.stem)] = fn.name
    return idx


def read_pdf_by_competence(directory: Path, competence: str) -> tuple[bytes | None, str | None]:
    if not competence or not directory.exists():
        return None, None

    target = normalize_for_match(competence)
    pdf_files = [p for p in directory.iterdir() if p.is_file() and p.suffix.lower() == ".pdf"]
    if not pdf_files:
        return None, None

    candidates = []
    for p in pdf_files:
        norm = normalize_for_match(p.stem)
        candidates.append((p, norm))

    for p, norm in candidates:
        if norm == target:
            return p.read_bytes(), p.name

    contains_hits = []
    for p, norm in candidates:
        if target in norm or norm in target:
            score = difflib.SequenceMatcher(None, target, norm).ratio()
            contains_hits.append((score, p))

    if contains_hits:
        contains_hits.sort(reverse=True, key=lambda x: x[0])
        best = contains_hits[0][1]
        return best.read_bytes(), best.name

    scored = []
    for p, norm in candidates:
        score = difflib.SequenceMatcher(None, target, norm).ratio()
        scored.append((score, p))
    scored.sort(reverse=True, key=lambda x: x[0])

    best_score, best = scored[0]
    if best_score >= 0.62:
        return best.read_bytes(), best.name

    return None, None


def list_illustrations() -> list[str]:
    exts = (".png", ".jpg", ".jpeg", ".webp", ".pdf")
    if not ILLUSTRATIONS_DIR.exists():
        return []
    files = []
    for fn in ILLUSTRATIONS_DIR.iterdir():
        if fn.is_file() and fn.suffix.lower() in exts:
            files.append(str(fn))
    files.sort(key=lambda p: natural_key(Path(p).name))
    return files


def pick_illustration_for_livret_number(illustrations: list[str], livret_num: str) -> str | None:
    if not livret_num:
        return None

    key = str(livret_num).strip()
    for path in illustrations:
        base = Path(path)
        if base.stem.strip() == key:
            return path
    return None


def build_illustration_pdf(image_path: str) -> bytes:
    buffer = BytesIO()
    c = canvas.Canvas(buffer, pagesize=A4)

    try:
        img = ImageReader(image_path)
        iw, ih = img.getSize()

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


def render_comm_template(template: str, date_debut_value, dispositif: list[str]) -> str:
    disp = ", ".join(dispositif).strip() if dispositif else "classe de rattachement"
    dt = date_debut_value.strftime("%d/%m/%Y") if date_debut_value else ""
    return template.format(date_debut=dt, dispositif=disp)


def make_unique_labels(df: pd.DataFrame) -> tuple[list[str], dict]:
    counts = {}
    labels = []
    mapping = {}

    for _, row in df.iterrows():
        competence = str(row["Compétence"]).strip()
        domaine = str(row["Domaine"]).strip()
        sous = str(row["Sous domaine"]).strip()

        counts[competence] = counts.get(competence, 0) + 1
        display = competence if counts[competence] == 1 else f"{competence} ({counts[competence]})"

        labels.append(display)
        mapping[display] = (domaine, sous, competence)

    return labels, mapping


def badge(text: str, color: str):
    st.markdown(
        f"<span style='display:inline-block;padding:6px 10px;margin:4px;"
        f"border-radius:12px;background:{color};color:white;font-size:12px;'>"
        f"{text}</span>",
        unsafe_allow_html=True,
    )


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
# COMMUNICATION
# =========================

DEFAULT_COMM_TEMPLATE = (
    "Madame, Monsieur,\n\n"
    "Afin d’accompagner au mieux votre enfant en l’absence de son enseignant, la circonscription va déployer "
    "un protocole pour garantir la continuité pédagogique des apprentissages.\n\n"
    "Celui-ci sera proposé dès le {date_debut} sous la forme d’un plan de travail comprenant des activités "
    "adaptées et progressives en lien avec les programmes officiels.\n\n"
    "Ce plan prendra la forme d’un fichier individuel que votre enfant pourra compléter en {dispositif}.\n\n"
    "L’équipe enseignante supervisera la bonne mise en œuvre de ce protocole et reste à votre disposition "
    "pour toute question éventuelle.\n\n"
    "Cordialement,"
)


# =========================
# RÉCAP
# =========================

def build_recap_text(
    livret_num: str,
    ecole: str,
    classe: str,
    enseignant_absent: str,
    dispositif: list[str],
    periode_label: str,
    competences: list[tuple[str, str, str]],
    communication: str | None,
) -> str:
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
    lines.append(f"Période : {periode_label}")
    lines.append("")
    lines.append("CONTENU DU LIVRET:")
    if competences:
        for dom, sous, comp in competences:
            lines.append(f"• {comp}")
    else:
        lines.append("• (Aucune compétence sélectionnée)")
    if communication:
        lines.append("")
        lines.append("MESSAGE AUX FAMILLES :")
        lines.append(communication)
    lines.append("")
    return "\n".join(lines)


# =========================
# COULEURS DOMAINES
# =========================

DOMAIN_COLORS = {
    "Mathématiques": "#2E86C1",
    "Français": "#C0392B",
    "Lecture et compréhension de l'écrit": "#AF601A",
    "Langage oral": "#8E44AD",
    "Questionner le monde": "#27AE60",
    "Enseignement moral et civique": "#7D6608",
    "Arts plastiques": "#E67E22",
    "Éducation musicale": "#16A085",
    "EPS": "#D35400",
    "Anglais": "#6C3483",
    "(Sans domaine)": "#7F8C8D",
}


# =========================
# UI
# =========================

st.set_page_config(page_title="Plan de continuité pédagogique", layout="wide")
ensure_dirs()

# ----- Bannière : logo à gauche, taille réduite -----
if LOGO_PATH.exists():
    col_logo, _ = st.columns([3, 1])
    with col_logo:
        st.image(str(LOGO_PATH), width=500)
else:
    st.warning(f"Logo introuvable : {LOGO_PATH.name}")

# ----- Diaporama -----
slides = build_slides_list()
if "slide_idx" not in st.session_state:
    st.session_state.slide_idx = 0

if slides:
    nav_l, nav_c, nav_r = st.columns([1, 4, 1], vertical_alignment="center")

    with nav_l:
        if st.button("◀", use_container_width=True):
            st.session_state.slide_idx = (st.session_state.slide_idx - 1) % len(slides)

    with nav_c:
        col_slide = st.columns([1, 3, 1])[1]
        with col_slide:
            st.image(slides[st.session_state.slide_idx], width=650)

    with nav_r:
        if st.button("▶", use_container_width=True):
            st.session_state.slide_idx = (st.session_state.slide_idx + 1) % len(slides)
else:
    st.info("Aucune slide détectée. Ajoute tes PNG dans le dossier 'slides/'.")

# ----- Planification -----
st.divider()
st.header("Planification")

st.markdown(
    """
**POUR LA RENTRÉE :**

**1.** Consulter le support interactif du plan de continuité pédagogique.  
**2.** Opérer les choix de mise en œuvre du PCP.  
**3.** Formaliser les choix dans la fiche PCP.
"""
)

plan_col1, plan_col2 = st.columns(2)
with plan_col1:
    st.link_button(
        "1️⃣ Consulter le support interactif",
        GENIALLY_URL,
        use_container_width=True,
    )
with plan_col2:
    if PROTOCOLE_CONTINUITE_PDF.exists():
        st.download_button(
            "3️⃣ Télécharger la fiche PCP (PDF)",
            data=PROTOCOLE_CONTINUITE_PDF.read_bytes(),
            file_name=PROTOCOLE_CONTINUITE_PDF.name,
            mime="application/pdf",
            use_container_width=True,
        )
    else:
        st.warning(f"Fichier introuvable : {PROTOCOLE_CONTINUITE_PDF.name}")

st.markdown(
    """
**EN CAS D’ABSENCE D’UN ENSEIGNANT :**  
Le directeur ou la directrice de l’école est invité(e) à utiliser cet outil afin de :

- suivre le protocole de continuité pédagogique pas à pas,
- identifier la date de début et la date de fin de l’absence,
- sélectionner les compétences à travailler,
- générer les livrets d’exercices et les supports de communication adaptés.
"""
)

st.divider()

# ----- Activation et mise en œuvre -----
st.header("Activation et mise en œuvre")
st.subheader("Informations générales")

rgpd_col1, rgpd_col2 = st.columns([3, 1])
with rgpd_col1:
    st.markdown(
        "🔒 **Important — Protection des données :** "
        "Les informations renseignées dans cet outil ne sont pas conservées en ligne."
    )

livret_num = st.text_input("Numéro de livret (reporté sur les PDF)", value="")
enseignant_absent = st.text_input("Enseignant absent", value="")

row1 = st.columns([2, 2, 3, 3])
with row1[0]:
    ecole = st.text_input("Nom de l'école", value="")
with row1[1]:
    try:
        classes_disponibles = load_class_list()
    except Exception as e:
        st.error(f"Erreur chargement classes depuis {EXCEL_PATH.name} : {e}")
        classes_disponibles = []
    classe = st.selectbox("Classe concernée", classes_disponibles)
with row1[2]:
    DISPOSITIFS = [
        "Répartition dans les autres classes",
        "Répartition dans une classe d'un même niveau",
        "Répartition dans une classe d'un même niveau + regroupement",
        "Co-intervention / renfort interne",
    ]
    dispositif = st.multiselect("Dispositif choisi", options=DISPOSITIFS, default=[])
with row1[3]:
    st.markdown("##### Période")
    fin_indet = st.checkbox("Fin d'absence indéterminée", value=False)
    date_debut = st.date_input("Date de début", value=date.today())
    if fin_indet:
        st.markdown("**Date de fin :** indéterminée")
        date_fin = None
    else:
        date_fin = st.date_input("Date de fin", value=date.today())

if fin_indet:
    periode_label = f"À partir du {date_debut.strftime('%d/%m/%Y')}"
else:
    periode_label = f"Du {date_debut.strftime('%d/%m/%Y')} au {date_fin.strftime('%d/%m/%Y')}"

st.divider()

# ----- Communication -----
st.subheader("Communication (modèle modifiable)")
st.info(
    "Le message ci-dessous est proposé automatiquement. "
    "Vous pouvez le modifier si nécessaire."
)


if "communication_text" not in st.session_state:
    st.session_state.communication_text = render_comm_template(DEFAULT_COMM_TEMPLATE, date_debut, dispositif)
if "last_comm_seed" not in st.session_state:
    st.session_state.last_comm_seed = None

current_seed = (date_debut.strftime("%d/%m/%Y"), tuple(dispositif))
if st.session_state.last_comm_seed != current_seed:
    st.session_state.communication_text = render_comm_template(DEFAULT_COMM_TEMPLATE, date_debut, dispositif)
    st.session_state.last_comm_seed = current_seed

include_comm_in_recap = st.checkbox("Inclure la communication dans la fiche récapitulative", value=True)

communication = st.text_area(
    "Message aux familles (Dans le cahier de liaison et sur l'ENT)",
    value=st.session_state.communication_text,
    height=220,
)

st.session_state.communication_text = communication

st.divider()

# ----- Contenu du livret -----
st.subheader("Contenu du livret")

st.info(
    "Afin d’identifier les compétences travaillées durant la période précédant l’absence, "
    "vous pouvez vous aider du cahier journal de la classe, des programmations et des guides du maître utilisés par l’enseignant."
)

if not classe:
    st.warning("Sélectionne une classe.")
    st.stop()

try:
    df_comp = load_competences_for_class(classe).copy()
except Exception as e:
    st.error(f"Erreur chargement compétences pour {classe} : {e}")
    st.stop()

df_comp = df_comp.dropna(subset=["Domaine", "Sous domaine", "Compétence"]).copy()
df_comp["Domaine"] = df_comp["Domaine"].astype(str).str.strip()
df_comp["Sous domaine"] = df_comp["Sous domaine"].astype(str).str.strip()
df_comp["Compétence"] = df_comp["Compétence"].astype(str).str.strip()

# Domaines
domaines_dispo = sorted(df_comp["Domaine"].dropna().unique().tolist())
domaines_selected = st.multiselect(
    "1) Domaine(s)",
    options=domaines_dispo,
    default=[],
)

df_dom = df_comp[df_comp["Domaine"].isin(domaines_selected)].copy()

if domaines_selected:
    st.markdown("**Domaines sélectionnés :**")
    for dom in domaines_selected:
        badge(dom, DOMAIN_COLORS.get(dom, "#34495E"))

# Sous-domaines
sous_dispo = sorted(df_dom["Sous domaine"].dropna().unique().tolist())
sous_selected = st.multiselect(
    "2) Sous-domaine(s)",
    options=sous_dispo,
    default=[],
)

df_sous = df_dom[df_dom["Sous domaine"].isin(sous_selected)].copy()

if sous_selected:
    st.markdown("**Sous-domaines sélectionnés :**")
    for sous in sous_selected:
        domaine_ref = None
        try:
            domaine_ref = df_dom[df_dom["Sous domaine"] == sous]["Domaine"].iloc[0]
        except Exception:
            domaine_ref = "(Sans domaine)"
        badge(sous, DOMAIN_COLORS.get(domaine_ref, "#34495E"))

# Compétences : affichage réduit à la compétence seule
labels, label_to_triplet = make_unique_labels(df_sous)

selected_labels = st.multiselect(
    "3) Compétence(s)",
    options=labels,
    default=[],
)

selected_triplets: list[tuple[str, str, str]] = []
selected_competences_only: list[str] = []

for lab in selected_labels:
    dom, sous, comp = label_to_triplet[lab]
    selected_triplets.append((dom, sous, comp))
    selected_competences_only.append(comp)

if selected_triplets:
    st.markdown("**Compétences sélectionnées :**")
    for dom, sous, comp in selected_triplets:
        badge(comp, DOMAIN_COLORS.get(dom, "#34495E"))

# ----- Fiche récapitulative -----
comm_for_recap = communication if include_comm_in_recap else None
recap_text = build_recap_text(
    livret_num=livret_num,
    ecole=ecole,
    classe=classe,
    enseignant_absent=enseignant_absent,
    dispositif=dispositif,
    periode_label=periode_label,
    competences=selected_triplets,
    communication=comm_for_recap,
)

st.title("Fiche récapitulative")
st.text_area("Prévisualisation", recap_text, height=240)

st.divider()

# =========================
# TÉLÉCHARGEMENTS
# =========================

st.subheader("Téléchargements")
st.markdown(
    "**💡 Conseil : téléchargez directement le livret d’exercices et le livret de corrections pour tout avoir au même endroit.**"
)

if not selected_competences_only:
    st.info("Sélectionne au moins une compétence pour générer les livrets.")
    st.stop()

recap_pdf = build_text_pdf(
    title="Fiche récapitulative — Plan de continuité pédagogique",
    body_text=recap_text,
    subtitle=f"N° de livret : {livret_num}" if livret_num else None,
)

illus = list_illustrations()
chosen_illustration = pick_illustration_for_livret_number(illus, livret_num)

illus_pdf = None
if chosen_illustration:
    if chosen_illustration.lower().endswith(".pdf"):
        illus_pdf = Path(chosen_illustration).read_bytes()
    else:
        illus_pdf = build_illustration_pdf(chosen_illustration)

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

parts_ex = [recap_pdf]
parts_corr = [recap_pdf]
if illus_pdf is not None:
    parts_ex.append(illus_pdf)
    parts_corr.append(illus_pdf)
parts_ex.extend(exercices_pdfs)
parts_corr.extend(corrections_pdfs)

livret_exercices = merge_pdfs(parts_ex)
livret_corrections = merge_pdfs(parts_corr)

dl1, dl2 = st.columns(2)

with dl1:
    st.download_button(
        "📘 Télécharger le livret d’exercices (PDF)",
        data=livret_exercices,
        file_name=f"livret_exercices_{slugify_filename(classe)}_{slugify_filename(livret_num) if livret_num else 'livret'}.pdf",
        mime="application/pdf",
        use_container_width=True,
        help="Recommandé : télécharge aussi le livret de corrections.",
    )
with dl2:
    st.download_button(
        "📕 Télécharger le livret de corrections (PDF)",
        data=livret_corrections,
        file_name=f"livret_corrections_{slugify_filename(classe)}_{slugify_filename(livret_num) if livret_num else 'livret'}.pdf",
        mime="application/pdf",
        use_container_width=True,
        help="Recommandé : télécharge aussi le livret d’exercices.",
    )

with st.expander("Diagnostic (PDF trouvés dans les bibliothèques)"):
    if chosen_illustration:
        st.success(f"Illustration utilisée : {Path(chosen_illustration).name}")
    else:
        st.info("Aucune illustration trouvée pour ce numéro de livret.")
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
