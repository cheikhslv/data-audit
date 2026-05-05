import io
import pandas as pd


def exporter_flags_excel(dict_df: dict) -> bytes:
    buffer = io.BytesIO()
    with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
        for nom_onglet, df in dict_df.items():
            if isinstance(df, pd.DataFrame) and not df.empty:
                df.to_excel(writer, sheet_name=nom_onglet[:31], index=False)
    return buffer.getvalue()
