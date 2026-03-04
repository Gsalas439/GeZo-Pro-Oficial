import streamlit as st
import pandas as pd
import sqlite3
from datetime import datetime, timedelta
import plotly.express as px
import io

# --- 1. CONFIGURACIÓN ELITE ---
st.set_page_config(page_title="GeZo Elite Pro v3", page_icon="💎", layout="wide")

# Diseño CSS de alto nivel
st.markdown("""
    <style>
    .main { background-color: #f8f9fa; }
    [data-testid="stMetricValue"] { font-size: 28px; color: #1f77b4; font-weight: bold; }
    .stAlert { border-radius: 15px; }
    .stButton>button { 
        border-radius: 8px; 
        transition: all 0.3s; 
        background-color: #004a99; 
        color: white;
        font-weight: bold;
    }
    .stButton>button:hover { transform: scale(1.02); background-color: #0066cc; }
    </style>
    """, unsafe_allow_html=True)

# --- 2. BASE DE DATOS OPTIMIZADA ---
conn = sqlite3.connect('gezo_pro_v3.db', check_same_thread=False)
c = conn.cursor()

def init_db():
    c.execute('CREATE TABLE IF NOT EXISTS usuarios (id INTEGER PRIMARY KEY, nombre TEXT, clave TEXT, expira TEXT, rol TEXT, precio_plan REAL)')
    c.execute('CREATE TABLE IF NOT EXISTS movimientos (id INTEGER PRIMARY KEY, usuario_id INTEGER, fecha TEXT, desc TEXT, monto REAL, tipo TEXT, cat TEXT)')
    c.execute('CREATE TABLE IF NOT EXISTS deudas (id INTEGER PRIMARY KEY, usuario_id INTEGER, concepto TEXT, monto_total REAL, pagado REAL, tipo TEXT)') # tipo: 'debo' o 'me_deben'
    conn.commit()

init_db()

# Admin por defecto
c.execute("SELECT * FROM usuarios WHERE nombre='admin'")
if not c.fetchone():
    c.execute("INSERT INTO usuarios (nombre, clave, expira, rol) VALUES ('admin', 'admin123', '2099-12-31', 'admin')")
    conn.commit()

# --- 3. SISTEMA DE SESIÓN ---
if 'autenticado' not in st.session_state:
    st.session_state.autenticado = False

if not st.session_state.autenticado:
    col1, col2, col3 = st.columns([1,2,1])
    with col2:
        st.image("https://cdn-icons-png.flaticon.com/512/1052/1052856.png", width=80)
        st.title("Bienvenido a GeZo Elite")
        with st.form("login"):
            u = st.text_input("Usuario")
            p = st.text_input("Contraseña", type="password")
            if st.form_submit_button("INICIAR SESIÓN SEGURO"):
                c.execute("SELECT id, nombre, rol, expira FROM usuarios WHERE nombre=? AND clave=?", (u, p))
                res = c.fetchone()
                if res:
                    exp = datetime.strptime(res[3], "%Y-%m-%d").date()
                    if datetime.now().date() <= exp:
                        st.session_state.update({"autenticado":True, "uid":res[0], "uname":res[1], "rol":res[2]})
                        st.rerun()
                    else: st.error("Suscripción vencida 🛑")
                else: st.error("Credenciales incorrectas ❌")
    st.stop()

# --- 4. NAVEGACIÓN ---
with st.sidebar:
    st.title(f"🚀 {st.session_state.uname}")
    st.info(f"Rol: {st.session_state.rol.capitalize()}")
    menu = st.radio("Módulos:", ["📊 Dashboard", "💸 Movimientos", "🤝 Préstamos/Deudas", "⚙️ Admin"])
    if st.button("Cerrar Sesión"):
        st.session_state.autenticado = False
        st.rerun()

# --- 5. LÓGICA DE MÓDULOS ---

if menu == "📊 Dashboard":
    st.header("Análisis de Salud Financiera")
    df = pd.read_sql(f"SELECT * FROM movimientos WHERE usuario_id={st.session_state.uid}", conn)
    
    if not df.empty:
        df['fecha'] = pd.to_datetime(df['fecha'])
        ing = df[df['tipo']=='Ingreso']['monto'].sum()
        gas = df[df['tipo']=='Gasto']['monto'].sum()
        bal = ing - gas
        
        c1, c2, c3 = st.columns(3)
        c1.metric("Ingresos (₡)", f"₡{ing:,.0f}", "↑")
        c2.metric("Gastos (₡)", f"₡{gas:,.0f}", "↓", delta_color="inverse")
        c3.metric("Balance Actual", f"₡{bal:,.0f}", "💰")

        st.divider()
        col_a, col_b = st.columns(2)
        with col_a:
            fig_pie = px.pie(df, values='monto', names='cat', hole=.4, title="¿En qué gastas?", color_discrete_sequence=px.colors.sequential.RdBu)
            st.plotly_chart(fig_pie, use_container_width=True)
        with col_b:
            df_line = df.groupby('fecha')['monto'].sum().reset_index()
            fig_line = px.line(df_line, x='fecha', y='monto', title="Evolución de Dinero")
            st.plotly_chart(fig_line, use_container_width=True)
    else:
        st.warning("No hay datos suficientes para mostrar el dashboard.")

elif menu == "💸 Movimientos":
    st.header("Registro de Transacciones")
    with st.expander("➕ Agregar Nuevo Movimiento", expanded=True):
        c1, c2 = st.columns(2)
        with c1:
            desc = st.text_input("Descripción")
            monto = st.number_input("Monto ₡", min_value=0)
        with c2:
            tipo = st.selectbox("Tipo", ["Ingreso", "Gasto"])
            cat = st.selectbox("Categoría", ["Salario", "Ventas", "Comida", "Casa", "Diversión", "Préstamo", "Otro"])
        if st.button("GUARDAR EN NUBE"):
            c.execute("INSERT INTO movimientos (usuario_id, fecha, desc, monto, tipo, cat) VALUES (?,?,?,?,?,?)",
                      (st.session_state.uid, datetime.now().strftime("%Y-%m-%d"), desc, monto, tipo, cat))
            conn.commit()
            st.success("Registrado correctamente")
            st.rerun()

elif menu == "🤝 Préstamos/Deudas":
    st.header("Control de Deudas y Cobros")
    with st.form("deudas"):
        pers = st.text_input("Nombre de la Persona/Entidad")
        m_t = st.number_input("Monto Total ₡", min_value=0)
        t_d = st.radio("Tipo", ["Me deben (Cobro)", "Yo debo (Deuda)"], horizontal=True)
        if st.form_submit_button("Crear Compromiso"):
            tipo_db = 'me_deben' if "Me deben" in t_d else 'debo'
            c.execute("INSERT INTO deudas (usuario_id, concepto, monto_total, pagado, tipo) VALUES (?,?,?,?,?)",
                      (st.session_state.uid, pers, m_t, 0, tipo_db))
            conn.commit()
            st.rerun()

    st.subheader("Estado de Cuentas")
    deudas_df = pd.read_sql(f"SELECT * FROM deudas WHERE usuario_id={st.session_state.uid}", conn)
    for i, row in deudas_df.iterrows():
        progreso = (row['pagado'] / row['monto_total']) if row['monto_total'] > 0 else 0
        color = "green" if row['tipo'] == 'me_deben' else "orange"
        st.write(f"*{row['concepto']}* ({row['tipo'].replace('_', ' ').upper()})")
        st.progress(progreso)
        st.write(f"₡{row['pagado']:,.0f} de ₡{row['monto_total']:,.0f}")

elif menu == "⚙️ Admin" and st.session_state.rol == 'admin':
    st.header("Panel de Control Maestro")
    with st.expander("Crear Nuevo Usuario / Plan"):
        nu = st.text_input("Usuario")
        np = st.text_input("Clave")
        planes = {"Semanal":7, "Mensual":30, "Trimestral":90, "Semestral":180, "Anual":365, "Eterno":36500}
        sel_plan = st.selectbox("Plan", list(planes.keys()))
        if st.button("DAR ALTA"):
            fv = (datetime.now() + timedelta(days=planes[sel_plan])).strftime("%Y-%m-%d")
            c.execute("INSERT INTO usuarios (nombre, clave, expira, rol) VALUES (?,?,?,?)", (nu, np, fv, 'usuario'))
            conn.commit()
            st.success(f"Listo! Expira el {fv}")

    st.subheader("Usuarios en el Sistema")
    u_list = pd.read_sql("SELECT nombre, expira FROM usuarios WHERE rol!='admin'", conn)
    st.dataframe(u_list, use_container_width=True)
