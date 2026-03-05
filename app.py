import streamlit as st
import pandas as pd
import psycopg2
from datetime import datetime, timedelta
import plotly.express as px
from fpdf import FPDF
import io
import time

# --- 1. ESTÉTICA Y DISEÑO UI (CSS EXPANDIDO LÍNEA POR LÍNEA) ---
st.set_page_config(page_title="GeZo Elite Pro", page_icon="💎", layout="wide")

st.markdown("""
    <style>
    .main { 
        background-color: #0b0e14; 
        color: #e0e0e0; 
    }
    div[data-testid="stMetric"] {
        background: rgba(0, 198, 255, 0.08);
        border-radius: 20px; 
        padding: 25px; 
        border: 1px solid #00c6ff;
        box-shadow: 0px 8px 25px rgba(0, 198, 255, 0.15);
        border-left: 10px solid #00c6ff;
    }
    .stButton>button {
        border-radius: 15px; 
        background: linear-gradient(135deg, #00f2fe 0%, #4facfe 100%);
        color: black; 
        font-weight: 800; 
        width: 100%; 
        border: none; 
        height: 4.2em;
        transition: 0.4s all; 
        text-transform: uppercase; 
        letter-spacing: 1.5px;
    }
    .stButton>button:hover { 
        transform: translateY(-4px); 
        box-shadow: 0px 10px 30px #00c6ff; 
        color: white; 
    }
    .coach-box { 
        padding: 35px; 
        border-radius: 25px; 
        margin: 25px 0; 
        border-left: 15px solid; 
        line-height: 2.2; 
        font-size: 1.25em; 
    }
    .rojo { 
        background-color: rgba(255, 75, 75, 0.15); 
        border-color: #ff4b4b; 
        color: #ff4b4b; 
    }
    .verde { 
        background-color: rgba(37, 211, 102, 0.15); 
        border-color: #25d366; 
        color: #25d366; 
    }
    .alerta { 
        background-color: rgba(241, 196, 15, 0.15); 
        border-color: #f1c40f; 
        color: #f1c40f; 
    }
    .user-card {
        background: rgba(255, 255, 255, 0.05); 
        padding: 30px; 
        border-radius: 20px;
        border: 1px solid #333; 
        margin-bottom: 20px; 
        border-left: 8px solid #00f2fe;
        transition: 0.4s;
    }
    .user-card:hover { 
        background: rgba(255, 255, 255, 0.1); 
        border-color: #00f2fe; 
        transform: scale(1.01); 
    }
    .bank-btn {
        background-color: #1a1d24; 
        border: 2px solid #00c6ff; 
        color: #00c6ff !important;
        padding: 20px; 
        border-radius: 15px; 
        text-align: center; 
        display: block; 
        text-decoration: none; 
        font-weight: bold; 
        margin-top: 15px; 
        transition: 0.3s;
    }
    .bank-btn:hover { 
        background: #00c6ff; 
        color: black !important; 
    }
    </style>
    """, unsafe_allow_html=True)

# --- 2. MOTOR DE DATOS (CONEXIÓN Y REPARACIÓN AUTOMÁTICA) ---
@st.cache_resource(show_spinner="Conectando con la Bóveda GeZo...")
def get_connection():
    try:
        return psycopg2.connect(st.secrets["DB_URL"], connect_timeout=60)
    except Exception as e:
        st.error(f"Error crítico de conexión: {e}")
        st.stop()

def inicializar_db():
    conn = get_connection()
    c = conn.cursor()
    # Creación de Tablas Maestras
    c.execute('''CREATE TABLE IF NOT EXISTS usuarios 
                 (id SERIAL PRIMARY KEY, nombre TEXT UNIQUE, clave TEXT, expira DATE, rol TEXT, 
                  plan TEXT, precio TEXT, presupuesto DECIMAL DEFAULT 250000)''')
    
    c.execute('''CREATE TABLE IF NOT EXISTS movimientos 
                 (id SERIAL PRIMARY KEY, usuario_id INTEGER, fecha DATE, descrip TEXT, monto DECIMAL, tipo TEXT, cat TEXT, vence DATE)''')
    
    c.execute('''CREATE TABLE IF NOT EXISTS metas 
                 (id SERIAL PRIMARY KEY, usuario_id INTEGER, nombre TEXT, objetivo DECIMAL, actual DECIMAL DEFAULT 0)''')
    
    c.execute('''CREATE TABLE IF NOT EXISTS deudas 
                 (id SERIAL PRIMARY KEY, usuario_id INTEGER, nombre TEXT, monto_total DECIMAL, pagado DECIMAL DEFAULT 0)''')
    
    # Parches de Columnas (Fix para errores de Neon)
    try:
        c.execute("ALTER TABLE movimientos ADD COLUMN IF NOT EXISTS vence DATE")
        c.execute("ALTER TABLE usuarios ADD COLUMN IF NOT EXISTS precio TEXT")
    except:
        pass
        
    # Creación del Admin si no existe
    c.execute("SELECT * FROM usuarios WHERE nombre='admin'")
    if not c.fetchone():
        c.execute("INSERT INTO usuarios (nombre, clave, expira, rol, plan, precio) VALUES (%s,%s,%s,%s,%s,%s)", 
                  ('admin', 'admin123', '2099-12-31', 'admin', 'Dueño Master', 'N/A'))
    conn.commit()
    c.close()

# Ejecución de motor de arranque
inicializar_db()

# --- 3. SERVICIOS (PDF Y FORMATEO DE TEXTO) ---
def limpiar_texto(texto):
    if not texto: return ""
    acentos = {"á":"a","é":"e","í":"i","ó":"o","ú":"u","ñ":"n","₡":"CRC ","Á":"A","É":"E","Í":"I","Ó":"O","Ú":"U","Ñ":"N"}
    for k, v in acentos.items(): texto = texto.replace(k, v)
    return str(texto).encode('latin-1', 'ignore').decode('latin-1')

def generar_pdf_pro(nombre, plan, monto, vence):
    pdf = FPDF()
    pdf.add_page()
    pdf.set_fill_color(11, 14, 20); pdf.rect(0, 0, 210, 297, 'F')
    pdf.set_text_color(255, 255, 255); pdf.set_font("Arial", 'B', 30)
    pdf.cell(200, 50, limpiar_texto("GEZO ELITE PRO 💎"), ln=True, align='C')
    pdf.set_font("Arial", '', 18); pdf.ln(15)
    pdf.cell(200, 15, "RECIBO DIGITAL DE SUSCRIPCION", ln=True, align='C')
    pdf.ln(25); pdf.set_font("Arial", '', 15)
    pdf.cell(200, 12, f"Cliente: {limpiar_texto(nombre)}", ln=True)
    pdf.cell(200, 12, f"Plan: {limpiar_texto(plan)}", ln=True)
    pdf.cell(200, 12, f"Monto Pagado: {limpiar_texto(str(monto))}", ln=True)
    pdf.cell(200, 12, f"Expiracion: {vence}", ln=True)
    pdf.ln(70); pdf.set_font("Arial", 'I', 11)
    pdf.cell(200, 10, "Comprobante oficial generado por el sistema GeZo.", ln=True, align='C')
    return pdf.output(dest='S').encode('latin-1', errors='replace')

# --- 4. GESTIÓN DE SESIÓN ---
if 'autenticado' not in st.session_state:
    st.session_state.autenticado = False

if not st.session_state.autenticado:
    st.title("💎 GeZo Elite Pro")
    st.subheader("Bienvenido al Control Financiero de Alto Nivel")
    with st.container():
        with st.form("login_form"):
            u_in = st.text_input("Usuario GeZo")
            p_in = st.text_input("Contraseña", type="password")
            if st.form_submit_button("INGRESAR AL PANEL ELITE"):
                conn = get_connection(); c = conn.cursor()
                c.execute("SELECT id, nombre, rol, plan, expira FROM usuarios WHERE nombre=%s AND clave=%s", (u_in, p_in))
                res = c.fetchone()
                if res:
                    if datetime.now().date() > res[4]:
                        st.error("❌ Membresía vencida. Contacte al administrador.")
                    else:
                        st.session_state.update({"autenticado":True, "uid":res[0], "uname":res[1], "rol":res[2], "plan":res[3]})
                        st.rerun()
                else:
                    st.error("❌ Credenciales incorrectas.")
                c.close()
    st.stop()

# --- 5. NAVEGACIÓN Y MENÚ ---
with st.sidebar:
    st.markdown(f"## Hola, \n### {st.session_state.uname} 👑")
    st.info(f"Suscripción: {st.session_state.plan}")
    st.divider()
    menu = st.radio("MÓDULOS DISPONIBLES:", [
        "📊 Dashboard IA", 
        "💸 Registrar Cuentas", 
        "📱 SINPE Rápido", 
        "🤝 Metas y Deudas", 
        "💱 Conversor", 
        "⚙️ Panel Admin"
    ])
    st.divider()
    if st.button("🔒 CERRAR SESIÓN"):
        st.session_state.autenticado = False
        st.rerun()

# --- 6. MÓDULO: DASHBOARD IA (EXPANDIDO) ---
if menu == "📊 Dashboard IA":
    st.header("Análisis de Inteligencia Financiera 🤖")
    df = pd.read_sql(f"SELECT * FROM movimientos WHERE usuario_id={st.session_state.uid}", get_connection())
    
    ing = float(df[df['tipo']=='Ingreso']['monto'].sum()) if not df.empty else 0
    gas = float(df[df['tipo']=='Gasto']['monto'].sum()) if not df.empty else 0
    bal = ing - gas
    
    col1, col2, col3 = st.columns(3)
    col1.metric("INGRESOS", f"₡{ing:,.0f}")
    col2.metric("GASTOS", f"₡{gas:,.0f}", delta_color="inverse")
    col3.metric("SALDO DISPONIBLE", f"₡{bal:,.0f}")

    if ing > 0:
        pct = (gas / ing) * 100
        if bal < 0: 
            st.markdown(f'<div class="coach-box rojo"><h3>🚨 ALERTA ROJA</h3><p>Déficit detectado de <b>₡{abs(bal):,.0f}</b>. Tus gastos superan tus ingresos.</p></div>', unsafe_allow_html=True)
        elif pct > 80: 
            st.markdown(f'<div class="coach-box alerta"><h3>⚠️ RIESGO ALTO</h3><p>Has consumido el {pct:.1f}% de tus ingresos. Margen de seguridad mínimo.</p></div>', unsafe_allow_html=True)
        else: 
            st.markdown(f'<div class="coach-box verde"><h3>💎 SALUD ELITE</h3><p>Gestión impecable. Tienes un ahorro real de <b>₡{bal:,.0f}</b>.</p></div>', unsafe_allow_html=True)
    
    if not df.empty:
        st.plotly_chart(px.pie(df[df['tipo']=='Gasto'], values='monto', names='cat', hole=.5, template="plotly_dark", title="Distribución de Gastos Mensuales"))

# --- 7. MÓDULO: REGISTRO (CON PENSIÓN INCLUIDA) ---
elif menu == "💸 Registrar Cuentas":
    st.header("Gestión de Entradas y Salidas")
    g_cats = ["⚖️ Pensión Alimentaria", "⚡ Recibo de Luz", "💧 Recibo de Agua", "🏠 Alquiler/Hipoteca", "🛒 Súper", "📱 Plan Celular", "🏦 Préstamo", "📦 Otros"]
    i_cats = ["💵 Salario", "📱 SINPE Recibido", "💰 Negocio/Ventas", "📈 Inversiones", "📦 Otros"]

    with st.form("form_movimiento"):
        cx, cy = st.columns(2)
        with cx:
            t_m = st.radio("Tipo:", ["Gasto", "Ingreso"], horizontal=True)
            m_m = st.number_input("Monto (₡)", min_value=0.0, step=1000.0)
        with cy:
            c_m = st.selectbox("Categoría:", g_cats if t_m == "Gasto" else i_cats)
            v_m = st.date_input("Vencimiento", datetime.now())
        
        if st.form_submit_button("SINCRONIZAR CON LA NUBE"):
            conn = get_connection(); c = conn.cursor()
            c.execute("INSERT INTO movimientos (usuario_id, fecha, descrip, monto, tipo, cat, vence) VALUES (%s,%s,%s,%s,%s,%s,%s)", 
                      (st.session_state.uid, datetime.now().date(), f"Registro {c_m}", m_m, t_m, c_m, v_m))
            conn.commit(); c.close(); st.success("✅ Datos guardados correctamente.")

# --- 8. MÓDULO: SINPE RÁPIDO ---
elif menu == "📱 SINPE Rápido":
    st.header("SINPE Móvil Elite")
    ns = st.text_input("Número de Teléfono Destino")
    ms = st.number_input("Monto a enviar (₡)", min_value=0)
    bs = st.selectbox("Banco:", ["BNCR", "BAC", "BCR", "BP", "Davivienda", "Promerica"])
    if st.button("ABRIR BANCA Y REGISTRAR"):
        st.markdown(f'<a href="https://www.google.com" target="_blank" class="bank-btn">🚀 ABRIR APLICACIÓN BANCARIA {bs}</a>', unsafe_allow_html=True)

# --- 9. MÓDULO: METAS Y DEUDAS (RECUPERADO) ---
elif menu == "🤝 Metas y Deudas":
    st.header("Visión Financiera a Largo Plazo")
    t1, t2 = st.tabs(["🎯 Mis Metas de Ahorro", "🏦 Control de Deudas"])
    
    with t1:
        with st.form("form_metas"):
            nm = st.text_input("¿Qué quieres comprar/ahorrar?"); om = st.number_input("Monto Objetivo (₡)", min_value=0.0)
            if st.form_submit_button("ACTIVAR META"):
                conn = get_connection(); c = conn.cursor()
                c.execute("INSERT INTO metas (usuario_id, nombre, objetivo) VALUES (%s,%s,%s)", (st.session_state.uid, nm, om))
                conn.commit(); c.close(); st.success("🎯 Meta añadida al radar.")
    
    with t2:
        df_d = pd.read_sql(f"SELECT * FROM deudas WHERE usuario_id={st.session_state.uid}", get_connection())
        if not df_d.empty: st.table(df_d)
        else: st.info("No tienes deudas registradas. ¡Sigue así!")

# --- 10. MÓDULO: CONVERSOR ---
elif menu == "💱 Conversor":
    st.header("Conversor de Divisas Pro")
    mc = st.number_input("Monto a convertir:", min_value=0.0)
    st.metric("Dólares ($)", f"{(mc/522.0):,.2f}")
    st.metric("Colones (₡)", f"{(mc*512.0):,.2f}")

# --- 11. MÓDULO: ADMIN (PDF Y CONTROL TOTAL) ---
elif menu == "⚙️ Panel Admin" and st.session_state.rol == 'admin':
    st.header("Administración de Clientes GeZo")
    
    with st.expander("➕ REGISTRAR NUEVO CLIENTE"):
        with st.form("nuevo_user"):
            un = st.text_input("Username"); uk = st.text_input("Password"); up = st.selectbox("Plan", ["Semana Gratis", "Mensual", "Anual"])
            if st.form_submit_button("DAR DE ALTA"):
                dias = {"Semana Gratis":7, "Mensual":30, "Anual":365}
                precios = {"Semana Gratis":"₡0", "Mensual":"₡5,000", "Anual":"₡45,000"}
                vf = (datetime.now() + timedelta(days=dias[up])).date()
                conn = get_connection(); c = conn.cursor()
                c.execute("INSERT INTO usuarios (nombre, clave, expira, rol, plan, precio) VALUES (%s,%s,%s,%s,%s,%s)", (un, uk, vf, 'usuario', up, precios[up]))
                conn.commit(); c.close(); st.rerun()

    st.subheader("Base de Clientes")
    u_list = pd.read_sql("SELECT * FROM usuarios WHERE rol!='admin'", get_connection())
    for i, r in u_list.iterrows():
        with st.container():
            st.markdown(f'<div class="user-card">👤 <b>{r["nombre"]}</b> | 💎 {r["plan"]} | Vence: {r["expira"]}</div>', unsafe_allow_html=True)
            p_bin = generar_pdf_pro(r['nombre'], r['plan'], r['precio'], str(r['expira']))
            st.download_button(f"📄 Recibo {r['nombre']}", p_bin, f"Recibo_{r['nombre']}.pdf", key=f"pdf_{r['id']}")
            if st.button(f"🗑️ Eliminar a {r['nombre']}", key=f"del_{r['id']}"):
                conn = get_connection(); c = conn.cursor(); c.execute(f"DELETE FROM usuarios WHERE id={r['id']}"); conn.commit(); c.close(); st.rerun()
