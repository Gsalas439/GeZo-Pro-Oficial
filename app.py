import streamlit as st
import pandas as pd
import sqlite3
from datetime import datetime, timedelta
import plotly.express as px

# --- 1. CONFIGURACIÓN Y ESTILO ---
st.set_page_config(page_title="GeZo Elite Pro", page_icon="💎", layout="wide")

st.markdown("""
    <style>
    .main { background-color: #0e1117; color: white; }
    div[data-testid="stMetric"] {
        background: rgba(255, 255, 255, 0.05);
        border-radius: 15px; padding: 20px; border: 1px solid rgba(255, 255, 255, 0.1);
    }
    .stButton>button {
        border-radius: 12px; background: linear-gradient(90deg, #00c6ff 0%, #0072ff 100%);
        color: white; font-weight: bold; height: 3.5em; width: 100%;
    }
    .whatsapp-btn {
        background-color: #25d366; color: white; padding: 15px;
        text-align: center; border-radius: 10px; text-decoration: none;
        display: block; font-weight: bold; margin-top: 20px;
    }
    .status-tag {
        padding: 5px 12px; border-radius: 20px; font-size: 12px;
        background: rgba(0, 198, 255, 0.2); border: 1px solid #00c6ff; color: #00c6ff;
    }
    </style>
    """, unsafe_allow_html=True)

# --- 2. BASE DE DATOS ---
conn = sqlite3.connect('gezo_comercial_v1.db', check_same_thread=False)
c = conn.cursor()

def inicializar_db():
    c.execute('''CREATE TABLE IF NOT EXISTS usuarios 
                 (id INTEGER PRIMARY KEY, nombre TEXT, clave TEXT, expira TEXT, rol TEXT, 
                  plan TEXT DEFAULT 'Prueba', presupuesto REAL DEFAULT 250000)''')
    c.execute('''CREATE TABLE IF NOT EXISTS movimientos 
                 (id INTEGER PRIMARY KEY, usuario_id INTEGER, fecha TEXT, desc TEXT, monto REAL, tipo TEXT, cat TEXT)''')
    c.execute("SELECT * FROM usuarios WHERE nombre='admin'")
    if not c.fetchone():
        c.execute("INSERT INTO usuarios (nombre, clave, expira, rol, plan) VALUES (?,?,?,?,?)", 
                  ('admin', 'admin123', '2099-12-31', 'admin', 'Dueño'))
    conn.commit()

inicializar_db()

# --- 3. VARIABLES GLOBALES ---
WHATSAPP_NUM = "50663712477"
MENSAJE_PAGO = "Hola GeZo, quiero renovar mi suscripción de la App. Mi usuario es: "

# --- 4. LOGIN Y SEGURIDAD ---
if 'autenticado' not in st.session_state:
    st.session_state.autenticado = False

if not st.session_state.autenticado:
    st.title("💎 GeZo Elite Pro")
    with st.form("login_form"):
        u = st.text_input("Usuario")
        p = st.text_input("Contraseña", type="password")
        if st.form_submit_button("INICIAR SESIÓN"):
            c.execute("SELECT id, nombre, rol, presupuesto, plan, expira FROM usuarios WHERE nombre=? AND clave=?", (u, p))
            res = c.fetchone()
            if res:
                fecha_exp = datetime.strptime(res[5], "%Y-%m-%d").date()
                if datetime.now().date() > fecha_exp:
                    st.error(f"🚫 Tu plan '{res[4]}' ha vencido.")
                    st.markdown(f'<a href="https://wa.me/{WHATSAPP_NUM}?text={MENSAJE_PAGO}{u}" class="whatsapp-btn">📲 Tocar aquí para renovar por WhatsApp</a>', unsafe_allow_html=True)
                else:
                    st.session_state.update({"autenticado":True, "uid":res[0], "uname":res[1], "rol":res[2], "pres":res[3], "plan":res[4]})
                    st.rerun()
            else: st.error("Credenciales incorrectas")
    st.stop()

# --- 5. SIDEBAR ---
with st.sidebar:
    st.title(f"👑 {st.session_state.uname}")
    st.markdown(f'<span class="status-tag">{st.session_state.plan}</span>', unsafe_allow_html=True)
    menu = st.radio("Menú", ["📊 Mi Dashboard", "💸 Registrar Gasto", "⚙️ Panel Admin"])
    if st.button("Cerrar Sesión"):
        st.session_state.autenticado = False
        st.rerun()

# --- 6. MÓDULOS ---

if menu == "📊 Mi Dashboard":
    st.header("Análisis de tus Finanzas")
    df = pd.read_sql(f"SELECT * FROM movimientos WHERE usuario_id={st.session_state.uid}", conn)
    ing = df[df['tipo']=='Ingreso']['monto'].sum() if not df.empty else 0
    gas = df[df['tipo']=='Gasto']['monto'].sum() if not df.empty else 0
    
    c1, c2, c3 = st.columns(3)
    c1.metric("Ingresos", f"₡{ing:,.0f}")
    c2.metric("Gastos", f"₡{gas:,.0f}")
    c3.metric("Balance", f"₡{ing-gas:,.0f}")

elif menu == "💸 Registrar Gasto":
    st.header("Nuevo Registro")
    with st.form("reg"):
        desc = st.text_input("¿En qué gastaste?")
        monto = st.number_input("Monto (₡)", min_value=0)
        cat = st.selectbox("Categoría", ["Comida", "Casa", "Sinpe", "Ocio", "Salud", "Transporte"])
        tipo = st.selectbox("Tipo", ["Gasto", "Ingreso"])
        if st.form_submit_button("GUARDAR EN NUBE"):
            c.execute("INSERT INTO movimientos (usuario_id, fecha, desc, monto, tipo, cat) VALUES (?,?,?,?,?,?)",
                      (st.session_state.uid, datetime.now().strftime("%Y-%m-%d"), desc, monto, tipo, cat))
            conn.commit()
            st.success("¡Datos guardados!")

elif menu == "⚙️ Panel Admin":
    if st.session_state.rol == 'admin':
        st.header("Gestión de Clientes")
        with st.form("nuevo_u"):
            nu = st.text_input("Nombre del Cliente")
            np = st.text_input("Contraseña")
            # --- PLANES CON PRECIOS ---
            dict_p = {
                "Prueba (1 semana) - GRATIS": 7,
                "Mensual - ₡5,000": 30,
                "Semestral - ₡25,000": 180,
                "Anual - ₡45,000": 365,
                "Eterno - ₡100,000": 36500
            }
            p_sel = st.selectbox("Elegir Plan y Precio", list(dict_p.keys()))
            if st.form_submit_button("CREAR Y ACTIVAR"):
                ven = (datetime.now() + timedelta(days=dict_p[p_sel])).strftime("%Y-%m-%d")
                c.execute("INSERT INTO usuarios (nombre, clave, expira, rol, plan) VALUES (?,?,?,?,?)",
                          (nu, np, ven, 'usuario', p_sel))
                conn.commit()
                st.success(f"✅ Activado: {nu} hasta el {ven}")
        
        st.subheader("Lista de Clientes")
        st.table(pd.read_sql("SELECT nombre, plan, expira FROM usuarios WHERE rol!='admin'", conn))
    else:
        st.error("Acceso solo para el Dueño (Admin)")
