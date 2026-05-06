import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go

from src.ingestion import charger_fichier
from src.kpis import (
    kpi_generaux, revenu_par_lob, revenu_par_segment,
    revenu_par_canal, tendance_mensuelle, top_clients,
)
from src.flags import (
    flag_marge_negative, flag_cogs_zero, flag_doublons,
    flag_concentration_client, flag_marge_decroissante, resume_flags,
)
from src.export import exporter_flags_excel
import re as _re
from src.multi_year import (
    nb_mois_fichier, kpi_annee,
    yoy_par_lob, yoy_par_segment, evolution_clients,
    analyse_frais_passage, analyse_expor,
)

# ── DETECTER_ANNEE ────────────────────────────────────────────────────────────
def detecter_annee(nom_fichier: str) -> str:
    nom = nom_fichier.upper()

    # Pattern Sage X3 JJMMAA : apres "AU" → ex: au_311225 → 2025
    m = _re.search(r"AU[\s_](\d{2})(\d{2})(\d{2})", nom)
    if m:
        yr = int(m.group(3))
        return str(2000 + yr)

    # Blocs de 6 chiffres avec separateurs → JJMMAA, prendre le dernier
    blocs = _re.findall(r"(?:^|[\s_\-])(\d{6})(?:[\s_\-]|$)", nom)
    if blocs:
        yr = int(blocs[-1][4:6])
        return str(2000 + yr)

    # N importe quel bloc de 6 chiffres → JJMMAA
    blocs6 = _re.findall(r"\d{6}", nom)
    if blocs6:
        yr = int(blocs6[-1][4:6])
        if 0 <= yr <= 99:
            return str(2000 + yr)

    # Annee 4 chiffres explicite
    for tok in _re.findall(r"\d{4}", nom):
        if 2000 <= int(tok) <= 2099:
            return tok

    return "Inconnu"


st.set_page_config(page_title="Audit Analytics", page_icon="📊", layout="wide")

RED, BLACK, GRAY, LGRAY, MGRAY = "#C8102E", "#1A1A1A", "#F7F7F7", "#EEEEEE", "#888888"
COLORS = ["#1A1A1A", "#C8102E", "#AAAAAA", "#E8E8E8"]

# ── CSS ──────────────────────────────────────────────
st.markdown(f"""<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800&display=swap');
html,body,[class*="css"]{{font-family:'Inter',sans-serif!important;background:#F7F7F7!important;}}
.block-container{{padding:0 1.5rem 2rem 1.5rem!important;max-width:100%!important;}}

[data-testid="stSidebar"]{{background:white!important;border-right:1px solid {LGRAY}!important;overflow-y:auto!important;height:100vh!important;}}
[data-testid="stSidebar"] > div:first-child{{overflow-y:auto!important;height:100vh!important;padding-bottom:20px;}}
[data-testid="stSidebar"] *{{color:{BLACK}!important;}}
[data-testid="stSidebar"] [data-testid="stFileUploaderDropzone"]{{background:{GRAY}!important;border:1.5px dashed #ccc!important;border-radius:8px!important;}}
[data-testid="stSidebar"] [data-testid="stFileUploaderDropzone"]:hover{{border-color:{RED}!important;background:#fff5f6!important;}}
[data-testid="stSidebar"] button[data-testid="baseButton-secondary"]{{background:{RED}!important;color:white!important;border:none!important;border-radius:6px!important;font-weight:600!important;font-size:11px!important;width:100%!important;}}
[data-testid="stSidebar"] .stRadio>div{{gap:1px!important;}}
[data-testid="stSidebar"] .stRadio label{{padding:7px 12px!important;border-radius:6px!important;font-size:12px!important;color:{MGRAY}!important;font-weight:500!important;margin:1px 6px!important;cursor:pointer;}}
[data-testid="stSidebar"] .stRadio label:has(input:checked){{background:#fff0f2!important;color:{RED}!important;font-weight:700!important;border-left:2px solid {RED}!important;}}
[data-testid="stSidebar"] .stRadio label:hover{{background:{GRAY}!important;color:{BLACK}!important;}}
[data-testid="stSidebar"] .stCaption{{color:#bbb!important;font-size:10px!important;padding:0 12px!important;}}
[data-testid="stSidebar"] hr{{border-color:{LGRAY}!important;margin:8px 0!important;}}

div[data-testid="stSidebar"] div[data-baseweb="radio"] label {{font-size:11px!important;padding:5px 12px 5px 28px!important;border-radius:5px!important;color:#aaa!important;}}
div[data-testid="stSidebar"] div[data-baseweb="radio"] label:has(input:checked) {{color:{RED}!important;font-weight:700!important;background:#fff0f2!important;border-left:2px solid {RED}!important;}}

.topbar{{background:white;border-bottom:1px solid {LGRAY};padding:10px 0;display:flex;align-items:center;gap:12px;margin:0 -1.5rem 1.5rem;padding-left:1.5rem;padding-right:1.5rem;}}
.topbar-logo{{height:28px;width:auto;}}
.topbar-sep{{width:1px;height:20px;background:{LGRAY};}}
.topbar-title{{font-size:16px;font-weight:700;color:{BLACK};}}
.topbar-pill{{margin-left:auto;background:{GRAY};color:{MGRAY};border:1px solid {LGRAY};padding:3px 10px;border-radius:20px;font-size:10px;font-weight:500;}}

.kpi-grid{{display:grid;grid-template-columns:repeat(4,1fr);gap:12px;margin-bottom:16px;}}
.kpi-grid-3{{display:grid;grid-template-columns:repeat(3,1fr);gap:12px;margin-bottom:16px;}}
.kpi-card{{background:white;border:1px solid {LGRAY};border-radius:10px;padding:14px 16px;}}
.kpi-label{{font-size:10px;color:{MGRAY};font-weight:600;text-transform:uppercase;letter-spacing:0.4px;margin-bottom:5px;}}
.kpi-val{{font-size:24px;font-weight:700;color:{BLACK};line-height:1.1;}}
.kpi-val-red{{font-size:24px;font-weight:700;color:{RED};line-height:1.1;}}
.kpi-val-green{{font-size:24px;font-weight:700;color:#198754;line-height:1.1;}}
.kpi-sub{{font-size:10px;color:#bbb;margin-top:3px;}}
.kpi-bar-track{{height:3px;background:{LGRAY};border-radius:2px;margin-top:8px;}}
.kpi-bar-fill{{height:3px;border-radius:2px;}}
.badge-sm{{display:inline-block;padding:2px 7px;border-radius:20px;font-size:10px;font-weight:600;margin-top:4px;}}
.badge-red{{background:#fff0f2;color:{RED};}}
.badge-orange{{background:#fff8f0;color:#fd7e14;}}
.badge-green{{background:#f0faf4;color:#198754;}}
.badge-gray{{background:{GRAY};color:{MGRAY};}}

.chart-card{{background:white;border:1px solid {LGRAY};border-radius:10px;padding:14px 16px;margin-bottom:12px;}}
.chart-title{{font-size:12px;font-weight:600;color:{BLACK};margin-bottom:12px;}}
.chart-sub{{font-size:10px;color:{MGRAY};margin-top:-8px;margin-bottom:10px;}}
.table-card{{background:white;border:1px solid {LGRAY};border-radius:10px;padding:14px 16px;margin-bottom:12px;}}

.flag-grid{{display:grid;grid-template-columns:repeat(4,1fr);gap:12px;margin-bottom:16px;}}
.flag-card{{background:white;border:1px solid {LGRAY};border-radius:10px;padding:12px 14px;display:flex;align-items:center;gap:10px;}}
.flag-icon{{width:32px;height:32px;border-radius:8px;display:flex;align-items:center;justify-content:center;font-size:14px;flex-shrink:0;}}
.fi-red{{background:#fff0f2;}}.fi-orange{{background:#fff8f0;}}
.flag-count{{font-size:20px;font-weight:700;color:{BLACK};line-height:1;}}
.flag-name{{font-size:10px;color:{MGRAY};margin-top:2px;}}

.section-title{{font-size:13px;font-weight:700;color:{BLACK};margin-bottom:12px;padding-bottom:6px;border-bottom:1px solid {LGRAY};}}

[data-testid="stExpander"]{{background:white!important;border:1px solid {LGRAY}!important;border-radius:10px!important;margin-bottom:8px;}}
[data-testid="stExpander"] summary{{font-size:12px!important;font-weight:600!important;padding:10px 14px!important;color:{BLACK}!important;}}
.stDownloadButton button{{background:{RED}!important;color:white!important;border:none!important;border-radius:6px!important;font-weight:600!important;font-size:12px!important;}}
hr{{border-color:{LGRAY}!important;}}
div[data-testid="metric-container"]{{display:none!important;}}
[data-testid="stDataFrame"]{{border:1px solid {LGRAY};border-radius:8px;overflow:hidden;}}
.stSuccess,.stError,.stWarning,.stInfo{{border-radius:8px!important;}}
</style>""", unsafe_allow_html=True)


# ── HELPERS ──────────────────────────────────────────
def fmt(val):
    if pd.isna(val): return "—"
    try:
        if abs(val) >= 1e9: return f"{val/1e9:,.1f} Mrd"
        if abs(val) >= 1e6: return f"{val/1e6:,.1f} M"
        return f"{val:,.0f}"
    except: return str(val)

def plotly_white(fig, height=240, legend=False):
    fig.update_layout(
        height=height, margin=dict(t=10,b=10,l=10,r=10),
        paper_bgcolor="white", plot_bgcolor="white",
        font=dict(family="Inter", color=BLACK, size=11),
        xaxis=dict(gridcolor=LGRAY, linecolor=LGRAY, tickfont=dict(color=MGRAY,size=10), title=""),
        yaxis=dict(gridcolor=LGRAY, linecolor=LGRAY, tickfont=dict(color=MGRAY,size=10), title=""),
        showlegend=legend,
        legend=dict(font=dict(size=10), bgcolor="white", bordercolor=LGRAY, borderwidth=1, orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
    )
    return fig

def color_marge_cell(val):
    try:
        v = float(val)
        if v < 0: return f"color:{RED};font-weight:700"
        elif v < 5: return "color:#fd7e14;font-weight:600"
        return "color:#198754;font-weight:600"
    except: return ""

def kpi_card_html(label, val, sub="", color=BLACK, bar_color=RED, bar_pct=100):
    return f"""<div class="kpi-card">
      <div class="kpi-label">{label}</div>
      <div style="font-size:24px;font-weight:700;color:{color};line-height:1.1;">{val}</div>
      {'<div class="kpi-sub">'+sub+'</div>' if sub else ''}
      <div class="kpi-bar-track"><div class="kpi-bar-fill" style="width:{min(bar_pct,100):.0f}%;background:{bar_color};"></div></div>
    </div>"""


# ── LOGO SVG (Logo D) ────────────────────────────────
LOGO_SVG = (
    '<svg width="210" height="64" viewBox="0 0 210 64" xmlns="http://www.w3.org/2000/svg">'
    '<circle cx="32" cy="32" r="30" fill="#1A1A1A"/>'
    '<polyline points="14,43 20,28 28,36 36,18 46,24" fill="none" stroke="#C8102E" '
    'stroke-width="3" stroke-linecap="round" stroke-linejoin="round"/>'
    '<circle cx="46" cy="24" r="4" fill="#C8102E"/>'
    '<text x="74" y="26" font-family="Inter,sans-serif" font-size="17" font-weight="700" fill="#1A1A1A">Audit Analytics</text>'
    '<rect x="74" y="32" width="36" height="2" rx="1" fill="#C8102E"/>'
    '<text x="74" y="50" font-family="Inter,sans-serif" font-size="11" font-weight="400" fill="#888888">Financial Intelligence</text>'
    '</svg>'
)

# ── SIDEBAR ──────────────────────────────────────────
with st.sidebar:
    # Logo D
    st.markdown(
        '<div style="padding:16px 14px 14px;border-bottom:1px solid ' + LGRAY + ';margin-bottom:12px;">'
        + LOGO_SVG +
        '</div>',
        unsafe_allow_html=True,
    )

    fichiers = st.file_uploader(
        "Fichiers de reporting",
        type=["xlsx", "xls", "csv"],
        accept_multiple_files=True,
        help="Chargez un ou plusieurs fichiers pour démarrer l'analyse",
    )

    if fichiers:
        for f in fichiers:
            annee = detecter_annee(f.name)
            st.caption(f"✓ {annee} — {f.name[:24]}…")

    # Navigation visible uniquement quand des fichiers sont chargés
    nb_fichiers = len(fichiers) if fichiers else 0
    if nb_fichiers > 0:
        st.markdown("<hr>", unsafe_allow_html=True)
        st.markdown(
            '<div style="font-size:9px;font-weight:700;color:#bbb;letter-spacing:1.5px;'
            'text-transform:uppercase;padding:4px 12px 4px;">Navigation</div>',
            unsafe_allow_html=True,
        )
        pages_base  = ["Dashboard", "Analyse clients", "Flags de risque"]
        pages_multi = ["Comparaison YoY", "Analyse volume", "Canal EXPOR", "Évolution clients", "Frais de Passage"]
        pages_dispo = pages_base + (pages_multi if nb_fichiers >= 2 else [])
        page = st.radio("Navigation", pages_dispo, label_visibility="collapsed")
        if nb_fichiers == 1:
            st.markdown("<hr>", unsafe_allow_html=True)
            st.caption("📊 Ajoutez un 2e fichier pour activer les analyses multi-périodes")
    else:
        page = "Dashboard"  # valeur par défaut (non utilisée avant st.stop())


# ── PAGE D'ACCUEIL (aucun fichier chargé) ────────────
if not fichiers:
    features = [
        ("📊", "KPIs & tendances",   "Revenu, marge, volume par LOB, segment et canal"),
        ("👥", "Analyse clients",    "Concentration, évolution, marges décroissantes"),
        ("🚨", "Détection risques",  "Marges négatives, COGS nuls, doublons"),
        ("🔀", "Multi-périodes",     "Comparaison entre périodes, tendances et écarts"),
    ]

    # Construire les cartes séparément pour éviter tout problème d'échappement
    cards_html = ""
    for icon, title, desc in features:
        cards_html += (
            '<div style="background:#F7F7F7;border:0.5px solid #E8E8E8;'
            'border-radius:9px;padding:16px 14px;">'
            '<div style="font-size:20px;margin-bottom:10px;">' + icon + '</div>'
            '<div style="font-size:12px;font-weight:600;color:#1A1A1A;margin-bottom:4px;">' + title + '</div>'
            '<div style="font-size:11px;color:#888;line-height:1.55;">' + desc + '</div>'
            '</div>'
        )

    homepage_html = (
        '<div style="overflow:hidden;border-radius:12px;border:0.5px solid #e0e0e0;margin-top:8px;">'

        # ── Bandeau rouge
        '<div style="background:#C8102E;padding:48px 48px 52px;">'
        '<div style="font-size:11px;font-weight:600;color:rgba(255,255,255,0.5);'
        'letter-spacing:0.14em;text-transform:uppercase;margin-bottom:24px;">'
        'Audit Analytics'
        '</div>'
        '<div style="font-size:38px;font-weight:700;color:white;line-height:1.15;margin-bottom:16px;">'
        'Analysez. D&#233;tectez.<br>Comparez.'
        '</div>'
        '<div style="font-size:15px;color:rgba(255,255,255,0.72);line-height:1.7;max-width:520px;">'
        'Un outil d&#8217;audit financier universel. Importez vos fichiers de reporting, '
        'obtenez vos KPIs, identifiez les risques et comparez autant de p&#233;riodes '
        'que vous souhaitez.'
        '</div>'
        '</div>'

        # ── Partie blanche
        '<div style="background:white;padding:32px 48px 40px;">'

        # Zone upload décorative
        '<div style="display:flex;align-items:center;gap:16px;'
        'border:1.5px dashed #C8102E;border-radius:10px;'
        'padding:22px 24px;margin-bottom:28px;background:#fffafb;">'
        '<div style="width:48px;height:48px;background:#fff1f2;border-radius:10px;'
        'display:flex;align-items:center;justify-content:center;flex-shrink:0;font-size:22px;">📂</div>'
        '<div>'
        '<div style="font-size:14px;font-weight:600;color:#1A1A1A;margin-bottom:5px;">'
        'Chargez vos fichiers dans la barre lat&#233;rale pour d&#233;marrer'
        '</div>'
        '<div style="font-size:12px;color:#888;line-height:1.6;">'
        'Formats accept&#233;s&nbsp;: XLSX, XLS, CSV &middot; '
        'Plusieurs fichiers simultan&#233;s pour la comparaison multi-p&#233;riodes'
        '</div>'
        '</div>'
        '</div>'

        # 4 cartes modules
        '<div style="display:grid;grid-template-columns:repeat(4,1fr);gap:12px;">'
        + cards_html +
        '</div>'

        '</div>'  # fin partie blanche
        '</div>'  # fin wrapper
    )

    st.markdown(homepage_html, unsafe_allow_html=True)
    st.stop()


# ── CHARGER FICHIERS ─────────────────────────────────
@st.cache_data
def charger_un(f):
    return charger_fichier(f)

dfs, metas = {}, {}
_inconnu_idx = 0
for f in fichiers:
    df_t, meta_t = charger_un(f)
    if df_t is not None and not df_t.empty:
        a = detecter_annee(f.name)
        if a == "Inconnu":
            _inconnu_idx += 1
            a = f"Fichier {_inconnu_idx}"
        elif a in dfs:
            a = f"{a}b"
        dfs[a] = df_t
        metas[a] = meta_t

if not dfs:
    st.error("Aucun fichier valide chargé.")
    st.stop()

annees        = sorted(dfs.keys())
annee_recente = annees[-1]

# ── TOPBAR ───────────────────────────────────────────
st.markdown(f"""<div class="topbar">
  <div style="width:3px;height:22px;background:{RED};border-radius:2px;"></div>
  <div style="font-size:15px;font-weight:700;color:{BLACK};">Audit Analytics</div>
  <div class="topbar-sep"></div>
  <div class="topbar-title" style="font-weight:400;color:{MGRAY};">{page}</div>
  <div class="topbar-pill">📁 {" · ".join(annees)}</div>
</div>""", unsafe_allow_html=True)


# ════════════════════════════════════════════════════
# PAGE : DASHBOARD
# ════════════════════════════════════════════════════
if page == "Dashboard":
    if len(annees) == 1:
        tabs_obj = [st.container()]
    else:
        labels = [f"{a} ({nb_mois_fichier(dfs[a])}m)" if nb_mois_fichier(dfs[a]) < 12 else a for a in annees]
        tabs_obj = st.tabs(labels)

    for _annee_tab, _tab_obj in zip(annees, tabs_obj):
        with _tab_obj:
            annee = _annee_tab
            df    = dfs[annee]
            nb    = metas[annee].get("nb_lignes", len(df))
            nb_mois = nb_mois_fichier(df)
            note  = f" · {nb_mois} mois" if nb_mois < 12 else ""
            kpis  = kpi_generaux(df)
            resume = resume_flags(df)
            total_flags = resume["nb_marge_negative"] + resume["nb_cogs_zero"] + resume["nb_doublons"]

            c1, c2, c3, c4 = st.columns(4)
            c1.markdown(kpi_card_html(f"Revenu {annee}{note}", fmt(kpis['revenu_total']), f"{nb:,} transactions SINV", bar_color=RED), unsafe_allow_html=True)
            c2.markdown(kpi_card_html("Marge (COGS>0)", f"{kpis['marge_pct_globale']:.1f}%", "Hors Frais de Passage", color=RED if kpis['marge_pct_globale'] < 10 else "#198754", bar_color="#198754", bar_pct=kpis['marge_pct_globale']), unsafe_allow_html=True)
            c3.markdown(kpi_card_html("Volume total", fmt(kpis['volume_total']), "Unités facturées", bar_color=BLACK, bar_pct=70), unsafe_allow_html=True)
            c4.markdown(f"""<div class="kpi-card">
          <div class="kpi-label">Flags détectés</div>
          <div style="font-size:24px;font-weight:700;color:{BLACK};line-height:1.1;">{total_flags:,}</div>
          <div style="margin-top:6px;">
            <span class="badge-sm badge-red">🔴 {resume['nb_marge_negative']} marge nég.</span><br>
            <span class="badge-sm badge-orange" style="margin-top:3px;">🟠 {resume['nb_doublons']} doublons</span>
          </div>
        </div>""", unsafe_allow_html=True)

            st.markdown("<div style='margin-top:4px'></div>", unsafe_allow_html=True)

            col1, col2 = st.columns([3, 2])
            with col1:
                st.markdown('<div class="chart-card"><div class="chart-title">Tendance mensuelle du revenu</div>', unsafe_allow_html=True)
                trend = tendance_mensuelle(df)
                if not trend.empty:
                    max_idx = trend["revenu"].idxmax()
                    colors  = [RED if i == max_idx else "#DDDDDD" for i in trend.index]
                    fig = go.Figure()
                    fig.add_trace(go.Bar(x=trend["mois"], y=trend["revenu"], marker_color=colors, marker_line_width=0, name="Revenu", hovertemplate="%{x}<br>%{y:,.0f}<extra></extra>"))
                    fig.add_trace(go.Scatter(x=trend["mois"], y=trend["revenu"], mode="lines+markers", line=dict(color=RED, width=2), marker=dict(size=5, color=RED), name="Tendance"))
                    plotly_white(fig, 230)
                    fig.update_xaxes(tickangle=45)
                    fig.update_layout(showlegend=False)
                    st.plotly_chart(fig, width="stretch")
                st.markdown('</div>', unsafe_allow_html=True)

            with col2:
                st.markdown('<div class="chart-card"><div class="chart-title">Répartition par LOB</div>', unsafe_allow_html=True)
                lob_df = revenu_par_lob(df)
                if not lob_df.empty:
                    lob_plot = lob_df[lob_df["lob"] != "Autre"].head(6)
                    fig = px.pie(lob_plot, values="revenu", names="lob",
                                 color_discrete_sequence=[BLACK, RED, "#555", "#888", "#bbb", "#ddd"],
                                 hole=0.5)
                    fig.update_traces(textfont_size=10, textposition="outside",
                                      hovertemplate="%{label}<br>%{value:,.0f}<br>%{percent}<extra></extra>")
                    plotly_white(fig, 230, legend=True)
                    fig.update_layout(legend=dict(orientation="v", x=1.05, y=0.5))
                    st.plotly_chart(fig, width="stretch")
                st.markdown('</div>', unsafe_allow_html=True)

            col3, col4 = st.columns(2)
            with col3:
                st.markdown('<div class="chart-card"><div class="chart-title">Marge % — Top 15 clients</div><div class="chart-sub">Vert = OK · Orange = faible · Rouge = négative</div>', unsafe_allow_html=True)
                if "tiers" in df.columns:
                    col_nom = "raison_sociale" if "raison_sociale" in df.columns else "tiers"
                    marge_cli = df.groupby(col_nom).agg(revenu=("montant_ht", "sum"), marge=("marge_total", "sum")).reset_index()
                    marge_cli["marge_pct"] = (marge_cli["marge"] / marge_cli["revenu"].replace(0, pd.NA) * 100).round(1)
                    marge_cli = marge_cli[marge_cli["revenu"] > 0].dropna(subset=["marge_pct"])
                    top15 = marge_cli.nlargest(15, "revenu").sort_values("marge_pct")
                    top15["couleur"] = top15["marge_pct"].apply(lambda x: RED if x < 0 else ("#fd7e14" if x < 5 else "#198754"))
                    fig = go.Figure(go.Bar(
                        x=top15["marge_pct"], y=top15[col_nom], orientation="h",
                        marker_color=top15["couleur"], marker_line_width=0,
                        text=top15["marge_pct"].apply(lambda x: f"{x:.1f}%"),
                        textposition="outside", textfont=dict(size=10),
                        hovertemplate="%{y}<br>Marge: %{x:.1f}%<extra></extra>",
                    ))
                    fig.add_vline(x=0, line_color=BLACK, line_width=1)
                    fig.add_vline(x=5, line_dash="dot", line_color=MGRAY, line_width=1)
                    plotly_white(fig, 280)
                    fig.update_xaxes(title="Marge %", zeroline=True, zerolinecolor=BLACK, zerolinewidth=1)
                    fig.update_layout(showlegend=False)
                    st.plotly_chart(fig, width="stretch")
                st.markdown('</div>', unsafe_allow_html=True)

            with col4:
                st.markdown('<div class="chart-card"><div class="chart-title">Revenu par canal de vente</div>', unsafe_allow_html=True)
                canal_df = revenu_par_canal(df)
                if not canal_df.empty:
                    canal_plot = canal_df[canal_df["canal"] != "Autre"]
                    fig = px.bar(canal_plot, x="revenu", y="canal", orientation="h",
                                 color="marge_pct",
                                 color_continuous_scale=[[0, "#fff0f2"], [0.5, MGRAY], [1, BLACK]],
                                 text_auto=".2s",
                                 hover_data={"revenu": ":,.0f", "marge_pct": ":.1f%", "canal": False})
                    fig.update_traces(marker_line_width=0, textfont_size=10)
                    plotly_white(fig, 240)
                    fig.update_coloraxes(colorbar=dict(title="Marge%", tickfont=dict(size=9)))
                    st.plotly_chart(fig, width="stretch")
                st.markdown('</div>', unsafe_allow_html=True)

            col5, col6 = st.columns(2)
            with col5:
                st.markdown('<div class="chart-card"><div class="chart-title">Revenu par segment</div>', unsafe_allow_html=True)
                seg_df = revenu_par_segment(df)
                if not seg_df.empty:
                    seg_plot = seg_df[seg_df["segment"] != "Non défini"]
                    if not seg_plot.empty:
                        fig = px.bar(seg_plot, x="revenu", y="segment", orientation="h",
                                     color="marge_pct",
                                     color_continuous_scale=[[0, RED], [0.5, MGRAY], [1, BLACK]],
                                     text_auto=".2s")
                        fig.update_traces(marker_line_width=0)
                        plotly_white(fig, max(180, len(seg_plot) * 44))
                        st.plotly_chart(fig, width="stretch")
                    total_rev = seg_df["revenu"].sum()
                    non_def   = seg_df[seg_df["segment"] == "Non défini"]["revenu"].sum()
                    if total_rev > 0:
                        st.caption(f"⚠️ {non_def/total_rev*100:.0f}% sans segment")
                st.markdown('</div>', unsafe_allow_html=True)

            with col6:
                st.markdown('<div class="chart-card"><div class="chart-title">Top 10 clients</div>', unsafe_allow_html=True)
                top = top_clients(df, 10)
                if not top.empty:
                    col_nom2 = "raison_sociale" if "raison_sociale" in top.columns else "tiers"
                    fig = px.bar(top.sort_values("revenu"), x="revenu", y=col_nom2, orientation="h",
                                 color="marge_pct",
                                 color_continuous_scale=[[0, RED], [0.4, MGRAY], [1, "#198754"]],
                                 text_auto=".2s",
                                 hover_data={"revenu": ":,.0f", "marge_pct": ":.1f", col_nom2: False})
                    fig.update_traces(marker_line_width=0)
                    plotly_white(fig, max(220, len(top) * 30))
                    fig.update_coloraxes(colorbar=dict(title="Marge%", tickfont=dict(size=9)))
                    st.plotly_chart(fig, width="stretch")
                st.markdown('</div>', unsafe_allow_html=True)


# ════════════════════════════════════════════════════
# PAGE : ANALYSE CLIENTS
# ════════════════════════════════════════════════════
elif page == "Analyse clients":
    if len(annees) == 1:
        tabs_obj3 = [st.container()]
    else:
        labels3 = [f"{a} ({nb_mois_fichier(dfs[a])}m)" if nb_mois_fichier(dfs[a]) < 12 else a for a in annees]
        tabs_obj3 = st.tabs(labels3)

    for _annee_tab3, _tab_obj3 in zip(annees, tabs_obj3):
        with _tab_obj3:
            annee = _annee_tab3
            df    = dfs[annee]
            st.caption(f"Données {annee} · SINV uniquement")

            col1, col2 = st.columns([3, 2])
            with col1:
                st.markdown('<div class="table-card"><div class="chart-title">Top 10 clients par revenu</div>', unsafe_allow_html=True)
                top = top_clients(df, 10)
                if not top.empty:
                    st.dataframe(top.style.map(color_marge_cell, subset=["marge_pct"]), width="stretch", hide_index=True)
                st.markdown('</div>', unsafe_allow_html=True)

            with col2:
                conc = flag_concentration_client(df)
                if conc:
                    pct     = conc["pct_top3"]
                    couleur = RED if conc["flag"] else "#198754"
                    fig = go.Figure(go.Indicator(
                        mode="gauge+number",
                        value=pct,
                        number={
                            "suffix": "%",
                            "font": {"size": 36, "color": couleur, "family": "Inter"},
                            "valueformat": ".1f",
                        },
                        gauge={
                            "axis": {"range": [0, 100], "tickwidth": 1, "tickcolor": MGRAY, "tickfont": {"size": 10}},
                            "bar": {"color": couleur, "thickness": 0.35},
                            "steps": [{"range": [0, 50], "color": "#f0faf4"}, {"range": [50, 100], "color": "#fff0f2"}],
                            "threshold": {"line": {"color": RED, "width": 3}, "thickness": 0.8, "value": 50},
                        },
                        title={"text": "Concentration Top 3", "font": {"size": 12, "color": MGRAY}},
                        domain={"x": [0, 1], "y": [0.15, 1]},
                    ))
                    fig.update_layout(
                        height=260,
                        margin=dict(t=40, b=60, l=10, r=10),
                        paper_bgcolor="white",
                        font=dict(family="Inter"),
                    )
                    st.markdown('<div class="kpi-card">', unsafe_allow_html=True)
                    st.plotly_chart(fig, use_container_width=True)
                    if conc["flag"]: st.error(f"🔴 {pct:.1f}% > seuil 50%")
                    else: st.success(f"✅ {pct:.1f}% < seuil 50%")
                    st.dataframe(conc["top3"], hide_index=True, width="stretch")
                    st.markdown('</div>', unsafe_allow_html=True)

            col3, col4 = st.columns(2)
            with col3:
                st.markdown('<div class="table-card"><div class="chart-title">Clients à marge décroissante</div>', unsafe_allow_html=True)
                decr = flag_marge_decroissante(df)
                if decr.empty: st.success("Aucun client en baisse 2 mois de suite.")
                else:
                    st.warning(f"{len(decr)} client(s) en baisse continue")
                    st.dataframe(decr, width="stretch", hide_index=True)
                st.markdown('</div>', unsafe_allow_html=True)

            with col4:
                st.markdown('<div class="table-card"><div class="chart-title">Clients à marge négative</div>', unsafe_allow_html=True)
                if "tiers" in df.columns:
                    col_nom = "raison_sociale" if "raison_sociale" in df.columns else "tiers"
                    cli_neg = df.groupby(col_nom).agg(revenu=("montant_ht", "sum"), marge=("marge_total", "sum")).reset_index()
                    cli_neg["marge_pct"] = (cli_neg["marge"] / cli_neg["revenu"].replace(0, pd.NA) * 100).round(2)
                    cli_neg_f = cli_neg[cli_neg["marge_pct"] < 0].sort_values("marge_pct")
                    if cli_neg_f.empty: st.success("Aucun client à marge négative.")
                    else:
                        st.error(f"{len(cli_neg_f)} client(s) à marge négative")
                        st.dataframe(cli_neg_f, width="stretch", hide_index=True)
                st.markdown('</div>', unsafe_allow_html=True)


# ════════════════════════════════════════════════════
# PAGE : FLAGS
# ════════════════════════════════════════════════════
elif page == "Flags de risque":
    if len(annees) == 1:
        tabs_obj2 = [st.container()]
    else:
        labels2 = [f"{a} ({nb_mois_fichier(dfs[a])}m)" if nb_mois_fichier(dfs[a]) < 12 else a for a in annees]
        tabs_obj2 = st.tabs(labels2)

    for _annee_tab2, _tab_obj2 in zip(annees, tabs_obj2):
        with _tab_obj2:
            annee  = _annee_tab2
            df     = dfs[annee]
            resume = resume_flags(df)

            st.markdown(f"""<div class="flag-grid">
          <div class="flag-card"><div class="flag-icon fi-red">📉</div>
            <div><div class="flag-count">{resume['nb_marge_negative']}</div><div class="flag-name">Marge négative</div></div></div>
          <div class="flag-card"><div class="flag-icon fi-red">⚠️</div>
            <div><div class="flag-count">{resume['nb_cogs_zero']}</div><div class="flag-name">COGS = 0</div></div></div>
          <div class="flag-card"><div class="flag-icon fi-orange">🔁</div>
            <div><div class="flag-count">{resume['nb_doublons']}</div><div class="flag-name">Doublons</div></div></div>
          <div class="flag-card"><div class="flag-icon fi-orange">📊</div>
            <div><div class="flag-count">{resume['nb_marge_decroissante']}</div><div class="flag-name">Marge décroissante</div></div></div>
        </div>""", unsafe_allow_html=True)

            with st.expander("📉 Transactions à marge négative", expanded=True):
                marge_neg = flag_marge_negative(df)
                if marge_neg.empty: st.success("Aucune.")
                else:
                    st.error(f"{len(marge_neg)} transaction(s)")
                    st.dataframe(marge_neg, width="stretch", hide_index=True)
                    st.download_button("📥 Exporter", data=exporter_flags_excel({"Marge négative": marge_neg}), file_name=f"flag_marge_negative_{annee}.xlsx", mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")

            with st.expander("⚠️ COGS = 0", expanded=True):
                cogs_zero = flag_cogs_zero(df)
                if cogs_zero.empty: st.success("Aucune anomalie.")
                else:
                    st.error(f"{len(cogs_zero)} ligne(s)")
                    st.dataframe(cogs_zero, width="stretch", hide_index=True)
                    st.download_button("📥 Exporter", data=exporter_flags_excel({"COGS zéro": cogs_zero}), file_name=f"flag_cogs_zero_{annee}.xlsx", mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")

            with st.expander("🔁 Doublons", expanded=True):
                doublons = flag_doublons(df)
                if doublons.empty: st.success("Aucun doublon.")
                else:
                    st.warning(f"{len(doublons)} ligne(s)")
                    st.dataframe(doublons, width="stretch", hide_index=True)
                    st.download_button("📥 Exporter", data=exporter_flags_excel({"Doublons": doublons}), file_name=f"flag_doublons_{annee}.xlsx", mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")

            with st.expander("📊 Concentration client"):
                conc = flag_concentration_client(df)
                if conc:
                    pct = conc["pct_top3"]
                    if conc["flag"]: st.warning(f"Top 3 = {pct}% (seuil {conc['seuil']}%)")
                    else: st.info(f"Top 3 = {pct}% — OK")
                    st.dataframe(conc["top3"], width="stretch", hide_index=True)

            st.divider()
            with st.expander("📥 Export complet"):
                tous = {
                    "Marge négative":    flag_marge_negative(df),
                    "COGS zéro":         flag_cogs_zero(df),
                    "Doublons":          flag_doublons(df),
                    "Marge décroissante": flag_marge_decroissante(df),
                }
                st.download_button("📥 Exporter tous les flags", data=exporter_flags_excel(tous), file_name=f"audit_flags_{annee}.xlsx", mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")


# ════════════════════════════════════════════════════
# PAGE : COMPARAISON YOY
# ════════════════════════════════════════════════════
elif page == "Comparaison YoY":
    kpis_all = {a: kpi_annee(dfs[a], a) for a in annees}

    def delta_html(val_curr, val_prev, is_pct=False, invert=False):
        if val_prev == 0 or pd.isna(val_prev):
            return '<span style="color:#bbb;font-size:11px;">—</span>'
        diff  = val_curr - val_prev
        pct   = diff / abs(val_prev) * 100
        good  = (diff > 0) if not invert else (diff < 0)
        color = "#198754" if good else RED
        arrow = "▲" if diff > 0 else "▼"
        label = f"{arrow} {abs(diff):.1f} pp" if is_pct else f"{arrow} {abs(pct):.1f}%"
        return f'<span style="color:{color};font-weight:700;font-size:12px;">{label}</span>'

    st.markdown('<div class="chart-card">', unsafe_allow_html=True)
    st.markdown('<div class="chart-title">📊 Tableau de synthèse — comparaison directe</div>', unsafe_allow_html=True)

    header_cells = "<th style='text-align:left;padding:8px 12px;font-size:11px;color:#888;font-weight:600;border-bottom:2px solid #eee;'>Indicateur</th>"
    for i, a in enumerate(annees):
        nb_m   = kpis_all[a]['nb_mois']
        suffix = f" ({nb_m}m)" if kpis_all[a]['annualise'] else ""
        header_cells += f"<th style='text-align:right;padding:8px 12px;font-size:11px;color:{COLORS[i]};font-weight:700;border-bottom:2px solid {COLORS[i]};'>{a}{suffix}</th>"
        if i > 0:
            prev_a = annees[i - 1]
            header_cells += f"<th style='text-align:center;padding:8px 8px;font-size:11px;color:#888;font-weight:600;border-bottom:2px solid #eee;'>vs {prev_a}</th>"

    def build_row(label, vals, fmt_fn, is_pct=False, invert=False):
        row = f"<td style='padding:8px 12px;font-size:12px;font-weight:600;color:#333;border-bottom:1px solid #f5f5f5;'>{label}</td>"
        for i, (a, v) in enumerate(zip(annees, vals)):
            row += f"<td style='text-align:right;padding:8px 12px;font-size:13px;font-weight:700;color:#1a1a1a;border-bottom:1px solid #f5f5f5;'>{fmt_fn(v)}</td>"
            if i > 0:
                row += f"<td style='text-align:center;padding:8px 8px;border-bottom:1px solid #f5f5f5;'>{delta_html(vals[i], vals[i-1], is_pct=is_pct, invert=invert)}</td>"
        return row

    rev_vals   = [kpis_all[a]['revenu']    for a in annees]
    marge_vals = [kpis_all[a]['marge_pct'] for a in annees]
    vol_vals   = [kpis_all[a]['volume']    for a in annees]
    tx_vals    = [kpis_all[a]['nb_tx']     for a in annees]

    table_html = f"""
    <div style="overflow-x:auto;">
    <table style="width:100%;border-collapse:collapse;font-family:Inter,sans-serif;">
      <thead><tr>{header_cells}</tr></thead>
      <tbody>
        <tr>{build_row("💰 Revenu total",    rev_vals,   fmt)}</tr>
        <tr>{build_row("📈 Marge %",         marge_vals, lambda v: f"{v:.1f}%", is_pct=True)}</tr>
        <tr>{build_row("📦 Volume total",    vol_vals,   fmt)}</tr>
        <tr>{build_row("🔢 Nb transactions", tx_vals,    lambda v: f"{int(v):,}")}</tr>
      </tbody>
    </table>
    </div>"""
    st.markdown(table_html, unsafe_allow_html=True)
    st.markdown('</div>', unsafe_allow_html=True)

    if len(annees) >= 2:
        st.markdown("<div style='margin-top:12px'></div>", unsafe_allow_html=True)
        for i in range(1, len(annees)):
            a_prev, a_curr = annees[i - 1], annees[i]
            k_p, k_c       = kpis_all[a_prev], kpis_all[a_curr]
            note_p = f" ({k_p['nb_mois']}m)" if k_p['annualise'] else ""
            note_c = f" ({k_c['nb_mois']}m)" if k_c['annualise'] else ""
            st.markdown(f'<div class="section-title">📅 {a_prev}{note_p} → {a_curr}{note_c}</div>', unsafe_allow_html=True)

            def delta_pct(curr, prev):
                if prev == 0: return 0, "—"
                d = (curr - prev) / abs(prev) * 100
                return d, f"{'▲' if d >= 0 else '▼'} {abs(d):.1f}%"

            rev_d, rev_s = delta_pct(k_c['revenu'], k_p['revenu'])
            mrg_d        = k_c['marge_pct'] - k_p['marge_pct']
            vol_d, vol_s = delta_pct(k_c['volume'], k_p['volume'])
            tx_d,  tx_s  = delta_pct(k_c['nb_tx'],  k_p['nb_tx'])

            rev_col  = "#198754" if rev_d >= 0 else RED
            marg_col = "#198754" if mrg_d >= 0 else RED
            vol_col  = "#198754" if vol_d >= 0 else RED

            c1, c2, c3, c4 = st.columns(4)
            c1.markdown(f"""<div class="kpi-card">
              <div class="kpi-label">Revenu {a_curr}</div>
              <div style="font-size:22px;font-weight:700;color:#1a1a1a;">{fmt(k_c['revenu'])}</div>
              <div style="font-size:11px;color:{rev_col};font-weight:700;margin-top:4px;">{rev_s} vs {a_prev}</div>
              <div class="kpi-sub">{fmt(k_p['revenu'])} en {a_prev}</div>
              <div class="kpi-bar-track"><div class="kpi-bar-fill" style="width:{min(abs(rev_d),100):.0f}%;background:{rev_col};"></div></div>
            </div>""", unsafe_allow_html=True)
            c2.markdown(f"""<div class="kpi-card">
              <div class="kpi-label">Marge % {a_curr}</div>
              <div style="font-size:22px;font-weight:700;color:{marg_col};">{k_c['marge_pct']:.1f}%</div>
              <div style="font-size:11px;color:{marg_col};font-weight:700;margin-top:4px;">{'▲' if mrg_d>=0 else '▼'} {abs(mrg_d):.1f} pp vs {a_prev}</div>
              <div class="kpi-sub">{k_p['marge_pct']:.1f}% en {a_prev}</div>
              <div class="kpi-bar-track"><div class="kpi-bar-fill" style="width:{min(k_c['marge_pct'],100):.0f}%;background:{marg_col};"></div></div>
            </div>""", unsafe_allow_html=True)
            c3.markdown(f"""<div class="kpi-card">
              <div class="kpi-label">Volume {a_curr}</div>
              <div style="font-size:22px;font-weight:700;color:#1a1a1a;">{fmt(k_c['volume'])}</div>
              <div style="font-size:11px;color:{vol_col};font-weight:700;margin-top:4px;">{vol_s} vs {a_prev}</div>
              <div class="kpi-sub">{fmt(k_p['volume'])} en {a_prev}</div>
              <div class="kpi-bar-track"><div class="kpi-bar-fill" style="width:70%;background:{vol_col};"></div></div>
            </div>""", unsafe_allow_html=True)
            c4.markdown(f"""<div class="kpi-card">
              <div class="kpi-label">Transactions {a_curr}</div>
              <div style="font-size:22px;font-weight:700;color:#1a1a1a;">{k_c['nb_tx']:,}</div>
              <div style="font-size:11px;color:{'#198754' if tx_d>=0 else RED};font-weight:700;margin-top:4px;">{tx_s} vs {a_prev}</div>
              <div class="kpi-sub">{k_p['nb_tx']:,} en {a_prev}</div>
              <div class="kpi-bar-track"><div class="kpi-bar-fill" style="width:{min(abs(tx_d),100):.0f}%;background:{'#198754' if tx_d>=0 else RED};"></div></div>
            </div>""", unsafe_allow_html=True)

    st.markdown("<div style='margin-top:16px'></div>", unsafe_allow_html=True)

    col1, col2 = st.columns(2)
    with col1:
        st.markdown('<div class="chart-card"><div class="chart-title">💰 Revenu par LOB — comparaison</div>', unsafe_allow_html=True)
        lob_yoy = yoy_par_lob(dfs)
        if not lob_yoy.empty:
            fig = go.Figure()
            for i, a in enumerate(annees):
                if a in lob_yoy.columns:
                    fig.add_trace(go.Bar(name=a, x=lob_yoy["lob"], y=lob_yoy[a], marker_color=COLORS[i], marker_line_width=0,
                                         text=lob_yoy[a].apply(lambda v: fmt(v)), textposition="outside", textfont=dict(size=9)))
            fig.update_layout(barmode="group", bargap=0.25)
            plotly_white(fig, 280, legend=True)
            st.plotly_chart(fig, width="stretch")
            if len(annees) >= 2:
                a_prev2, a_last = annees[-2], annees[-1]
                if a_prev2 in lob_yoy.columns and a_last in lob_yoy.columns:
                    lob_delta = lob_yoy[["lob", a_prev2, a_last]].copy()
                    lob_delta["Δ %"] = ((lob_delta[a_last] - lob_delta[a_prev2]) / lob_delta[a_prev2].replace(0, pd.NA) * 100).round(1)
                    lob_delta = lob_delta.rename(columns={"lob": "LOB", a_prev2: f"Revenu {a_prev2}", a_last: f"Revenu {a_last}"})
                    lob_delta[f"Revenu {a_prev2}"] = lob_delta[f"Revenu {a_prev2}"].apply(fmt)
                    lob_delta[f"Revenu {a_last}"]  = lob_delta[f"Revenu {a_last}"].apply(fmt)
                    lob_delta["Δ %"] = lob_delta["Δ %"].apply(lambda v: f"▲ {v:.1f}%" if not pd.isna(v) and v >= 0 else (f"▼ {abs(v):.1f}%" if not pd.isna(v) else "—"))
                    st.dataframe(lob_delta, width="stretch", hide_index=True)
        st.markdown('</div>', unsafe_allow_html=True)

    with col2:
        st.markdown('<div class="chart-card"><div class="chart-title">📦 Volume par segment — comparaison</div>', unsafe_allow_html=True)
        seg_yoy = yoy_par_segment(dfs)
        if not seg_yoy.empty:
            fig = go.Figure()
            for i, a in enumerate(annees):
                if a in seg_yoy.columns:
                    fig.add_trace(go.Bar(name=a, x=seg_yoy["segment"], y=seg_yoy[a], marker_color=COLORS[i], marker_line_width=0,
                                         text=seg_yoy[a].apply(lambda v: fmt(v)), textposition="outside", textfont=dict(size=9)))
            fig.update_layout(barmode="group", bargap=0.25)
            plotly_white(fig, 280, legend=True)
            st.plotly_chart(fig, width="stretch")
            if len(annees) >= 2:
                a_prev2, a_last = annees[-2], annees[-1]
                if a_prev2 in seg_yoy.columns and a_last in seg_yoy.columns:
                    seg_delta = seg_yoy[["segment", a_prev2, a_last]].copy()
                    seg_delta["Δ %"] = ((seg_delta[a_last] - seg_delta[a_prev2]) / seg_delta[a_prev2].replace(0, pd.NA) * 100).round(1)
                    seg_delta = seg_delta.rename(columns={"segment": "Segment", a_prev2: f"Volume {a_prev2}", a_last: f"Volume {a_last}"})
                    seg_delta[f"Volume {a_prev2}"] = seg_delta[f"Volume {a_prev2}"].apply(fmt)
                    seg_delta[f"Volume {a_last}"]  = seg_delta[f"Volume {a_last}"].apply(fmt)
                    seg_delta["Δ %"] = seg_delta["Δ %"].apply(lambda v: f"▲ {v:.1f}%" if not pd.isna(v) and v >= 0 else (f"▼ {abs(v):.1f}%" if not pd.isna(v) else "—"))
                    st.dataframe(seg_delta, width="stretch", hide_index=True)
        st.markdown('</div>', unsafe_allow_html=True)

    st.markdown('<div class="chart-card"><div class="chart-title">📅 Tendance mensuelle du revenu — toutes périodes superposées</div><div class="chart-sub">Même mois, toutes périodes · saisonnalité et croissance</div>', unsafe_allow_html=True)
    fig = go.Figure()
    MOIS_FR = {"01": "Jan", "02": "Fév", "03": "Mar", "04": "Avr", "05": "Mai", "06": "Jun",
               "07": "Jul", "08": "Aoû", "09": "Sep", "10": "Oct", "11": "Nov", "12": "Déc"}
    for i, a in enumerate(annees):
        trend = tendance_mensuelle(dfs[a])
        if not trend.empty:
            trend["mois_num"]   = trend["mois"].str[-2:]
            trend["mois_label"] = trend["mois_num"].map(MOIS_FR).fillna(trend["mois_num"])
            fig.add_trace(go.Scatter(x=trend["mois_label"], y=trend["revenu"], mode="lines+markers", name=a,
                                     line=dict(color=COLORS[i], width=2.5), marker=dict(size=6, color=COLORS[i]),
                                     hovertemplate=f"<b>{a}</b> %{{x}}<br>Revenu: %{{y:,.0f}}<extra></extra>"))
    plotly_white(fig, 280, legend=True)
    st.plotly_chart(fig, width="stretch")
    st.markdown('</div>', unsafe_allow_html=True)


# ════════════════════════════════════════════════════
# PAGE : ANALYSE VOLUME
# ════════════════════════════════════════════════════
elif page == "Analyse volume":
    if len(annees) == 1:
        tabs_obj4    = [st.container()]
        annees_tabs4 = annees
    else:
        labels4      = [f"{a} ({nb_mois_fichier(dfs[a])}m)" if nb_mois_fichier(dfs[a]) < 12 else a for a in annees]
        tabs_obj4    = st.tabs(labels4)
        annees_tabs4 = annees

    for _annee_tab4, _tab_obj4 in zip(annees_tabs4, tabs_obj4):
        with _tab_obj4:
            annee   = _annee_tab4
            df      = dfs[annee]
            nb_mois = nb_mois_fichier(df)
            st.caption(f"{annee} · {nb_mois} mois · SINV uniquement")

            col1, col2, col3 = st.columns(3)
            with col1:
                st.markdown('<div class="chart-card"><div class="chart-title">Volume par produit</div>', unsafe_allow_html=True)
                if "segment" in df.columns:
                    seg = df[df["segment"] != "Non défini"].groupby("segment")["qte"].sum().reset_index().sort_values("qte", ascending=False)
                    if not seg.empty:
                        fig = px.bar(seg, x="segment", y="qte", color_discrete_sequence=[BLACK], text_auto=".2s")
                        fig.update_traces(marker_line_width=0)
                        plotly_white(fig, 240)
                        fig.update_layout(showlegend=False)
                        st.plotly_chart(fig, width="stretch")
                st.markdown('</div>', unsafe_allow_html=True)

            with col2:
                st.markdown('<div class="chart-card"><div class="chart-title">Volume par canal</div>', unsafe_allow_html=True)
                if "canal" in df.columns:
                    canal = df[df["canal"] != "Autre"].groupby("canal")["qte"].sum().reset_index().sort_values("qte", ascending=False)
                    if not canal.empty:
                        fig = px.pie(canal, values="qte", names="canal",
                                     color_discrete_sequence=[BLACK, RED, MGRAY, "#bbb", "#ddd"], hole=0.4)
                        fig.update_traces(textfont_size=10)
                        plotly_white(fig, 240, legend=True)
                        st.plotly_chart(fig, width="stretch")
                st.markdown('</div>', unsafe_allow_html=True)

            with col3:
                st.markdown('<div class="chart-card"><div class="chart-title">Top 10 clients — volume</div>', unsafe_allow_html=True)
                if "qte" in df.columns:
                    col_nom = "raison_sociale" if "raison_sociale" in df.columns else "tiers"
                    top_vol = df.groupby(col_nom)["qte"].sum().nlargest(10).reset_index()
                    top_vol.columns = ["client", "volume"]
                    fig = px.bar(top_vol.sort_values("volume"), x="volume", y="client", orientation="h",
                                 color_discrete_sequence=[RED], text_auto=".2s")
                    fig.update_traces(marker_line_width=0)
                    plotly_white(fig, 240)
                    fig.update_layout(showlegend=False)
                    st.plotly_chart(fig, width="stretch")
                st.markdown('</div>', unsafe_allow_html=True)


# ════════════════════════════════════════════════════
# PAGE : CANAL EXPOR
# ════════════════════════════════════════════════════
elif page == "Canal EXPOR":
    expor = analyse_expor(dfs)
    if expor["revenu_par_annee"].empty:
        st.info("Aucune transaction EXPOR dans les fichiers chargés.")
    else:
        rev_df = expor["revenu_par_annee"]
        cols   = st.columns(len(rev_df))
        for i, (_, row) in enumerate(rev_df.iterrows()):
            with cols[i]:
                st.markdown(kpi_card_html(f"EXPOR {row['annee']}", fmt(row['revenu_expor']), f"{row['pct_total']:.1f}% du revenu total", bar_color=RED, bar_pct=row['pct_total'] * 2), unsafe_allow_html=True)

        st.markdown('<div class="chart-card"><div class="chart-title">Évolution revenu EXPOR</div>', unsafe_allow_html=True)
        fig = px.bar(rev_df, x="annee", y="revenu_expor", color_discrete_sequence=[RED], text_auto=".2s")
        fig.update_traces(marker_line_width=0)
        plotly_white(fig, 220)
        fig.update_layout(showlegend=False)
        st.plotly_chart(fig, width="stretch")
        st.markdown('</div>', unsafe_allow_html=True)

        if not expor["clients"].empty:
            st.markdown('<div class="table-card"><div class="chart-title">Clients EXPOR — liste complète</div>', unsafe_allow_html=True)
            st.dataframe(expor["clients"].sort_values(["annee", "revenu"], ascending=[True, False]).style.map(color_marge_cell, subset=["marge_pct"]), width="stretch", hide_index=True)
            st.markdown('</div>', unsafe_allow_html=True)


# ════════════════════════════════════════════════════
# PAGE : ÉVOLUTION CLIENTS
# ════════════════════════════════════════════════════
elif page == "Évolution clients":
    if len(annees) < 2:
        st.info("Chargez au moins 2 fichiers.")
    else:
        for i in range(len(annees) - 1):
            a_ref, a_cmp = annees[i], annees[i + 1]
            st.markdown(f'<div class="section-title">📅 {a_ref} → {a_cmp}</div>', unsafe_allow_html=True)
            evol = evolution_clients(dfs[a_ref], dfs[a_cmp], a_ref, a_cmp)
            if not evol: continue

            c1, c2, c3, c4 = st.columns(4)
            c1.markdown(kpi_card_html("Clients nouveaux",  len(evol['nouveaux']),  f"Absents en {a_ref}", color="#198754", bar_color="#198754", bar_pct=50), unsafe_allow_html=True)
            c2.markdown(kpi_card_html("Clients disparus",  len(evol['disparus']),  f"Absents en {a_cmp}", color=RED,       bar_color=RED,       bar_pct=50), unsafe_allow_html=True)
            c3.markdown(kpi_card_html("Croissance >50%",   len(evol['croissants']),"Forte hausse",        color="#198754", bar_color="#198754", bar_pct=60), unsafe_allow_html=True)
            c4.markdown(kpi_card_html("Baisse >30%",       len(evol['en_baisse']), "Forte baisse",        color=RED,       bar_color=RED,       bar_pct=60), unsafe_allow_html=True)

            col1, col2 = st.columns(2)
            with col1:
                if not evol["croissants"].empty:
                    st.markdown('<div class="table-card"><div class="chart-title">📈 Forte croissance (&gt;50%)</div>', unsafe_allow_html=True)
                    st.dataframe(evol["croissants"].head(15), width="stretch", hide_index=True)
                    st.markdown('</div>', unsafe_allow_html=True)
                if not evol["nouveaux"].empty:
                    st.markdown('<div class="table-card"><div class="chart-title">🆕 Clients nouveaux</div>', unsafe_allow_html=True)
                    st.dataframe(evol["nouveaux"].head(15), width="stretch", hide_index=True)
                    st.markdown('</div>', unsafe_allow_html=True)
            with col2:
                if not evol["en_baisse"].empty:
                    st.markdown('<div class="table-card"><div class="chart-title">📉 Forte baisse (&gt;30%)</div>', unsafe_allow_html=True)
                    st.dataframe(evol["en_baisse"].head(15), width="stretch", hide_index=True)
                    st.markdown('</div>', unsafe_allow_html=True)
                if not evol["disparus"].empty:
                    st.markdown('<div class="table-card"><div class="chart-title">❌ Clients disparus</div>', unsafe_allow_html=True)
                    st.dataframe(evol["disparus"].head(15), width="stretch", hide_index=True)
                    st.markdown('</div>', unsafe_allow_html=True)
            st.divider()


# ════════════════════════════════════════════════════
# PAGE : FRAIS DE PASSAGE
# ════════════════════════════════════════════════════
elif page == "Frais de Passage":
    st.caption("Clients avec marge > 90% — COGS = 0 (Frais de Passage, comptes internes)")
    fp = analyse_frais_passage(dfs)

    if fp.empty:
        st.info("Aucun client avec marge > 90%.")
    else:
        cols = st.columns(len(annees))
        for i, a in enumerate(annees):
            fp_a      = fp[fp["annee"] == a]
            rev_total = dfs[a]["montant_ht"].sum()
            rev_fp    = fp_a["revenu"].sum()
            pct       = rev_fp / rev_total * 100 if rev_total > 0 else 0
            with cols[i]:
                st.markdown(kpi_card_html(f"Frais de Passage {a}", fmt(rev_fp), f"{pct:.1f}% du total · {len(fp_a)} clients", bar_color=RED, bar_pct=pct * 3), unsafe_allow_html=True)

        if len(annees) > 1:
            st.markdown('<div class="chart-card"><div class="chart-title">Évolution des Frais de Passage</div>', unsafe_allow_html=True)
            fp_by = fp.groupby("annee")["revenu"].sum().reset_index()
            fig   = px.bar(fp_by, x="annee", y="revenu", color_discrete_sequence=[RED], text_auto=".2s")
            fig.update_traces(marker_line_width=0)
            plotly_white(fig, 220)
            fig.update_layout(showlegend=False)
            st.plotly_chart(fig, width="stretch")
            st.markdown('</div>', unsafe_allow_html=True)

        st.markdown('<div class="table-card"><div class="chart-title">Liste complète — marge &gt; 90%</div>', unsafe_allow_html=True)
        cols_show = [c for c in ["annee", "raison_sociale", "tiers", "revenu", "cogs", "marge", "marge_pct"] if c in fp.columns]
        st.dataframe(fp[cols_show].sort_values(["annee", "revenu"], ascending=[True, False]), width="stretch", hide_index=True)
        st.markdown('</div>', unsafe_allow_html=True)

        st.download_button(
            "📥 Exporter Frais de Passage",
            data=exporter_flags_excel({"Frais de Passage": fp}),
            file_name="frais_passage.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )