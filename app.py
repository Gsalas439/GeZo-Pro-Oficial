import streamlit as st
import pandas as pd
import psycopg2
from datetime import datetime, timedelta, date
import plotly.express as px
import time

# --- 1. CONFIGURACIÓN E INYECCIÓN DE SEGURIDAD UI ---
st.set_page_config(page_title="GeZo Elite Pro", page_icon="💎", layout="wide", initial_sidebar_state="expanded")

# CSS para ocultar "Manage app", el lomo de Streamlit y forzar el Sidebar
st.markdown("""
    <style>
    /* Ocultar elementos de Streamlit */
    #MainMenu {visibility: hidden !important;}
    header {visibility: hidden !important;}
    footer {visibility: hidden !important;}
    .stDeployButton {display:none !important;}
    [data-testid="stToolbar"] {display: none !important;}
    [data-testid="stDecoration"] {display: none !important;}
    [data-testid="stStatusWidget"] {display: none !important;}
    
    /* Forzar diseño limpio */
    .main { background-color: #0b0e14; color: #e0e0e0; }
    [data-testid="stSidebar"] { 
        background-color: #0f121a !important; 
        border-right: 1px solid #1e2633;
        min-width: 250px !important;
    }
    
    /* Estilos de tarjetas */
    .bac-card {
        background: linear-gradient(135deg, #ff4b4b 0%, #a30000 100%);
        border-radius: 12px; padding: 15px; text-align: center; border: 1px solid #ff4b4b; margin-bottom: 10px;
    }
    .balance-card {
        background: linear-gradient(135deg, #1e2633 0%, #0b0e14 100%);
        border-radius: 15px; padding: 20px; border: 1px solid #333; text-align: center; margin-bottom: 15px;
    }
    .metric-value { font-size: 2em; font-weight: 900; color: #00f2fe; }
    .ia-box {
        background: rgba(0, 242, 254, 0.05); border: 1px solid #00f2fe;
        padding: 20px; border-radius: 15px; border-left: 8px solid #00f2fe; margin-top: 15px;
    }
    </style>
    """, unsafe_allow_html=True)

# --- 2. MOTOR DE BASE DE DATOS ---
@st.cache_resource
def get_connection():
    try:
        return psycopg2.connect(st.secrets["DB_URL"], connect_timeout=60)
    except Exception as e:
        st.error("Error de conexión con la base de datos."); st.stop()

def reg_mov(monto, tipo, cat, desc):
    if monto > 0:
        conn = get_connection(); c = conn.cursor()
        c.execute("INSERT INTO movimientos (usuario_id, fecha, descrip, monto, tipo, cat) VALUES (%s,%s,%s,%s,%s,%s)", 
                  (st.session_state.uid, date.today(), desc, monto, tipo, cat))
        conn.commit(); c.close()

# --- 3. SISTEMA DE LOGIN ---
if 'autenticado' not in st.session_state:
    st.session_state.autenticado = False

if not st.session_state.autenticado:
    st.title("💎 GeZo Elite Pro")
    with st.form("login_form"):
        u = st.text_input("Usuario")
        p = st.text_input("Clave", type="password")
        if st.form_submit_button("ENTRAR"):
            conn = get_connection(); c = conn.cursor()
            c.execute("SELECT id, nombre, rol, plan, expira FROM usuarios WHERE nombre=%s AND clave=%s", (u, p))
            res = c.fetchone()
            if res:
                if date.today() <= res[4]:
                    st.session_state.update({"autenticado":True, "uid":res[0], "uname":res[1], "rol":res[2], "plan":res[3]})
                    st.rerun()
                else: st.error("Membresía expirada.")
            else: st.error("Usuario o clave incorrectos.")
            c.close()
    st.stop()

# --- 4. SIDEBAR DE NAVEGACIÓN (Prioridad Alta) ---
with st.sidebar:
    st.markdown(f"### 👑 BIENVENIDO\n**{st.session_state.uname}**")
    st.divider()
    
    # Aquí definimos el menú que dices que no ves
    menu = st.selectbox("IR A:", [
        "📊 Dashboard e IA", 
        "💸 Registrar Movimiento", 
        "🎯 Mis Metas", 
        "💸 Deudas (Yo debo)", 
        "💰 Cobros (Me deben)", 
        "📱 SINPE Móvil", 
        "📜 Historial"
    ])
    
    st.divider()
    with st.expander("🔐 Seguridad"):
        nv_p = st.text_input("Nueva Clave", type="password")
        if st.button("Actualizar"):
            conn = get_connection(); c = conn.cursor()
            c.execute("UPDATE usuarios SET clave=%s WHERE id=%s", (nv_p, st.session_state.uid))
            conn.commit(); c.close(); st.success("Clave actualizada.")
    
    if st.button("Cerrar Sesión"):
        st.session_state.autenticado = False
        st.rerun()

# --- 5. LÓGICA DE MÓDULOS ---

if menu == "📊 Dashboard e IA":
    st.subheader("Estado Financiero y Divisas BAC")
    
    # Tipo de Cambio
    c1, c2 = st.columns(2)
    with c1: st.markdown('<div class="bac-card"><small>BAC COMPRA</small><br><b>₡512.00</b></div>', unsafe_allow_html=True)
    with c2: st.markdown('<div class="bac-card"><small>BAC VENTA</small><br><b>₡524.00</b></div>', unsafe_allow_html=True)
    
    per = st.select_slider("Periodo:", options=["Día", "Semana", "Mes"])
    dias = {"Día": 0, "Semana": 7, "Mes": 30}
    f_in = date.today() - timedelta(days=dias[per])
    
    df = pd.read_sql(f"SELECT * FROM movimientos WHERE usuario_id={st.session_state.uid} AND fecha >= '{f_in}'", get_connection())
    
    if not df.empty:
        ing = float(df[df['tipo']=='Ingreso'].monto.sum())
        gas = float(df[df['tipo']=='Gasto'].monto.sum())
        neto = ing - gas
        
        # Tarjetas de balance
        col1, col2, col3 = st.columns(3)
        with col1: st.markdown(f'<div class="balance-card"><small>INGRESOS</small><br><span class="metric-value">₡{ing:,.0f}</span></div>', unsafe_allow_html=True)
        with col2: st.markdown(f'<div class="balance-card"><small>GASTOS</small><br><span class="metric-value" style="color:#ff4b4b;">₡{gas:,.0f}</span></div>', unsafe_allow_html=True)
        with col3: st.markdown(f'<div class="balance-card"><small>NETO</small><br><span class="metric-value" style="color:#2ecc71;">₡{neto:,.0f}</span></div>', unsafe_allow_html=True)
        
        # IA Advice
        st.markdown('<div class="ia-box">', unsafe_allow_html=True)
        st.markdown("#### 🤖 GeZo AI Advisor")
        if neto > 0:
            st.write(f"¡Felicidades! Tienes una ganancia neta. Para liquidez perfecta, ahorra **₡{neto*0.2:,.0f}** hoy.")
        else:
            st.write(f"Alerta: Estás en negativo por ₡{abs(neto):,.0f}. Reduce gastos variables.")
        st.markdown('</div>', unsafe_allow_html=True)
    else:
        st.info("Registra movimientos para ver el análisis.")

elif menu == "💸 Registrar Movimiento":
    st.header("Entrada de Datos")
    t = st.radio("Tipo:", ["Gasto", "Ingreso"], horizontal=True)
    cat = st.selectbox("Categoría:", ["Comida", "Salario", "Venta", "Servicios", "Otros"])
    with st.form("f_reg"):
        m = st.number_input("Monto ₡", min_value=0.0)
        d = st.text_input("Detalle")
        if st.form_submit_button("GUARDAR"):
            reg_mov(m, t, cat, d); st.success("Guardado"); time.sleep(0.5); st.rerun()

elif menu == "🎯 Mis Metas":
    st.header("Metas de Ahorro")
    # (Lógica de metas idéntica a la anterior para asegurar estabilidad)
    df_m = pd.read_sql(f"SELECT * FROM metas WHERE usuario_id={st.session_state.uid}", get_connection())
    for _, r in df_m.iterrows():
        st.write(f"🎯 **{r['nombre']}**")
        st.progress(min(float(r['actual'])/float(r['objetivo']), 1.0))
        if st.button(f"Abonar ₡1000 a {r['nombre']}", key=r['id']):
             conn = get_connection(); c = conn.cursor(); c.execute("UPDATE metas SET actual=actual+1000 WHERE id=%s", (r['id'],)); conn.commit(); c.close(); st.rerun()

elif menu == "💸 Deudas (Yo debo)":
    st.header("Cuentas por Pagar")
    # Lógica de deudas...
    st.write("Registra aquí lo que debes a terceros.")

elif menu == "💰 Cobros (Me deben)":
    st.header("Cuentas por Cobrar")
    st.write("Registra aquí lo que te deben a ti.")

elif menu == "📱 SINPE Móvil":
    st.header("Acceso a SINPE")
    num = st.text_input("Número:")
    mon = st.number_input("Monto:")
    if st.button("Registrar y Abrir Banco"):
        reg_mov(mon, "Gasto", "SINPE", f"A: {num}")
        st.success("Registrado. Abre tu app bancaria ahora.")

elif menu == "📜 Historial":
    st.header("Historial")
    df_h = pd.read_sql(f"SELECT * FROM movimientos WHERE usuario_id={st.session_state.uid} ORDER BY id DESC", get_connection())
    st.table(df_h)
