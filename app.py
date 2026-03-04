import streamlit as st
import pandas as pd
import sqlite3
from datetime import datetime, timedelta
import plotly.express as px
import plotly.graph_objects as go

# --- 1. CONFIGURACIÓN DE ALTO NIVEL ---
st.set_page_config(page_title="GeZo Elite Pro", page_icon="💎", layout="wide")

# Diseño "Premium Glass" y Optimización Móvil
st.markdown("""
    <style>
    .main { background-color: #0e1117; color: white; }
    div[data-testid="stMetric"] {
        background: rgba(255, 255, 255, 0.05);
        border-radius: 15px;
        padding: 20px;
        border: 1px solid rgba(255, 255, 255, 0.1);
        backdrop-filter: blur(10px);
    }
    .stButton>button {
        border-radius: 12px;
        background: linear-gradient(90deg, #00c6ff 0%, #0072ff 100%);
        color: white; font-weight: bold; border: none; height: 3.5em;
    }
    .prediction-box {
        background: rgba(255, 165, 0, 0.1);
        padding: 15px; border-radius: 12px; border-left: 5px solid orange; margin: 10px 0;
    }
    </style>
    """, unsafe_allow_html=True)

# --- 2. MOTOR DE DATOS ---
conn = sqlite3.connect('gezo_ultimate.db', check_same_thread=False)
c = conn.cursor()
c.execute('CREATE TABLE IF NOT EXISTS usuarios (id INTEGER PRIMARY KEY, nombre TEXT, clave TEXT, expira TEXT, rol TEXT, presupuesto REAL DEFAULT 250000)')
c.execute('CREATE TABLE IF NOT EXISTS movimientos (id INTEGER PRIMARY KEY, usuario_id INTEGER, fecha TEXT, desc TEXT, monto REAL, tipo TEXT, cat TEXT)')
c.execute('CREATE TABLE IF NOT EXISTS metas (id INTEGER PRIMARY KEY, usuario_id INTEGER, nombre TEXT, objetivo REAL, actual REAL)')
conn.commit()

# --- 3. LOGICA INTELIGENTE ---
def obtener_tc(): return {"venta": 518.00} # Simulación BCCR

if 'autenticado' not in st.session_state: st.session_state.autenticado = False
if 'ver_montos' not in st.session_state: st.session_state.ver_montos = True

# --- 4. ACCESO ---
if not st.session_state.autenticado:
    st.title("💎 GeZo Elite Pro")
    st.subheader("La evolución de tus finanzas")
    with st.form("login"):
        u = st.text_input("Usuario")
        p = st.text_input("Contraseña", type="password")
        if st.form_submit_button("INICIAR SESIÓN ELITE"):
            c.execute("SELECT id, nombre, rol, presupuesto FROM usuarios WHERE nombre=? AND clave=?", (u, p))
            res = c.fetchone()
            if res:
                st.session_state.update({"autenticado":True, "uid":res[0], "uname":res[1], "rol":res[2], "pres":res[3]})
                st.rerun()
    st.stop()

# --- 5. PANEL DE CONTROL (SIDEBAR) ---
tc = obtener_tc()
with st.sidebar:
    st.title(f"👑 {st.session_state.uname}")
    st.button("👁️ Privacidad", on_click=lambda: st.session_state.update({"ver_montos": not st.session_state.ver_montos}))
    menu = st.radio("Navegación", ["📊 Dashboard IA", "💸 Registro Rápido", "🎯 Metas Ahorro", "⚙️ Ajustes"])
    st.markdown(f"--- \n *Dólar:* ₡{tc['venta']}")
    if st.button("Cerrar Sesión"):
        st.session_state.autenticado = False
        st.rerun()

# --- MÓDULO DASHBOARD CON IA ---
if menu == "📊 Dashboard IA":
    st.header("Análisis Predictivo")
    
    df = pd.read_sql(f"SELECT * FROM movimientos WHERE usuario_id={st.session_state.uid}", conn)
    ing = df[df['tipo']=='Ingreso']['monto'].sum() if not df.empty else 0
    gas = df[df['tipo']=='Gasto']['monto'].sum() if not df.empty else 0
    bal = ing - gas
    
    # Métrica de Privacidad
    m_ing = f"₡{ing:,.0f}" if st.session_state.ver_montos else "₡ *"
    m_gas = f"₡{gas:,.0f}" if st.session_state.ver_montos else "₡ *"
    m_bal = f"₡{bal:,.0f}" if st.session_state.ver_montos else "₡ *"

    c1, c2, c3 = st.columns(3)
    c1.metric("Ingresos", m_ing)
    c2.metric("Gastos", m_gas, delta="-Presupuesto", delta_color="inverse")
    c3.metric("Saldo Real", m_bal)

    # --- PREDICCIÓN INTELIGENTE ---
    if gas > 0:
        dias_mes = 30
        dia_actual = datetime.now().day
        gasto_diario = gas / dia_actual
        proyeccion = gasto_diario * dias_mes
        
        st.markdown(f'<div class="prediction-box">🤖 <b>Predicción GeZo:</b> Al ritmo actual, terminarás el mes gastando <b>₡{proyeccion:,.0f}</b>.</div>', unsafe_allow_html=True)
        if proyeccion > st.session_state.pres:
            st.error(f"⚠️ ¡Cuidado! Superarás tu presupuesto por ₡{proyeccion - st.session_state.pres:,.0f}")

    # Gráfico de Gastos
    if not df.empty and gas > 0:
        fig = px.bar(df[df['tipo']=='Gasto'], x='cat', y='monto', color='cat', title="Gastos por Categoría", template="plotly_dark")
        st.plotly_chart(fig, use_container_width=True)

# --- MÓDULO REGISTRO RÁPIDO (TIPO IPHONE) ---
elif menu == "💸 Registro Rápido":
    st.header("Nuevo Movimiento")
    col_a, col_b = st.columns(2)
    with col_a:
        st.button("📱 SINPE Rápido", on_click=lambda: st.toast("Modo SINPE Activo"))
    
    with st.form("reg"):
        desc = st.text_input("¿En qué gastaste?")
        monto = st.number_input("Monto (₡)", min_value=0)
        moneda = st.radio("Moneda", ["₡ Colones", "$ Dólares"], horizontal=True)
        cat = st.selectbox("Categoría", ["Comida", "Super", "Sinpe", "Ocio", "Transporte", "Casa", "Salario"])
        tipo = st.selectbox("Tipo", ["Gasto", "Ingreso"])
        
        if st.form_submit_button("REGISTRAR AHORA"):
            monto_final = monto if "₡" in moneda else monto * tc['venta']
            c.execute("INSERT INTO movimientos (usuario_id, fecha, desc, monto, tipo, cat) VALUES (?,?,?,?,?,?)",
                      (st.session_state.uid, datetime.now().strftime("%Y-%m-%d"), desc, monto_final, tipo, cat))
            conn.commit()
            st.balloons()
            st.success("Guardado en la nube ☁️")

# --- MÓDULO METAS DE AHORRO ---
elif menu == "🎯 Metas Ahorro":
    st.header("Tus Metas")
    with st.expander("Añadir Nueva Meta"):
        n_meta = st.text_input("Nombre de la meta (ej. Marchamo)")
        obj_meta = st.number_input("Monto Objetivo (₡)", min_value=0)
        if st.button("Crear Meta"):
            c.execute("INSERT INTO metas (usuario_id, nombre, objetivo, actual) VALUES (?,?,?,?)", (st.session_state.uid, n_meta, obj_meta, 0))
            conn.commit()
            st.rerun()
    
    metas_df = pd.read_sql(f"SELECT * FROM metas WHERE usuario_id={st.session_state.uid}", conn)
    for i, r in metas_df.iterrows():
        st.write(f"*{r['nombre']}*")
        prog = (r['actual'] / r['objetivo']) if r['objetivo'] > 0 else 0
        st.progress(prog)
        st.write(f"₡{r['actual']:,.0f} de ₡{r['objetivo']:,.0f} ({prog*100:.1f}%)")

# --- MÓDULO ADMIN ---
elif menu == "⚙️ Ajustes" and st.session_state.rol == 'admin':
    st.header("Admin: Gestión de Usuarios")
    nu = st.text_input("Nombre Usuario")
    np = st.text_input("Contraseña")
    pres_u = st.number_input("Presupuesto Mensual", value=250000)
    if st.button("CREAR USUARIO PRO"):
        fv = (datetime.now() + timedelta(days=30)).strftime("%Y-%m-%d")
        c.execute("INSERT INTO usuarios (nombre, clave, expira, rol, presupuesto) VALUES (?,?,?,?,?)", (nu, np, fv, 'usuario', pres_u))
        conn.commit()
        st.success("Usuario creado con éxito")
