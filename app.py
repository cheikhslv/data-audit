import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go

from src.ingestion import charger_fichier
from src.kpis import (
    kpi_generaux, revenu_par_lob, revenu_par_segment,
    revenu_par_canal, tendance_mensuelle, top_clients,
    marge_par_client_mensuelle,
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

st.markdown("""
<style>
    .block-container { padding-top: 1.5rem; }
    .metric-card { background: #f8f9fa; border-radius: 8px; padding: 1rem; }
    .flag-red { background-color: #fff0f0; border-left: 3px solid #dc3545; padding: 0.5rem 1rem; border-radius: 4px; margin-bottom: 0.5rem; }
    .flag-orange { background-color: #fff8f0; border-left: 3px solid #fd7e14; padding: 0.5rem 1rem; border-radius: 4px; margin-bottom: 0.5rem; }
</style>
""", unsafe_allow_html=True)


with st.sidebar:
    st.markdown("### 📊 Audit Analytics")
    st.markdown("*Oryx Energies Group*")
    st.divider()

    fichier = st.file_uploader(
        "Charger un Flash Report",
        type=["xlsx", "xls", "csv"],
        help="Fichier exporté depuis Sage X3 (.xlsx ou .csv)"
    )

    if fichier:
        st.success(f"✓ {fichier.name}")

    st.divider()
    st.markdown("**Navigation**")
    page = st.radio(
        "",
        ["Vue générale", "Analyse clients", "Flags de risque"],
        label_visibility="collapsed",
    )


if not fichier:
    st.markdown("## Bienvenue sur Audit Analytics")
    st.markdown("Chargez un fichier Flash Report Sage X3 dans la barre latérale pour démarrer l'analyse.")
    st.info("Formats acceptés : Excel (.xlsx) ou CSV avec séparateur point-virgule ou tabulation.")
    st.stop()


@st.cache_data
def charger(fichier):
    return charger_fichier(fichier)

df, meta = charger(fichier)

if df is None or df.empty:
    st.error("Impossible de lire le fichier. Vérifiez le format.")
    st.stop()

if meta.get("colonnes_manquantes"):
    with st.expander(f"⚠️ {len(meta['colonnes_manquantes'])} colonne(s) non détectée(s)"):
        st.write(meta["colonnes_manquantes"])


if page == "Vue générale":
    st.subheader("Vue générale")

    kpis = kpi_generaux(df)
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Revenu total", f"{kpis['revenu_total']:,.0f}")
    c2.metric("Marge % globale", f"{kpis['marge_pct_globale']:.1f}%")
    c3.metric("Volume total", f"{kpis['volume_total']:,.0f}")
    c4.metric("Transactions", f"{kpis['nb_transactions']:,}")

    st.divider()

    col_left, col_right = st.columns(2)

    with col_left:
        st.markdown("**Tendance mensuelle du revenu**")
        trend = tendance_mensuelle(df)
        if not trend.empty:
            fig = px.line(trend, x="mois", y="revenu", markers=True,
                          color_discrete_sequence=["#7F77DD"])
            fig.update_layout(margin=dict(t=10, b=10), height=250,
                              xaxis_title="", yaxis_title="Revenu")
            st.plotly_chart(fig, use_container_width=True)

    with col_right:
        st.markdown("**Revenu par LOB**")
        lob = revenu_par_lob(df)
        if not lob.empty:
            fig = px.bar(lob, x="lob", y="revenu",
                         color_discrete_sequence=["#7F77DD"])
            fig.update_layout(margin=dict(t=10, b=10), height=250,
                              xaxis_title="", yaxis_title="Revenu")
            st.plotly_chart(fig, use_container_width=True)

    st.markdown("**Revenu par segment produit**")
    seg = revenu_par_segment(df)
    if not seg.empty:
        fig = px.bar(seg, x="revenu", y="segment", orientation="h",
                     color_discrete_sequence=["#7F77DD"])
        fig.update_layout(margin=dict(t=10, b=10), height=max(200, len(seg) * 40),
                          xaxis_title="Revenu", yaxis_title="")
        st.plotly_chart(fig, use_container_width=True)


elif page == "Analyse clients":
    st.subheader("Analyse clients")

    col_left, col_right = st.columns([2, 1])

    with col_left:
        st.markdown("**Top 10 clients par revenu**")
        top = top_clients(df, 10)
        if not top.empty:
            def color_marge(val):
                if val < 0:
                    return "color: #dc3545; font-weight: bold"
                elif val < 5:
                    return "color: #fd7e14"
                return "color: #198754"

            st.dataframe(
                top.style.applymap(color_marge, subset=["marge_pct"]),
                use_container_width=True, hide_index=True,
            )

    with col_right:
        st.markdown("**Concentration client**")
        conc = flag_concentration_client(df)
        if conc:
            pct = conc["pct_top3"]
            couleur = "🔴" if conc["flag"] else "🟡"
            st.metric("Top 3 clients / Revenu total", f"{pct}%",
                      delta=f"Seuil : {conc['seuil']}%",
                      delta_color="inverse")
            if conc["flag"]:
                st.warning(f"{couleur} Concentration élevée — top 3 > {conc['seuil']}%")
            else:
                st.info(f"Concentration top 3 : {pct}% — OK")
            st.dataframe(conc["top3"], hide_index=True, use_container_width=True)

    st.divider()
    st.markdown("**Clients à marge décroissante (2 mois consécutifs)**")
    decroissants = flag_marge_decroissante(df)
    if decroissants.empty:
        st.success("Aucun client avec marge décroissante sur 2 mois consécutifs.")
    else:
        st.warning(f"{len(decroissants)} client(s) avec marge en baisse 2 mois de suite")
        st.dataframe(decroissants, use_container_width=True, hide_index=True)

    st.divider()
    st.markdown("**Clients à marge négative**")
    cli_neg = df.groupby("tiers").agg(
        revenu=("montant_ht", "sum"), marge=("marge_total", "sum")
    ).reset_index()
    cli_neg["marge_pct"] = (cli_neg["marge"] / cli_neg["revenu"] * 100).round(2)
    cli_neg_filtre = cli_neg[cli_neg["marge_pct"] < 0].sort_values("marge_pct")
    if cli_neg_filtre.empty:
        st.success("Aucun client à marge négative globale.")
    else:
        st.dataframe(cli_neg_filtre, use_container_width=True, hide_index=True)


elif page == "Flags de risque":
    st.subheader("Flags de risque")

    resume = resume_flags(df)

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("🔴 Marge négative", resume["nb_marge_negative"])
    c2.metric("🔴 COGS = 0", resume["nb_cogs_zero"])
    c3.metric("🟠 Doublons", resume["nb_doublons"])
    c4.metric("🟠 Marge décroissante", resume["nb_marge_decroissante"])

    st.divider()

    with st.expander("🔴 Transactions à marge négative", expanded=True):
        marge_neg = flag_marge_negative(df)
        if marge_neg.empty:
            st.success("Aucune transaction à marge négative.")
        else:
            st.error(f"{len(marge_neg)} transaction(s) à marge négative")
            st.dataframe(marge_neg, use_container_width=True, hide_index=True)
            st.download_button(
                "📥 Exporter en Excel",
                data=exporter_flags_excel({"Marge négative": marge_neg}),
                file_name="flag_marge_negative.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            )

    with st.expander("🔴 Transactions COGS = 0", expanded=True):
        cogs_zero = flag_cogs_zero(df)
        if cogs_zero.empty:
            st.success("Aucune anomalie COGS détectée.")
        else:
            st.error(f"{len(cogs_zero)} ligne(s) avec COGS = 0 et CA > 0")
            st.dataframe(cogs_zero, use_container_width=True, hide_index=True)
            st.download_button(
                "📥 Exporter en Excel",
                data=exporter_flags_excel({"COGS zéro": cogs_zero}),
                file_name="flag_cogs_zero.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            )

    with st.expander("🟠 Doublons de factures", expanded=True):
        doublons = flag_doublons(df)
        if doublons.empty:
            st.success("Aucun doublon détecté.")
        else:
            st.warning(f"{len(doublons)} ligne(s) en doublon potentiel")
            st.dataframe(doublons, use_container_width=True, hide_index=True)
            st.download_button(
                "📥 Exporter en Excel",
                data=exporter_flags_excel({"Doublons": doublons}),
                file_name="flag_doublons.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            )

    with st.expander("🟠 Concentration client", expanded=False):
        conc = flag_concentration_client(df)
        if conc:
            pct = conc["pct_top3"]
            if conc["flag"]:
                st.warning(f"⚠️ Top 3 clients représentent {pct}% du revenu total (seuil : {conc['seuil']}%)")
            else:
                st.info(f"Top 3 clients : {pct}% du revenu total — sous le seuil de {conc['seuil']}%")
            st.dataframe(conc["top3"], use_container_width=True, hide_index=True)

    st.divider()
    with st.expander("📥 Export complet tous les flags"):
        tous_flags = {
            "Marge négative": flag_marge_negative(df),
            "COGS zéro": flag_cogs_zero(df),
            "Doublons": flag_doublons(df),
            "Marge décroissante": flag_marge_decroissante(df),
        }
        st.download_button(
            "📥 Exporter tous les flags en Excel",
            data=exporter_flags_excel(tous_flags),
            file_name="audit_flags_complet.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )
