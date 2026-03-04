import streamlit as st
import pandas as pd
import psycopg2
from datetime import datetime, timedelta
import plotly.express as px
import io

# --- 1. CONFIGURACIÓN Y ESTÉTICA ELITE ---
st.set_page_config(page_title="GeZo Elite Pro", page_icon="💎", layout="wide")

st.markdown("""
    <style>
    .main { background-color: #0b0e14; color: #e0e0e0; }
    div[data-testid="stMetric"] {
        background: linear-gradient(135deg, rgba(0, 198, 255, 0.1) 0%, rgba(0, 114, 255, 0.1) 100%);
        border-radius: 15px; padding: 20px; border: 1px solid #00c6ff;
    }
    .stButton>button {
        border-radius: 12px; background: linear-gradient(90deg, #00f2fe 0%, #4facfe 100%);
        color: black; font-weight: bold; height: 3.5em; width: 100%; border: none;
    }
    .coach-box {
        background: rgba(255, 255, 255, 0.03); padding: 20px; border-radius: 15px;
        border: 1px dashed #00f2fe; margin: 20px 0;
    }
    .emergencia-box {
        background: linear-gradient(90deg, #333333 0%, #222222 100%);
        padding: 15px; border-radius: 12px; border-left: 5px solid #ff007f; margin-bottom: 20px;
    }
    .whatsapp-btn {
        background-color: #25d366; color: white; padding: 10px 20px;
        border-radius: 10px; text-decoration: none; font-weight: bold; display: inline-block;
        text-align: center; width: 100%;
    }
    </style>
    """, unsafe_allow_html=True)

# --- 2. MOTOR DE DATOS (POSTGRESQL) ---
def get_connection():
    return psycopg2.connect(st.secrets["DB_URL"])

def inicializar_db():
    conn = get_connection()
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS usuarios 
                 (id SERIAL PRIMARY KEY, nombre TEXT UNIQUE, clave TEXT, expira DATE, rol TEXT, 
                  plan TEXT, presupuesto DECIMAL DEFAULT 250000)''')
    c.execute('''CREATE TABLE IF NOT EXISTS movimientos 
                 (id SERIAL PRIMARY KEY, usuario_id INTEGER, fecha DATE, descrip TEXT, monto DECIMAL, tipo TEXT, cat TEXT)''')
    c.execute('''CREATE TABLE IF NOT EXISTS metas 
                 (id SERIAL PRIMARY KEY, usuario_id INTEGER, nombre TEXT, objetivo DECIMAL, actual DECIMAL)''')
    c.execute('''CREATE TABLE IF NOT EXISTS deudas 
                 (id SERIAL PRIMARY KEY, usuario_id INTEGER, nombre TEXT, monto_total DECIMAL, pagado DECIMAL DEFAULT 0, tipo TEXT)''')
    
    c.execute("SELECT * FROM usuarios WHERE nombre='admin'")
    if not c.fetchone():
        c.execute("INSERT INTO usuarios (nombre, clave, expira, rol, plan) VALUES (%s, %s, %s, %s, %s)", 
                  ('admin', 'admin123', '2099-12-31', 'admin', 'Dueño Master'))
    conn.commit()
    c.close()
    conn.close()

try:
    inicializar_db()
except Exception as e:
    st.error(f"Error de Conexión: {e}")
    st.stop()

# --- 3. LÓGICA DE ACCESO ---
WHATSAPP_NUM = "50663712477"
TC_DOLAR = 518.00 

if 'autenticado' not in st.session_state: st.session_state.autenticado = False
if 'ver_montos' not in st.session_state: st.session_state.ver_montos = True

if not st.session_state.autenticado:
    st.title("💎 GeZo Elite Pro")
    with st.form("login"):
        u = st.text_input("Usuario")
        p = st.text_input("Contraseña", type="password")
        if st.form_submit_button("INGRESAR"):
            conn = get_connection()
            c = conn.cursor()
            c.execute("SELECT id, nombre, rol, presupuesto, plan, expira FROM usuarios WHERE nombre=%s AND clave=%s", (u, p))
            res = c.fetchone()
            if res:
                if datetime.now().date() > res[5]:
                    st.error("⚠️ Tu suscripción ha vencido.")
                    st.markdown(f'<a href="https://wa.me/{WHATSAPP_NUM}?text=Hola, mi suscripción venció" class="whatsapp-btn">📲 Contactar Soporte</a>', unsafe_allow_html=True)
                else:
                    st.session_state.update({"autenticado":True, "uid":res[0], "uname":res[1], "rol":res[2], "pres":res[3], "plan":res[4]})
                    st.rerun()
            else: st.error("Acceso incorrecto.")
            c.close()
            conn.close()
    st.stop()

def fmt(n): return f"₡{float(n):,.0f}" if st.session_state.ver_montos else "₡ *.*"

# --- 4. NAVEGACIÓN ---
with st.sidebar:
    st.title(f"👑 {st.session_state.uname}")
    st.info(f"Plan: {st.session_state.plan}")
    if st.button("👁️ Privacidad"):
        st.session_state.ver_montos = not st.session_state.ver_montos
        st.rerun()
    menu = st.radio("Secciones", ["📊 Dashboard IA", "📱 SINPE Rápido", "💸 Registrar", "🤝 Deudas y Cobros", "💱 Conversor", "🎯 Metas", "⚙️ Admin"])
    if st.button("Cerrar Sesión"):
        st.session_state.autenticado = False
        st.rerun()

# --- 5. MÓDULOS ---

if menu == "📊 Dashboard IA":
    st.header("Análisis GeZo IA")
    st.markdown('<div class="emergencia-box">🛡️ RETO: Fondo de Emergencia ₡500,000</div>', unsafe_allow_html=True)
    
    df = pd.read_sql(f"SELECT * FROM movimientos WHERE usuario_id={st.session_state.uid}", get_connection())
    ing = df[df['tipo']=='Ingreso']['monto'].sum() if not df.empty else 0
    gas = df[df['tipo']=='Gasto']['monto'].sum() if not df.empty else 0
    balance = float(ing) - float(gas)
    
    c1, c2, c3 = st.columns(3)
    c1.metric("Ingresos", fmt(ing))
    c2.metric("Gastos", fmt(gas), delta_color="inverse")
    c3.metric("Saldo Real", fmt(balance))

    st.markdown('<div class="coach-box">', unsafe_allow_html=True)
    st.subheader("🤖 Recomendaciones")
    if balance < 0: st.error("⚠️ Estás gastando más de lo que ganas. ¡Cuidado!")
    else: st.success("💎 Balance positivo. ¡Vas por buen camino!")
    st.markdown('</div>', unsafe_allow_html=True)

    if not df.empty:
        fig = px.pie(df[df['tipo']=='Gasto'], values='monto', names='cat', hole=.4, template="plotly_dark")
        st.plotly_chart(fig, use_container_width=True)

elif menu == "📱 SINPE Rápido":
    st.header("Envío SINPE")
    with st.form("s_f"):
        num = st.text_input("Número (8 dígitos)")
        mon = st.number_input("Monto", min_value=0)
        ban = st.selectbox("Banco", ["BNCR", "BAC", "BCR", "BP"])
        if st.form_submit_button("REGISTRAR Y ABRIR BANCO"):
            conn = get_connection()
            c = conn.cursor()
            c.execute("INSERT INTO movimientos (usuario_id, fecha, descrip, monto, tipo, cat) VALUES (%s,%s,%s,%s,%s,%s)",
                      (st.session_state.uid, datetime.now().date(), f"SINPE a {num}", mon, "Gasto", "📱 SINPE"))
            conn.commit()
            c.close()
            conn.close()
            lk = {"BNCR": "https://www.bnmovil.fi.cr/", "BAC": "https://www.baccredomatic.com/", "BCR": "https://www.bancobcr.com/", "BP": "https://www.bancopopular.fi.cr/"}
            st.markdown(f'<a href="{lk[ban]}" target="_blank" class="whatsapp-btn">🚀 Ir a {ban}</a>', unsafe_allow_html=True)

elif menu == "💸 Registrar":
    st.header("Nuevo Movimiento")
    with st.form("r_f"):
        desc = st.text_input("Detalle")
        monto = st.number_input("Monto", min_value=0.0)
        cat = st.selectbox("Categoría", ["⚖️ Pensión", "⛽ Gasolina", "🛒 Súper", "🏠 Casa", "⚡ Servicios", "📱 SINPE", "💡 Gastos Hormiga", "🏦 Deudas", "💰 Ahorro", "💵 Salario", "📦 Otros"])
        tipo = st.selectbox("Tipo", ["Gasto", "Ingreso"])
        if st.form_submit_button("GUARDAR"):
            conn = get_connection()
            c = conn.cursor()
            c.execute("INSERT INTO movimientos (usuario_id, fecha, descrip, monto, tipo, cat) VALUES (%s,%s,%s,%s,%s,%s)",
                      (st.session_state.uid, datetime.now().date(), desc, monto, tipo, cat))
            conn.commit()
            c.close()
            conn.close()
            st.success("¡Hecho!")

elif menu == "⚙️ Admin":
    if st.session_state.rol == 'admin':
        st.header("💎 Gestión de Membresías")
        
        config_planes = {
            "Prueba (7 días)": {"d": 7, "p": "Gratis"},
            "Mensual": {"d": 30, "p": "₡5,000"},
            "Trimestral": {"d": 90, "p": "₡13,500"},
            "Semestral": {"d": 180, "p": "₡25,000"},
            "Anual": {"d": 365, "p": "₡45,000"},
            "Eterno (De por vida)": {"d": 36500, "p": "₡100,000"} 
        }

        with st.form("admin_form"):
            c1, c2 = st.columns(2)
            with c1:
                u_new = st.text_input("Usuario")
                p_new = st.text_input("Clave")
            with c2:
                p_sel = st.selectbox("Plan:", list(config_planes.keys()))
                st.info(f"Precio: {config_planes[p_sel]['p']}")
            
            if st.form_submit_button("ACTIVAR CUENTA"):
                vf = (datetime.now() + timedelta(days=config_planes[p_sel]['d'])).date()
                conn = get_connection()
                c = conn.cursor()
                try:
                    c.execute("INSERT INTO usuarios (nombre, clave, expira, rol, plan) VALUES (%s,%s,%s,%s,%s)", 
                              (u_new, p_new, vf, 'usuario', p_sel))
                    conn.commit()
                    st.success(f"¡Activado! Vence: {vf}")
                except: st.error("El usuario ya existe.")
                finally:
                    c.close()
                    conn.close()

        st.subheader("👥 Usuarios en el Sistema")
        df_u = pd.read_sql("SELECT nombre, plan, expira FROM usuarios WHERE rol!='admin' ORDER BY expira DESC", get_connection())
        st.table(df_u)

elif menu == "🤝 Deudas y Cobros":
    st.header("Préstamos y Cobros")
    with st.form("d_f"):
        dn = st.text_input("Nombre")
        dm = st.number_input("Monto", min_value=0.0)
        dt = st.selectbox("Tipo", ["Me deben", "Yo debo"])
        if st.form_submit_button("REGISTRAR"):
            conn = get_connection()
            c = conn.cursor()
            c.execute("INSERT INTO deudas (usuario_id, nombre, monto_total, pagado, tipo) VALUES (%s,%s,%s,%s,%s)", (st.session_state.uid, dn, dm, 0, dt))
            conn.commit()
            c.close()
            conn.close()
            st.rerun()
    
    st.subheader("Resumen")
    deu = pd.read_sql(f"SELECT * FROM deudas WHERE usuario_id={st.session_state.uid}", get_connection())
    for _, r in deu.iterrows():
        resta = float(r['monto_total']) - float(r['pagado'])
        st.write(f"*{r['nombre']}*: Falta {fmt(resta)} ({r['tipo']})")

elif menu == "💱 Conversor":
    st.header("Calculadora de Divisas")
    m = st.number_input("Monto", min_value=0.0)
    st.write(f"₡{m * TC_DOLAR:,.2f} colones | ${m / TC_DOLAR:,.2f} dólares")

elif menu == "🎯 Metas":
    st.header("Tus Metas")
    metas = pd.read_sql(f"SELECT * FROM metas WHERE usuario_id={st.session_state.uid}", get_connection())
    for _, r in metas.iterrows():
        st.write(f"*{r['nombre']}*")
        st.progress(float(r['actual'])/float(r['objetivo']) if float(r['objetivo']) > 0 else 0)
