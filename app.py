import streamlit as st
import pandas as pd
import psycopg2
from datetime import datetime, timedelta, date
import plotly.express as px
import time

# --- 1. ESTÉTICA ELITE PRO + LIMPIEZA TOTAL ---
st.set_page_config(page_title="GeZo Elite Pro", page_icon="💎", layout="wide")

st.markdown("""
    <style>
    #MainMenu {visibility: hidden;} header {visibility: hidden;} footer {visibility: hidden;}
    .stDeployButton {display:none;} [data-testid="stToolbar"] {display: none !important;}
    .main { background-color: #0b0e14; color: #e0e0e0; }
    [data-testid="stSidebar"] { background-color: #0f121a; border-right: 1px solid #1e2633; }
    
    /* Tarjetas de Balance Pro */
    .balance-card {
        background: linear-gradient(135deg, #1e2633 0%, #0b0e14 100%);
        border-radius: 20px; padding: 20px; border: 1px solid #333;
        text-align: center; box-shadow: 0 10px 30px rgba(0,0,0,0.5);
    }
    .metric-value { font-size: 2em; font-weight: 900; color: #00f2fe; }
    .metric-label { font-size: 0.9em; color: #888; text-transform: uppercase; }
    
    div[data-testid="stMetric"] {
        background: rgba(0, 198, 255, 0.05); border-radius: 15px; padding: 15px; border-left: 5px solid #00f2fe;
    }
    .user-card { background: rgba(255, 255, 255, 0.03); padding: 15px; border-radius: 12px; border: 1px solid #222; margin-bottom: 10px; }
    </style>
    """, unsafe_allow_html=True)

# --- 2. MOTOR DE BASE DE DATOS ---
@st.cache_resource
def get_connection():
    try: return psycopg2.connect(st.secrets["DB_URL"], connect_timeout=60)
    except Exception as e: st.error(f"Error DB: {e}"); st.stop()

def inicializar_db():
    conn = get_connection(); c = conn.cursor()
    c.execute("CREATE TABLE IF NOT EXISTS usuarios (id SERIAL PRIMARY KEY, nombre TEXT UNIQUE, clave TEXT, expira DATE, rol TEXT, plan TEXT)")
    c.execute("CREATE TABLE IF NOT EXISTS movimientos (id SERIAL PRIMARY KEY, usuario_id INTEGER, fecha DATE, descrip TEXT, monto DECIMAL, tipo TEXT, cat TEXT)")
    c.execute("CREATE TABLE IF NOT EXISTS metas (id SERIAL PRIMARY KEY, usuario_id INTEGER, nombre TEXT, objetivo DECIMAL, actual DECIMAL DEFAULT 0)")
    c.execute("CREATE TABLE IF NOT EXISTS deudas (id SERIAL PRIMARY KEY, usuario_id INTEGER, nombre TEXT, monto_total DECIMAL, pagado DECIMAL DEFAULT 0, tipo_registro TEXT, fecha_vence DATE)")
    c.execute("CREATE TABLE IF NOT EXISTS contactos (id SERIAL PRIMARY KEY, usuario_id INTEGER, nombre TEXT, telefono TEXT)")
    
    c.execute("SELECT * FROM usuarios WHERE nombre='admin'")
    if not c.fetchone():
        c.execute("INSERT INTO usuarios (nombre, clave, expira, rol, plan) VALUES ('admin', 'admin123', '2099-12-31', 'admin', 'Master')")
    conn.commit(); c.close()

inicializar_db()

# --- 3. LOGIN ---
if 'autenticado' not in st.session_state: st.session_state.autenticado = False
if not st.session_state.autenticado:
    st.title("💎 GeZo Elite Pro")
    with st.form("login"):
        u = st.text_input("Usuario"); p = st.text_input("Clave", type="password")
        if st.form_submit_button("INGRESAR"):
            conn = get_connection(); c = conn.cursor()
            c.execute("SELECT id, nombre, rol, plan, expira FROM usuarios WHERE nombre=%s AND clave=%s", (u, p))
            res = c.fetchone()
            if res:
                if date.today() > res[4]: st.error("Membresía vencida.")
                else: st.session_state.update({"autenticado":True, "uid":res[0], "uname":res[1], "rol":res[2], "plan":res[3]}); st.rerun()
            else: st.error("Acceso incorrecto.")
            c.close()
    st.stop()

# --- 4. FUNCIONES DE CONEXIÓN (EL CORAZÓN DEL BALANCE) ---
def registrar_movimiento(monto, tipo, cat, desc):
    conn = get_connection(); c = conn.cursor()
    c.execute("INSERT INTO movimientos (usuario_id, fecha, descrip, monto, tipo, cat) VALUES (%s,%s,%s,%s,%s,%s)", 
              (st.session_state.uid, date.today(), desc, monto, tipo, cat))
    conn.commit(); c.close()

# --- 5. NAVEGACIÓN ---
with st.sidebar:
    st.markdown(f"### 👑 {st.session_state.uname}")
    menu = st.radio("NAVEGACIÓN", ["📊 Dashboard General", "💸 Nuevo Registro", "📜 Historial", "🎯 Metas", "🏦 Deudas y Cobros", "📱 SINPE Rápido"])
    if st.session_state.rol == 'admin':
        if st.checkbox("⚙️ Panel Admin"): menu = "⚙️ Admin"
    if st.button("CERRAR SESIÓN"): st.session_state.autenticado = False; st.rerun()

# --- 6. MÓDULOS ---

if menu == "📊 Dashboard General":
    st.header("Perspectiva Financiera")
    periodo = st.select_slider("Rango de Análisis", options=["Día", "Semana", "Mes"])
    
    # Filtros de fecha según periodo
    hoy = date.today()
    if periodo == "Día": fecha_inicio = hoy
    elif periodo == "Semana": fecha_inicio = hoy - timedelta(days=7)
    else: fecha_inicio = hoy - timedelta(days=30)
    
    # Query unificada
    df = pd.read_sql(f"SELECT * FROM movimientos WHERE usuario_id={st.session_state.uid} AND fecha >= '{fecha_inicio}'", get_connection())
    
    if not df.empty:
        ingresos = float(df[df['tipo']=='Ingreso']['monto'].sum())
        gastos = float(df[df['tipo']=='Gasto']['monto'].sum())
        generado = ingresos - gastos
        
        # UI de Balances
        c1, c2, c3 = st.columns(3)
        with c1: st.markdown(f'<div class="balance-card"><p class="metric-label">Ingresos {periodo}</p><p class="metric-value">₡{ingresos:,.0f}</p></div>', unsafe_allow_html=True)
        with c2: st.markdown(f'<div class="balance-card"><p class="metric-label">Gastos {periodo}</p><p class="metric-value" style="color:#ff4b4b;">₡{gastos:,.0f}</p></div>', unsafe_allow_html=True)
        with c3: st.markdown(f'<div class="balance-card"><p class="metric-label">Generación Neta</p><p class="metric-value" style="color:#2ecc71;">₡{generado:,.0f}</p></div>', unsafe_allow_html=True)
        
        st.divider()
        st.subheader(f"Distribución de Gastos ({periodo})")
        fig = px.bar(df[df['tipo']=='Gasto'], x='cat', y='monto', color='cat', template="plotly_dark", barmode='group')
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("No hay datos suficientes para el balance de este periodo.")

elif menu == "💸 Nuevo Registro":
    st.header("Entrada/Salida Directa")
    tipo = st.radio("Tipo:", ["Gasto", "Ingreso"], horizontal=True)
    cat = st.selectbox("Categoría:", ["Salario", "Venta", "Luz", "Agua", "Comida", "Ocio", "Transporte", "Otros"])
    with st.form("f_reg"):
        monto = st.number_input("Monto (₡)", min_value=0.0); det = st.text_input("Nota:")
        if st.form_submit_button("GUARDAR"):
            registrar_movimiento(monto, tipo, cat, det)
            st.success("Registrado y sincronizado con el balance."); st.rerun()

elif menu == "🎯 Metas":
    st.header("Ahorros Conectados")
    # Al ahorrar, se crea un registro de GASTO bajo la categoría 'Ahorro Meta'
    df_m = pd.read_sql(f"SELECT * FROM metas WHERE usuario_id={st.session_state.uid}", get_connection())
    for _, r in df_m.iterrows():
        st.markdown(f'<div class="user-card">🎯 {r["nombre"]} | ₡{float(r["actual"]):,.0f} / ₡{float(r["objetivo"]):,.0f}</div>', unsafe_allow_html=True)
        c_a, c_b = st.columns([2,1]); ab = c_a.number_input("Monto a mover al ahorro:", min_value=0.0, key=f"ab_{r['id']}")
        if c_b.button("TRASLADAR", key=f"btn_{r['id']}"):
            conn = get_connection(); c = conn.cursor()
            c.execute("UPDATE metas SET actual = actual + %s WHERE id = %s", (ab, r['id']))
            conn.commit(); c.close()
            registrar_movimiento(ab, "Gasto", "🎯 Ahorro Meta", f"Abono a: {r['nombre']}")
            st.success("Ahorro registrado en balance."); st.rerun()

elif menu == "🏦 Deudas y Cobros":
    st.header("Gestión de Saldos")
    t1, t2 = st.tabs(["💸 Mis Deudas", "💰 Mis Cobros"])
    with t1:
        df_d = pd.read_sql(f"SELECT * FROM deudas WHERE usuario_id={st.session_state.uid} AND tipo_registro='DEUDA'", get_connection())
        for _, r in df_d.iterrows():
            pend = float(r['monto_total']) - float(r['pagado'])
            st.markdown(f'<div class="user-card">🔴 {r["nombre"]} | Pendiente: ₡{pend:,.0f}</div>', unsafe_allow_html=True)
            c_a, c_b = st.columns(2); ab = c_a.number_input("Monto a pagar:", min_value=0.0, key=f"d_{r['id']}")
            if c_b.button("PAGAR CUOTA", key=f"bd_{r['id']}"):
                conn = get_connection(); c = conn.cursor(); c.execute("UPDATE deudas SET pagado=pagado+%s WHERE id=%s",(ab, r['id'])); conn.commit(); c.close()
                registrar_movimiento(ab, "Gasto", "🏦 Pago Deuda", f"Pago a: {r['nombre']}")
                st.rerun()
    with t2:
        df_c = pd.read_sql(f"SELECT * FROM deudas WHERE usuario_id={st.session_state.uid} AND tipo_registro='COBRO'", get_connection())
        for _, r in df_c.iterrows():
            pend = float(r['monto_total']) - float(r['pagado'])
            st.markdown(f'<div class="user-card">🟢 {r["nombre"]} | Pendiente: ₡{pend:,.0f}</div>', unsafe_allow_html=True)
            c_a, c_b = st.columns(2); ab = c_a.number_input("Monto recibido:", min_value=0.0, key=f"c_{r['id']}")
            if c_b.button("REGISTRAR PAGO", key=f"bc_{r['id']}"):
                conn = get_connection(); c = conn.cursor(); c.execute("UPDATE deudas SET pagado=pagado+%s WHERE id=%s",(ab, r['id'])); conn.commit(); c.close()
                registrar_movimiento(ab, "Ingreso", "💸 Cobro Recibido", f"De: {r['nombre']}")
                st.rerun()

elif menu == "📱 SINPE Rápido":
    st.header("SINPE Móvil Express")
    num = st.text_input("Número:")
    monto = st.number_input("Monto (₡):", min_value=0.0)
    if st.button("REGISTRAR Y ABRIR BANCO"):
        registrar_movimiento(monto, "Gasto", "📱 SINPE", f"Enviado a: {num}")
        st.markdown(f'<a href="https://www.google.com" target="_blank" class="bank-btn">🏦 ABRIR BANCO AHORA</a>', unsafe_allow_html=True)

elif menu == "📜 Historial":
    st.header("Flujo Detallado")
    df_h = pd.read_sql(f"SELECT id, fecha, cat, monto, tipo, descrip FROM movimientos WHERE usuario_id={st.session_state.uid} ORDER BY id DESC", get_connection())
    st.dataframe(df_h, use_container_width=True)
    if st.button("Limpiar historial del día"):
        conn = get_connection(); c = conn.cursor(); c.execute("DELETE FROM movimientos WHERE usuario_id=%s AND fecha=%s", (st.session_state.uid, date.today())); conn.commit(); c.close(); st.rerun()

elif menu == "⚙️ Admin":
    st.header("Panel Maestro")
    st.write("Solo tú puedes ver esto.")
    # (Lógica de creación de usuarios aquí...)
