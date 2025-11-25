import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go
import re
import colorsys

st.set_page_config(page_title="CPU Usage Dashboard", page_icon="🖥️", layout="wide")

# Estilos CSS personalizados para limpiar la UI de Streamlit
st.markdown("""
    <style>
        .block-container {padding-top: 2rem; padding-bottom: 2rem;}
        h1 {color: #2c3e50;}
        h2, h3 {color: #34495e;}
    </style>
""", unsafe_allow_html=True)

st.title("🔍 CPU Percentage Dashboard — VMs")
st.markdown("App interactiva para monitorear porcentajes de CPU por VM y NE Name. Usa archivos exportados (CSV).")

# --- FUNCIONES DE PROCESAMIENTO ---

def extract_vm_info(vm_str):
    """
    Extrae el VM Name y el VM Type de la cadena raw del CSV.
    Ejemplo raw: "nodeName=VNFP, VM Name=SPU_CGW_0080"
    Retorna: (vm_name, vm_type)
    """
    if pd.isna(vm_str):
        return None, None
    
    # Extraer VM Name
    match_name = re.search(r"VM Name=([^,\"]+)", str(vm_str))
    if match_name:
        vm_name = match_name.group(1).strip()
    else:
        vm_name = str(vm_str).strip()
    
    # Extraer VM Type
    vm_name_upper = vm_name.upper()
    
    # REGLAS ESPECÍFICAS (Orden de prioridad)
    if "IPU_A" in vm_name_upper:
        vm_type = "IPU_A"
    elif "IPU_B_ARM" in vm_name_upper:
        vm_type = "IPU_B_ARM"
    elif "IPU_B" in vm_name_upper:
        vm_type = "IPU_B"
    elif "ISU_ARM" in vm_name_upper:
        vm_type = "ISU_ARM"
    elif "ISU_C48" in vm_name_upper:
        vm_type = "ISU_C48"
    elif "SDU_A_ARM" in vm_name_upper:
        vm_type = "SDU_A_ARM"
    elif "SDU_A" in vm_name_upper:
        vm_type = "SDU_A"
    elif "SPU_CGW" in vm_name_upper:
        vm_type = "SPU_CGW"
    elif "SPU_J_ARM" in vm_name_upper:
        vm_type = "SPU_J_ARM"
    elif "SPU_J" in vm_name_upper:
        vm_type = "SPU_J"
    elif "SPU_M_ARM" in vm_name_upper:
        vm_type = "SPU_M_ARM"
    elif "SPU_M" in vm_name_upper:
        vm_type = "SPU_M"
    elif "OMU" in vm_name_upper:
        vm_type = "OMU"
    else:
        # Patrón general: Primera palabra en mayúsculas antes de un guion bajo o número
        match_type = re.search(r"^([A-Z]+)", vm_name)
        if match_type:
            vm_type = match_type.group(1)
        else:
            vm_type = "UNKNOWN"
            
    return vm_name, vm_type

def generate_color_map(df):
    """
    Genera un mapa de colores donde:
    - Cada NE tiene un tono base único (mismo hue) de una paleta fija
    - Cada VM Type dentro del NE tiene saturación/luminosidad única
    Esto crea "familias" de colores visualmente agrupadas pero distinguibles.
    """
    # Paleta fija de tonos (hues) - siempre en el mismo orden
    # Distribuidos uniformemente en el espectro de color
    FIXED_HUES = [
        0.00,  # Rojo
        0.10,  # Rojo-naranja
        0.20,  # Naranja
        0.30,  # Amarillo
        0.40,  # Amarillo-verde
        0.50,  # Verde
        0.60,  # Verde-cian
        0.70,  # Cian
        0.80,  # Azul
        0.90,  # Magenta
    ]
    
    ne_names = sorted(df["NE Name"].unique())
    
    # Asignar tono fijo a cada NE según su posición alfabética
    ne_hues = {}
    for i, ne in enumerate(ne_names):
        # Usar módulo para ciclar si hay más NEs que colores en la paleta
        ne_hues[ne] = FIXED_HUES[i % len(FIXED_HUES)]
    
    # Generar colores para cada combinación NE-VMType
    color_map = {}
    for ne in ne_names:
        base_hue = ne_hues[ne]
        ne_vm_types = sorted(df[df["NE Name"] == ne]["VM_Type"].unique())
        
        for j, vm_type in enumerate(ne_vm_types):
            # Variar saturación y luminosidad para diferenciar tipos de VM
            # Saturación: 70% a 100% (colores más vivos y saturados)
            # Luminosidad: 90% a 70% (de claro a oscuro, invertido para mejor contraste)
            num_types = max(len(ne_vm_types) - 1, 1)
            saturation = 0.70 + (j / num_types) * 0.30
            lightness = 0.70 - (j / num_types) * 0.20
            
            # Convertir HSL a RGB
            r, g, b = colorsys.hls_to_rgb(base_hue, lightness, saturation)
            color_hex = f'#{int(r*255):02x}{int(g*255):02x}{int(b*255):02x}'
            
            legend_key = f"{ne} - {vm_type}"
            color_map[legend_key] = color_hex
    
    return color_map

@st.cache_data
def load_data(uploaded_file):
    try:
        # Leer contenido para buscar cabecera
        content = uploaded_file.getvalue().decode('utf-8', errors='replace')
        lines = content.split('\n')
        header_row = 0
        for i, line in enumerate(lines[:50]):
            if "Start Time" in line and "NE Name" in line:
                header_row = i
                break
        
        uploaded_file.seek(0)
        df = pd.read_csv(uploaded_file, skiprows=header_row)
        
        # Limpieza de columnas
        df.columns = [c.strip() for c in df.columns]
        
        # Validar columnas
        required_cols = ["Start Time", "NE Name", "VM", "CPU usage (%)"]
        if not all(col in df.columns for col in required_cols):
            return None

        # Procesar fechas
        df["Date"] = pd.to_datetime(df["Start Time"], errors='coerce')
        
        # Procesar VM Info
        vm_info = df["VM"].apply(extract_vm_info)
        df["VM_Name"] = [x[0] for x in vm_info]
        df["VM_Type"] = [x[1] for x in vm_info]
        
        # Asegurar CPU numérico
        df["CPU_Usage"] = pd.to_numeric(df["CPU max usage (%)"], errors='coerce')
        # df["CPU_Average_Usage"] = pd.to_numeric(df["CPU average usage (%)"], errors='coerce')
        
        # Eliminar filas inválidas
        df = df.dropna(subset=["Date", "CPU_Usage", "VM_Name"])
        
        return df
        
    except Exception as e:
        st.error(f"Error procesando el archivo {uploaded_file.name}: {e}")
        return None

# --- INTERFAZ ---

with st.sidebar:
    st.header("Carga de Datos")
    # Permitir múltiples archivos
    uploaded_files = st.file_uploader("Subir archivos CSV (Export Performance)", type=["csv"], accept_multiple_files=True)
    
    st.markdown("---")
    st.subheader("Configuración")

if uploaded_files:
    # Selector de archivo activo
    file_map = {f.name: f for f in uploaded_files}
    selected_filename = st.selectbox("Seleccionar archivo para visualizar", list(file_map.keys()))
    
    active_file = file_map[selected_filename]
    df = load_data(active_file)
    
    if df is not None and not df.empty:
        # --- FILTROS ---
        min_date = df["Date"].min()
        max_date = df["Date"].max()
        
        start_date, end_date = st.sidebar.date_input(
            "Rango de Fechas",
            value=(min_date.date(), max_date.date()),
            min_value=min_date.date(),
            max_value=max_date.date()
        )
        
        all_nes = sorted(df["NE Name"].unique())
        selected_nes = st.sidebar.multiselect("NE Name", all_nes, default=all_nes)
        
        all_types = sorted(df["VM_Type"].unique())
        selected_types = st.sidebar.multiselect("VM Type", all_types, default=all_types)
        
        threshold = st.sidebar.slider("Umbral CPU (%)", 0, 100, 80)

        # Aplicar filtros
        mask = (
            (df["Date"].dt.date >= start_date) &
            (df["Date"].dt.date <= end_date) &
            (df["NE Name"].isin(selected_nes)) &
            (df["VM_Type"].isin(selected_types))
        )
        df_filtered = df.loc[mask]
        
        if df_filtered.empty:
            st.warning("No hay datos para los filtros seleccionados.")
        else:
            # --- DASHBOARD ---
            
            # Métricas
            col1, col2, col3, col4 = st.columns(4)
            col1.metric("NEs Únicos", df_filtered["NE Name"].nunique())
            col2.metric("VMs Únicas", df_filtered["VM_Name"].nunique())
            col3.metric("CPU Promedio", f"{df_filtered['CPU_Usage'].mean():.2f}%")
            col4.metric("CPU Max", f"{df_filtered['CPU_Usage'].max():.2f}%")
            
            st.markdown("---")
            
            # --- GRÁFICA DE TENDENCIA PERSONALIZADA ---
            st.subheader("Tendencia de CPU por NE y Tipo de VM (Promedio Horario)")
            
            # AGRUPACIÓN POR HORA: Reducir ruido visual
            df_filtered["Date_Hour"] = df_filtered["Date"].dt.floor("2H")
            
            # Agrupar por hora y VM para sacar el promedio
            df_trend = df_filtered.groupby(["Date_Hour", "NE Name", "VM_Name", "VM_Type"])["CPU_Usage"].mean().reset_index()
            
            # Renombrar para compatibilidad con el gráfico
            df_trend = df_trend.rename(columns={"Date_Hour": "Date"})
            
            # IMPORTANTE: Ordenar por VM y Fecha para que las líneas conecten correctamente
            df_trend = df_trend.sort_values(["VM_Name", "Date"])
            
            # Crear columna combinada para la leyenda
            df_trend["Legend"] = df_trend["NE Name"] + " - " + df_trend["VM_Type"]
            
            # Generar mapa de colores personalizado
            color_map = generate_color_map(df_trend)
            
            # Usar px.line con line_group para conectar puntos de la misma VM
            fig_line = px.line(
                df_trend, 
                x="Date", 
                y="CPU_Usage", 
                color="Legend",
                line_group="VM_Name", # Conecta solo puntos de la misma VM
                markers=True, # Mostrar puntos
                title="CPU Usage (Promedio cada 2 Horas)",
                template="plotly_white", # Tema limpio
                color_discrete_map=color_map # Aplicar colores personalizados
            )
            
            # Ajustes estéticos avanzados
            fig_line.update_traces(
                marker=dict(size=4, opacity=0.8), 
                line=dict(width=2),
                opacity=0.8 # Transparencia general para ver densidad
            )
            
            # Hover unificado para comparar valores en el mismo instante
            fig_line.update_layout(
                hovermode="x unified"
            )
            
            st.plotly_chart(fig_line, use_container_width=True)
            
            # --- OTRAS GRÁFICAS ---
            col_left, col_right = st.columns(2)
            
            with col_left:
                st.subheader("Top VMs (CPU Promedio)")
                top_n = st.slider("Top N", 5, 50, 10)
                vm_stats = df_filtered.groupby(["VM_Name", "VM_Type", "NE Name"])["CPU_Usage"].mean().reset_index()
                top_vms = vm_stats.sort_values("CPU_Usage", ascending=False).head(top_n)
                st.dataframe(top_vms.style.format({"CPU_Usage": "{:.2f}%"}), use_container_width=True)
                
            with col_right:
                st.subheader("Promedio por NE Name")
                ne_stats = df_filtered.groupby("NE Name")["CPU_Usage"].mean().reset_index().sort_values("CPU_Usage", ascending=False)
                fig_bar = px.bar(
                    ne_stats, 
                    x="NE Name", 
                    y="CPU_Usage", 
                    color="NE Name",
                    text_auto='.2f',
                    template="plotly_white"
                )
                fig_bar.update_layout(showlegend=False)
                st.plotly_chart(fig_bar, use_container_width=True)

            st.subheader("Comparativa por Tipo de VM")
            type_stats = df_filtered.groupby("VM_Type")["CPU_Usage"].agg(['mean', 'max']).reset_index()
            type_stats = type_stats.sort_values('mean', ascending=False)
            
            fig_type = px.bar(
                type_stats, 
                x="VM_Type", 
                y=["mean", "max"], 
                barmode='group',
                title="Promedio vs Máximo CPU por Tipo",
                template="plotly_white"
            )
            st.plotly_chart(fig_type, use_container_width=True)
            
            with st.expander("Ver Datos Detallados"):
                st.dataframe(df_filtered.sort_values("Date", ascending=False))
                
    else:
        st.error("El archivo seleccionado no tiene el formato esperado o está vacío.")

else:
    st.info("👆 Sube uno o más archivos CSV para comenzar.")
