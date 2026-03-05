import streamlit as st
import pandas as pd
import psycopg2
from datetime import datetime, timedelta, date
import plotly.express as px
import time

# --- 1. ESTÉTICA ELITE PRO ---
st.set_page_config(page_title="GeZo Elite Pro", page_icon="💎", layout="wide")

st.markdown("""
    <style>
    #MainMenu {visibility: hidden;} header {visibility: hidden;} footer {visibility: hidden;}
    .stDeployButton {display:none;} [data-testid="stToolbar"] {display: none !important;}
    .main { background-color: #0b0e14; color: #e0e0e0; }
    [data-testid="stSidebar"] { background-color: #0f121a; border-right: 1px solid #1e2633; }
    
    .balance-card {
        background: linear-gradient(135deg, #1e2633 0%, #0b0e14 100%);
        border-radius: 20px; padding: 20px; border: 1px solid #333;
        text-align: center; box-shadow: 0 10px 30px rgba(0,0,0,0.5); margin-bottom: 20px;
    }
    .metric-value { font-size: 2.2em; font-weight: 900; color: #00f2fe; }
    .metric-label { font-size: 0.9em; color: #888; text-transform: uppercase; }
    
    /* Burbuja de IA */
    .ia-box {
        background: rgba(0, 242, 254, 0.05); border: 1px solid #00f2fe;
        padding: 20px; border-radius: 20px; border-left: 10px solid #00f2fe;
        margin-top: 20px; position: relative;
    }
    .ia-badge { background: #00f2fe; color: #000; padding: 2px 10px; border-radius: 5px; font-weight: bold; font-size: 0.7em; }
    
    .user-card { background: rgba(255, 255, 255, 0.03); padding: 15px; border-radius: 12px; border: 1px solid #222; margin-bottom: 10px; border-left: 5px solid #00f2fe; }
    .bank-btn { 
        background: #00f2fe; color: #000 !important; padding: 15px; border-radius: 12px; 
        text-align: center; display: block; text-decoration: none; font-weight: 900; margin-top: 10px;
    }
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
    conn.commit(); c.close()

inicializar_db()

def reg_mov(monto, tipo, cat, desc):
    if monto > 0:
        conn = get_connection(); c = conn.cursor()
        c.execute("INSERT INTO movimientos (usuario_id, fecha, descrip, monto, tipo, cat) VALUES (%s,%s,%s,%s,%s,%s)", 
                  (st.session_state.uid, date.today(), desc, monto, tipo, cat))
        conn.commit(); c.close()

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
            if res and date.today() <= res[4]:
                st.session_state.update({"autenticado":True, "uid":res[0], "uname":res[1], "rol":res[2], "plan":res[3]}); st.rerun()
            else: st.error("Acceso denegado o membresía vencida.")
            c.close()
    st.stop()

# --- 4. NAVEGACIÓN ---
with st.sidebar:
    st.markdown(f"### 👑 {st.session_state.uname}")
    menu = st.radio("MENÚ", ["📊 Dashboard IA", "💸 Registros", "🎯 Metas", "🏦 Deudas", "📱 SINPE", "📜 Historial"])
    with st.expander("🔐 Seguridad"):
        nv_p = st.text_input("Nueva Clave", type="password")
        if st.button("CAMBIAR"):
            conn = get_connection(); c = conn.cursor(); c.execute("UPDATE usuarios SET clave=%s WHERE id=%s", (nv_p, st.session_state.uid)); conn.commit(); c.close(); st.success("Listo")
    if st.button("SALIR"): st.session_state.autenticado = False; st.rerun()

# --- 5. MÓDULOS ---

if menu == "📊 Dashboard IA":
    st.header("Análisis de Inteligencia Financiera")
    per = st.select_slider("Rango de análisis:", options=["Día", "Semana", "Mes"])
    dias = {"Día": 0, "Semana": 7, "Mes": 30}
    f_inicio = date.today() - timedelta(days=dias[per])
    
    df = pd.read_sql(f"SELECT * FROM movimientos WHERE usuario_id={st.session_state.uid} AND fecha >= '{f_inicio}'", get_connection())
    
    if not df.empty:
        ing = float(df[df['tipo']=='Ingreso']['monto'].sum())
        gas = float(df[df['tipo']=='Gasto']['monto'].sum())
        neto = ing - gas
        
        c1, c2, c3 = st.columns(3)
        with c1: st.markdown(f'<div class="balance-card"><p class="metric-label">Ingresos</p><p class="metric-value">₡{ing:,.0f}</p></div>', unsafe_allow_html=True)
        with c2: st.markdown(f'<div class="balance-card"><p class="metric-label">Gastos</p><p class="metric-value" style="color:#ff4b4b;">₡{gas:,.0f}</p></div>', unsafe_allow_html=True)
        with c3: st.markdown(f'<div class="balance-card"><p class="metric-label">Generación Neta</p><p class="metric-value" style="color:#2ecc71;">₡{neto:,.0f}</p></div>', unsafe_allow_html=True)
        
        # --- LÓGICA DE IA ---
        st.markdown('<div class="ia-box">', unsafe_allow_html=True)
        st.markdown('<span class="ia-badge">GEZO AI ADVISOR</span>', unsafe_allow_html=True)
        
        ahorro_ideal = neto * 0.20 if neto > 0 else 0
        
        if neto < 0:
            st.markdown(f"### 🔴 ¡Alerta de Números Rojos, {st.session_state.uname}!")
            st.write("Tus gastos están superando tus ingresos. Te recomiendo revisar la sección de 'Historial' y recortar gastos variables inmediatamente. ¡No uses tarjetas de crédito hoy!")
        elif neto > 0:
            st.markdown(f"### 🟢 ¡Excelente trabajo, {st.session_state.uname}!")
            st.write(f"Vas por muy buen camino. Para mantener una **liquidez perfecta**, hoy deberías separar **₡{ahorro_ideal:,.0f}** (20%) hacia tus metas de ahorro.")
        else:
            st.write("Estás en el punto de equilibrio. Intenta generar un ingreso extra hoy para salir de la zona neutra.")
        
        st.markdown('</div>', unsafe_allow_html=True)
        st.plotly_chart(px.bar(df, x='cat', y='monto', color='tipo', template="plotly_dark"), use_container_width=True)
    else: st.info("Registra tu primer movimiento para activar la IA.")

elif menu == "💸 Registros":
    st.header("Entrada/Salida")
    t_mov = st.radio("Tipo:", ["Gasto", "Ingreso"], horizontal=True)
    cat = st.selectbox("Categoría:", ["Salario", "Ventas", "Luz/Agua", "Comida", "Casa", "Otros"] if t_mov == "Gasto" else ["Salario", "Ventas", "SINPE", "Otros"])
    with st.form("f"):
        m = st.number_input("Monto (₡)", min_value=0.0); d = st.text_input("Nota")
        if st.form_submit_button("GUARDAR"):
            reg_mov(m, t_mov, cat, d); st.success("Guardado"); time.sleep(0.5); st.rerun()

elif menu == "🎯 Metas":
    st.header("Mis Metas")
    with st.expander("Nueva Meta"):
        with st.form("fm"):
            n = st.text_input("Nombre"); obj = st.number_input("Objetivo")
            if st.form_submit_button("CREAR"):
                conn = get_connection(); c = conn.cursor(); c.execute("INSERT INTO metas (usuario_id, nombre, objetivo) VALUES (%s,%s,%s)", (st.session_state.uid, n, obj)); conn.commit(); c.close(); st.rerun()
    df_m = pd.read_sql(f"SELECT * FROM metas WHERE usuario_id={st.session_state.uid}", get_connection())
    for _, r in df_m.iterrows():
        st.markdown(f'<div class="user-card">🎯 {r["nombre"]} | ₡{float(r["actual"]):,.0f} / ₡{float(r["objetivo"]):,.0f}</div>', unsafe_allow_html=True)
        st.progress(min(float(r['actual'])/float(r['objetivo']), 1.0))
        c1, c2 = st.columns([2,1]); m_a = c1.number_input("Ahorrar:", min_value=0.0, key=r['id'])
        if c2.button("ABONAR", key=f"b{r['id']}"):
            conn = get_connection(); c = conn.cursor(); c.execute("UPDATE metas SET actual=actual+%s WHERE id=%s", (m_a, r['id'])); conn.commit(); c.close()
            reg_mov(m_a, "Gasto", "🎯 Ahorro", f"Meta: {r['nombre']}"); st.rerun()

elif menu == "🏦 Deudas":
    st.header("Deudas y Cobros")
    # Pestañas de Deudas/Cobros restauradas
    t1, t2 = st.tabs(["💸 Debo", "💰 Me deben"])
    # ... (Lógica de deudas igual a la anterior pero con reg_mov conectado)

elif menu == "📱 SINPE":
    st.header("SINPE Rápido")
    num = st.text_input("Número:"); mon = st.number_input("Monto")
    if st.button("PROCESAR"):
        reg_mov(mon, "Gasto", "📱 SINPE", f"A: {num}")
        st.markdown(f'<a href="https://www.google.com" target="_blank" class="bank-btn">🏦 IR AL BANCO</a>', unsafe_allow_html=True)

elif menu == "📜 Historial":
    st.header("Historial")
    df_h = pd.read_sql(f"SELECT id, fecha, cat, monto, tipo FROM movimientos WHERE usuario_id={st.session_state.uid} ORDER BY id DESC", get_connection())
    for _, row in df_h.iterrows():
        c1, c2, c3 = st.columns([1,4,1])
        c1.write("🟢" if row['tipo']=="Ingreso" else "🔴")
        c2.write(f"**{row['cat']}** | ₡{row['monto']:,.0f}")
        if c3.button("🗑️", key=row['id']):
            conn = get_connection(); c = conn.cursor(); c.execute(f"DELETE FROM movimientos WHERE id={row['id']}"); conn.commit(); c.close(); st.rerun()
