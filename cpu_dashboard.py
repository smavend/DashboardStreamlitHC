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
    Soporta dos formatos:
    1. Old: "nodeName=VNFP, VM Name=SPU_CGW_0080"
    2. New: "Virtual machine name=VES_SBC08_BSU_3"
    Retorna: (vm_name, vm_type)
    """
    if pd.isna(vm_str):
        return None, None
    
    vm_str = str(vm_str).strip()
    
    # --- FORMATO NUEVO ---
    # Ejemplo: "Virtual machine name=VES_SBC08_BSU_3"
    if "Virtual machine name=" in vm_str:
        try:
            # Extraer el valor después del igual
            full_vm_name = vm_str.split("Virtual machine name=")[1].strip()
            
            parts = full_vm_name.split('_')
            
            # Regla: Retirar site y nombre del equipo (primeras 1 partes)
            # Ejemplo: ARQ_SBCOMU02_OMUSBIG2_1 -> [ARQ, SBCOMU02, OMUSBIG2, 1] -> SBCOMU02_OMUSBIG2_1
            
            if len(parts) > 1:
                # VM Name: Desde la 2ra parte hasta el final
                vm_name = "_".join(parts[1:])
                
                # VM Type: Desde la 2ra parte hasta el penúltimo
                # (Es decir, el nuevo VM Name sin el último segmento)
                if len(parts) > 2:
                    vm_type = "_".join(parts[1:-1])
                else:
                    # Caso borde: A_B_C -> VM Name=C. Type?
                    # Si solo queda una parte en el nombre (ej. C), el tipo podría ser C o UNKNOWN.
                    # Asumiremos que es esa misma parte si no hay sufijo numérico claro, o UNKNOWN.
                    # Para consistencia con "hasta el último guion bajo", si no hay guiones en el nuevo nombre,
                    # tomamos todo el nombre.
                    vm_type = vm_name
            else:
                # Fallback si no tiene la estructura esperada (menos de 2 partes)
                vm_name = full_vm_name
                vm_type = "UNKNOWN"
                
            return vm_name, vm_type
        except Exception:
            return vm_str, "ERROR"

    # --- FORMATO ANTIGUO ---
    # Ejemplo raw: "nodeName=VNFP, VM Name=SPU_CGW_0080"
    
    # Extraer VM Name
    match_name = re.search(r"VM Name=([^,\"]+)", vm_str)
    if match_name:
        vm_name = match_name.group(1).strip()
    else:
        vm_name = vm_str
    
    # Extraer VM Type (Lógica original)
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
    elif "SPU_B" in vm_name_upper:
        vm_type = "SPU_B"
    elif "SPU_C" in vm_name_upper:
        vm_type = "SPU_C"
    elif "SPU_K1" in vm_name_upper:
        vm_type = "SPU_K1"
    elif "SPU_O" in vm_name_upper:
        vm_type = "SPU_O"
    elif "SPU_P" in vm_name_upper:
        vm_type = "SPU_P"
    elif "SPU_J_ARM" in vm_name_upper:
        vm_type = "SPU_J_ARM"
    elif "SPU_J" in vm_name_upper:
        vm_type = "SPU_J"
    elif "SPU_M_ARM" in vm_name_upper:
        vm_type = "SPU_M_ARM"
    elif "SPU_M" in vm_name_upper:
        vm_type = "SPU_M"
    elif "SPU_G" in vm_name_upper:
        vm_type = "SPU_G"
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
            
            legend_key = f"{vm_type}"
            color_map[legend_key] = color_hex
    
    return color_map

def generate_color_map_single_ne(df, ne_name):
    """
    Genera un mapa de colores para un solo NE usando diferentes hues de la paleta
    para cada VM Type (en lugar de variaciones del mismo tono).
    """
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
    
    vm_types = sorted(df[df["NE Name"] == ne_name]["VM_Type"].unique())
    
    color_map = {}
    for i, vm_type in enumerate(vm_types):
        # Asignar un hue diferente a cada VM Type
        hue = FIXED_HUES[i % len(FIXED_HUES)]
        
        # Usar saturación y luminosidad fijas para colores vibrantes
        saturation = 0.85
        lightness = 0.60
        
        # Convertir HSL a RGB
        r, g, b = colorsys.hls_to_rgb(hue, lightness, saturation)
        color_hex = f'#{int(r*255):02x}{int(g*255):02x}{int(b*255):02x}'
        
        legend_key = f"{vm_type}"
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
        
        # Limpieza de columnas (strip whitespace)
        df.columns = [c.strip() for c in df.columns]
        
        # Validar columnas mínimas requeridas
        # Nota: "CPU usage" puede variar de nombre, lo validamos después
        required_cols_base = ["Start Time", "NE Name", "VM"]
        if not all(col in df.columns for col in required_cols_base):
            return None

        # Procesar fechas
        # Intentar inferir formato, soporta ISO y formatos locales
        df["Date"] = pd.to_datetime(df["Start Time"], errors='coerce')
        
        # Procesar VM Info
        vm_info = df["VM"].apply(extract_vm_info)
        df["VM_Name"] = [x[0] for x in vm_info]
        df["VM_Type"] = [x[1] for x in vm_info]
        
        # Procesar CPU Usage (Soporte para ambos formatos)
        if "Maximum CPU Load (%)" in df.columns:
            # Nuevo formato
            df["CPU_Usage"] = pd.to_numeric(df["Mean CPU Load (%)"], errors='coerce')
        elif "CPU max usage (%)" in df.columns:
            # Viejo formato
            df["CPU_Usage"] = pd.to_numeric(df["CPU average usage (%)"], errors='coerce')
        else:
            # Fallback o error
            st.error("No se encontró columna de CPU (Maximum CPU Load (%) o CPU max usage (%))")
            return None
            
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
        
        st.sidebar.markdown("---")
        
        # --- FILTROS ---
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
            df_trend["Legend"] = df_trend["VM_Type"]
            
            # Generar mapa de colores personalizado
            color_map = generate_color_map(df_trend)
            
            # Obtener NE Names únicos seleccionados
            unique_nes = sorted(df_trend["NE Name"].unique())
            
            # --- LÓGICA DE DISTRIBUCIÓN DE GRÁFICOS ---
            if len(unique_nes) == 1:
                # CASO 1: Un solo NE Name -> Gráfico de ancho completo
                ne_name = unique_nes[0]
                df_ne = df_trend[df_trend["NE Name"] == ne_name].copy()
                
                # Usar mapa de colores con diferentes hues para cada VM Type
                color_map_single = generate_color_map_single_ne(df_trend, ne_name)
                
                fig_line = px.line(
                    df_ne, 
                    x="Date", 
                    y="CPU_Usage", 
                    color="Legend",
                    line_group="VM_Name",
                    markers=True,
                    title=f"CPU Usage - {ne_name} (Promedio cada 2 Horas)",
                    template="plotly_white",
                    color_discrete_map=color_map_single
                )
                
                fig_line.update_traces(
                    marker=dict(size=4, opacity=0.8), 
                    line=dict(width=2),
                    opacity=0.8
                )
                
                fig_line.update_layout(
                    hovermode="closest",
                    legend=dict(
                        orientation="v",
                        yanchor="top",
                        y=1,
                        xanchor="left",
                        x=1.02
                    )
                )

                fig_line.update_yaxes(range=[0, 100])
                
                st.plotly_chart(fig_line, use_container_width=True)
                
            else:
                # CASO 2: Múltiples NE Names -> Gráficos distribuidos 2 por fila con paginación
                
                # Configuración de paginación
                GRAPHS_PER_PAGE = 6
                total_nes = len(unique_nes)
                total_pages = (total_nes + GRAPHS_PER_PAGE - 1) // GRAPHS_PER_PAGE  # Redondear hacia arriba
                
                # Inicializar página actual en session state
                if 'current_page' not in st.session_state:
                    st.session_state.current_page = 0
                
                # Controles de paginación
                col_info, col_prev, col_next = st.columns([3, 1, 1])
                
                # Calcular índices para la página actual
                start_idx = st.session_state.current_page * GRAPHS_PER_PAGE
                end_idx = min(start_idx + GRAPHS_PER_PAGE, total_nes)
                page_nes = unique_nes[start_idx:end_idx]
                
                # Generar gráficos para la página actual (2 por fila)
                for i in range(0, len(page_nes), 2):
                    cols = st.columns(2)
                    
                    # Primer gráfico de la fila
                    with cols[0]:
                        try:
                            ne_name = page_nes[i]
                            df_ne = df_trend[df_trend["NE Name"] == ne_name].copy()
                            
                            # Usar mapa de colores con diferentes hues para cada VM Type
                            color_map_single = generate_color_map_single_ne(df_trend, ne_name)
                            
                            if df_ne.empty:
                                st.warning(f"No hay datos para {ne_name}")
                            else:
                                fig_line = px.line(
                                    df_ne, 
                                    x="Date", 
                                    y="CPU_Usage", 
                                    color="Legend",
                                    line_group="VM_Name",
                                    markers=True,
                                    title=f"{ne_name}",
                                    template="plotly_white",
                                    color_discrete_map=color_map_single
                                )
                                
                                fig_line.update_traces(
                                    marker=dict(size=4, opacity=0.8), 
                                    line=dict(width=2),
                                    opacity=0.8
                                )
                                
                                fig_line.update_layout(
                                    hovermode="closest",
                                    legend=dict(
                                        orientation="v",
                                        yanchor="top",
                                        y=1,
                                        xanchor="left",
                                        x=1.02
                                    )
                                )

                                fig_line.update_yaxes(range=[0, 100])
                                
                                st.plotly_chart(fig_line, use_container_width=True)
                        except Exception as e:
                            st.error(f"Error al generar gráfico para {page_nes[i]}: {str(e)}")
                    
                    # Segundo gráfico de la fila (si existe)
                    if i + 1 < len(page_nes):
                        with cols[1]:
                            try:
                                ne_name = page_nes[i + 1]
                                df_ne = df_trend[df_trend["NE Name"] == ne_name].copy()
                                
                                
                                color_map_single = generate_color_map_single_ne(df_trend, ne_name)
                                if df_ne.empty:
                                    st.warning(f"No hay datos para {ne_name}")
                                else:
                                    fig_line = px.line(
                                        df_ne, 
                                        x="Date", 
                                        y="CPU_Usage", 
                                        color="Legend",
                                        line_group="VM_Name",
                                        markers=True,
                                        title=f"{ne_name}",
                                        template="plotly_white",
                                        color_discrete_map=color_map_single
                                    )
                                    
                                    fig_line.update_traces(
                                        marker=dict(size=4, opacity=0.8), 
                                        line=dict(width=2),
                                        opacity=0.8
                                    )
                                    
                                    fig_line.update_layout(
                                        hovermode="closest",
                                        legend=dict(
                                            orientation="v",
                                            yanchor="top",
                                            y=1,
                                            xanchor="left",
                                            x=1.02
                                        )
                                    )

                                    fig_line.update_yaxes(range=[0, 100])
                                    
                                    st.plotly_chart(fig_line, use_container_width=True)
                            except Exception as e:
                                st.error(f"Error al generar gráfico para {page_nes[i + 1]}: {str(e)}")
                
                # Controles de paginación al final también
                st.markdown("---")
                col_prev2, col_info2, col_next2 = st.columns([1, 3, 1])
                
                with col_prev2:
                    if st.button("⬅️ Anterior ", key="prev_bottom", disabled=(st.session_state.current_page == 0)):
                        st.session_state.current_page -= 1
                        st.rerun()
                
                with col_info2:
                    st.info(f"Página {st.session_state.current_page + 1} de {total_pages}")
                
                with col_next2:
                    if st.button("Siguiente ➡️ ", key="next_bottom", disabled=(st.session_state.current_page >= total_pages - 1)):
                        st.session_state.current_page += 1
                        st.rerun()
            
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
