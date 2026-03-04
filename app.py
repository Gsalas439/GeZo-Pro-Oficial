import streamlit as st
import pandas as pd
import sqlite3
from datetime import datetime, timedelta
import plotly.express as px

# --- 1. CONFIGURACIÓN Y ESTÉTICA "GLASSMORPHISM" ---
st.set_page_config(page_title="GeZo Elite Pro", page_icon="💎", layout="wide")

st.markdown("""
    <style>
    .main { background-color: #0e1117; color: white; }
    div[data-testid="stMetric"] {
        background: rgba(255, 255, 255, 0.05);
        border-radius: 15px; padding: 20px; border: 1px solid rgba(255, 255, 255, 0.1);
        backdrop-filter: blur(10px);
    }
    .stButton>button {
        border-radius: 12px; background: linear-gradient(90deg, #00c6ff 0%, #0072ff 100%);
        color: white; font-weight: bold; height: 3.5em; width: 100%; border: none;
    }
    .whatsapp-btn {
        background-color: #25d366; color: white; padding: 15px; text-align: center;
        border-radius: 12px; text-decoration: none; display: block; font-weight: bold; margin-top: 20px;
    }
    .prediction-box {
        background: rgba(255, 165, 0, 0.1); padding: 15px; border-radius: 12px;
        border-left: 5px solid orange; margin: 10px 0;
    }
    .status-tag {
        padding: 5px 12px; border-radius: 20px; font-size: 12px;
        background: rgba(0, 198, 255, 0.2); border: 1px solid #00c6ff; color: #00c6ff;
    }
    </style>
    """, unsafe_allow_html=True)

# --- 2. MOTOR DE DATOS (VERSION FINAL) ---
conn = sqlite3.connect('gezo_final_master.db', check_same_thread=False)
c = conn.cursor()

def inicializar_db():
    c.execute('''CREATE TABLE IF NOT EXISTS usuarios 
                 (id INTEGER PRIMARY KEY, nombre TEXT, clave TEXT, expira TEXT, rol TEXT, 
                  plan TEXT DEFAULT 'Prueba', presupuesto REAL DEFAULT 250000)''')
    c.execute('''CREATE TABLE IF NOT EXISTS movimientos 
                 (id INTEGER PRIMARY KEY, usuario_id INTEGER, fecha TEXT, desc TEXT, monto REAL, tipo TEXT, cat TEXT)''')
    c.execute('''CREATE TABLE IF NOT EXISTS metas 
                 (id INTEGER PRIMARY KEY, usuario_id INTEGER, nombre TEXT, objetivo REAL, actual REAL)''')
    
    c.execute("SELECT * FROM usuarios WHERE nombre='admin'")
    if not c.fetchone():
        c.execute("INSERT INTO usuarios (nombre, clave, expira, rol, plan) VALUES (?,?,?,?,?)", 
                  ('admin', 'admin123', '2099-12-31', 'admin', 'Dueño Master'))
    conn.commit()

inicializar_db()

# --- 3. VARIABLES Y SESIÓN ---
WHATSAPP_NUM = "50663712477"
TC_DOLAR = 518.00 # Tipo de cambio venta aproximado

if 'autenticado' not in st.session_state: st.session_state.autenticado = False
if 'ver_montos' not in st.session_state: st.session_state.ver_montos = True

# --- 4. LOGIN Y BLOQUEO POR PAGO ---
if not st.session_state.autenticado:
    st.title("💎 GeZo Elite Pro")
    with st.form("login_form"):
        u = st.text_input("Usuario")
        p = st.text_input("Contraseña", type="password")
        if st.form_submit_button("ACCEDER AL SISTEMA"):
            c.execute("SELECT id, nombre, rol, presupuesto, plan, expira FROM usuarios WHERE nombre=? AND clave=?", (u, p))
            res = c.fetchone()
            if res:
                fecha_exp = datetime.strptime(res[5], "%Y-%m-%d").date()
                if datetime.now().date() > fecha_exp:
                    st.error(f"🚫 Tu suscripción ({res[4]}) ha vencido.")
                    st.markdown(f'<a href="https://wa.me/{WHATSAPP_NUM}?text=Hola GeZo, quiero renovar mi plan. Usuario: {u}" class="whatsapp-btn">📲 Contactar Soporte para Renovar</a>', unsafe_allow_html=True)
                else:
                    st.session_state.update({"autenticado":True, "uid":res[0], "uname":res[1], "rol":res[2], "pres":res[3], "plan":res[4]})
                    st.rerun()
            else: st.error("Credenciales incorrectas")
    st.stop()

# --- 5. INTERFAZ Y NAVEGACIÓN ---
with st.sidebar:
    st.title(f"👑 {st.session_state.uname}")
    st.markdown(f'<span class="status-tag">{st.session_state.plan}</span>', unsafe_allow_html=True)
    
    if st.button("👁️ Privacidad (Ocultar/Ver)"):
        st.session_state.ver_montos = not st.session_state.ver_montos
        st.rerun()
    
    menu = st.radio("Módulos", ["📊 Dashboard IA", "💸 Registrar", "💱 Conversor $", "🎯 Metas", "⚙️ Admin"])
    st.markdown(f"--- \n *Dólar:* ₡{TC_DOLAR}")
    if st.button("Cerrar Sesión"):
        st.session_state.autenticado = False
        st.rerun()

# --- 6. FUNCIONALIDADES ---

def fmt(n): return f"₡{n:,.0f}" if st.session_state.ver_montos else "₡ *.*"

# --- DASHBOARD IA ---
if menu == "📊 Dashboard IA":
    st.header("Análisis Predictivo")
    df = pd.read_sql(f"SELECT * FROM movimientos WHERE usuario_id={st.session_state.uid}", conn)
    ing = df[df['tipo']=='Ingreso']['monto'].sum() if not df.empty else 0
    gas = df[df['tipo']=='Gasto']['monto'].sum() if not df.empty else 0
    
    c1, c2, c3 = st.columns(3)
    c1.metric("Ingresos", fmt(ing))
    c2.metric("Gastos", fmt(gas), delta="-Consumo", delta_color="inverse")
    c3.metric("Balance", fmt(ing - gas))

    if gas > 0:
        dia_act = datetime.now().day
        proy = (gas / dia_act) * 30
        st.markdown(f'<div class="prediction-box">🤖 <b>Proyección GeZo:</b> Al ritmo de hoy, cerrarás el mes gastando <b>{fmt(proy)}</b>.</div>', unsafe_allow_html=True)

    if not df.empty and gas > 0:
        fig = px.pie(df[df['tipo']=='Gasto'], values='monto', names='cat', hole=.4, template="plotly_dark", title="¿En qué gastas?")
        st.plotly_chart(fig, use_container_width=True)

# --- REGISTRO ---
elif menu == "💸 Registrar":
    st.header("Nuevo Movimiento")
    with st.form("reg"):
        desc = st.text_input("Detalle")
        monto = st.number_input("Monto", min_value=0.0)
        mon = st.radio("Moneda", ["₡ Colones", "$ Dólares"], horizontal=True)
        cat = st.selectbox("Categoría", ["Comida", "Casa", "Sinpe", "Ocio", "Transporte", "Ahorro"])
        tipo = st.selectbox("Tipo", ["Gasto", "Ingreso"])
        if st.form_submit_button("GUARDAR EN NUBE"):
            m_final = monto if "₡" in mon else monto * TC_DOLAR
            c.execute("INSERT INTO movimientos (usuario_id, fecha, desc, monto, tipo, cat) VALUES (?,?,?,?,?,?)",
                      (st.session_state.uid, datetime.now().strftime("%Y-%m-%d"), desc, m_final, tipo, cat))
            conn.commit()
            st.success("¡Datos sincronizados! 🚀")

# --- CONVERSOR ---
elif menu == "💱 Conversor $":
    st.header("Calculadora de Divisas")
    val = st.number_input("Monto a convertir", min_value=0.0)
    col1, col2 = st.columns(2)
    col1.metric("De $ a ₡", f"₡{val * TC_DOLAR:,.2f}")
    col2.metric("De ₡ a $", f"${val / TC_DOLAR:,.2f}")

# --- METAS ---
elif menu == "🎯 Metas":
    st.header("Metas de Ahorro")
    with st.expander("Nueva Meta"):
        n_m = st.text_input("Nombre de la meta")
        o_m = st.number_input("Objetivo (₡)", min_value=0)
        if st.button("Crear"):
            c.execute("INSERT INTO metas (usuario_id, nombre, objetivo, actual) VALUES (?,?,?,?)", (st.session_state.uid, n_m, o_m, 0))
            conn.commit()
            st.rerun()
    
    metas_df = pd.read_sql(f"SELECT * FROM metas WHERE usuario_id={st.session_state.uid}", conn)
    for i, r in metas_df.iterrows():
        st.write(f"*{r['nombre']}*")
        prog = (r['actual'] / r['objetivo']) if r['objetivo'] > 0 else 0
        st.progress(prog)
        st.caption(f"{fmt(r['actual'])} de {fmt(r['objetivo'])}")

# --- ADMIN ---
elif menu == "⚙️ Admin":
    if st.session_state.rol == 'admin':
        st.header("Panel de Clientes")
        with st.form("nu"):
            un, uc = st.text_input("Usuario"), st.text_input("Clave")
            precios = {
                "Prueba (1 semana) - GRATIS": 7,
                "Mensual - ₡5,000": 30,
                "Semestral - ₡25,000": 180,
                "Anual - ₡45,000": 365,
                "Eterno - ₡100,000": 36500
            }
            p_sel = st.selectbox("Plan", list(precios.keys()))
            if st.form_submit_button("ACTIVAR CLIENTE"):
                venc = (datetime.now() + timedelta(days=precios[p_sel])).strftime("%Y-%m-%d")
                c.execute("INSERT INTO usuarios (nombre, clave, expira, rol, plan) VALUES (?,?,?,?,?)", (un, uc, venc, 'usuario', p_sel))
                conn.commit()
                st.success(f"Usuario {un} creado hasta {venc}")
        
        st.subheader("Usuarios Activos")
        st.dataframe(pd.read_sql("SELECT nombre, plan, expira FROM usuarios WHERE rol!='admin'", conn))
    else:
        st.error("Área restringida.")
