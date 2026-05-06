import streamlit as st
import pandas as pd
import plotly.express as px

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

st.set_page_config(
    page_title="Audit Analytics — Oryx Energies",
    page_icon="📊",
    layout="wide",
)

LOGO_B64 = "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"
RED   = "#C8102E"
BLACK = "#1A1A1A"
GRAY  = "#F5F5F5"
LGRAY = "#EEEEEE"

st.markdown(f"""
<style>
  @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');
  html, body, [class*="css"] {{ font-family: 'Inter', sans-serif !important; }}

  .block-container {{ padding: 0 2rem 2rem 2rem !important; }}

  /* ── Sidebar ── */
  [data-testid="stSidebar"] {{
    background: white !important;
    border-right: 1px solid {LGRAY} !important;
    overflow: hidden !important;
    height: 100vh !important;
  }}
  [data-testid="stSidebar"] > div:first-child {{
    overflow: hidden !important;
    height: 100vh !important;
  }}
  [data-testid="stSidebar"] [data-testid="stFileUploader"] {{
    margin: 0 !important;
  }}
  [data-testid="stSidebar"] [data-testid="stFileUploader"] label {{
    display: none !important;
  }}
  [data-testid="stSidebar"] [data-testid="stFileUploaderDropzone"] {{
    background: #fff5f6 !important;
    border: 1.5px dashed {RED} !important;
    border-radius: 10px !important;
    padding: 16px 12px !important;
    text-align: center !important;
    cursor: pointer !important;
  }}
  [data-testid="stSidebar"] [data-testid="stFileUploaderDropzone"]:hover {{
    background: #ffecee !important;
  }}
  [data-testid="stSidebar"] [data-testid="stFileUploaderDropzoneInstructions"] {{
    display: none !important;
  }}
  [data-testid="stSidebar"] button[data-testid="baseButton-secondary"] {{
    background: {RED} !important;
    color: white !important;
    border: none !important;
    border-radius: 8px !important;
    font-weight: 700 !important;
    font-size: 12px !important;
    width: 100% !important;
    padding: 10px !important;
    margin-top: 4px !important;
  }}
  [data-testid="stSidebar"] * {{ color: {BLACK} !important; }}

  /* Sidebar header */
  .sb-header {{
    display: flex; align-items: center; gap: 10px;
    padding: 10px 16px 10px;
    border-bottom: 1px solid {LGRAY};
    margin-bottom: 4px;
  }}
  .sb-logo-box {{
    
    
  }}
  .sb-logo-box img {{ height: 42px; width: auto; }}
  .sb-title {{ font-size: 14px; font-weight: 800; color: {BLACK}; line-height: 1.2; letter-spacing: 0.3px; }}
  .sb-sub   {{ font-size: 10px; color: #999; }}



  /* Nav label */
  .sb-nav-label {{
    font-size: 10px; font-weight: 700; color: #999;
    letter-spacing: 1.5px; text-transform: uppercase;
    padding: 8px 16px 4px;
  }}

  /* Nav items */
  [data-testid="stSidebar"] .stRadio > div {{
    gap: 2px !important;
  }}
  [data-testid="stSidebar"] .stRadio label {{
    padding: 9px 16px !important;
    border-radius: 0 !important;
    font-size: 13px !important;
    color: #444 !important;
    font-weight: 600 !important;
    cursor: pointer;
  }}
  [data-testid="stSidebar"] .stRadio label:has(input:checked) {{
    background: #fff5f6 !important;
    color: {RED} !important;
    font-weight: 600 !important;
    border-left: 3px solid {RED};
  }}

  /* ── Top bar ── */
  .topbar {{
    background: white;
    border-bottom: 1px solid {LGRAY};
    padding: 12px 0 12px;
    display: flex; align-items: center; gap: 14px;
    margin: 0 -2rem 1.5rem;
    padding-left: 2rem; padding-right: 2rem;
  }}
  .topbar-title {{ font-size: 15px; font-weight: 700; color: {BLACK}; }}
  .topbar-pill {{
    margin-left: auto;
    background: #fff5f6; color: {RED};
    border: 1px solid #fdd;
    padding: 4px 12px; border-radius: 20px;
    font-size: 11px; font-weight: 600;
  }}

  /* ── Page title ── */
  .page-title {{
    font-size: 22px; font-weight: 800; color: {BLACK};
    border-left: 4px solid {RED};
    padding-left: 12px; margin-bottom: 2px;
  }}
  .page-caption {{ font-size: 11px; color: #aaa; margin-bottom: 1rem; padding-left: 16px; }}

  /* ── Metric cards ── */
  div[data-testid="metric-container"] {{
    background: white !important;
    border: 1px solid {LGRAY} !important;
    border-bottom: 3px solid {RED} !important;
    border-radius: 10px !important;
    padding: 14px 16px !important;
  }}
  div[data-testid="metric-container"] label {{
    font-size: 11px !important; color: #999 !important;
    text-transform: uppercase; letter-spacing: 0.5px; font-weight: 500 !important;
  }}
  div[data-testid="metric-container"] [data-testid="stMetricValue"] {{
    font-size: 26px !important; font-weight: 800 !important; color: {BLACK} !important;
  }}

  /* ── Charts card ── */
  .chart-card {{
    background: white; border: 1px solid {LGRAY};
    border-radius: 10px; padding: 14px 16px; margin-bottom: 8px;
  }}
  .chart-card-title {{
    font-size: 11px; font-weight: 600; color: #888;
    text-transform: uppercase; letter-spacing: 0.5px; margin-bottom: 10px;
  }}

  /* ── Expanders ── */
  [data-testid="stExpander"] {{
    border: 1px solid {LGRAY} !important;
    border-radius: 10px !important;
    background: white !important;
    margin-bottom: 8px;
  }}
  [data-testid="stExpander"] summary {{
    font-size: 13px !important; font-weight: 600 !important;
    padding: 12px 16px !important;
  }}

  /* ── Download button ── */
  .stDownloadButton button {{
    background: {RED} !important; color: white !important;
    border: none !important; border-radius: 6px !important;
    font-weight: 600 !important; font-size: 12px !important;
    padding: 7px 16px !important;
  }}
  .stDownloadButton button:hover {{ background: #a00d24 !important; }}

  /* ── Divider ── */
  hr {{ border-color: {LGRAY} !important; margin: 1rem 0 !important; }}

  /* ── Dataframe ── */
  [data-testid="stDataFrame"] {{
    border: 1px solid {LGRAY}; border-radius: 8px; overflow: hidden;
  }}

  /* ── Alerts ── */
  .stSuccess {{ border-left: 4px solid #198754 !important; }}
  .stError   {{ border-left: 4px solid {RED} !important; }}
  .stWarning {{ border-left: 4px solid #fd7e14 !important; }}
</style>
""", unsafe_allow_html=True)


def fmt_num(val):
    if pd.isna(val): return "—"
    try:
        if abs(val) >= 1e9: return f"{val/1e9:,.1f} Mrd"
        if abs(val) >= 1e6: return f"{val/1e6:,.1f} M"
        return f"{val:,.0f}"
    except: return str(val)


def plotly_layout(fig, height=260):
    fig.update_layout(
        height=height, margin=dict(t=5, b=5, l=5, r=5),
        paper_bgcolor="white", plot_bgcolor="white",
        font=dict(family="Inter", color=BLACK),
        xaxis=dict(gridcolor=LGRAY, linecolor=LGRAY, tickfont=dict(size=11)),
        yaxis=dict(gridcolor=LGRAY, linecolor=LGRAY, tickfont=dict(size=11)),
        showlegend=False,
    )
    return fig


# ── SIDEBAR ──────────────────────────────────────────
with st.sidebar:
    st.markdown(f"""
    <div class="sb-header">
      <div class="sb-logo-box">
        <img src="data:image/png;base64,{LOGO_B64}">
      </div>
      <div>
        <div class="sb-title">Audit Analytics</div>
      </div>
    </div>
    """, unsafe_allow_html=True)

    fichier = st.file_uploader("Charger un Flash Report", type=["xlsx","xls","csv"])
    if fichier:
        st.success(f"✓ {fichier.name}")

    st.markdown('<div class="sb-nav-label">Navigation</div>', unsafe_allow_html=True)
    page = st.radio("Navigation", ["Vue générale","Analyse clients","Flags de risque"],
                    label_visibility="collapsed")


# ── NO FILE ──────────────────────────────────────────
if not fichier:
    st.markdown(f"""
    
    """, unsafe_allow_html=True)

    st.markdown('<div class="page-title">Bienvenue</div>', unsafe_allow_html=True)
    st.markdown('<div class="page-caption">Chargez un fichier Flash Report Sage X3 pour démarrer l\'analyse.</div>', unsafe_allow_html=True)

    col1, col2, col3 = st.columns(3)
    for col, num, title, sub in [
        (col1,"1","Upload du fichier","Flash Report exporté depuis Sage X3"),
        (col2,"2","Analyse automatique","KPIs, marges et tendances calculés"),
        (col3,"3","Flags de risque","Anomalies détectées et exportables"),
    ]:
        with col:
            st.markdown(f"""
            <div style="background:white;border:1px solid {LGRAY};border-top:3px solid {RED};
                        border-radius:10px;padding:16px 18px;height:100%;">
              <div style="width:24px;height:24px;background:{RED};border-radius:50%;
                          color:white;font-size:11px;font-weight:700;display:flex;
                          align-items:center;justify-content:center;margin-bottom:10px;">{num}</div>
              <div style="font-size:13px;font-weight:600;color:{BLACK};margin-bottom:4px;">{title}</div>
              <div style="font-size:11px;color:#999;">{sub}</div>
            </div>
            """, unsafe_allow_html=True)
    st.stop()


@st.cache_data
def charger(f):
    return charger_fichier(f)

df, meta = charger(fichier)

if df is None or df.empty:
    st.error("Impossible de lire le fichier. Vérifiez le format.")
    st.stop()

if meta.get("colonnes_manquantes"):
    st.warning(f"⚠️ Colonnes critiques non détectées : {', '.join(meta['colonnes_manquantes'])}")

nb       = meta.get("nb_lignes", len(df))
nb_avoir = meta.get("nb_avoirs", 0)
st.sidebar.caption(f"{nb:,} factures SINV chargées")
if nb_avoir > 0:
    st.sidebar.caption(f"*{nb_avoir} avoirs (CRM) exclus*")

# Top bar
nom_fichier = fichier.name.replace("Requêteur_","").replace(".xlsx","").replace("_"," ")
st.markdown(f"""
<div class="topbar">
  <div class="topbar-title">Audit Analytics</div>
  <div class="topbar-pill">📁 {nom_fichier} · {nb:,} transactions</div>
</div>
""", unsafe_allow_html=True)


# ── PAGE 1 ───────────────────────────────────────────
if page == "Vue générale":
    st.markdown('<div class="page-title">Vue générale</div>', unsafe_allow_html=True)
    st.markdown('<div class="page-caption">Périmètre : factures SINV uniquement — avoirs (CRM) exclus</div>', unsafe_allow_html=True)

    kpis = kpi_generaux(df)
    c1,c2,c3,c4 = st.columns(4)
    c1.metric("Revenu total (SINV)", fmt_num(kpis["revenu_total"]))
    c2.metric("Marge % globale",     f"{kpis['marge_pct_globale']:.1f}%")
    c3.metric("Volume total",        fmt_num(kpis["volume_total"]))
    c4.metric("Nb transactions",     f"{kpis['nb_transactions']:,}")

    st.markdown("<div style='margin-top:16px'></div>", unsafe_allow_html=True)
    col1, col2 = st.columns(2)

    with col1:
        st.markdown('<div class="chart-card"><div class="chart-card-title">Tendance mensuelle du revenu</div>', unsafe_allow_html=True)
        trend = tendance_mensuelle(df)
        if not trend.empty:
            fig = px.line(trend, x="mois", y="revenu", markers=True,
                          color_discrete_sequence=[RED])
            fig.update_traces(line_width=2.5, marker_size=7, marker_color=RED)
            fig.update_xaxes(tickangle=45, title="")
            fig.update_yaxes(title="")
            plotly_layout(fig, 240)
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("Données de date non disponibles.")
        st.markdown('</div>', unsafe_allow_html=True)

    with col2:
        st.markdown('<div class="chart-card"><div class="chart-card-title">Revenu par LOB</div>', unsafe_allow_html=True)
        lob_df = revenu_par_lob(df)
        if not lob_df.empty:
            lob_plot = lob_df[lob_df["lob"] != "Autre"]
            fig = px.bar(lob_plot, x="lob", y="revenu",
                         color_discrete_sequence=[RED], text_auto=".2s")
            fig.update_traces(marker_line_width=0)
            fig.update_xaxes(title=""); fig.update_yaxes(title="")
            plotly_layout(fig, 240)
            st.plotly_chart(fig, use_container_width=True)
        st.markdown('</div>', unsafe_allow_html=True)

    col3, col4 = st.columns(2)

    with col3:
        st.markdown('<div class="chart-card"><div class="chart-card-title">Revenu par segment (hors Non défini)</div>', unsafe_allow_html=True)
        seg_df = revenu_par_segment(df)
        if not seg_df.empty:
            seg_plot = seg_df[seg_df["segment"] != "Non défini"]
            if not seg_plot.empty:
                fig = px.bar(seg_plot, x="revenu", y="segment", orientation="h",
                             color_discrete_sequence=[RED], text_auto=".2s")
                fig.update_traces(marker_line_width=0)
                fig.update_xaxes(title=""); fig.update_yaxes(title="")
                plotly_layout(fig, max(200, len(seg_plot)*48))
                st.plotly_chart(fig, use_container_width=True)
            total_rev = seg_df["revenu"].sum()
            non_def   = seg_df[seg_df["segment"]=="Non défini"]["revenu"].sum()
            if total_rev > 0:
                pct_nd = non_def / total_rev * 100
                st.caption(f"⚠️ {pct_nd:.0f}% du revenu sans segment — classification produit absente dans Sage X3")
        st.markdown('</div>', unsafe_allow_html=True)

    with col4:
        st.markdown('<div class="chart-card"><div class="chart-card-title">Revenu par canal de vente</div>', unsafe_allow_html=True)
        canal_df = revenu_par_canal(df)
        if not canal_df.empty:
            canal_plot = canal_df[canal_df["canal"] != "Autre"]
            fig = px.bar(canal_plot, x="canal", y="revenu",
                         color_discrete_sequence=[BLACK], text_auto=".2s")
            fig.update_traces(marker_line_width=0)
            fig.update_xaxes(title=""); fig.update_yaxes(title="")
            plotly_layout(fig, max(200, len(canal_plot)*48))
            st.plotly_chart(fig, use_container_width=True)
        st.markdown('</div>', unsafe_allow_html=True)


# ── PAGE 2 ───────────────────────────────────────────
elif page == "Analyse clients":
    st.markdown('<div class="page-title">Analyse clients</div>', unsafe_allow_html=True)
    st.markdown('<div class="page-caption">Périmètre : factures SINV uniquement</div>', unsafe_allow_html=True)

    col1, col2 = st.columns([2,1])

    with col1:
        st.markdown('<div class="chart-card"><div class="chart-card-title">Top 10 clients par revenu</div>', unsafe_allow_html=True)
        top = top_clients(df, 10)
        if not top.empty:
            def color_marge(val):
                try:
                    v = float(val)
                    if v < 0:   return f"color:{RED};font-weight:600"
                    elif v < 5: return "color:#fd7e14"
                    return "color:#198754"
                except: return ""
            st.dataframe(top.style.map(color_marge, subset=["marge_pct"]),
                         use_container_width=True, hide_index=True)
        st.markdown('</div>', unsafe_allow_html=True)

    with col2:
        st.markdown('<div class="chart-card"><div class="chart-card-title">Concentration client</div>', unsafe_allow_html=True)
        conc = flag_concentration_client(df)
        if conc:
            pct = conc["pct_top3"]
            st.metric("Top 3 / Revenu total", f"{pct}%",
                      delta="Seuil : 50%", delta_color="inverse")
            if conc["flag"]:
                st.error(f"🔴 Concentration élevée : {pct}% > 50%")
            else:
                st.success(f"✅ OK : {pct}% < 50%")
            st.dataframe(conc["top3"], hide_index=True, use_container_width=True)
        st.markdown('</div>', unsafe_allow_html=True)

    st.markdown("<div style='margin-top:8px'></div>", unsafe_allow_html=True)
    col3, col4 = st.columns(2)

    with col3:
        st.markdown('<div class="chart-card"><div class="chart-card-title">Clients à marge décroissante (2 mois consécutifs)</div>', unsafe_allow_html=True)
        decr = flag_marge_decroissante(df)
        if decr.empty:
            st.success("Aucun client avec marge décroissante 2 mois de suite.")
        else:
            st.warning(f"{len(decr)} client(s) en baisse continue")
            st.dataframe(decr, use_container_width=True, hide_index=True)
        st.markdown('</div>', unsafe_allow_html=True)

    with col4:
        st.markdown('<div class="chart-card"><div class="chart-card-title">Clients à marge négative (cumul)</div>', unsafe_allow_html=True)
        if "tiers" in df.columns and "montant_ht" in df.columns:
            col_nom = "raison_sociale" if "raison_sociale" in df.columns else "tiers"
            cli_neg = df.groupby(col_nom).agg(
                revenu=("montant_ht","sum"), marge=("marge_total","sum")
            ).reset_index()
            cli_neg["marge_pct"] = (cli_neg["marge"] / cli_neg["revenu"].replace(0,pd.NA) * 100).round(2)
            cli_neg_f = cli_neg[cli_neg["marge_pct"] < 0].sort_values("marge_pct")
            if cli_neg_f.empty:
                st.success("Aucun client à marge négative globale.")
            else:
                st.error(f"{len(cli_neg_f)} client(s) à marge négative")
                st.dataframe(cli_neg_f, use_container_width=True, hide_index=True)
        st.markdown('</div>', unsafe_allow_html=True)


# ── PAGE 3 ───────────────────────────────────────────
elif page == "Flags de risque":
    st.markdown('<div class="page-title">Flags de risque</div>', unsafe_allow_html=True)
    st.markdown('<div class="page-caption">Périmètre : factures SINV uniquement</div>', unsafe_allow_html=True)

    resume = resume_flags(df)
    c1,c2,c3,c4 = st.columns(4)
    c1.metric("🔴 Marge négative",     resume["nb_marge_negative"])
    c2.metric("🔴 COGS = 0",           resume["nb_cogs_zero"])
    c3.metric("🟠 Doublons",           resume["nb_doublons"])
    c4.metric("🟠 Marge décroissante", resume["nb_marge_decroissante"])

    st.markdown("<div style='margin-top:16px'></div>", unsafe_allow_html=True)

    with st.expander("🔴 Transactions à marge négative", expanded=True):
        marge_neg = flag_marge_negative(df)
        if marge_neg.empty:
            st.success("Aucune transaction à marge négative.")
        else:
            st.error(f"{len(marge_neg)} transaction(s) détectée(s)")
            st.dataframe(marge_neg, use_container_width=True, hide_index=True)
            st.download_button("📥 Exporter",
                data=exporter_flags_excel({"Marge négative": marge_neg}),
                file_name="flag_marge_negative.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")

    with st.expander("🔴 Transactions COGS = 0", expanded=True):
        cogs_zero = flag_cogs_zero(df)
        if cogs_zero.empty:
            st.success("Aucune anomalie COGS.")
        else:
            st.error(f"{len(cogs_zero)} ligne(s) avec COGS = 0 et CA > 0")
            st.dataframe(cogs_zero, use_container_width=True, hide_index=True)
            st.download_button("📥 Exporter",
                data=exporter_flags_excel({"COGS zéro": cogs_zero}),
                file_name="flag_cogs_zero.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")

    with st.expander("🟠 Doublons de factures", expanded=True):
        doublons = flag_doublons(df)
        if doublons.empty:
            st.success("Aucun doublon détecté.")
        else:
            st.warning(f"{len(doublons)} ligne(s) en doublon potentiel")
            st.dataframe(doublons, use_container_width=True, hide_index=True)
            st.download_button("📥 Exporter",
                data=exporter_flags_excel({"Doublons": doublons}),
                file_name="flag_doublons.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")

    with st.expander("🟠 Concentration client", expanded=False):
        conc = flag_concentration_client(df)
        if conc:
            pct = conc["pct_top3"]
            if conc["flag"]:
                st.warning(f"Top 3 clients = {pct}% du revenu (seuil : {conc['seuil']}%)")
            else:
                st.info(f"Top 3 clients = {pct}% du revenu — OK")
            st.dataframe(conc["top3"], use_container_width=True, hide_index=True)

    st.divider()
    with st.expander("📥 Export complet tous les flags"):
        tous = {
            "Marge négative":     flag_marge_negative(df),
            "COGS zéro":          flag_cogs_zero(df),
            "Doublons":           flag_doublons(df),
            "Marge décroissante": flag_marge_decroissante(df),
        }
        st.download_button("📥 Exporter tous les flags",
            data=exporter_flags_excel(tous),
            file_name="audit_flags_complet.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
