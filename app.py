import streamlit as st
import pandas as pd
import psycopg2
from datetime import datetime, timedelta
import plotly.express as px
from fpdf import FPDF
import io
import time

# --- 1. ESTÉTICA Y DISEÑO UI ---
st.set_page_config(page_title="GeZo Elite Pro", page_icon="💎", layout="wide")

st.markdown("""
    <style>
    .main { background-color: #0b0e14; color: #e0e0e0; }
    div[data-testid="stMetric"] {
        background: rgba(0, 198, 255, 0.08);
        border-radius: 20px; padding: 25px; border: 1px solid #00c6ff;
        box-shadow: 0px 8px 25px rgba(0, 198, 255, 0.15);
        border-left: 10px solid #00c6ff;
    }
    .stButton>button {
        border-radius: 15px; background: linear-gradient(135deg, #00f2fe 0%, #4facfe 100%);
        color: black; font-weight: 800; width: 100%; border: none; height: 4.2em;
        transition: 0.4s all; text-transform: uppercase; letter-spacing: 1.5px;
    }
    .stButton>button:hover { transform: translateY(-4px); box-shadow: 0px 10px 30px #00c6ff; color: white; }
    .coach-box { padding: 35px; border-radius: 25px; margin: 25px 0; border-left: 15px solid; line-height: 2.2; font-size: 1.25em; }
    .rojo { background-color: rgba(255, 75, 75, 0.15); border-color: #ff4b4b; color: #ff4b4b; }
    .verde { background-color: rgba(37, 211, 102, 0.15); border-color: #25d366; color: #25d366; }
    .alerta { background-color: rgba(241, 196, 15, 0.15); border-color: #f1c40f; color: #f1c40f; }
    .user-card { background: rgba(255, 255, 255, 0.05); padding: 30px; border-radius: 20px; border: 1px solid #333; margin-bottom: 20px; border-left: 8px solid #00f2fe; }
    .bank-btn { background-color: #1a1d24; border: 2px solid #00c6ff; color: #00c6ff !important; padding: 20px; border-radius: 15px; text-align: center; display: block; text-decoration: none; font-weight: bold; margin-top: 15px; }
    </style>
    """, unsafe_allow_html=True)

# --- 2. MOTOR DE DATOS ---
@st.cache_resource(show_spinner="Conectando con la Bóveda GeZo...")
def get_connection():
    try:
        return psycopg2.connect(st.secrets["DB_URL"], connect_timeout=60)
    except Exception as e:
        st.error(f"Error crítico de conexión: {e}")
        st.stop()

def inicializar_db():
    conn = get_connection(); c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS usuarios 
                 (id SERIAL PRIMARY KEY, nombre TEXT UNIQUE, clave TEXT, expira DATE, rol TEXT, plan TEXT, precio TEXT)''')
    c.execute('''CREATE TABLE IF NOT EXISTS movimientos 
                 (id SERIAL PRIMARY KEY, usuario_id INTEGER, fecha DATE, descrip TEXT, monto DECIMAL, tipo TEXT, cat TEXT, vence DATE)''')
    c.execute('''CREATE TABLE IF NOT EXISTS metas 
                 (id SERIAL PRIMARY KEY, usuario_id INTEGER, nombre TEXT, objetivo DECIMAL, actual DECIMAL DEFAULT 0)''')
    c.execute('''CREATE TABLE IF NOT EXISTS deudas 
                 (id SERIAL PRIMARY KEY, usuario_id INTEGER, nombre TEXT, monto_total DECIMAL, pagado DECIMAL DEFAULT 0)''')
    try:
        c.execute("ALTER TABLE movimientos ADD COLUMN IF NOT EXISTS vence DATE")
        c.execute("ALTER TABLE usuarios ADD COLUMN IF NOT EXISTS precio TEXT")
    except: pass
    c.execute("SELECT * FROM usuarios WHERE nombre='admin'")
    if not c.fetchone():
        c.execute("INSERT INTO usuarios (nombre, clave, expira, rol, plan, precio) VALUES (%s,%s,%s,%s,%s,%s)", 
                  ('admin', 'admin123', '2099-12-31', 'admin', 'Dueño Master', 'N/A'))
    conn.commit(); c.close()

inicializar_db()

# --- 3. SERVICIOS PDF ---
def limpiar_texto(texto):
    if not texto: return ""
    acentos = {"á":"a","é":"e","í":"i","ó":"o","ú":"u","ñ":"n","₡":"CRC ","Á":"A","É":"E","Í":"I","Ó":"O","Ú":"U","Ñ":"N"}
    for k, v in acentos.items(): texto = texto.replace(k, v)
    return str(texto).encode('latin-1', 'ignore').decode('latin-1')

def generar_pdf_pro(nombre, plan, monto, vence):
    pdf = FPDF(); pdf.add_page()
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
    return pdf.output(dest='S').encode('latin-1', errors='replace')

# --- 4. ACCESO ---
if 'autenticado' not in st.session_state: st.session_state.autenticado = False

if not st.session_state.autenticado:
    st.title("💎 GeZo Elite Pro")
    with st.form("login"):
        u_in = st.text_input("Usuario GeZo"); p_in = st.text_input("Contraseña", type="password")
        if st.form_submit_button("INGRESAR AL PANEL ELITE"):
            conn = get_connection(); c = conn.cursor()
            c.execute("SELECT id, nombre, rol, plan, expira FROM usuarios WHERE nombre=%s AND clave=%s", (u_in, p_in))
            res = c.fetchone()
            if res:
                if datetime.now().date() > res[4]: st.error("Membresía vencida.")
                else:
                    st.session_state.update({"autenticado":True, "uid":res[0], "uname":res[1], "rol":res[2], "plan":res[3]})
                    st.rerun()
            else: st.error("❌ Credenciales incorrectas.")
            c.close()
    st.stop()

# --- 5. NAVEGACIÓN ---
with st.sidebar:
    st.markdown(f"## Hola, {st.session_state.uname} 👑")
    menu = st.radio("MÓDULOS:", ["📊 Dashboard IA", "💸 Registrar Cuentas", "📱 SINPE Rápido", "🤝 Metas y Deudas", "💱 Conversor", "⚙️ Panel Admin"])
    if st.button("🔒 CERRAR SESIÓN"): st.session_state.autenticado = False; st.rerun()

# --- 6. MÓDULO DASHBOARD ---
if menu == "📊 Dashboard IA":
    st.header("Análisis de Inteligencia Financiera 🤖")
    df = pd.read_sql(f"SELECT * FROM movimientos WHERE usuario_id={st.session_state.uid}", get_connection())
    if not df.empty:
        ing = float(df[df['tipo']=='Ingreso']['monto'].sum()); gas = float(df[df['tipo']=='Gasto']['monto'].sum()); bal = ing - gas
        c1, c2, c3 = st.columns(3)
        c1.metric("INGRESOS", f"₡{ing:,.0f}"); c2.metric("GASTOS", f"₡{gas:,.0f}", delta_color="inverse"); c3.metric("SALDO", f"₡{bal:,.0f}")
        st.plotly_chart(px.pie(df[df['tipo']=='Gasto'], values='monto', names='cat', hole=.5, template="plotly_dark"))
    else: st.info("No hay movimientos registrados.")

# --- 7. MÓDULO REGISTRO (BLOQUE CORREGIDO SEGÚN SOLICITUD) ---
elif menu == "💸 Registrar Cuentas":
    st.header("Gestión de Entradas y Salidas")
    
    # Categorías de Egresos
    categorias_gastos = ["⚖️ Pensión Alimentaria", "⚡ Recibo de Luz", "💧 Recibo de Agua", "🏠 Alquiler/Hipoteca", "🛒 Súper/Comida", "📱 Plan Celular/Internet", "🏦 Préstamo Bancario", "🚗 Combustible/Transporte", "🏥 Salud/Farmacia", "🎓 Educación/Escuela", "📦 Otros Gastos"]
    
    # Categorías de Ingresos (AMPLIADA)
    categorias_ingresos = ["💵 Salario Mensual", "💰 Aguinaldo", "📱 SINPE Recibido", "📈 Ventas/Negocio Propio", "🧧 Comisiones/Bonos", "🚜 Ingresos por Servicios/Freelance", "🏢 Alquileres Cobrados", "🏦 Intereses/Inversiones", "🎁 Regalos/Premios", "💸 Devolución de Dinero", "📦 Otros Ingresos"]

    with st.form("form_movimiento"):
        col_a, col_b = st.columns(2)
        with col_a:
            tipo_mov = st.radio("Seleccione el Tipo:", ["Gasto", "Ingreso"], horizontal=True)
            monto_mov = st.number_input("Monto (₡)", min_value=0.0, step=5000.0)
        
        with col_b:
            lista_final = categorias_ingresos if tipo_mov == "Ingreso" else categorias_gastos
            cat_mov = st.selectbox("Categoría Correspondiente:", lista_final)
            fecha_pago = st.date_input("Fecha del Pago Correspondiente:", datetime.now())
        
        nota_opcional = st.text_input("Nota adicional (Opcional):", placeholder="Ej: Pago de horas extra")
        
        if st.form_submit_button("REGISTRAR EN BITÁCORA"):
            try:
                conn = get_connection(); c = conn.cursor()
                c.execute("INSERT INTO movimientos (usuario_id, fecha, descrip, monto, tipo, cat, vence) VALUES (%s,%s,%s,%s,%s,%s,%s)", 
                          (st.session_state.uid, datetime.now().date(), f"{cat_mov}: {nota_opcional}", monto_mov, tipo_mov, cat_mov, fecha_pago))
                conn.commit(); c.close()
                st.success(f"✅ {tipo_mov} registrado con éxito.")
                time.sleep(1); st.rerun()
            except Exception as e: st.error(f"Error: {e}")

# --- 8. MÓDULOS RESTANTES INTACTOS ---
elif menu == "📱 SINPE Rápido":
    st.header("SINPE Móvil Elite")
    ns = st.text_input("Número destino"); ms = st.number_input("Monto", min_value=0)
    st.markdown(f'<a href="https://www.google.com" target="_blank" class="bank-btn">🚀 ABRIR APP BANCARIA</a>', unsafe_allow_html=True)

elif menu == "🤝 Metas y Deudas":
    st.header("Visión Financiera")
    t1, t2 = st.tabs(["🎯 Metas", "🏦 Deudas"])
    with t1: st.info("Módulo de ahorro activo.")
    with t2: st.info("Control de préstamos activo.")

elif menu == "💱 Conversor":
    st.header("Conversor de Divisas Pro")
    mc = st.number_input("Monto (₡):", min_value=0.0)
    st.metric("Dólares ($)", f"{(mc/522.0):,.2f}")

elif menu == "⚙️ Panel Admin" and st.session_state.rol == 'admin':
    st.header("Administración de Clientes")
    with st.expander("➕ NUEVO CLIENTE"):
        with st.form("nu"):
            un = st.text_input("User"); uk = st.text_input("Pass"); up = st.selectbox("Plan", ["Mensual", "Anual"])
            if st.form_submit_button("ACTIVAR"):
                vf = (datetime.now() + timedelta(days=30)).date()
                conn = get_connection(); c = conn.cursor()
                c.execute("INSERT INTO usuarios (nombre, clave, expira, rol, plan, precio) VALUES (%s,%s,%s,%s,%s,%s)", (un, uk, vf, 'usuario', up, "5000"))
                conn.commit(); c.close(); st.rerun()
    u_list = pd.read_sql("SELECT * FROM usuarios WHERE rol!='admin'", get_connection())
    for i, r in u_list.iterrows():
        st.markdown(f'<div class="user-card">👤 {r["nombre"]} | Vence: {r["expira"]}</div>', unsafe_allow_html=True)
        pb = generar_pdf_pro(r['nombre'], r['plan'], r['precio'], str(r['expira']))
        st.download_button(f"Recibo {r['nombre']}", pb, f"Recibo_{r['id']}.pdf")
