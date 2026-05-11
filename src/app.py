"""
Outil d'Audit Interne — Oryx Energies Group
Dashboard d'analyse Flash Report Sage X3
"""

import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots

from ingestion import charger_fichier
from multi_year import detecter_annee, kpi_annee, yoy_par_lob, yoy_par_segment, evolution_clients
from kpis import kpi_generaux, revenu_par_lob, revenu_par_segment, revenu_par_canal, tendance_mensuelle, top_clients
from flags import flag_marge_negative, flag_cogs_zero, flag_doublons, flag_concentration_client, flag_marge_decroissante
from export import exporter_flags_excel
from ageing_credit_risk import (
    charger_ageing, kpi_ageing, ageing_par_lob, ageing_par_tranche,
    top_clients_risque, flag_overdue_critique, flag_depassement_credit,
    flag_balance_negative, flag_180_plus, flag_securite_expiree,
    resume_flags_ageing
)
from detailed_aged_balance import (
    charger_detailed_aged, kpi_detailed, top_clients_overdue,
    transactions_par_type, flag_factures_impayees_60j,
    flag_paiements_sans_facture, flag_solde_negatif,
    flag_echeances_depassees, resume_flags_detailed
)
from general_balance import (
    charger_general_balance, kpi_general, balance_par_classe,
    top_comptes_mouvement, flag_comptes_desequilibres,
    flag_comptes_solde_inhabituel, flag_comptes_sans_mouvement,
    flag_variation_significative, resume_flags_general
)

# ---------------------------------------------------------------------------
# Config page
# ---------------------------------------------------------------------------
st.set_page_config(
    page_title="Oryx Energies — Audit Analytics",
    page_icon="🛢️",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ---------------------------------------------------------------------------
# Palette couleurs Oryx
# ---------------------------------------------------------------------------
ORYX_BLUE   = "#003366"
ORYX_ORANGE = "#FF6600"
ORYX_LIGHT  = "#F0F4FA"
GREEN       = "#2ECC71"
RED         = "#E74C3C"
AMBER       = "#F39C12"

# ---------------------------------------------------------------------------
# CSS global
# ---------------------------------------------------------------------------
st.markdown("""
<style>
    .main { background-color: #F8FAFC; }
    .stMetric { background: white; border-radius: 10px; padding: 12px; box-shadow: 0 1px 4px rgba(0,0,0,0.08); }
    .flag-red   { background: #FFF0F0; border-left: 4px solid #E74C3C; padding: 10px 16px; border-radius: 6px; margin: 6px 0; }
    .flag-amber { background: #FFFBF0; border-left: 4px solid #F39C12; padding: 10px 16px; border-radius: 6px; margin: 6px 0; }
    .flag-green { background: #F0FFF4; border-left: 4px solid #2ECC71; padding: 10px 16px; border-radius: 6px; margin: 6px 0; }
    .section-title { font-size: 1.1rem; font-weight: 700; color: #003366; margin: 18px 0 8px 0; }
    .strata-badge { display: inline-block; padding: 2px 10px; border-radius: 12px; font-size: 0.78rem; font-weight: 600; }
    div[data-testid="metric-container"] { background: white; border-radius: 10px; padding: 14px; box-shadow: 0 1px 4px rgba(0,0,0,0.07); }
</style>
""", unsafe_allow_html=True)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def fmt_rwf(val: float) -> str:
    """Formate en milliards/millions RWF."""
    if abs(val) >= 1e9:
        return f"{val/1e9:.1f} Mrd RWF"
    if abs(val) >= 1e6:
        return f"{val/1e6:.1f} M RWF"
    return f"{val:,.0f} RWF"


def fmt_pct(val: float) -> str:
    return f"{val:.1f}%"


def delta_color(val: float) -> str:
    return GREEN if val >= 0 else RED


def badge_flag(label: str, niveau: str) -> str:
    colors = {"red": ("#E74C3C", "white"), "amber": ("#F39C12", "white"), "green": ("#2ECC71", "white")}
    bg, fg = colors.get(niveau, ("#999", "white"))
    return f'<span class="strata-badge" style="background:{bg};color:{fg}">{label}</span>'


def plot_bar(df, x, y, title, color=ORYX_BLUE, orientation="v", text_col=None):
    fig = px.bar(df, x=x, y=y, title=title, orientation=orientation,
                 text=text_col or y,
                 color_discrete_sequence=[color])
    fig.update_traces(texttemplate="%{text:,.0f}", textposition="outside")
    fig.update_layout(showlegend=False, plot_bgcolor="white", paper_bgcolor="white",
                      title_font_color=ORYX_BLUE, margin=dict(t=40, b=20, l=10, r=10))
    fig.update_xaxes(showgrid=False)
    fig.update_yaxes(showgrid=True, gridcolor="#EEE")
    return fig


def plot_line(df, x, y, title, color=ORYX_ORANGE):
    fig = px.line(df, x=x, y=y, title=title, markers=True,
                  color_discrete_sequence=[color])
    fig.update_layout(plot_bgcolor="white", paper_bgcolor="white",
                      title_font_color=ORYX_BLUE, margin=dict(t=40, b=20, l=10, r=10))
    fig.update_xaxes(showgrid=False)
    fig.update_yaxes(showgrid=True, gridcolor="#EEE")
    return fig


# ---------------------------------------------------------------------------
# Sidebar — upload fichiers
# ---------------------------------------------------------------------------

with st.sidebar:
    st.image("https://upload.wikimedia.org/wikipedia/commons/thumb/a/a7/Camponotus_flavomarginatus_ant.jpg/1px-transparent.png", width=1)  # placeholder
    st.markdown(f"## 🛢️ Oryx Energies\n### Audit Analytics")
    st.divider()

    st.markdown("**📂 Upload Flash Reports**")
    st.caption("Uploadez 1 à 3 fichiers (années différentes) pour l'analyse multi-années.")

    fichiers = st.file_uploader(
        "Fichiers Sage X3 (.xlsx / .csv)",
        type=["xlsx", "csv"],
        accept_multiple_files=True,
        label_visibility="collapsed",
    )

    st.divider()

    if fichiers:
        st.markdown("**Fichiers chargés :**")
        for f in fichiers:
            annee = detecter_annee(f.name)
            st.markdown(f"- `{f.name}` → **{annee}**")

    st.divider()
    st.markdown("**📂 Upload Ageing Credit Risk**")
    st.caption("Fichier Crystal Reports .xls — 1 feuille par année (2024/2025/2026)")
    fichier_ageing = st.file_uploader(
        "Ageing Credit Risk (.xls / .xlsx)",
        type=["xls", "xlsx"],
        accept_multiple_files=False,
        label_visibility="collapsed",
        key="ageing_upload",
    )
    st.divider()
    st.markdown("**📂 Upload Detailed Aged Balance**")
    fichier_detailed = st.file_uploader(
        "Detailed Aged Balance (.xls / .xlsx)",
        type=["xls", "xlsx"],
        accept_multiple_files=False,
        label_visibility="collapsed",
        key="detailed_upload",
    )
    st.divider()
    st.markdown("**📂 Upload General Balance**")
    fichier_general = st.file_uploader(
        "General Balance (.xls / .xlsx)",
        type=["xls", "xlsx"],
        accept_multiple_files=False,
        label_visibility="collapsed",
        key="general_upload",
    )
    st.divider()
    st.caption("Oryx Energies Group — Internal Audit\nMai 2026")


# ---------------------------------------------------------------------------
# Chargement et validation
# ---------------------------------------------------------------------------

if not fichiers:
    st.markdown(f"""
    <div style="text-align:center; padding: 80px 20px;">
        <h1 style="color:{ORYX_BLUE}">🛢️ Oryx Energies — Audit Analytics</h1>
        <p style="font-size:1.1rem; color:#666;">
            Uploadez un ou plusieurs fichiers Flash Report Sage X3 dans le panneau de gauche<br>
            pour démarrer l'analyse.
        </p>
        <div style="background:{ORYX_LIGHT}; border-radius:12px; padding:24px; margin-top:32px; text-align:left; max-width:500px; margin-left:auto; margin-right:auto;">
            <b>Formats acceptés :</b> .xlsx, .csv (Sage X3)<br>
            <b>Multi-années :</b> uploadez jusqu'à 3 fichiers<br>
            <b>Filiale test :</b> RW01 Rwanda
        </div>
    </div>
    """, unsafe_allow_html=True)
    st.stop()

# Charger tous les fichiers
@st.cache_data(show_spinner="Chargement des données Sage X3...")
def charger_tous(fichiers_data: list) -> dict:
    """Cache par contenu de fichier."""
    resultats = {}
    for nom, contenu in fichiers_data:
        import io as _io

        class FakeFichier:
            def __init__(self, n, c):
                self.name = n
                self._c = c
            def read(self):
                return self._c

        fake = FakeFichier(nom, contenu)
        segments, meta = charger_fichier(fake)
        if segments is not None:
            annee = detecter_annee(nom)
            resultats[annee] = {"segments": segments, "meta": meta, "nom": nom}
    return resultats

# Lire les bytes une fois (Streamlit file_uploader ne permet pas re-read après cache)
fichiers_data = [(f.name, f.read()) for f in fichiers]
all_data = charger_tous(fichiers_data)

if not all_data:
    st.error("Aucun fichier n'a pu être chargé. Vérifiez le format.")
    st.stop()

annees_dispo = sorted(all_data.keys())
annee_principale = annees_dispo[-1]  # année la plus récente = vue principale

# DataFrames principaux (vraies ventes uniquement)
dfs_ventes = {a: all_data[a]["segments"]["ventes"] for a in annees_dispo}
df = dfs_ventes[annee_principale]

# Résumé chargement dans sidebar
with st.sidebar:
    for annee in annees_dispo:
        stats = all_data[annee]["segments"]["stats"]
        st.markdown(f"**{annee}** — {stats['nb_ventes']} ventes | {stats['nb_avoirs']} avoirs | {stats['nb_frais_passage']} frais passage")


# ---------------------------------------------------------------------------
# Chargement Ageing Credit Risk
# ---------------------------------------------------------------------------

@st.cache_data(show_spinner="Chargement Ageing Credit Risk...")
def charger_ageing_cache(nom, contenu):
    class FakeFichier:
        def __init__(self, n, c): self.name = n; self._c = c
        def read(self): return self._c
    return charger_ageing(FakeFichier(nom, contenu))

data_ageing = None
if fichier_ageing is not None:
    try:
        contenu_ageing = fichier_ageing.read()
        data_ageing = charger_ageing_cache(fichier_ageing.name, contenu_ageing)
        with st.sidebar:
            st.markdown(f"**Ageing chargé :** {', '.join(data_ageing['annees'])} ({sum(len(data_ageing[a]['df']) for a in data_ageing['annees'])} clients)")
    except Exception as e:
        st.sidebar.error(f"Erreur Ageing : {e}")

# ---------------------------------------------------------------------------
# Chargement Detailed Aged Balance
# ---------------------------------------------------------------------------

@st.cache_data(show_spinner="Chargement Detailed Aged Balance...")
def charger_detailed_cache(nom, contenu):
    class FakeFichier:
        def __init__(self, n, c): self.name = n; self._c = c
        def read(self): return self._c
    return charger_detailed_aged(FakeFichier(nom, contenu))

data_detailed = None
if fichier_detailed is not None:
    try:
        data_detailed = charger_detailed_cache(fichier_detailed.name, fichier_detailed.read())
        with st.sidebar:
            st.markdown(f"**Detailed Aged chargé :** {', '.join(data_detailed['annees'])}")
    except Exception as e:
        st.sidebar.error(f"Erreur Detailed Aged : {e}")

# ---------------------------------------------------------------------------
# Chargement General Balance
# ---------------------------------------------------------------------------

@st.cache_data(show_spinner="Chargement General Balance...")
def charger_general_cache(nom, contenu):
    class FakeFichier:
        def __init__(self, n, c): self.name = n; self._c = c
        def read(self): return self._c
    return charger_general_balance(FakeFichier(nom, contenu))

data_general = None
if fichier_general is not None:
    try:
        data_general = charger_general_cache(fichier_general.name, fichier_general.read())
        with st.sidebar:
            st.markdown(f"**General Balance chargé :** {', '.join(data_general['annees'])}")
    except Exception as e:
        st.sidebar.error(f"Erreur General Balance : {e}")

# ---------------------------------------------------------------------------
# Onglets principaux
# ---------------------------------------------------------------------------

tab_vue, tab_clients, tab_flags, tab_avoirs, tab_fp, tab_yoy, tab_ageing, tab_detailed, tab_general = st.tabs([
    "📊 Vue Générale",
    "👥 Clients",
    "🚨 Flags de Risque",
    "📋 Avoirs (CRM)",
    "🔄 Frais de Passage",
    "📈 Multi-Années",
    "⚠️ Ageing Credit Risk",
    "📋 Detailed Aged Balance",
    "⚖️ General Balance",
])


# ===========================================================================
# TAB 1 — VUE GÉNÉRALE
# ===========================================================================
with tab_vue:
    st.markdown(f"### Vue générale — Flash Report {annee_principale}")
    st.caption(f"Source : {all_data[annee_principale]['nom']} · Périmètre : SINV compte 31 (vraies ventes uniquement)")

    if df.empty:
        st.warning("Aucune ligne de vente (SINV compte 31) dans ce fichier.")
    else:
        kpis = kpi_generaux(df)

        # KPIs principaux
        c1, c2, c3, c4, c5 = st.columns(5)
        c1.metric("💰 Revenu total", fmt_rwf(kpis["revenu_total"]))
        c2.metric("📦 Volume total", f"{kpis['volume_total']:,.0f} L")
        c3.metric("📈 Marge %", fmt_pct(kpis["marge_pct_globale"]),
                  help="Calculée sur les lignes COGS > 0 uniquement")
        c4.metric("💵 Marge totale", fmt_rwf(kpis["marge_totale"]))
        c5.metric("🧾 Transactions", f"{kpis['nb_transactions']:,}")

        st.divider()

        # Tendance mensuelle
        tend = tendance_mensuelle(df)
        if not tend.empty:
            col_g, col_d = st.columns(2)
            with col_g:
                fig_tend = plot_line(tend, "mois", "revenu",
                                     f"Tendance mensuelle du revenu — {annee_principale}")
                fig_tend.update_traces(
                    text=[fmt_rwf(v) for v in tend["revenu"]],
                    textposition="top center", mode="lines+markers+text",
                    textfont_size=10,
                )
                st.plotly_chart(fig_tend, use_container_width=True)

            with col_d:
                lob_df = revenu_par_lob(df)
                if not lob_df.empty:
                    fig_lob = px.bar(lob_df, x="lob", y="revenu",
                                     title="Revenu par LOB",
                                     color="marge_pct",
                                     color_continuous_scale=["#E74C3C", "#F39C12", "#2ECC71"],
                                     text="revenu")
                    fig_lob.update_traces(texttemplate="%{text:,.0f}", textposition="outside")
                    fig_lob.update_layout(plot_bgcolor="white", paper_bgcolor="white",
                                          coloraxis_colorbar_title="Marge %",
                                          margin=dict(t=40, b=20))
                    st.plotly_chart(fig_lob, use_container_width=True)

        st.divider()

        col_l, col_r = st.columns(2)
        with col_l:
            seg_df = revenu_par_segment(df)
            if not seg_df.empty:
                fig_seg = px.bar(seg_df, x="revenu", y="segment", orientation="h",
                                 title="Revenu par Segment",
                                 color="marge_pct",
                                 color_continuous_scale=["#E74C3C", "#F39C12", "#2ECC71"],
                                 text="revenu")
                fig_seg.update_traces(texttemplate="%{text:,.0f}", textposition="outside")
                fig_seg.update_layout(plot_bgcolor="white", paper_bgcolor="white",
                                      yaxis={"categoryorder": "total ascending"},
                                      margin=dict(t=40, b=20))
                st.plotly_chart(fig_seg, use_container_width=True)

        with col_r:
            canal_df = revenu_par_canal(df)
            if not canal_df.empty:
                fig_canal = px.bar(canal_df, x="canal", y="revenu",
                                   title="Revenu par Canal de Vente",
                                   color_discrete_sequence=[ORYX_BLUE],
                                   text="revenu")
                fig_canal.update_traces(texttemplate="%{text:,.0f}", textposition="outside")
                fig_canal.update_layout(plot_bgcolor="white", paper_bgcolor="white",
                                        margin=dict(t=40, b=20))
                st.plotly_chart(fig_canal, use_container_width=True)


# ===========================================================================
# TAB 2 — CLIENTS
# ===========================================================================
with tab_clients:
    st.markdown(f"### Analyse clients — {annee_principale}")
    st.caption("Périmètre : SINV compte 31 uniquement")

    if df.empty:
        st.warning("Aucune donnée disponible.")
    else:
        top10 = top_clients(df, n=10)
        conc  = flag_concentration_client(df)

        col_t, col_p = st.columns([3, 2])

        with col_t:
            st.markdown('<div class="section-title">Top 10 clients par revenu</div>', unsafe_allow_html=True)
            if not top10.empty:
                # Formatage affichage
                top10_disp = top10.copy()
                top10_disp["revenu"] = top10_disp["revenu"].apply(fmt_rwf)
                top10_disp["marge"] = top10_disp["marge"].apply(fmt_rwf)
                top10_disp["marge_pct"] = top10_disp["marge_pct"].apply(lambda x: f"{x:.1f}%")
                cols_show = [c for c in ["raison_sociale", "tiers", "revenu", "marge_pct", "marge", "nb_transactions"] if c in top10_disp.columns]
                st.dataframe(top10_disp[cols_show], use_container_width=True, hide_index=True)

        with col_p:
            st.markdown('<div class="section-title">Concentration client</div>', unsafe_allow_html=True)
            if conc:
                pct = conc["pct_top3"]
                seuil = conc["seuil"]
                flag_on = conc["flag"]

                niveau = "red" if flag_on else "green"
                label  = f"⚠️ {pct}% > seuil {seuil}%" if flag_on else f"✅ {pct}% < seuil {seuil}%"
                st.markdown(f'<div class="flag-{niveau}">{label}</div>', unsafe_allow_html=True)

                top3 = conc["top3"]
                rev_total = df["montant_ht"].sum()
                rev_top3  = top3["revenu"].sum()
                rev_reste = rev_total - rev_top3

                pie_data = pd.concat([
                    top3.rename(columns={"client": "label", "revenu": "valeur"}),
                    pd.DataFrame([{"label": "Autres clients", "valeur": rev_reste}])
                ], ignore_index=True)

                fig_pie = px.pie(pie_data, names="label", values="valeur",
                                 title="Top 3 vs reste",
                                 color_discrete_sequence=[ORYX_ORANGE, "#FF9944", "#FFCC88", "#CCDDEE"])
                fig_pie.update_layout(paper_bgcolor="white", margin=dict(t=40, b=10))
                st.plotly_chart(fig_pie, use_container_width=True)

        st.divider()

        # Clients marge négative
        st.markdown('<div class="section-title">Clients avec marge négative</div>', unsafe_allow_html=True)
        neg = flag_marge_negative(df)
        if neg.empty:
            st.markdown('<div class="flag-green">✅ Aucun client à marge négative</div>', unsafe_allow_html=True)
        else:
            st.markdown(f'<div class="flag-red">🔴 {len(neg)} transactions à marge négative</div>', unsafe_allow_html=True)
            st.dataframe(neg, use_container_width=True, hide_index=True)

        st.divider()

        # Marge décroissante
        st.markdown('<div class="section-title">Clients avec marge décroissante (≥ 2 mois consécutifs)</div>', unsafe_allow_html=True)
        from flags import flag_marge_decroissante
        dec = flag_marge_decroissante(df)
        if dec.empty:
            st.markdown('<div class="flag-green">✅ Aucune tendance décroissante détectée</div>', unsafe_allow_html=True)
        else:
            st.markdown(f'<div class="flag-amber">🟠 {len(dec)} clients avec marge en baisse</div>', unsafe_allow_html=True)
            st.dataframe(dec, use_container_width=True, hide_index=True)


# ===========================================================================
# TAB 3 — FLAGS DE RISQUE
# ===========================================================================
with tab_flags:
    st.markdown(f"### Flags de risque — {annee_principale}")
    st.caption("Périmètre : SINV compte 31 · Chaque tableau est exportable en Excel")

    if df.empty:
        st.warning("Aucune donnée disponible.")
    else:
        neg_df  = flag_marge_negative(df)
        cogs_df = flag_cogs_zero(df)
        dup_df  = flag_doublons(df)
        conc    = flag_concentration_client(df)
        dec_df  = flag_marge_decroissante(df)

        # Résumé flags
        f1, f2, f3, f4, f5 = st.columns(5)
        f1.metric("🔴 Marge négative",    len(neg_df),  delta=None)
        f2.metric("🔴 COGS = 0",          len(cogs_df), delta=None)
        f3.metric("🟠 Doublons factures", len(dup_df),  delta=None)
        f4.metric("🟠 Concentration",     f"{conc.get('pct_top3', 0)}%", delta=None)
        f5.metric("🟠 Marge décroissante",len(dec_df),  delta=None)

        st.divider()

        # --- Flag 1 : Marge négative ---
        with st.expander(f"🔴 Marge négative — {len(neg_df)} transactions", expanded=len(neg_df) > 0):
            if neg_df.empty:
                st.markdown('<div class="flag-green">✅ Aucune transaction à marge négative</div>', unsafe_allow_html=True)
            else:
                st.markdown('<div class="flag-red">🔴 Transactions avec marge totale < 0 — à investiguer</div>', unsafe_allow_html=True)
                st.dataframe(neg_df, use_container_width=True, hide_index=True)

        # --- Flag 2 : COGS = 0 ---
        with st.expander(f"🔴 COGS = 0 — {len(cogs_df)} lignes", expanded=len(cogs_df) > 0):
            if cogs_df.empty:
                st.markdown('<div class="flag-green">✅ Aucune anomalie COGS = 0 sur compte 31</div>', unsafe_allow_html=True)
            else:
                st.markdown('<div class="flag-red">🔴 Lignes avec COGS = 0 et CA > 0 — anomalie données Sage</div>', unsafe_allow_html=True)
                st.dataframe(cogs_df, use_container_width=True, hide_index=True)

        # --- Flag 3 : Doublons ---
        with st.expander(f"🟠 Doublons de factures — {len(dup_df)} lignes", expanded=len(dup_df) > 0):
            if dup_df.empty:
                st.markdown('<div class="flag-green">✅ Aucun doublon détecté</div>', unsafe_allow_html=True)
            else:
                st.markdown('<div class="flag-amber">🟠 Même Tiers + Montant + Date + Article — vérifier si facturation double</div>', unsafe_allow_html=True)
                st.dataframe(dup_df, use_container_width=True, hide_index=True)

        # --- Flag 4 : Concentration ---
        with st.expander(f"🟠 Concentration client — Top 3 = {conc.get('pct_top3', 0)}%", expanded=False):
            if conc:
                flag_c = conc["flag"]
                niveau = "amber" if flag_c else "green"
                msg    = f"{'🟠 Concentration élevée' if flag_c else '✅ Concentration normale'} — Top 3 = {conc['pct_top3']}% (seuil : {conc['seuil']}%)"
                st.markdown(f'<div class="flag-{niveau}">{msg}</div>', unsafe_allow_html=True)
                st.dataframe(conc["top3"], use_container_width=True, hide_index=True)

        # --- Flag 5 : Marge décroissante ---
        with st.expander(f"🟠 Marge décroissante — {len(dec_df)} clients", expanded=len(dec_df) > 0):
            if dec_df.empty:
                st.markdown('<div class="flag-green">✅ Aucun client avec marge en baisse continue</div>', unsafe_allow_html=True)
            else:
                st.markdown('<div class="flag-amber">🟠 Marge % en baisse sur 2+ mois consécutifs</div>', unsafe_allow_html=True)
                st.dataframe(dec_df, use_container_width=True, hide_index=True)

        st.divider()

        # Export Excel
        st.markdown("**📥 Exporter tous les flags**")
        flags_dict = {
            "Marge_Negative":    neg_df,
            "COGS_Zero":         cogs_df,
            "Doublons":          dup_df,
            "Concentration_Top3": conc.get("top3", pd.DataFrame()),
            "Marge_Decroissante": dec_df,
        }
        excel_bytes = exporter_flags_excel(flags_dict)
        st.download_button(
            label="⬇️ Télécharger flags en Excel",
            data=excel_bytes,
            file_name=f"flags_audit_{annee_principale}.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )


# ===========================================================================
# TAB 4 — AVOIRS (CRM)
# ===========================================================================
with tab_avoirs:
    st.markdown(f"### Avoirs (Credit Notes) — {annee_principale}")
    st.caption("Périmètre : type facture = CRM · Affiché séparément, non inclus dans les KPIs principaux")

    df_avoirs = all_data[annee_principale]["segments"]["avoirs"]

    if df_avoirs.empty:
        st.info("Aucun avoir dans ce fichier.")
    else:
        # KPIs avoirs
        rev_avoirs  = df_avoirs["montant_ht"].sum() if "montant_ht" in df_avoirs.columns else 0
        nb_avoirs   = len(df_avoirs)
        nb_clients  = df_avoirs["tiers"].nunique() if "tiers" in df_avoirs.columns else 0
        rev_ventes  = df["montant_ht"].sum() if "montant_ht" in df.columns else 1
        pct_avoirs  = abs(rev_avoirs) / rev_ventes * 100 if rev_ventes else 0

        a1, a2, a3, a4 = st.columns(4)
        a1.metric("📋 Nb avoirs",       f"{nb_avoirs:,}")
        a2.metric("💸 Montant total",   fmt_rwf(rev_avoirs),
                  help="Négatif = remboursement client")
        a3.metric("👥 Clients concernés", f"{nb_clients:,}")
        a4.metric("% du CA ventes",     fmt_pct(pct_avoirs),
                  help="Avoirs / Revenu ventes SINV compte 31")

        st.divider()

        # Avoirs par LOB
        if "lob" in df_avoirs.columns and "montant_ht" in df_avoirs.columns:
            col_l, col_r = st.columns(2)
            with col_l:
                av_lob = df_avoirs.groupby("lob")["montant_ht"].sum().reset_index()
                fig_av = px.bar(av_lob, x="lob", y="montant_ht",
                                title="Avoirs par LOB",
                                color_discrete_sequence=[ORYX_ORANGE],
                                text="montant_ht")
                fig_av.update_traces(texttemplate="%{text:,.0f}", textposition="outside")
                fig_av.update_layout(plot_bgcolor="white", paper_bgcolor="white", margin=dict(t=40))
                st.plotly_chart(fig_av, use_container_width=True)

            with col_r:
                if "mois" in df_avoirs.columns:
                    av_mois = df_avoirs.groupby("mois")["montant_ht"].sum().reset_index().sort_values("mois")
                    fig_av_m = plot_line(av_mois, "mois", "montant_ht",
                                         "Évolution mensuelle des avoirs", color=RED)
                    st.plotly_chart(fig_av_m, use_container_width=True)

        st.divider()

        # Tableau détail
        st.markdown('<div class="section-title">Détail des avoirs</div>', unsafe_allow_html=True)
        cols_av = [c for c in ["num_piece", "tiers", "raison_sociale", "lob", "canal",
                                "montant_ht", "marge_total", "date", "designation"] if c in df_avoirs.columns]
        st.dataframe(df_avoirs[cols_av].sort_values("montant_ht"), use_container_width=True, hide_index=True)

        # Export avoirs
        av_bytes = exporter_flags_excel({"Avoirs_CRM": df_avoirs[cols_av] if cols_av else df_avoirs})
        st.download_button("⬇️ Exporter avoirs en Excel", data=av_bytes,
                           file_name=f"avoirs_CRM_{annee_principale}.xlsx",
                           mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")


# ===========================================================================
# TAB 5 — FRAIS DE PASSAGE
# ===========================================================================
with tab_fp:
    st.markdown(f"### Frais de Passage (compte 36) — {annee_principale}")
    st.caption("Périmètre : SINV compte 36 · Flux de transit — exclus du CA et de la marge principaux")

    df_fp = all_data[annee_principale]["segments"]["frais_passage"]

    if df_fp.empty:
        st.info("Aucun frais de passage dans ce fichier.")
    else:
        rev_fp     = df_fp["montant_ht"].sum() if "montant_ht" in df_fp.columns else 0
        nb_fp      = len(df_fp)
        nb_cli_fp  = df_fp["tiers"].nunique() if "tiers" in df_fp.columns else 0
        rev_ventes = df["montant_ht"].sum() if "montant_ht" in df.columns else 1
        pct_fp     = rev_fp / (rev_ventes + rev_fp) * 100 if (rev_ventes + rev_fp) else 0

        f1, f2, f3, f4 = st.columns(4)
        f1.metric("🔄 Nb lignes", f"{nb_fp:,}")
        f2.metric("💰 Montant transit", fmt_rwf(rev_fp))
        f3.metric("👥 Clients", f"{nb_cli_fp:,}")
        f4.metric("% flux total", fmt_pct(pct_fp),
                  help="Frais de passage / (Ventes + Frais de passage)")

        st.divider()

        st.markdown("""
        <div class="flag-amber">
        ⚠️ <b>Note audit</b> : Les frais de passage (compte 36) représentent des flux de transit 
        où Oryx est intermédiaire. La marge à 100% est artificielle — pas de COGS réel. 
        Ces montants ne constituent pas du chiffre d'affaires au sens P&L.
        </div>
        """, unsafe_allow_html=True)

        st.divider()

        # Top clients frais de passage
        if "tiers" in df_fp.columns and "montant_ht" in df_fp.columns:
            col_nom = "raison_sociale" if "raison_sociale" in df_fp.columns else "tiers"
            top_fp = df_fp.groupby(col_nom)["montant_ht"].sum().reset_index().sort_values("montant_ht", ascending=False).head(10)
            fig_fp = px.bar(top_fp, x="montant_ht", y=col_nom, orientation="h",
                            title="Top 10 clients — Frais de Passage",
                            color_discrete_sequence=["#7B8FA1"],
                            text="montant_ht")
            fig_fp.update_traces(texttemplate="%{text:,.0f}", textposition="outside")
            fig_fp.update_layout(plot_bgcolor="white", paper_bgcolor="white",
                                 yaxis={"categoryorder": "total ascending"}, margin=dict(t=40))
            st.plotly_chart(fig_fp, use_container_width=True)

        st.divider()

        cols_fp = [c for c in ["num_piece", "tiers", "raison_sociale", "canal", "montant_ht", "date", "compte"] if c in df_fp.columns]
        st.dataframe(df_fp[cols_fp].sort_values("montant_ht", ascending=False), use_container_width=True, hide_index=True)

        fp_bytes = exporter_flags_excel({"Frais_Passage_C36": df_fp[cols_fp] if cols_fp else df_fp})
        st.download_button("⬇️ Exporter frais de passage", data=fp_bytes,
                           file_name=f"frais_passage_{annee_principale}.xlsx",
                           mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")


# ===========================================================================
# TAB 6 — MULTI-ANNÉES (YoY)
# ===========================================================================
with tab_yoy:
    st.markdown("### Analyse multi-années — Comparaison YoY")

    if len(annees_dispo) < 2:
        st.info("💡 Uploadez 2 ou 3 fichiers Flash Report (années différentes) pour activer la comparaison YoY.")
    else:
        # KPIs par année
        kpis_annees = {a: kpi_annee(dfs_ventes[a], a) for a in annees_dispo}

        st.markdown("#### KPIs clés par année")
        cols_a = st.columns(len(annees_dispo))
        for i, annee in enumerate(annees_dispo):
            k = kpis_annees[annee]
            annualise_note = f" ⚠️ {k['nb_mois']} mois" if k["annualise"] else ""
            cols_a[i].metric(
                f"**{annee}**{annualise_note}",
                fmt_rwf(k["revenu"]),
                help=f"Marge : {k['marge_pct']}% · {k['nb_tx']:,} transactions"
            )
            cols_a[i].caption(f"Marge : {k['marge_pct']}% | {k['nb_tx']:,} tx | {k['nb_mois']} mois")

        # Note annualisation
        for annee in annees_dispo:
            k = kpis_annees[annee]
            if k["annualise"]:
                st.warning(f"⚠️ **{annee}** : données partielles ({k['nb_mois']} mois). Les comparaisons YoY sont indicatives.")

        st.divider()

        # YoY par LOB
        lob_yoy = yoy_par_lob(dfs_ventes)
        if not lob_yoy.empty:
            st.markdown("#### Revenu par LOB — comparaison YoY")
            fig_yoy_lob = go.Figure()
            colors_yoy = [ORYX_BLUE, ORYX_ORANGE, "#2ECC71"]
            for i, annee in enumerate(annees_dispo):
                if annee in lob_yoy.columns:
                    fig_yoy_lob.add_trace(go.Bar(
                        name=annee,
                        x=lob_yoy["lob"],
                        y=lob_yoy[annee],
                        marker_color=colors_yoy[i % len(colors_yoy)],
                        text=lob_yoy[annee].apply(lambda v: f"{v/1e9:.1f}Mrd"),
                        textposition="outside",
                    ))
            fig_yoy_lob.update_layout(
                barmode="group", plot_bgcolor="white", paper_bgcolor="white",
                title="Revenu par LOB — YoY", title_font_color=ORYX_BLUE,
                legend_title="Année", margin=dict(t=40)
            )
            st.plotly_chart(fig_yoy_lob, use_container_width=True)

        # YoY par segment (volume)
        seg_yoy = yoy_par_segment(dfs_ventes)
        if not seg_yoy.empty:
            st.markdown("#### Volume par Segment — comparaison YoY")
            fig_yoy_seg = go.Figure()
            for i, annee in enumerate(annees_dispo):
                if annee in seg_yoy.columns:
                    fig_yoy_seg.add_trace(go.Bar(
                        name=annee,
                        x=seg_yoy["segment"],
                        y=seg_yoy[annee],
                        marker_color=colors_yoy[i % len(colors_yoy)],
                    ))
            fig_yoy_seg.update_layout(
                barmode="group", plot_bgcolor="white", paper_bgcolor="white",
                title="Volume (litres) par Segment — YoY", title_font_color=ORYX_BLUE,
                legend_title="Année", margin=dict(t=40)
            )
            st.plotly_chart(fig_yoy_seg, use_container_width=True)

        # Évolution clients entre les 2 années les plus récentes
        if len(annees_dispo) >= 2:
            a_ref = annees_dispo[-2]
            a_cmp = annees_dispo[-1]
            st.markdown(f"#### Évolution clients — {a_ref} → {a_cmp}")
            evol = evolution_clients(dfs_ventes[a_ref], dfs_ventes[a_cmp], a_ref, a_cmp)
            if evol:
                e1, e2, e3, e4 = st.columns(4)
                e1.metric("🆕 Nouveaux clients",      len(evol.get("nouveaux", [])))
                e2.metric("❌ Clients disparus",       len(evol.get("disparus", [])))
                e3.metric("📈 Clients en forte hausse (≥50%)", len(evol.get("croissants", [])))
                e4.metric("📉 Clients en forte baisse (≤-30%)", len(evol.get("en_baisse", [])))

                col_l, col_r = st.columns(2)
                with col_l:
                    if not evol["croissants"].empty:
                        st.markdown("**Top clients en hausse**")
                        st.dataframe(evol["croissants"].head(10), use_container_width=True, hide_index=True)
                with col_r:
                    if not evol["en_baisse"].empty:
                        st.markdown("**Clients en baisse significative**")
                        st.dataframe(evol["en_baisse"].head(10), use_container_width=True, hide_index=True)


# ===========================================================================
# TAB 7 — AGEING CREDIT RISK
# ===========================================================================
with tab_ageing:
    st.markdown("### ⚠️ Ageing Credit Risk — Analyse du risque crédit")

    if data_ageing is None:
        st.info("💡 Uploadez le fichier Ageing Credit Risk (.xls) dans le panneau de gauche pour activer cette analyse.")
        st.markdown(f"""
        <div style="background:{ORYX_LIGHT}; border-radius:12px; padding:24px; margin-top:16px;">
            <b>Ce module analyse :</b><br>
            • La balance par client et par tranche d'ancienneté (Courant, 0-30j, 31-60j...)<br>
            • Les clients en dépassement de limite de crédit<br>
            • Les créances ≥ 180 jours (risque de perte)<br>
            • L'évolution du risque crédit sur 2024, 2025 et 2026
        </div>
        """, unsafe_allow_html=True)
    else:
        annees_ageing = data_ageing["annees"]

        # Sélecteur d'année
        annee_ag = st.selectbox(
            "Année d'analyse",
            options=annees_ageing,
            index=len(annees_ageing) - 1,
        )

        df_ag   = data_ageing[annee_ag]["df"]
        meta_ag = data_ageing[annee_ag]["meta"]
        k_ag    = kpi_ageing(df_ag)

        st.caption(f"Source : {meta_ag['societe']} | Date de référence : {meta_ag['date_ref_str']} | {k_ag['nb_clients']} clients")

        # ── KPIs principaux ──────────────────────────────────────────────
        st.divider()
        c1, c2, c3, c4, c5 = st.columns(5)
        c1.metric("💰 Balance totale",    fmt_rwf(k_ag["balance_totale"]))
        c2.metric("⏰ Total Overdue",     fmt_rwf(k_ag["total_overdue"]),
                  delta=f"{k_ag['pct_overdue']}% de la balance",
                  delta_color="inverse")
        c3.metric("🔴 91+ jours",         fmt_rwf(k_ag["total_91_plus"]),
                  delta=f"{k_ag['pct_91_plus']}% de la balance",
                  delta_color="inverse")
        c4.metric("⚠️ Excès crédit",      f"{k_ag['nb_excess']} clients")
        c5.metric("📉 Balance négative",  f"{k_ag['nb_neg']} clients",
                  delta=fmt_rwf(k_ag["balance_negative"]),
                  delta_color="inverse")

        st.divider()

        # ── Graphiques ───────────────────────────────────────────────────
        col_l, col_r = st.columns(2)

        with col_l:
            # Distribution par tranche
            tranches_df = ageing_par_tranche(df_ag)
            colors_tranches = ["#2ECC71", "#F39C12", "#E67E22", "#E74C3C", "#C0392B", "#922B21", "#641E16"]
            fig_tr = px.bar(
                tranches_df, x="tranche", y="montant",
                title=f"Balance par tranche d'ancienneté — {annee_ag}",
                color="tranche",
                color_discrete_sequence=colors_tranches,
                text="pct"
            )
            fig_tr.update_traces(texttemplate="%{text:.1f}%", textposition="outside")
            fig_tr.update_layout(
                showlegend=False, plot_bgcolor="white", paper_bgcolor="white",
                title_font_color=ORYX_BLUE, margin=dict(t=40, b=20)
            )
            st.plotly_chart(fig_tr, use_container_width=True)

        with col_r:
            # Par LOB
            lob_ag = ageing_par_lob(df_ag)
            if not lob_ag.empty:
                fig_lob_ag = px.bar(
                    lob_ag, x="lob", y="balance",
                    title=f"Balance par LOB — {annee_ag}",
                    color="pct_overdue",
                    color_continuous_scale=["#2ECC71", "#F39C12", "#E74C3C"],
                    text="balance"
                )
                fig_lob_ag.update_traces(texttemplate="%{text:,.0f}", textposition="outside")
                fig_lob_ag.update_layout(
                    plot_bgcolor="white", paper_bgcolor="white",
                    coloraxis_colorbar_title="% Overdue",
                    title_font_color=ORYX_BLUE, margin=dict(t=40, b=20)
                )
                st.plotly_chart(fig_lob_ag, use_container_width=True)

        # ── Top clients ──────────────────────────────────────────────────
        st.markdown('<div class="section-title">Top 10 clients par balance</div>', unsafe_allow_html=True)
        top_ag = top_clients_risque(df_ag, 10)
        if not top_ag.empty:
            top_disp = top_ag.copy()
            for col in ["balance_totale", "total_overdue", "total_91_plus", "limite_credit"]:
                if col in top_disp.columns:
                    top_disp[col] = top_disp[col].apply(fmt_rwf)
            for col in ["pct_overdue", "pct_91_plus"]:
                if col in top_disp.columns:
                    top_disp[col] = top_disp[col].apply(lambda x: f"{x:.1f}%")
            if "exces_bool" in top_disp.columns:
                top_disp["exces_bool"] = top_disp["exces_bool"].apply(lambda x: "⚠️ OUI" if x else "")
            st.dataframe(top_disp, use_container_width=True, hide_index=True)

        st.divider()

        # ── FLAGS ────────────────────────────────────────────────────────
        st.markdown("### 🚨 Flags de risque Ageing")

        f_ov  = flag_overdue_critique(df_ag)
        f_exc = flag_depassement_credit(df_ag)
        f_neg = flag_balance_negative(df_ag)
        f_180 = flag_180_plus(df_ag)
        f_sec = flag_securite_expiree(df_ag, meta_ag.get("date_ref"))

        fa1, fa2, fa3, fa4, fa5 = st.columns(5)
        fa1.metric("🔴 Overdue >50% en 91+j", f"{len(f_ov)} clients")
        fa2.metric("🔴 Dépassement crédit",    f"{len(f_exc)} clients")
        fa3.metric("🟠 Balance négative",       f"{len(f_neg)} clients")
        fa4.metric("🔴 Créances ≥ 180j",        f"{len(f_180)} clients")
        fa5.metric("🟠 Garantie expirée",        f"{len(f_sec)} clients")

        with st.expander(f"🔴 Clients avec overdue critique (>50% en 91+ jours) — {len(f_ov)} clients", expanded=len(f_ov) > 0):
            if f_ov.empty:
                st.markdown('<div class="flag-green">✅ Aucun client critique</div>', unsafe_allow_html=True)
            else:
                st.markdown('<div class="flag-red">🔴 Ces clients ont plus de 50% de leur balance en 91+ jours — risque de perte élevé</div>', unsafe_allow_html=True)
                st.dataframe(f_ov, use_container_width=True, hide_index=True)

        with st.expander(f"🔴 Dépassement limite de crédit — {len(f_exc)} clients", expanded=len(f_exc) > 0):
            if f_exc.empty:
                st.markdown('<div class="flag-green">✅ Aucun dépassement détecté</div>', unsafe_allow_html=True)
            else:
                st.markdown('<div class="flag-red">🔴 Clients dont la balance dépasse la limite approuvée</div>', unsafe_allow_html=True)
                st.dataframe(f_exc, use_container_width=True, hide_index=True)

        with st.expander(f"🟠 Balance négative — {len(f_neg)} clients", expanded=False):
            if f_neg.empty:
                st.markdown('<div class="flag-green">✅ Aucune balance négative</div>', unsafe_allow_html=True)
            else:
                st.markdown('<div class="flag-amber">🟠 Avoirs non imputés ou trop-perçus — à réconcilier</div>', unsafe_allow_html=True)
                st.dataframe(f_neg, use_container_width=True, hide_index=True)

        with st.expander(f"🔴 Créances ≥ 180 jours — {len(f_180)} clients", expanded=len(f_180) > 0):
            if f_180.empty:
                st.markdown('<div class="flag-green">✅ Aucune créance ≥ 180 jours</div>', unsafe_allow_html=True)
            else:
                st.markdown('<div class="flag-red">🔴 Créances très anciennes — risque de perte, provision à envisager</div>', unsafe_allow_html=True)
                st.dataframe(f_180, use_container_width=True, hide_index=True)

        with st.expander(f"🟠 Garanties expirées — {len(f_sec)} clients", expanded=False):
            if f_sec.empty:
                st.markdown('<div class="flag-green">✅ Aucune garantie expirée détectée</div>', unsafe_allow_html=True)
            else:
                st.markdown('<div class="flag-amber">🟠 Garanties expirées — renouvellement requis</div>', unsafe_allow_html=True)
                st.dataframe(f_sec, use_container_width=True, hide_index=True)

        st.divider()

        # ── Évolution YoY Ageing ─────────────────────────────────────────
        if len(annees_ageing) > 1:
            st.markdown("### 📈 Évolution du risque crédit — comparaison annuelle")

            yoy_rows = []
            for a in annees_ageing:
                k = kpi_ageing(data_ageing[a]["df"])
                yoy_rows.append({
                    "Année":          a,
                    "Balance (Mrd)":  round(k["balance_totale"] / 1e9, 2),
                    "Overdue (Mrd)":  round(k["total_overdue"] / 1e9, 2),
                    "91+ jours (Mrd)":round(k["total_91_plus"] / 1e9, 2),
                    "% Overdue":      k["pct_overdue"],
                    "% 91+":          k["pct_91_plus"],
                    "Excès crédit":   k["nb_excess"],
                    "Nb clients":     k["nb_clients"],
                })
            yoy_ag_df = pd.DataFrame(yoy_rows)
            st.dataframe(yoy_ag_df, use_container_width=True, hide_index=True)

            # Graphique évolution balance vs overdue
            fig_yoy_ag = go.Figure()
            fig_yoy_ag.add_trace(go.Bar(
                name="Balance totale",
                x=yoy_ag_df["Année"], y=yoy_ag_df["Balance (Mrd)"],
                marker_color=ORYX_BLUE,
            ))
            fig_yoy_ag.add_trace(go.Bar(
                name="Overdue",
                x=yoy_ag_df["Année"], y=yoy_ag_df["Overdue (Mrd)"],
                marker_color=ORYX_ORANGE,
            ))
            fig_yoy_ag.add_trace(go.Bar(
                name="91+ jours",
                x=yoy_ag_df["Année"], y=yoy_ag_df["91+ jours (Mrd)"],
                marker_color=RED,
            ))
            fig_yoy_ag.update_layout(
                barmode="group",
                title="Balance vs Overdue vs 91+ jours — YoY (Mrd RWF)",
                plot_bgcolor="white", paper_bgcolor="white",
                title_font_color=ORYX_BLUE,
                legend_title="Indicateur",
                margin=dict(t=40)
            )
            st.plotly_chart(fig_yoy_ag, use_container_width=True)

        # ── Export ───────────────────────────────────────────────────────
        st.divider()
        st.markdown("**📥 Exporter les flags Ageing**")
        flags_ag_dict = {
            f"Overdue_Critique_{annee_ag}":    f_ov,
            f"Depassement_Credit_{annee_ag}":  f_exc,
            f"Balance_Negative_{annee_ag}":    f_neg,
            f"Creances_180j_{annee_ag}":        f_180,
            f"Garanties_Expirees_{annee_ag}":   f_sec,
        }
        excel_ag = exporter_flags_excel(flags_ag_dict)
        st.download_button(
            label=f"⬇️ Télécharger flags Ageing {annee_ag}",
            data=excel_ag,
            file_name=f"flags_ageing_{annee_ag}.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )


# ===========================================================================
# TAB 8 — DETAILED AGED BALANCE
# ===========================================================================
with tab_detailed:
    st.markdown("### 📋 Detailed Aged Balance — Analyse par transaction")

    if data_detailed is None:
        st.info("💡 Uploadez le fichier Detailed Aged Balance (.xls) dans le panneau de gauche.")
        st.markdown(f"""
        <div style="background:{ORYX_LIGHT}; border-radius:12px; padding:24px; margin-top:16px;">
            <b>Ce module analyse :</b><br>
            • Toutes les transactions par client (factures, paiements, avoirs)<br>
            • Balance âgée par tranche : ≥60j, 30-59j, 0-29j<br>
            • Factures impayées depuis plus de 60 jours<br>
            • Clients avec solde négatif (avoirs non imputés)
        </div>
        """, unsafe_allow_html=True)
    else:
        annees_det = data_detailed["annees"]
        annee_det  = st.selectbox("Année", options=annees_det,
                                   index=len(annees_det)-1, key="sel_detailed")
        df_tx  = data_detailed[annee_det]["transactions"]
        df_cli = data_detailed[annee_det]["clients"]
        meta_d = data_detailed[annee_det]["meta"]
        k_det  = kpi_detailed(df_tx, df_cli)

        st.caption(f"Date de référence : {meta_d['date_ref_str']} | {k_det['nb_clients']} clients | {k_det['nb_transactions']:,} transactions")

        # KPIs
        d1, d2, d3, d4, d5 = st.columns(5)
        d1.metric("👥 Clients",        f"{k_det['nb_clients']:,}")
        d2.metric("🧾 Factures",        f"{k_det['nb_factures']:,}")
        d3.metric("💳 Paiements",       f"{k_det['nb_paiements']:,}")
        d4.metric("🔴 Overdue ≥60j",   fmt_rwf(k_det["total_j60_plus"]))
        d5.metric("💰 Balance nette",   fmt_rwf(k_det["balance_nette"]))

        st.divider()

        col_l, col_r = st.columns(2)
        with col_l:
            # Distribution par tranche
            tranches_data = {
                "≥60 jours":   k_det["total_j60_plus"],
                "30-59 jours": k_det["total_j30_59"],
                "0-29 jours":  k_det["total_j0_29"],
                "Non échu":    k_det["total_non_echu"],
            }
            df_tr = pd.DataFrame([{"tranche": k, "montant": v}
                                   for k, v in tranches_data.items()])
            fig_tr = px.bar(df_tr, x="tranche", y="montant",
                           title=f"Distribution par tranche — {annee_det}",
                           color="tranche",
                           color_discrete_sequence=[RED, ORYX_ORANGE, "#F39C12", GREEN],
                           text="montant")
            fig_tr.update_traces(texttemplate="%{text:,.0f}", textposition="outside")
            fig_tr.update_layout(showlegend=False, plot_bgcolor="white",
                                  paper_bgcolor="white", margin=dict(t=40))
            st.plotly_chart(fig_tr, use_container_width=True)

        with col_r:
            # Types de transactions
            tx_type = transactions_par_type(df_tx)
            fig_tx = px.bar(tx_type, x="type_tx", y="nb",
                           title="Transactions par type",
                           color_discrete_sequence=[ORYX_BLUE],
                           text="nb")
            fig_tx.update_traces(texttemplate="%{text:,}", textposition="outside")
            fig_tx.update_layout(plot_bgcolor="white", paper_bgcolor="white",
                                  margin=dict(t=40))
            st.plotly_chart(fig_tx, use_container_width=True)

        # Top clients overdue
        st.markdown('<div class="section-title">Top 10 clients — Overdue ≥ 60 jours</div>',
                    unsafe_allow_html=True)
        top_det = top_clients_overdue(df_cli, 10)
        if not top_det.empty:
            top_disp = top_det.copy()
            for col in ["j60_plus", "j30_59", "j0_29", "montant_total", "total_overdue"]:
                if col in top_disp.columns:
                    top_disp[col] = top_disp[col].apply(fmt_rwf)
            st.dataframe(top_disp, use_container_width=True, hide_index=True)

        st.divider()

        # FLAGS
        st.markdown("### 🚨 Flags de risque")
        flags_det = resume_flags_detailed(df_tx, df_cli)
        fd1, fd2, fd3, fd4 = st.columns(4)
        fd1.metric("🔴 Factures impayées ≥60j", f"{flags_det['nb_factures_60j_plus']:,}")
        fd2.metric("🟠 Paiements sans facture",  f"{flags_det['nb_paiements_sans_facture']}")
        fd3.metric("🟠 Soldes négatifs",          f"{flags_det['nb_soldes_negatifs']}")
        fd4.metric("🔴 Échéances >90j",           f"{flags_det['nb_echeances_90j_plus']:,}")

        with st.expander(f"🔴 Factures impayées ≥ 60 jours — {flags_det['nb_factures_60j_plus']:,} lignes",
                         expanded=False):
            f60 = flag_factures_impayees_60j(df_tx)
            if f60.empty:
                st.markdown('<div class="flag-green">✅ Aucune facture impayée ≥ 60j</div>',
                            unsafe_allow_html=True)
            else:
                st.dataframe(f60.head(50), use_container_width=True, hide_index=True)

        with st.expander(f"🟠 Soldes négatifs — {flags_det['nb_soldes_negatifs']} clients",
                         expanded=False):
            f_neg = flag_solde_negatif(df_cli)
            if f_neg.empty:
                st.markdown('<div class="flag-green">✅ Aucun solde négatif</div>',
                            unsafe_allow_html=True)
            else:
                st.markdown('<div class="flag-amber">🟠 Avoirs non imputés ou trop-perçus</div>',
                            unsafe_allow_html=True)
                st.dataframe(f_neg, use_container_width=True, hide_index=True)

        # Export
        st.divider()
        exp_det = exporter_flags_excel({
            f"Factures_60j_{annee_det}":      flag_factures_impayees_60j(df_tx).head(500),
            f"Soldes_Negatifs_{annee_det}":   flag_solde_negatif(df_cli),
            f"Echeances_90j_{annee_det}":     flag_echeances_depassees(df_tx, 90).head(500),
        })
        st.download_button("⬇️ Exporter flags Detailed Aged", data=exp_det,
                           file_name=f"flags_detailed_{annee_det}.xlsx",
                           mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")


# ===========================================================================
# TAB 9 — GENERAL BALANCE
# ===========================================================================
with tab_general:
    st.markdown("### ⚖️ General Balance — Balance générale comptable")

    if data_general is None:
        st.info("💡 Uploadez le fichier General Balance (.xls) dans le panneau de gauche.")
        st.markdown(f"""
        <div style="background:{ORYX_LIGHT}; border-radius:12px; padding:24px; margin-top:16px;">
            <b>Ce module analyse :</b><br>
            • Plan de comptes complet avec mouvements débit/crédit<br>
            • Soldes par classe de comptes (Trésorerie, Stocks, Tiers...)<br>
            • Vérification de l'équilibre comptable<br>
            • Détection de comptes à solde inhabituel<br>
            • Variation YoY par compte
        </div>
        """, unsafe_allow_html=True)
    else:
        annees_gen = data_general["annees"]
        annee_gen  = st.selectbox("Année", options=annees_gen,
                                   index=len(annees_gen)-1, key="sel_general")
        df_gen  = data_general[annee_gen]["comptes"]
        meta_gen = data_general[annee_gen]["meta"]
        k_gen   = kpi_general(df_gen)

        st.caption(f"Société : {meta_gen.get('societe', 'RW01')} | Devise : {meta_gen.get('devise', 'RWF')} | {k_gen['nb_comptes']} comptes")

        # KPIs
        g1, g2, g3, g4, g5 = st.columns(5)
        g1.metric("📚 Nb comptes",     f"{k_gen['nb_comptes']}")
        g2.metric("📈 Mvt Débit",      fmt_rwf(k_gen["total_mvt_debit"]))
        g3.metric("📉 Mvt Crédit",     fmt_rwf(k_gen["total_mvt_credit"]))
        g4.metric("💰 Solde Débit",    fmt_rwf(k_gen["total_solde_debit"]))
        g5.metric("⚖️ Équilibré",
                  "✅ OUI" if k_gen["equilibre"] else "❌ NON",
                  delta=None)

        if not k_gen["equilibre"]:
            st.markdown(f'<div class="flag-red">🔴 Écart d\'équilibre : {fmt_rwf(k_gen["ecart_equilibre"])}</div>',
                        unsafe_allow_html=True)

        st.divider()

        col_l, col_r = st.columns(2)
        with col_l:
            # Balance par classe
            bc = balance_par_classe(df_gen)
            fig_bc = px.bar(bc, x="classe", y="solde_net",
                           title=f"Solde net par classe — {annee_gen}",
                           color="solde_net",
                           color_continuous_scale=["#E74C3C", "#FFFFFF", "#2ECC71"],
                           text="solde_net")
            fig_bc.update_traces(texttemplate="%{text:,.0f}", textposition="outside")
            fig_bc.update_layout(plot_bgcolor="white", paper_bgcolor="white",
                                  showlegend=False, margin=dict(t=40),
                                  xaxis_tickangle=-30)
            st.plotly_chart(fig_bc, use_container_width=True)

        with col_r:
            # Top comptes par mouvement
            top_gen = top_comptes_mouvement(df_gen, 10)
            fig_top = px.bar(top_gen, x="mvt_total", y="num_compte",
                            orientation="h",
                            title="Top 10 comptes par volume mouvement",
                            color_discrete_sequence=[ORYX_BLUE],
                            text="description")
            fig_top.update_traces(textposition="outside")
            fig_top.update_layout(plot_bgcolor="white", paper_bgcolor="white",
                                   yaxis={"categoryorder": "total ascending"},
                                   margin=dict(t=40))
            st.plotly_chart(fig_top, use_container_width=True)

        # Tableau balance par classe
        st.markdown('<div class="section-title">Balance par classe de comptes</div>',
                    unsafe_allow_html=True)
        bc_disp = bc.copy()
        for col in ["mvt_debit", "mvt_credit", "mvt_net", "solde_debit", "solde_credit", "solde_net"]:
            if col in bc_disp.columns:
                bc_disp[col] = bc_disp[col].apply(fmt_rwf)
        st.dataframe(bc_disp, use_container_width=True, hide_index=True)

        st.divider()

        # FLAGS
        st.markdown("### 🚨 Flags de risque")
        flags_gen = resume_flags_general(df_gen)
        fg1, fg2, fg3 = st.columns(3)
        fg1.metric("🔴 Comptes déséquilibrés",   f"{flags_gen['nb_desequilibres']}")
        fg2.metric("🟠 Soldes inhabituels",        f"{flags_gen['nb_soldes_inhabituels']}")
        fg3.metric("🟠 Sans mouvement",            f"{flags_gen['nb_sans_mouvement']}")

        with st.expander(f"🟠 Comptes à solde inhabituel — {flags_gen['nb_soldes_inhabituels']} comptes",
                         expanded=flags_gen['nb_soldes_inhabituels'] > 0):
            f_inh = flag_comptes_solde_inhabituel(df_gen)
            if f_inh.empty:
                st.markdown('<div class="flag-green">✅ Aucun solde inhabituel</div>',
                            unsafe_allow_html=True)
            else:
                st.markdown('<div class="flag-amber">🟠 Vérifier ces comptes</div>',
                            unsafe_allow_html=True)
                st.dataframe(f_inh, use_container_width=True, hide_index=True)

        with st.expander(f"🟠 Comptes sans mouvement — {flags_gen['nb_sans_mouvement']} comptes",
                         expanded=False):
            f_sm = flag_comptes_sans_mouvement(df_gen)
            if f_sm.empty:
                st.markdown('<div class="flag-green">✅ Tous les comptes ont bougé</div>',
                            unsafe_allow_html=True)
            else:
                st.dataframe(f_sm, use_container_width=True, hide_index=True)

        # YoY variation
        if len(annees_gen) >= 2:
            st.divider()
            st.markdown("### 📈 Variation YoY")
            a_ref, a_cmp = annees_gen[-2], annees_gen[-1]
            var = flag_variation_significative(
                data_general[a_ref]["comptes"],
                data_general[a_cmp]["comptes"],
                a_ref, a_cmp, seuil_pct=50.0
            )
            st.markdown(f"**{len(var)} comptes** avec variation >50% entre {a_ref} et {a_cmp}")
            if not var.empty:
                st.dataframe(var.head(20), use_container_width=True, hide_index=True)

        # Export
        st.divider()
        exp_gen = exporter_flags_excel({
            f"Soldes_Inhabituels_{annee_gen}": flag_comptes_solde_inhabituel(df_gen),
            f"Sans_Mouvement_{annee_gen}":     flag_comptes_sans_mouvement(df_gen),
        })
        st.download_button("⬇️ Exporter flags General Balance", data=exp_gen,
                           file_name=f"flags_general_{annee_gen}.xlsx",
                           mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")