import streamlit as st
import pandas as pd
import psycopg2
from datetime import datetime, timedelta, date
import plotly.express as px
import time

# --- 1. CONFIGURACIÓN E INYECCIÓN DE INTERFAZ FORZADA ---
st.set_page_config(page_title="GeZo Elite Pro", page_icon="💎", layout="wide")

st.markdown("""
    <style>
    /* Bloqueo total de menús nativos de Streamlit */
    #MainMenu {visibility: hidden !important;}
    header {visibility: hidden !important;}
    footer {visibility: hidden !important;}
    .stDeployButton {display:none !important;}
    [data-testid="stToolbar"] {display: none !important;}
    
    /* Fondo y Estética General */
    .main { background-color: #0b0e14; color: #e0e0e0; }
    
    /* Botones de Menú Principal */
    .stButton>button {
        width: 100%;
        border-radius: 10px;
        height: 3em;
        background-color: #1e2633;
        color: white;
        border: 1px solid #333;
        transition: 0.3s;
    }
    .stButton>button:hover {
        border-color: #00f2fe;
        color: #00f2fe;
        background-color: #161b25;
    }
    
    /* Tarjetas de Datos */
    .bac-card {
        background: linear-gradient(135deg, #ff4b4b 0%, #a30000 100%);
        border-radius: 12px; padding: 15px; text-align: center; border: 1px solid #ff4b4b; margin-bottom: 10px;
    }
    .ia-box {
        background: rgba(0, 242, 254, 0.05); border: 1px solid #00f2fe;
        padding: 20px; border-radius: 15px; border-left: 8px solid #00f2fe; margin: 20px 0;
    }
    </style>
    """, unsafe_allow_html=True)

# --- 2. MOTOR DE BASE DE DATOS ---
@st.cache_resource
def get_connection():
    try: return psycopg2.connect(st.secrets["DB_URL"], connect_timeout=60)
    except: st.error("Error DB"); st.stop()

def reg_mov(monto, tipo, cat, desc):
    if monto > 0:
        conn = get_connection(); c = conn.cursor()
        c.execute("INSERT INTO movimientos (usuario_id, fecha, descrip, monto, tipo, cat) VALUES (%s,%s,%s,%s,%s,%s)", 
                  (st.session_state.uid, date.today(), desc, monto, tipo, cat))
        conn.commit(); c.close()

# --- 3. LOGIN ---
if 'autenticado' not in st.session_state: st.session_state.autenticado = False
if 'pagina' not in st.session_state: st.session_state.pagina = "Dashboard"

if not st.session_state.autenticado:
    st.title("💎 GeZo Elite Pro")
    with st.form("login_form"):
        u = st.text_input("Usuario"); p = st.text_input("Clave", type="password")
        if st.form_submit_button("ENTRAR"):
            conn = get_connection(); c = conn.cursor()
            c.execute("SELECT id, nombre, rol, plan, expira FROM usuarios WHERE nombre=%s AND clave=%s", (u, p))
            res = c.fetchone()
            if res and date.today() <= res[4]:
                st.session_state.update({"autenticado":True, "uid":res[0], "uname":res[1], "rol":res[2], "plan":res[3]})
                st.rerun()
            else: st.error("Error de acceso.")
    st.stop()

# --- 4. MENÚ DE BOTONES (VISIBLE PARA TODOS) ---
st.markdown(f"### 👑 GeZo Elite | Bienvenido, {st.session_state.uname}")
cols_menu = st.columns(7)
with cols_menu[0]: 
    if st.button("📊 Inicio"): st.session_state.pagina = "Dashboard"; st.rerun()
with cols_menu[1]: 
    if st.button("💸 Registro"): st.session_state.pagina = "Registro"; st.rerun()
with cols_menu[2]: 
    if st.button("🎯 Metas"): st.session_state.pagina = "Metas"; st.rerun()
with cols_menu[3]: 
    if st.button("🔴 Deudas"): st.session_state.pagina = "Deudas"; st.rerun()
with cols_menu[4]: 
    if st.button("🟢 Cobros"): st.session_state.pagina = "Cobros"; st.rerun()
with cols_menu[5]: 
    if st.button("📱 SINPE"): st.session_state.pagina = "SINPE"; st.rerun()
with cols_menu[6]: 
    if st.button("🔐 Clave"): st.session_state.pagina = "Seguridad"; st.rerun()

st.divider()

# --- 5. LÓGICA DE NAVEGACIÓN POR BOTONES ---

if st.session_state.pagina == "Dashboard":
    # Tipo de Cambio BAC
    c1, c2 = st.columns(2)
    with c1: st.markdown('<div class="bac-card"><small>BAC COMPRA</small><br><b>₡512.00</b></div>', unsafe_allow_html=True)
    with c2: st.markdown('<div class="bac-card"><small>BAC VENTA</small><br><b>₡524.00</b></div>', unsafe_allow_html=True)
    
    df = pd.read_sql(f"SELECT * FROM movimientos WHERE usuario_id={st.session_state.uid} AND fecha >= '{date.today() - timedelta(days=30)}'", get_connection())
    
    if not df.empty:
        ing = float(df[df['tipo']=='Ingreso'].monto.sum())
        gas = float(df[df['tipo']=='Gasto'].monto.sum())
        neto = ing - gas
        
        # IA Box
        st.markdown('<div class="ia-box">', unsafe_allow_html=True)
        st.markdown(f"#### 🤖 GeZo AI Advisor")
        st.write(f"Balance actual: ₡{neto:,.0f}. Para liquidez perfecta deberías ahorrar **₡{neto*0.2:,.0f}**.")
        st.markdown('</div>', unsafe_allow_html=True)
        
        st.plotly_chart(px.bar(df, x='fecha', y='monto', color='tipo', template="plotly_dark"), use_container_width=True)
    else:
        st.info("Dashboard vacío. Registra tu primer movimiento.")

elif st.session_state.pagina == "Registro":
    st.subheader("📝 Nuevo Movimiento")
    t = st.radio("Tipo", ["Gasto", "Ingreso"], horizontal=True)
    m = st.number_input("Monto ₡", min_value=0.0)
    d = st.text_input("Nota")
    if st.button("GUARDAR REGISTRO"):
        reg_mov(m, t, "General", d); st.success("Guardado"); time.sleep(1); st.session_state.pagina = "Dashboard"; st.rerun()

elif st.session_state.pagina == "Metas":
    st.subheader("🎯 Metas de Ahorro")
    # Lógica de creación y listado aquí...
    st.info("Módulo de metas activo.")

elif st.session_state.pagina == "Deudas":
    st.subheader("🔴 Deudas (Lo que yo debo)")
    # Pestaña de deudas...

elif st.session_state.pagina == "Cobros":
    st.subheader("🟢 Cobros (Lo que me deben)")
    # Pestaña de cobros...

elif st.session_state.pagina == "SINPE":
    st.subheader("📱 Registro SINPE Rápido")
    num = st.text_input("Número:")
    mon = st.number_input("Monto:")
    if st.button("REGISTRAR Y ABRIR BANCO"):
        reg_mov(mon, "Gasto", "SINPE", f"A: {num}")
        st.markdown(f'<a href="https://www.google.com" target="_blank" style="text-decoration:none; color:#00f2fe;">🚀 ABRIR BANCO</a>', unsafe_allow_html=True)

elif st.session_state.pagina == "Seguridad":
    st.subheader("🔐 Cambiar Contraseña")
    nv_p = st.text_input("Nueva Clave", type="password")
    if st.button("ACTUALIZAR"):
        conn = get_connection(); c = conn.cursor()
        c.execute("UPDATE usuarios SET clave=%s WHERE id=%s", (nv_p, st.session_state.uid))
        conn.commit(); c.close(); st.success("Clave cambiada con éxito.")
