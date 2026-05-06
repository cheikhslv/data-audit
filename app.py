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

# ── DETECTER_ANNEE (version corrigée — intégrée ici pour fiabilité) ──────────
# Les fichiers Sage X3 ont des dates JJMMAA : 010124_au_311224 → 2024
def detecter_annee(nom_fichier: str) -> str:
    # Pattern : après " au " ou "_au_" → DDMMAA (6 chiffres), prendre les 2 derniers = année
    m = _re.search(r'[\s_]au[\s_]\d{4}(\d{2})', nom_fichier, _re.IGNORECASE)
    if m:
        yr = int(m.group(1))
        if 0 <= yr <= 99:
            return str(2000 + yr)
    # Pattern date de début : JJMMAA séparé par espace ou underscore
    m2 = _re.search(r'[\s_]\d{4}(\d{2})[\s_]', nom_fichier)
    if m2:
        yr = int(m2.group(1))
        if 0 <= yr <= 99:
            return str(2000 + yr)
    # Fallback : entier 4 chiffres entre 2000 et 2099
    for tok in _re.findall(r'\d{4}', nom_fichier):
        if 2000 <= int(tok) <= 2099:
            return tok
    return "Inconnu"


st.set_page_config(page_title="Audit Analytics — Oryx Energies", page_icon="📊", layout="wide")

LOGO_B64 = "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"
RED, BLACK, GRAY, LGRAY, MGRAY = "#C8102E", "#1A1A1A", "#F7F7F7", "#EEEEEE", "#888888"
COLORS = ["#1A1A1A", "#C8102E", "#AAAAAA", "#E8E8E8"]

# ── CSS ──────────────────────────────────────────────
st.markdown(f"""<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800&display=swap');
html,body,[class*="css"]{{font-family:'Inter',sans-serif!important;background:#F7F7F7!important;}}
.block-container{{padding:0 1.5rem 2rem 1.5rem!important;max-width:100%!important;}}

/* SIDEBAR scrollable et compacte */
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

/* SUB-NAV années (clé: annee_dash_sel) */
[data-testid="stSidebar"] [data-testid="stRadio"][aria-label=""] + div .stRadio label,
div[data-testid="stSidebar"] div[data-baseweb="radio"] label {{font-size:11px!important;padding:5px 12px 5px 28px!important;border-radius:5px!important;color:#aaa!important;}}
div[data-testid="stSidebar"] div[data-baseweb="radio"] label:has(input:checked) {{color:{RED}!important;font-weight:700!important;background:#fff0f2!important;border-left:2px solid {RED}!important;}}

/* TOPBAR */
.topbar{{background:white;border-bottom:1px solid {LGRAY};padding:10px 0;display:flex;align-items:center;gap:12px;margin:0 -1.5rem 1.5rem;padding-left:1.5rem;padding-right:1.5rem;}}
.topbar-logo{{height:28px;width:auto;}}
.topbar-sep{{width:1px;height:20px;background:{LGRAY};}}
.topbar-title{{font-size:16px;font-weight:700;color:{BLACK};}}
.topbar-pill{{margin-left:auto;background:{GRAY};color:{MGRAY};border:1px solid {LGRAY};padding:3px 10px;border-radius:20px;font-size:10px;font-weight:500;}}

/* YEAR TABS */
.year-tabs{{display:flex;gap:6px;margin-bottom:16px;}}
.year-tab{{padding:6px 18px;border-radius:20px;font-size:13px;font-weight:600;border:1.5px solid {LGRAY};cursor:pointer;background:white;color:{MGRAY};}}
.year-tab.active{{background:{RED};color:white;border-color:{RED};}}
.year-note{{font-size:10px;color:#bbb;margin-left:8px;font-weight:400;}}

/* KPI CARDS */
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

/* CHART CARDS */
.chart-card{{background:white;border:1px solid {LGRAY};border-radius:10px;padding:14px 16px;margin-bottom:12px;}}
.chart-title{{font-size:12px;font-weight:600;color:{BLACK};margin-bottom:12px;}}
.chart-sub{{font-size:10px;color:{MGRAY};margin-top:-8px;margin-bottom:10px;}}
.table-card{{background:white;border:1px solid {LGRAY};border-radius:10px;padding:14px 16px;margin-bottom:12px;}}

/* FLAGS */
.flag-grid{{display:grid;grid-template-columns:repeat(4,1fr);gap:12px;margin-bottom:16px;}}
.flag-card{{background:white;border:1px solid {LGRAY};border-radius:10px;padding:12px 14px;display:flex;align-items:center;gap:10px;}}
.flag-icon{{width:32px;height:32px;border-radius:8px;display:flex;align-items:center;justify-content:center;font-size:14px;flex-shrink:0;}}
.fi-red{{background:#fff0f2;}}.fi-orange{{background:#fff8f0;}}
.flag-count{{font-size:20px;font-weight:700;color:{BLACK};line-height:1;}}
.flag-name{{font-size:10px;color:{MGRAY};margin-top:2px;}}

/* SECTION TITLE */
.section-title{{font-size:13px;font-weight:700;color:{BLACK};margin-bottom:12px;padding-bottom:6px;border-bottom:1px solid {LGRAY};}}

/* MISC */
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


# ── SIDEBAR ──────────────────────────────────────────
with st.sidebar:
    st.markdown(f"""
    <div style="padding:14px 14px 12px;border-bottom:1px solid {LGRAY};margin-bottom:8px;">
      <div style="font-size:14px;font-weight:700;color:{BLACK};">Audit Analytics</div>
      <div style="width:24px;height:2px;background:{RED};border-radius:2px;margin-top:5px;"></div>
    </div>""", unsafe_allow_html=True)

    fichiers = st.file_uploader("Flash Reports", type=["xlsx","xls","csv"],
        accept_multiple_files=True,
        help="Chargez 1 à 3 fichiers (FY2024, FY2025, FY2026)")

    if fichiers:
        for f in fichiers:
            annee = detecter_annee(f.name)
            st.caption(f"✓ {annee} — {f.name[:24]}…")

    st.markdown("<hr>", unsafe_allow_html=True)
    st.markdown(f'<div style="font-size:9px;font-weight:700;color:#bbb;letter-spacing:1.5px;text-transform:uppercase;padding:4px 12px 4px;">Navigation</div>', unsafe_allow_html=True)

    nb_fichiers = len(fichiers) if fichiers else 0
    pages_base  = ["Dashboard","Analyse clients","Flags de risque"]
    pages_multi = ["Comparaison YoY","Analyse volume","Canal EXPOR","Évolution clients","Frais de Passage"]
    pages_dispo = pages_base + (pages_multi if nb_fichiers >= 2 else [])

    page = st.radio("", pages_dispo, label_visibility="collapsed")

    if nb_fichiers == 1:
        st.markdown("<hr>", unsafe_allow_html=True)
        st.caption("📊 Ajoutez 2+ fichiers pour activer les analyses multi-années")


# ── NO FILE ──────────────────────────────────────────
if not fichiers:
    st.markdown(f"""<div class="topbar">
      <img class="topbar-logo" src="data:image/png;base64,{LOGO_B64}">
      <div class="topbar-sep"></div><div class="topbar-title">Audit Analytics</div>
    </div>""", unsafe_allow_html=True)

    c1,c2,c3 = st.columns(3)
    for col,num,e,title,sub in [
        (c1,"1","📁","Charger les Flash Reports","1 à 3 fichiers simultanément"),
        (c2,"2","⚡","Analyse automatique","KPIs, marges, tendances, flags"),
        (c3,"3","📈","Comparaison YoY","Évolution 2024 → 2025 → 2026"),
    ]:
        with col:
            st.markdown(f"""<div class="kpi-card">
              <div style="font-size:22px;margin-bottom:8px;">{e}</div>
              <div style="font-size:9px;color:{RED};font-weight:700;text-transform:uppercase;letter-spacing:1px;margin-bottom:4px;">Étape {num}</div>
              <div style="font-size:13px;font-weight:600;color:{BLACK};margin-bottom:3px;">{title}</div>
              <div style="font-size:11px;color:{MGRAY};">{sub}</div>
            </div>""", unsafe_allow_html=True)
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
    st.error("Aucun fichier valide.")
    st.stop()

annees      = sorted(dfs.keys())
annee_recente = annees[-1]

# Topbar
st.markdown(f"""<div class="topbar">
  <img class="topbar-logo" src="data:image/png;base64,{LOGO_B64}">
  <div class="topbar-sep"></div>
  <div class="topbar-title">{page}</div>
  <div class="topbar-pill">📁 Rwanda · {" · ".join(annees)}</div>
</div>""", unsafe_allow_html=True)





# ════════════════════════════════════════════════════
# PAGE : DASHBOARD
# ════════════════════════════════════════════════════
if page == "Dashboard":
    if len(annees) == 1:
        tabs_obj = [st.container()]
    else:
        labels = [f"{a} ({nb_mois_fichier(dfs[a])}m)" if nb_mois_fichier(dfs[a])<12 else a for a in annees]
        tabs_obj = st.tabs(labels)

    for _annee_tab, _tab_obj in zip(annees, tabs_obj):
      with _tab_obj:
        annee = _annee_tab
        df = dfs[annee]
        nb = metas[annee].get("nb_lignes", len(df))
        nb_mois = nb_mois_fichier(df)
        note = f" · {nb_mois} mois" if nb_mois < 12 else ""
        kpis   = kpi_generaux(df)
        resume = resume_flags(df)
        total_flags = resume["nb_marge_negative"] + resume["nb_cogs_zero"] + resume["nb_doublons"]

        # KPI row
        c1,c2,c3,c4 = st.columns(4)
        c1.markdown(kpi_card_html(f"Revenu {annee}{note}", fmt(kpis['revenu_total']), f"{nb:,} transactions SINV", bar_color=RED), unsafe_allow_html=True)
        c2.markdown(kpi_card_html("Marge (COGS>0)", f"{kpis['marge_pct_globale']:.1f}%", "Hors Frais de Passage", color=RED if kpis['marge_pct_globale']<10 else "#198754", bar_color="#198754", bar_pct=kpis['marge_pct_globale']), unsafe_allow_html=True)
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

        # Row 2: Tendance + Pie LOB
        col1, col2 = st.columns([3,2])
        with col1:
            st.markdown('<div class="chart-card"><div class="chart-title">Tendance mensuelle du revenu</div>', unsafe_allow_html=True)
            trend = tendance_mensuelle(df)
            if not trend.empty:
                max_idx = trend["revenu"].idxmax()
                colors = [RED if i==max_idx else "#DDDDDD" for i in trend.index]
                fig = go.Figure()
                fig.add_trace(go.Bar(x=trend["mois"], y=trend["revenu"], marker_color=colors, marker_line_width=0, name="Revenu", hovertemplate="%{x}<br>%{y:,.0f}<extra></extra>"))
                fig.add_trace(go.Scatter(x=trend["mois"], y=trend["revenu"], mode="lines+markers", line=dict(color=RED, width=2), marker=dict(size=5, color=RED), name="Tendance"))
                plotly_white(fig, 230)
                fig.update_xaxes(tickangle=45)
                fig.update_layout(showlegend=False)
                st.plotly_chart(fig, use_container_width=True)
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
                st.plotly_chart(fig, use_container_width=True)
            st.markdown('</div>', unsafe_allow_html=True)

        # Row 3: Marge clients + Canal
        col3, col4 = st.columns(2)
        with col3:
            st.markdown('<div class="chart-card"><div class="chart-title">Marge % — Top 15 clients</div><div class="chart-sub">Vert = OK · Orange = faible · Rouge = négative</div>', unsafe_allow_html=True)
            if "tiers" in df.columns:
                col_nom = "raison_sociale" if "raison_sociale" in df.columns else "tiers"
                marge_cli = df.groupby(col_nom).agg(
                    revenu=("montant_ht","sum"), marge=("marge_total","sum")
                ).reset_index()
                marge_cli["marge_pct"] = (marge_cli["marge"]/marge_cli["revenu"].replace(0,pd.NA)*100).round(1)
                marge_cli = marge_cli[marge_cli["revenu"]>0].dropna(subset=["marge_pct"])
                top15 = marge_cli.nlargest(15,"revenu").sort_values("marge_pct")
                top15["couleur"] = top15["marge_pct"].apply(
                    lambda x: RED if x<0 else ("#fd7e14" if x<5 else "#198754"))
                fig = go.Figure(go.Bar(
                    x=top15["marge_pct"],
                    y=top15[col_nom],
                    orientation="h",
                    marker_color=top15["couleur"],
                    marker_line_width=0,
                    text=top15["marge_pct"].apply(lambda x: f"{x:.1f}%"),
                    textposition="outside",
                    textfont=dict(size=10),
                    hovertemplate="%{y}<br>Marge: %{x:.1f}%<extra></extra>",
                ))
                fig.add_vline(x=0, line_color=BLACK, line_width=1)
                fig.add_vline(x=5, line_dash="dot", line_color=MGRAY, line_width=1)
                plotly_white(fig, 280)
                fig.update_xaxes(title="Marge %", zeroline=True, zerolinecolor=BLACK, zerolinewidth=1)
                fig.update_yaxes(title="")
                fig.update_layout(showlegend=False)
                st.plotly_chart(fig, use_container_width=True)
            st.markdown('</div>', unsafe_allow_html=True)

        with col4:
            st.markdown('<div class="chart-card"><div class="chart-title">Revenu par canal de vente</div>', unsafe_allow_html=True)
            canal_df = revenu_par_canal(df)
            if not canal_df.empty:
                canal_plot = canal_df[canal_df["canal"] != "Autre"]
                fig = px.bar(canal_plot, x="revenu", y="canal", orientation="h",
                             color="marge_pct",
                             color_continuous_scale=[[0,"#fff0f2"],[0.5,MGRAY],[1,BLACK]],
                             text_auto=".2s",
                             hover_data={"revenu":":,.0f","marge_pct":":.1f%","canal":False})
                fig.update_traces(marker_line_width=0, textfont_size=10)
                plotly_white(fig, 240)
                fig.update_coloraxes(colorbar=dict(title="Marge%",tickfont=dict(size=9)))
                st.plotly_chart(fig, use_container_width=True)
            st.markdown('</div>', unsafe_allow_html=True)

        # Row 4: Segment + Top clients
        col5, col6 = st.columns(2)
        with col5:
            st.markdown('<div class="chart-card"><div class="chart-title">Revenu par segment</div>', unsafe_allow_html=True)
            seg_df = revenu_par_segment(df)
            if not seg_df.empty:
                seg_plot = seg_df[seg_df["segment"] != "Non défini"]
                if not seg_plot.empty:
                    fig = px.bar(seg_plot, x="revenu", y="segment", orientation="h",
                                 color="marge_pct",
                                 color_continuous_scale=[[0,RED],[0.5,MGRAY],[1,BLACK]],
                                 text_auto=".2s")
                    fig.update_traces(marker_line_width=0)
                    plotly_white(fig, max(180, len(seg_plot)*44))
                    st.plotly_chart(fig, use_container_width=True)
                total_rev = seg_df["revenu"].sum()
                non_def = seg_df[seg_df["segment"]=="Non défini"]["revenu"].sum()
                if total_rev>0: st.caption(f"⚠️ {non_def/total_rev*100:.0f}% sans segment")
            st.markdown('</div>', unsafe_allow_html=True)

        with col6:
            st.markdown('<div class="chart-card"><div class="chart-title">Top 10 clients</div>', unsafe_allow_html=True)
            top = top_clients(df, 10)
            if not top.empty:
                col_nom2 = "raison_sociale" if "raison_sociale" in top.columns else "tiers"
                fig = px.bar(top.sort_values("revenu"), x="revenu", y=col_nom2, orientation="h",
                             color="marge_pct",
                             color_continuous_scale=[[0,RED],[0.4,MGRAY],[1,"#198754"]],
                             text_auto=".2s",
                             hover_data={"revenu":":,.0f","marge_pct":":.1f",col_nom2:False})
                fig.update_traces(marker_line_width=0)
                plotly_white(fig, max(220, len(top)*30))
                fig.update_coloraxes(colorbar=dict(title="Marge%",tickfont=dict(size=9)))
                st.plotly_chart(fig, use_container_width=True)
            st.markdown('</div>', unsafe_allow_html=True)


# ════════════════════════════════════════════════════
# PAGE : ANALYSE CLIENTS
# ════════════════════════════════════════════════════
elif page == "Analyse clients":
    if len(annees) == 1:
        tabs_obj3 = [st.container()]
    else:
        labels3 = [f"{a} ({nb_mois_fichier(dfs[a])}m)" if nb_mois_fichier(dfs[a])<12 else a for a in annees]
        tabs_obj3 = st.tabs(labels3)

    for _annee_tab3, _tab_obj3 in zip(annees, tabs_obj3):
      with _tab_obj3:
        annee = _annee_tab3
        df = dfs[annee]
        st.caption(f"Données {annee} · SINV uniquement")

        col1, col2 = st.columns([3,2])
        with col1:
            st.markdown('<div class="table-card"><div class="chart-title">Top 10 clients par revenu</div>', unsafe_allow_html=True)
            top = top_clients(df, 10)
            if not top.empty:
                st.dataframe(top.style.applymap(color_marge_cell, subset=["marge_pct"]), use_container_width=True, hide_index=True)
            st.markdown('</div>', unsafe_allow_html=True)

        with col2:
            conc = flag_concentration_client(df)
            if conc:
                pct = conc["pct_top3"]
                couleur = RED if conc["flag"] else "#198754"
                fig = go.Figure(go.Indicator(
                    mode="gauge+number",
                    value=pct,
                    number={"suffix":"%","font":{"size":28,"color":couleur,"family":"Inter"}},
                    gauge={
                        "axis":{"range":[0,100],"tickwidth":1,"tickcolor":MGRAY,"tickfont":{"size":10}},
                        "bar":{"color":couleur,"thickness":0.3},
                        "steps":[{"range":[0,50],"color":"#f0faf4"},{"range":[50,100],"color":"#fff0f2"}],
                        "threshold":{"line":{"color":RED,"width":3},"thickness":0.8,"value":50},
                    },
                    title={"text":"Concentration Top 3","font":{"size":12,"color":MGRAY}},
                ))
                fig.update_layout(height=200, margin=dict(t=30,b=10,l=20,r=20), paper_bgcolor="white", font=dict(family="Inter"))
                st.markdown('<div class="kpi-card">', unsafe_allow_html=True)
                st.plotly_chart(fig, use_container_width=True)
                if conc["flag"]: st.error(f"🔴 {pct}% > seuil 50%")
                else: st.success(f"✅ {pct}% < seuil 50%")
                st.dataframe(conc["top3"], hide_index=True, use_container_width=True)
                st.markdown('</div>', unsafe_allow_html=True)

        col3, col4 = st.columns(2)
        with col3:
            st.markdown('<div class="table-card"><div class="chart-title">Clients à marge décroissante</div>', unsafe_allow_html=True)
            decr = flag_marge_decroissante(df)
            if decr.empty: st.success("Aucun client en baisse 2 mois de suite.")
            else:
                st.warning(f"{len(decr)} client(s) en baisse continue")
                st.dataframe(decr, use_container_width=True, hide_index=True)
            st.markdown('</div>', unsafe_allow_html=True)

        with col4:
            st.markdown('<div class="table-card"><div class="chart-title">Clients à marge négative</div>', unsafe_allow_html=True)
            if "tiers" in df.columns:
                col_nom = "raison_sociale" if "raison_sociale" in df.columns else "tiers"
                cli_neg = df.groupby(col_nom).agg(revenu=("montant_ht","sum"),marge=("marge_total","sum")).reset_index()
                cli_neg["marge_pct"] = (cli_neg["marge"]/cli_neg["revenu"].replace(0,pd.NA)*100).round(2)
                cli_neg_f = cli_neg[cli_neg["marge_pct"]<0].sort_values("marge_pct")
                if cli_neg_f.empty: st.success("Aucun client à marge négative.")
                else:
                    st.error(f"{len(cli_neg_f)} client(s) à marge négative")
                    st.dataframe(cli_neg_f, use_container_width=True, hide_index=True)
            st.markdown('</div>', unsafe_allow_html=True)


# ════════════════════════════════════════════════════
# PAGE : FLAGS
# ════════════════════════════════════════════════════
elif page == "Flags de risque":
    if len(annees) == 1:
        tabs_obj2 = [st.container()]
    else:
        labels2 = [f"{a} ({nb_mois_fichier(dfs[a])}m)" if nb_mois_fichier(dfs[a])<12 else a for a in annees]
        tabs_obj2 = st.tabs(labels2)

    for _annee_tab2, _tab_obj2 in zip(annees, tabs_obj2):
      with _tab_obj2:
        annee = _annee_tab2
        df = dfs[annee]
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
                st.dataframe(marge_neg, use_container_width=True, hide_index=True)
                st.download_button("📥 Exporter", data=exporter_flags_excel({"Marge négative":marge_neg}), file_name=f"flag_marge_negative_{annee}.xlsx", mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")

        with st.expander("⚠️ COGS = 0", expanded=True):
            cogs_zero = flag_cogs_zero(df)
            if cogs_zero.empty: st.success("Aucune anomalie.")
            else:
                st.error(f"{len(cogs_zero)} ligne(s)")
                st.dataframe(cogs_zero, use_container_width=True, hide_index=True)
                st.download_button("📥 Exporter", data=exporter_flags_excel({"COGS zéro":cogs_zero}), file_name=f"flag_cogs_zero_{annee}.xlsx", mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")

        with st.expander("🔁 Doublons", expanded=True):
            doublons = flag_doublons(df)
            if doublons.empty: st.success("Aucun doublon.")
            else:
                st.warning(f"{len(doublons)} ligne(s)")
                st.dataframe(doublons, use_container_width=True, hide_index=True)
                st.download_button("📥 Exporter", data=exporter_flags_excel({"Doublons":doublons}), file_name=f"flag_doublons_{annee}.xlsx", mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")

        with st.expander("📊 Concentration client"):
            conc = flag_concentration_client(df)
            if conc:
                pct = conc["pct_top3"]
                if conc["flag"]: st.warning(f"Top 3 = {pct}% (seuil {conc['seuil']}%)")
                else: st.info(f"Top 3 = {pct}% — OK")
                st.dataframe(conc["top3"], use_container_width=True, hide_index=True)

        st.divider()
        with st.expander("📥 Export complet"):
            tous = {"Marge négative":flag_marge_negative(df),"COGS zéro":flag_cogs_zero(df),"Doublons":flag_doublons(df),"Marge décroissante":flag_marge_decroissante(df)}
            st.download_button("📥 Exporter tous les flags", data=exporter_flags_excel(tous), file_name=f"audit_flags_{annee}.xlsx", mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")


# ════════════════════════════════════════════════════
# PAGE : COMPARAISON YOY
# ════════════════════════════════════════════════════
elif page == "Comparaison YoY":
    kpis_all = {a: kpi_annee(dfs[a], a) for a in annees}

    # ── Helpers de delta ───────────────────────────
    def delta_html(val_curr, val_prev, is_pct=False, invert=False):
        """Génère badge delta coloré avec flèche."""
        if val_prev == 0 or pd.isna(val_prev):
            return '<span style="color:#bbb;font-size:11px;">—</span>'
        diff = val_curr - val_prev
        pct  = diff / abs(val_prev) * 100
        good = (diff > 0) if not invert else (diff < 0)
        color = "#198754" if good else RED
        arrow = "▲" if diff > 0 else "▼"
        if is_pct:
            label = f"{arrow} {abs(diff):.1f} pp"
        else:
            label = f"{arrow} {abs(pct):.1f}%"
        return f'<span style="color:{color};font-weight:700;font-size:12px;">{label}</span>'

    # ── 1. Tableau synthèse comparatif ─────────────
    st.markdown('<div class="chart-card">', unsafe_allow_html=True)
    st.markdown('<div class="chart-title">📊 Tableau de synthèse — comparaison directe</div>', unsafe_allow_html=True)

    # Construire les colonnes du tableau HTML
    header_cells = "<th style='text-align:left;padding:8px 12px;font-size:11px;color:#888;font-weight:600;border-bottom:2px solid #eee;'>Indicateur</th>"
    for i, a in enumerate(annees):
        nb_m = kpis_all[a]['nb_mois']
        suffix = f" ({nb_m}m)" if kpis_all[a]['annualise'] else ""
        header_cells += f"<th style='text-align:right;padding:8px 12px;font-size:11px;color:{COLORS[i]};font-weight:700;border-bottom:2px solid {COLORS[i]};'>{a}{suffix}</th>"
        if i > 0:
            prev_a = annees[i-1]
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
        <tr>{build_row("💰 Revenu total",      rev_vals,   fmt)}</tr>
        <tr>{build_row("📈 Marge %",           marge_vals, lambda v: f"{v:.1f}%", is_pct=True)}</tr>
        <tr>{build_row("📦 Volume total",      vol_vals,   fmt)}</tr>
        <tr>{build_row("🔢 Nb transactions",   tx_vals,    lambda v: f"{int(v):,}")}</tr>
      </tbody>
    </table>
    </div>"""
    st.markdown(table_html, unsafe_allow_html=True)
    st.markdown('</div>', unsafe_allow_html=True)

    # ── 2. KPI cards avec delta vs année précédente ─
    if len(annees) >= 2:
        st.markdown("<div style='margin-top:12px'></div>", unsafe_allow_html=True)
        # Comparer chaque paire consécutive
        for i in range(1, len(annees)):
            a_prev, a_curr = annees[i-1], annees[i]
            k_p, k_c = kpis_all[a_prev], kpis_all[a_curr]
            note_p = f" ({k_p['nb_mois']}m)" if k_p['annualise'] else ""
            note_c = f" ({k_c['nb_mois']}m)" if k_c['annualise'] else ""

            st.markdown(f'<div class="section-title">📅 {a_prev}{note_p} → {a_curr}{note_c}</div>', unsafe_allow_html=True)

            def delta_pct(curr, prev):
                if prev == 0: return 0, "—"
                d = (curr - prev) / abs(prev) * 100
                return d, f"{'▲' if d>=0 else '▼'} {abs(d):.1f}%"

            rev_d, rev_s = delta_pct(k_c['revenu'],    k_p['revenu'])
            mrg_d = k_c['marge_pct'] - k_p['marge_pct']
            vol_d, vol_s = delta_pct(k_c['volume'],    k_p['volume'])
            tx_d,  tx_s  = delta_pct(k_c['nb_tx'],     k_p['nb_tx'])

            rev_col   = "#198754" if rev_d >= 0 else RED
            marg_col  = "#198754" if mrg_d >= 0 else RED
            vol_col   = "#198754" if vol_d >= 0 else RED

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

    # ── 3. Graphiques comparatifs LOB + Segment ─────
    col1, col2 = st.columns(2)
    with col1:
        st.markdown('<div class="chart-card"><div class="chart-title">💰 Revenu par LOB — comparaison</div>', unsafe_allow_html=True)
        lob_yoy = yoy_par_lob(dfs)
        if not lob_yoy.empty:
            fig = go.Figure()
            for i, a in enumerate(annees):
                if a in lob_yoy.columns:
                    fig.add_trace(go.Bar(
                        name=a, x=lob_yoy["lob"], y=lob_yoy[a],
                        marker_color=COLORS[i], marker_line_width=0,
                        text=lob_yoy[a].apply(lambda v: fmt(v)),
                        textposition="outside", textfont=dict(size=9)
                    ))
            fig.update_layout(barmode="group", bargap=0.25)
            plotly_white(fig, 280, legend=True)
            st.plotly_chart(fig, use_container_width=True)

            # Tableau des deltas LOB
            if len(annees) >= 2:
                a_prev2, a_last = annees[-2], annees[-1]
                if a_prev2 in lob_yoy.columns and a_last in lob_yoy.columns:
                    lob_delta = lob_yoy[["lob", a_prev2, a_last]].copy()
                    lob_delta["Δ %"] = ((lob_delta[a_last] - lob_delta[a_prev2]) /
                                        lob_delta[a_prev2].replace(0, pd.NA) * 100).round(1)
                    lob_delta = lob_delta.rename(columns={"lob": "LOB", a_prev2: f"Revenu {a_prev2}", a_last: f"Revenu {a_last}"})
                    lob_delta[f"Revenu {a_prev2}"] = lob_delta[f"Revenu {a_prev2}"].apply(fmt)
                    lob_delta[f"Revenu {a_last}"]  = lob_delta[f"Revenu {a_last}"].apply(fmt)
                    lob_delta["Δ %"] = lob_delta["Δ %"].apply(
                        lambda v: f"▲ {v:.1f}%" if not pd.isna(v) and v >= 0 else (f"▼ {abs(v):.1f}%" if not pd.isna(v) else "—"))
                    st.dataframe(lob_delta, use_container_width=True, hide_index=True)
        st.markdown('</div>', unsafe_allow_html=True)

    with col2:
        st.markdown('<div class="chart-card"><div class="chart-title">📦 Volume par segment — comparaison</div>', unsafe_allow_html=True)
        seg_yoy = yoy_par_segment(dfs)
        if not seg_yoy.empty:
            fig = go.Figure()
            for i, a in enumerate(annees):
                if a in seg_yoy.columns:
                    fig.add_trace(go.Bar(
                        name=a, x=seg_yoy["segment"], y=seg_yoy[a],
                        marker_color=COLORS[i], marker_line_width=0,
                        text=seg_yoy[a].apply(lambda v: fmt(v)),
                        textposition="outside", textfont=dict(size=9)
                    ))
            fig.update_layout(barmode="group", bargap=0.25)
            plotly_white(fig, 280, legend=True)
            st.plotly_chart(fig, use_container_width=True)

            # Tableau delta segment
            if len(annees) >= 2:
                a_prev2, a_last = annees[-2], annees[-1]
                if a_prev2 in seg_yoy.columns and a_last in seg_yoy.columns:
                    seg_delta = seg_yoy[["segment", a_prev2, a_last]].copy()
                    seg_delta["Δ %"] = ((seg_delta[a_last] - seg_delta[a_prev2]) /
                                        seg_delta[a_prev2].replace(0, pd.NA) * 100).round(1)
                    seg_delta = seg_delta.rename(columns={"segment": "Segment", a_prev2: f"Volume {a_prev2}", a_last: f"Volume {a_last}"})
                    seg_delta[f"Volume {a_prev2}"] = seg_delta[f"Volume {a_prev2}"].apply(fmt)
                    seg_delta[f"Volume {a_last}"]  = seg_delta[f"Volume {a_last}"].apply(fmt)
                    seg_delta["Δ %"] = seg_delta["Δ %"].apply(
                        lambda v: f"▲ {v:.1f}%" if not pd.isna(v) and v >= 0 else (f"▼ {abs(v):.1f}%" if not pd.isna(v) else "—"))
                    st.dataframe(seg_delta, use_container_width=True, hide_index=True)
        st.markdown('</div>', unsafe_allow_html=True)

    # ── 4. Tendance mensuelle ────────────────────────
    st.markdown('<div class="chart-card"><div class="chart-title">📅 Tendance mensuelle du revenu — toutes années superposées</div><div class="chart-sub">Même mois, toutes années · permet de voir la saisonnalité et la croissance</div>', unsafe_allow_html=True)
    fig = go.Figure()
    MOIS_FR = {"01":"Jan","02":"Fév","03":"Mar","04":"Avr","05":"Mai","06":"Jun",
               "07":"Jul","08":"Aoû","09":"Sep","10":"Oct","11":"Nov","12":"Déc"}
    for i, a in enumerate(annees):
        trend = tendance_mensuelle(dfs[a])
        if not trend.empty:
            # Extraire le numéro de mois pour axe commun
            trend["mois_num"] = trend["mois"].str[-2:]
            trend["mois_label"] = trend["mois_num"].map(MOIS_FR).fillna(trend["mois_num"])
            fig.add_trace(go.Scatter(
                x=trend["mois_label"], y=trend["revenu"],
                mode="lines+markers", name=a,
                line=dict(color=COLORS[i], width=2.5),
                marker=dict(size=6, color=COLORS[i]),
                hovertemplate=f"<b>{a}</b> %{{x}}<br>Revenu: %{{y:,.0f}}<extra></extra>"
            ))
    plotly_white(fig, 280, legend=True)
    fig.update_xaxes(tickangle=0)
    st.plotly_chart(fig, use_container_width=True)
    st.markdown('</div>', unsafe_allow_html=True)



# ════════════════════════════════════════════════════
# PAGE : ANALYSE VOLUME
# ════════════════════════════════════════════════════
elif page == "Analyse volume":
    if len(annees) == 1:
        tabs_obj4 = [st.container()]
        annees_tabs4 = annees
    else:
        labels4 = [f"{a} ({nb_mois_fichier(dfs[a])}m)" if nb_mois_fichier(dfs[a])<12 else a for a in annees]
        tabs_obj4 = st.tabs(labels4)
        annees_tabs4 = annees

    for _annee_tab4, _tab_obj4 in zip(annees_tabs4, tabs_obj4):
      with _tab_obj4:
        annee = _annee_tab4
        df = dfs[annee]
    nb_mois = nb_mois_fichier(df)
    st.caption(f"{annee} · {nb_mois} mois · SINV uniquement")

    col1, col2, col3 = st.columns(3)
    with col1:
        st.markdown('<div class="chart-card"><div class="chart-title">Volume par produit</div>', unsafe_allow_html=True)
        if "segment" in df.columns:
            seg = df[df["segment"]!="Non défini"].groupby("segment")["qte"].sum().reset_index().sort_values("qte",ascending=False)
            if not seg.empty:
                fig = px.bar(seg, x="segment", y="qte", color_discrete_sequence=[BLACK], text_auto=".2s")
                fig.update_traces(marker_line_width=0)
                plotly_white(fig, 240)
                fig.update_layout(showlegend=False)
                st.plotly_chart(fig, use_container_width=True)
        st.markdown('</div>', unsafe_allow_html=True)

    with col2:
        st.markdown('<div class="chart-card"><div class="chart-title">Volume par canal</div>', unsafe_allow_html=True)
        if "canal" in df.columns:
            canal = df[df["canal"]!="Autre"].groupby("canal")["qte"].sum().reset_index().sort_values("qte",ascending=False)
            if not canal.empty:
                fig = px.pie(canal, values="qte", names="canal",
                             color_discrete_sequence=[BLACK,RED,MGRAY,"#bbb","#ddd"],
                             hole=0.4)
                fig.update_traces(textfont_size=10)
                plotly_white(fig, 240, legend=True)
                st.plotly_chart(fig, use_container_width=True)
        st.markdown('</div>', unsafe_allow_html=True)

    with col3:
        st.markdown('<div class="chart-card"><div class="chart-title">Top 10 clients — volume</div>', unsafe_allow_html=True)
        if "qte" in df.columns:
            col_nom = "raison_sociale" if "raison_sociale" in df.columns else "tiers"
            top_vol = df.groupby(col_nom)["qte"].sum().nlargest(10).reset_index()
            top_vol.columns = ["client","volume"]
            fig = px.bar(top_vol.sort_values("volume"), x="volume", y="client", orientation="h",
                         color_discrete_sequence=[RED], text_auto=".2s")
            fig.update_traces(marker_line_width=0)
            plotly_white(fig, 240)
            fig.update_layout(showlegend=False)
            st.plotly_chart(fig, use_container_width=True)
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
        cols = st.columns(len(rev_df))
        for i, (_, row) in enumerate(rev_df.iterrows()):
            with cols[i]:
                st.markdown(kpi_card_html(f"EXPOR {row['annee']}", fmt(row['revenu_expor']), f"{row['pct_total']:.1f}% du revenu total", bar_color=RED, bar_pct=row['pct_total']*2), unsafe_allow_html=True)

        st.markdown('<div class="chart-card"><div class="chart-title">Évolution revenu EXPOR</div>', unsafe_allow_html=True)
        fig = px.bar(rev_df, x="annee", y="revenu_expor", color_discrete_sequence=[RED], text_auto=".2s")
        fig.update_traces(marker_line_width=0)
        plotly_white(fig, 220)
        fig.update_layout(showlegend=False)
        st.plotly_chart(fig, use_container_width=True)
        st.markdown('</div>', unsafe_allow_html=True)

        if not expor["clients"].empty:
            st.markdown('<div class="table-card"><div class="chart-title">Clients EXPOR — liste complète</div>', unsafe_allow_html=True)
            st.dataframe(expor["clients"].sort_values(["annee","revenu"],ascending=[True,False]).style.applymap(color_marge_cell,subset=["marge_pct"]), use_container_width=True, hide_index=True)
            st.markdown('</div>', unsafe_allow_html=True)


# ════════════════════════════════════════════════════
# PAGE : ÉVOLUTION CLIENTS
# ════════════════════════════════════════════════════
elif page == "Évolution clients":
    if len(annees) < 2:
        st.info("Chargez au moins 2 fichiers.")
    else:
        for i in range(len(annees)-1):
            a_ref, a_cmp = annees[i], annees[i+1]
            st.markdown(f'<div class="section-title">📅 {a_ref} → {a_cmp}</div>', unsafe_allow_html=True)
            evol = evolution_clients(dfs[a_ref], dfs[a_cmp], a_ref, a_cmp)
            if not evol: continue

            c1,c2,c3,c4 = st.columns(4)
            c1.markdown(kpi_card_html("Clients nouveaux", len(evol['nouveaux']), f"Absents en {a_ref}", color="#198754", bar_color="#198754", bar_pct=50), unsafe_allow_html=True)
            c2.markdown(kpi_card_html("Clients disparus", len(evol['disparus']), f"Absents en {a_cmp}", color=RED, bar_color=RED, bar_pct=50), unsafe_allow_html=True)
            c3.markdown(kpi_card_html("Croissance >50%", len(evol['croissants']), "Forte hausse", color="#198754", bar_color="#198754", bar_pct=60), unsafe_allow_html=True)
            c4.markdown(kpi_card_html("Baisse >30%", len(evol['en_baisse']), "Forte baisse", color=RED, bar_color=RED, bar_pct=60), unsafe_allow_html=True)

            col1, col2 = st.columns(2)
            with col1:
                if not evol["croissants"].empty:
                    st.markdown('<div class="table-card"><div class="chart-title">📈 Forte croissance (&gt;50%)</div>', unsafe_allow_html=True)
                    st.dataframe(evol["croissants"].head(15), use_container_width=True, hide_index=True)
                    st.markdown('</div>', unsafe_allow_html=True)
                if not evol["nouveaux"].empty:
                    st.markdown('<div class="table-card"><div class="chart-title">🆕 Clients nouveaux</div>', unsafe_allow_html=True)
                    st.dataframe(evol["nouveaux"].head(15), use_container_width=True, hide_index=True)
                    st.markdown('</div>', unsafe_allow_html=True)
            with col2:
                if not evol["en_baisse"].empty:
                    st.markdown('<div class="table-card"><div class="chart-title">📉 Forte baisse (&gt;30%)</div>', unsafe_allow_html=True)
                    st.dataframe(evol["en_baisse"].head(15), use_container_width=True, hide_index=True)
                    st.markdown('</div>', unsafe_allow_html=True)
                if not evol["disparus"].empty:
                    st.markdown('<div class="table-card"><div class="chart-title">❌ Clients disparus</div>', unsafe_allow_html=True)
                    st.dataframe(evol["disparus"].head(15), use_container_width=True, hide_index=True)
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
            fp_a = fp[fp["annee"]==a]
            rev_total = dfs[a]["montant_ht"].sum()
            rev_fp = fp_a["revenu"].sum()
            pct = rev_fp/rev_total*100 if rev_total>0 else 0
            with cols[i]:
                st.markdown(kpi_card_html(f"Frais de Passage {a}", fmt(rev_fp), f"{pct:.1f}% du total · {len(fp_a)} clients", bar_color=RED, bar_pct=pct*3), unsafe_allow_html=True)

        if len(annees) > 1:
            st.markdown('<div class="chart-card"><div class="chart-title">Évolution des Frais de Passage</div>', unsafe_allow_html=True)
            fp_by = fp.groupby("annee")["revenu"].sum().reset_index()
            fig = px.bar(fp_by, x="annee", y="revenu", color_discrete_sequence=[RED], text_auto=".2s")
            fig.update_traces(marker_line_width=0)
            plotly_white(fig, 220)
            fig.update_layout(showlegend=False)
            st.plotly_chart(fig, use_container_width=True)
            st.markdown('</div>', unsafe_allow_html=True)

        st.markdown('<div class="table-card"><div class="chart-title">Liste complète — marge &gt; 90%</div>', unsafe_allow_html=True)
        cols_show = [c for c in ["annee","raison_sociale","tiers","revenu","cogs","marge","marge_pct"] if c in fp.columns]
        st.dataframe(fp[cols_show].sort_values(["annee","revenu"],ascending=[True,False]), use_container_width=True, hide_index=True)
        st.markdown('</div>', unsafe_allow_html=True)

        st.download_button("📥 Exporter Frais de Passage",
            data=exporter_flags_excel({"Frais de Passage":fp}),
            file_name="frais_passage.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
