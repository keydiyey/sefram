import streamlit as st
import pandas as pd
import io
import plotly.graph_objects as go

st.set_page_config(page_title="sefram?", layout="wide")

with st.sidebar:
    uploaded_file = st.file_uploader("Choose a file", type=["rec", "csv", "txt"])

@st.cache_data
def parse_and_downsample_file(file_bytes):
    try:
        lines = file_bytes.decode("utf-8").splitlines()
    except UnicodeDecodeError:
        lines = file_bytes.decode("latin-1").splitlines()
        
    lines = [line.strip() for line in lines if line.strip()]
    
    header_idx = -1
    for idx, line in enumerate(lines):
        if "Time;" in line:
            header_idx = idx
            break
            
    if header_idx == -1:
        return None, "Could not find the header line (containing 'Time;')."
        
    csv_data = "\n".join(lines[header_idx:])
    df = pd.read_csv(io.StringIO(csv_data), sep=";")
    
    df = df.dropna(how='all', axis=1)
    df = df.loc[:, ~df.columns.str.contains('^Unnamed')]
    
    voie_cols = [c for c in df.columns if 'Voie' in c or 'voie' in c.lower()]
    rename_dict = {col: f"TC{i+1}" for i, col in enumerate(voie_cols)}
    df = df.rename(columns=rename_dict)
    
    time_col = df.columns[0]
    
    df['Duration (min)'] = (df[time_col] // 60000).astype(int)
    df = df.drop_duplicates(subset=['Duration (min)'], keep='first')
    
    cols = list(df.columns)
    channel_cols = [c for c in cols if c not in ['Duration (min)', time_col]]
    
    df_final = df[['Duration (min)'] + channel_cols].copy()
    
    return df_final, channel_cols

if uploaded_file is not None:
    file_bytes = uploaded_file.getvalue()
    
    df_final, channel_cols = parse_and_downsample_file(file_bytes)
    
    if df_final is None:
        st.error(channel_cols)
    else:
        st.subheader("graph")
        
        fig = go.Figure()
        for col in channel_cols:
            fig.add_trace(go.Scatter(
                x=df_final['Duration (min)'], 
                y=df_final[col], 
                mode='lines', 
                name=col
            ))
            
        thresholds = [82, 80, 78, -28, -30, -32]
        for t in thresholds:
            fig.add_hline(
                y=t, 
                line_dash="dash", 
                line_color="red", 
                line_width=1.5
            )
            
        fig.update_layout(
            xaxis_title="Duration (min)",
            yaxis_title="Temperature (°C)",
            hovermode="x unified",
            margin=dict(l=40, r=40, t=20, b=40),
            legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
            xaxis=dict(
                showgrid=True,
                gridwidth=1,
                gridcolor='rgba(180, 180, 180, 0.6)',
                nticks=30,
                minor=dict(
                    showgrid=True,
                    gridwidth=0.5,
                    gridcolor='rgba(210, 210, 210, 0.4)'
                )
            ),
            yaxis=dict(
                showgrid=True,
                gridwidth=1,
                gridcolor='rgba(180, 180, 180, 0.6)',
                nticks=20,
                minor=dict(
                    showgrid=True,
                    gridwidth=0.5,
                    gridcolor='rgba(210, 210, 210, 0.4)'
                )
            ),
            template="plotly_white"
        )
        
        st.plotly_chart(fig, use_container_width=True)
            
        with st.expander("cleaned data", expanded=False):
            st.dataframe(df_final, use_container_width=True)