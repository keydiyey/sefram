import streamlit as st
import pandas as pd
import io
import plotly.graph_objects as go
import numpy as np

st.set_page_config(page_title="sefram?", layout="wide")


st.markdown(
    """
    <style>
    .top-banner {
        background-color: #1E3A8A;
        color: white;
        padding: 15px;
        text-align: center;
        font-size: 24px;
        font-weight: bold;
        border-radius: 5px;
        margin-bottom: 20px;
    }
    </style>
    <div class="top-banner">
        RELIABILITY ENGINEERING
    </div>
    """,
    unsafe_allow_html=True
)

with st.sidebar:
    uploaded_file = st.file_uploader("Choose a file", type=["csv", "txt"])

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
        df_final['Mean_Temp'] = df_final[channel_cols].mean(axis=1)
        df_final['Smoothed_Temp'] = df_final['Mean_Temp'].rolling(window=5, center=True, min_periods=1).mean()
        df_final['Slope'] = df_final['Smoothed_Temp'].diff().fillna(0)
        

        slope_threshold = 0.25
        
        conditions = [
            (df_final['Slope'] > slope_threshold),
            (df_final['Slope'] < -slope_threshold)
        ]
        choices = ['Ramp Up', 'Ramp Down']
        df_final['Phase'] = np.select(conditions, choices, default='Dwell') 
        

        df_final['Phase_Change'] = (df_final['Phase'] != df_final['Phase'].shift(1)).cumsum()
        
        phase_blocks = []
        for _, group in df_final.groupby('Phase_Change'):
            phase_type = group['Phase'].iloc[0]
            start_time = group['Duration (min)'].min()
            end_time = group['Duration (min)'].max()
            duration = end_time - start_time + 1
            avg_temp = group['Mean_Temp'].mean()
            
            if phase_type == 'Dwell':
                phase_type = 'Hot Dwell' if avg_temp > 25 else 'Cold Dwell'
                
            phase_blocks.append({
                "Phase": phase_type,
                "Start (min)": start_time,
                "End (min)": end_time,
                "Duration (min)": duration,
                "Avg Temp (°C)": round(avg_temp, 1)
            })
            
        df_phases = pd.DataFrame(phase_blocks)
        
        new_df = df_phases[df_phases["Duration (min)"] > 10]
            

        st.subheader("Graph")
        
        fig = go.Figure()
        
      
        color_map = {
            'Ramp Up': 'rgba(211, 211, 211, 0)',
            'Ramp Down': 'rgba(211, 211, 211, 0)', 
            'Hot Dwell': 'rgba(211, 211, 211, 0.5)',
            'Cold Dwell': 'rgba(211, 211, 211, 0.5)' 
        }
        
        for block in phase_blocks:
            fig.add_vrect(
                x0=block["Start (min)"], x1=block["End (min)"],
                fillcolor=color_map.get(block["Phase"], "rgba(0,0,0,0)"),
                layer="below", line_width=0
            )
        
        for col in channel_cols:
            fig.add_trace(go.Scatter(
                x=df_final['Duration (min)'], 
                y=df_final[col], 
                mode='lines', 
                name=col
            ))
            
        if "TC" in uploaded_file.name or "HF" in uploaded_file.name:
            thresholds = [120, -40]
        elif "DH" in uploaded_file.name:
            thresholds = [85]
        else:
            thresholds = [120]
            
        def addThresholdLine(y):
            return fig.add_hline(y=y, line_dash="dash", line_color="red", line_width=1)

        for t in thresholds:
            addThresholdLine(t + 2)
            addThresholdLine(t)
            addThresholdLine(t - 2)

        fig.add_hline(y=25, line_color="blue", line_width=1.5)
            
        fig.update_layout(
            xaxis_title="Duration (min)",
            yaxis_title="Temperature (°C)",
            hovermode="x unified",
            margin=dict(l=40, r=40, t=40, b=40),
            legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
            xaxis=dict(
                showgrid=True, gridwidth=1, gridcolor='rgba(180, 180, 180, 0.6)', nticks=30,
                minor=dict(showgrid=True, gridwidth=0.5, gridcolor='rgba(210, 210, 210, 0.4)')
            ),
            yaxis=dict(
                showgrid=True, gridwidth=1, gridcolor='rgba(180, 180, 180, 0.6)', nticks=20,
                minor=dict(showgrid=True, gridwidth=0.5, gridcolor='rgba(210, 210, 210, 0.4)')
            ),
            template="plotly_white"
        )
        
        st.plotly_chart(fig, width='stretch')
        

        with st.expander("summary", expanded=False):
            st.dataframe(new_df, width='stretch', hide_index=True)
            
        with st.expander("Cleaned Raw Data", expanded=False):
            st.dataframe(df_final[['Duration (min)'] + channel_cols], width='stretch')