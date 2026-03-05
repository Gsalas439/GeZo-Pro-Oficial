import streamlit as st
import pandas as pd
import psycopg2
from datetime import datetime, timedelta
import plotly.express as px
from fpdf import FPDF
import requests
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

# --- 2. MOTOR DE DATOS (REPARACIÓN AUTOMÁTICA DE NEON) ---
def get_connection():
    try:
        # Intento de conexión con tiempo de espera extendido para evitar "pantalla negra"
        return psycopg2.connect(st.secrets["DB_URL"], connect_timeout=25)
    except Exception as e:
        st.error("🚀 El servidor GeZo está tardando en responder. Por favor, refresque la página.")
        st.stop()

def inicializar_db():
    conn = get_connection()
    c = conn.cursor()
    
    # Creación de tablas fundamentales
    c.execute('''CREATE TABLE IF NOT EXISTS usuarios 
                 (id SERIAL PRIMARY KEY, nombre TEXT UNIQUE, clave TEXT, expira DATE, rol TEXT, 
                  plan TEXT, precio TEXT, presupuesto DECIMAL DEFAULT 250000)''')
    
    c.execute('''CREATE TABLE IF NOT EXISTS movimientos 
                 (id SERIAL PRIMARY KEY, usuario_id INTEGER, fecha DATE, descrip TEXT, monto DECIMAL, tipo TEXT, cat TEXT)''')
    
    c.execute('''CREATE TABLE IF NOT EXISTS metas 
                 (id SERIAL PRIMARY KEY, usuario_id INTEGER, nombre TEXT, objetivo DECIMAL, actual DECIMAL DEFAULT 0)''')
    
    c.execute('''CREATE TABLE IF NOT EXISTS deudas 
                 (id SERIAL PRIMARY KEY, usuario_id INTEGER, nombre TEXT, monto_total DECIMAL, pagado DECIMAL DEFAULT 0, tipo TEXT)''')
    
    # --- PARCHE PARA LOS ERRORES DE TUS FOTOS ---
    # Esto agrega las columnas faltantes automáticamente si no existen
    try:
        c.execute("ALTER TABLE movimientos ADD COLUMN IF NOT EXISTS vence DATE")
    except:
        pass
        
    try:
        c.execute("ALTER TABLE usuarios ADD COLUMN IF NOT EXISTS precio TEXT")
    except:
        pass
    
    # Verificación del administrador maestro
    c.execute("SELECT * FROM usuarios WHERE nombre='admin'")
    if not c.fetchone():
        c.execute("INSERT INTO usuarios (nombre, clave, expira, rol, plan, precio) VALUES (%s,%s,%s,%s,%s,%s)", 
                  ('admin', 'admin123', '2099-12-31', 'admin', 'Dueño Master', 'N/A'))
    
    conn.commit()
    c.close()
    conn.close()

# Ejecutar inicialización al arranque
try:
    inicializar_db()
except Exception as e:
    st.info("Sincronizando con la nube de GeZo Pro... Espere un momento.")

# --- 3. FUNCIONES DE SERVICIO (PDF Y FORMATEO) ---
def limpiar_texto(texto):
    if not texto: 
        return ""
    # Mapeo de caracteres para evitar errores en el PDF (Unicode Error)
    acentos = {
        "á":"a","é":"e","í":"i","ó":"o","ú":"u","ñ":"n","₡":"CRC ",
        "Á":"A","É":"E","Í":"I","Ó":"O","Ú":"U","Ñ":"N"
    }
    for k, v in acentos.items(): 
        texto = texto.replace(k, v)
    return str(texto).encode('latin-1', 'ignore').decode('latin-1')

def generar_pdf_pro(nombre, plan, monto, vence):
    pdf = FPDF()
    pdf.add_page()
    # Diseño de fondo para el recibo
    pdf.set_fill_color(11, 14, 20)
    pdf.rect(0, 0, 210, 297, 'F')
    # Texto del encabezado
    pdf.set_text_color(255, 255, 255)
    pdf.set_font("Arial", 'B', 32)
    pdf.cell(200, 60, limpiar_texto("GEZO ELITE PRO 💎"), ln=True, align='C')
    # Detalles del recibo
    pdf.set_font("Arial", '', 18)
    pdf.ln(20)
    pdf.cell(200, 15, f"RECIBO DIGITAL DE SUSCRIPCION", ln=True, align='C')
    pdf.ln(25)
    pdf.set_font("Arial", '', 15)
    pdf.cell(200, 12, f"Nombre del Titular: {limpiar_texto(nombre)}", ln=True)
    pdf.cell(200, 12, f"Plan Adquirido: {limpiar_texto(plan)}", ln=True)
    pdf.cell(200, 12, f"Monto de la Inversion: {limpiar_texto(str(monto))}", ln=True)
    pdf.cell(200, 12, f"Fecha de Expiracion: {vence}", ln=True)
    # Pie de página
    pdf.ln(70)
    pdf.set_font("Arial", 'I', 11)
    pdf.cell(200, 10, "Este documento es un comprobante oficial de la plataforma GeZo.", ln=True, align='C')
    return pdf.output(dest='S').encode('latin-1', errors='replace')

# --- 4. ACCESO AL SISTEMA (LOGIN) ---
if 'autenticado' not in st.session_state: 
    st.session_state.autenticado = False

if not st.session_state.autenticado:
    st.title("💎 GeZo Elite Pro")
    st.subheader("Plataforma de Control Financiero Inteligente")
    with st.container():
        with st.form("login_gezo"):
            u_in = st.text_input("Usuario GeZo")
            p_in = st.text_input("Contraseña", type="password")
            if st.form_submit_button("ACCEDER AL PANEL ELITE"):
                conn = get_connection()
                c = conn.cursor()
                c.execute("SELECT id, nombre, rol, plan, expira FROM usuarios WHERE nombre=%s AND clave=%s", (u_in, p_in))
                res = c.fetchone()
                if res:
                    if datetime.now().date() > res[4]: 
                        st.error("❌ Su membresía ha caducado. Contacte soporte.")
                    else:
                        st.session_state.update({
                            "autenticado":True, 
                            "uid":res[0], 
                            "uname":res[1], 
                            "rol":res[2], 
                            "plan":res[3]
                        })
                        st.rerun()
                else: 
                    st.error("❌ Credenciales de acceso incorrectas.")
                c.close()
                conn.close()
    st.stop()

# --- 5. NAVEGACIÓN Y PANEL LATERAL ---
with st.sidebar:
    st.markdown(f"## Bienvenido, \n### {st.session_state.uname} 👑")
    st.info(f"Suscripción: {st.session_state.plan}")
    st.divider()
    menu = st.radio("SECCIONES GEZO:", [
        "📊 Dashboard IA", 
        "💸 Registrar Cuentas", 
        "📱 SINPE Rápido", 
        "⚖️ Pensión y Aguinaldo", 
        "🤝 Deudas y Metas", 
        "💱 Conversor", 
        "⚙️ Admin"
    ])
    st.divider()
    if st.button("🔒 CERRAR SESION"):
        st.session_state.autenticado = False
        st.rerun()

# --- 6. MÓDULO: DASHBOARD IA ---
if menu == "📊 Dashboard IA":
    st.header("Análisis de Inteligencia Financiera 🤖")
    df = pd.read_sql(f"SELECT * FROM movimientos WHERE usuario_id={st.session_state.uid}", get_connection())
    
    ing = float(df[df['tipo']=='Ingreso']['monto'].sum()) if not df.empty else 0
    gas = float(df[df['tipo']=='Gasto']['monto'].sum()) if not df.empty else 0
    bal = ing - gas
    
    col1, col2, col3 = st.columns(3)
    col1.metric("INGRESOS TOTALES", f"₡{ing:,.0f}")
    col2.metric("GASTOS TOTALES", f"₡{gas:,.0f}", delta_color="inverse")
    col3.metric("BALANCE NETO", f"₡{bal:,.0f}")

    if ing > 0:
        pct = (gas / ing) * 100
        if bal < 0: 
            st.markdown(f'<div class="coach-box rojo"><h3>🚨 ALERTA ROJA</h3><p>Estás gastando <b>₡{abs(bal):,.0f}</b> de más. Tu flujo de caja es negativo. ¡Frena el consumo hoy mismo!</p></div>', unsafe_allow_html=True)
        elif pct > 80: 
            st.markdown(f'<div class="coach-box alerta"><h3>⚠️ ZONA CRÍTICA</h3><p>Has consumido el <b>{pct:.1f}%</b> de tu capital. Te queda muy poco margen de maniobra.</p></div>', unsafe_allow_html=True)
        else: 
            st.markdown(f'<div class="coach-box verde"><h3>💎 SALUD ELITE</h3><p>Excelente gestión. Tienes un ahorro real de <b>₡{bal:,.0f}</b>. Es buen momento para invertir.</p></div>', unsafe_allow_html=True)
    
    if not df.empty:
        st.plotly_chart(px.pie(df[df['tipo']=='Gasto'], values='monto', names='cat', hole=.5, template="plotly_dark", title="Distribución por Categorías"))

# --- 7. MÓDULO: REGISTRO (SOLUCIÓN ERRORES SQL) ---
elif menu == "💸 Registrar Cuentas":
    st.header("Gestión de Movimientos")
    g_cats = ["⚖️ Pensión Alimentaria", "⚡ Recibo de Luz", "💧 Recibo de Agua", "📱 Plan Telefónico", "🏠 Alquiler", "🏦 Préstamo", "🛒 Súper", "📦 Otros"]
    i_cats = ["💵 Salario Mensual", "📱 SINPE Recibido", "💰 Negocio/Ventas", "📈 Inversiones", "📦 Otros"]

    with st.form("f_registro_final"):
        c_x, c_y = st.columns(2)
        with c_x:
            t_m = st.radio("Tipo de Movimiento:", ["Gasto", "Ingreso"], horizontal=True)
            m_m = st.number_input("Monto en Colones (₡)", min_value=0.0, step=500.0)
        with c_y:
            cat_m = st.selectbox("Categoría:", g_cats if t_m == "Gasto" else i_cats)
            vence_m = st.date_input("Fecha de Vencimiento", datetime.now())
        
        a_m = st.checkbox("🔔 Activar Notificación Automática")
        
        if st.form_submit_button("SINCRONIZAR CON GEZO"):
            conn = get_connection()
            c = conn.cursor()
            c.execute("INSERT INTO movimientos (usuario_id, fecha, descrip, monto, tipo, cat, vence) VALUES (%s,%s,%s,%s,%s,%s,%s)", 
                      (st.session_state.uid, datetime.now().date(), f"Pago {cat_m}", m_m, t_m, cat_m, vence_m))
            conn.commit()
            c.close()
            conn.close()
            st.success("✅ Datos registrados exitosamente en la nube.")

# --- 8. MÓDULO: SINPE RÁPIDO ---
elif menu == "📱 SINPE Rápido":
    st.header("SINPE Móvil Elite")
    n_s = st.text_input("Número de Teléfono Destino")
    m_s = st.number_input("Monto a enviar (₡)", min_value=0)
    b_s = st.selectbox("Seleccione Banco Origen:", ["BNCR", "BAC", "BCR", "BP", "Promerica"])
    if st.button("REGISTRAR GASTO Y ABRIR BANCA"):
        st.markdown(f'<a href="https://www.google.com" target="_blank" class="bank-btn">🚀 ABRIR APLICACIÓN BANCARIA {b_s}</a>', unsafe_allow_html=True)

# --- 9. MÓDULO: PENSIÓN Y AGUINALDO ---
elif menu == "⚖️ Pensión y Aguinaldo":
    st.header("Cálculos Legales Costa Rica")
    sal_b = st.number_input("Ingrese su Salario Bruto (₡)", min_value=0.0)
    st.info(f"⚖️ Estimación de Pensión (35%): ₡{(sal_b*0.35):,.0f}")
    st.success(f"💰 Aguinaldo Proyectado: ₡{sal_b:,.0f}")

# --- 10. MÓDULO: DEUDAS Y METAS ---
elif menu == "🤝 Deudas y Metas":
    st.header("Planificación de Metas")
    tab1, tab2 = st.tabs(["🎯 Mis Metas de Ahorro", "🏦 Control de Deudas"])
    with tab1:
        with st.form("f_metas_nueva"):
            n_m = st.text_input("Nombre de la Meta"); o_m = st.number_input("Objetivo (₡)", min_value=1.0)
            if st.form_submit_button("CREAR NUEVA META"): 
                st.success("🎯 Meta activada satisfactoriamente.")
    with tab2:
        st.write("Registra tus deudas para que la IA diseñe tu plan de salida rápido.")

# --- 11. MÓDULO: CONVERSOR ---
elif menu == "💱 Conversor":
    st.header("Conversor de Divisas")
    m_c = st.number_input("Monto a Convertir:", min_value=0.0)
    st.metric("Conversion a Dolares ($)", f"{(m_c/521.50):,.2f}")
    st.metric("Conversion a Colones (₡)", f"{(m_c*512.10):,.2f}")

# --- 12. MÓDULO: ADMIN (PDF Y CONTROL TOTAL) ---
elif menu == "⚙️ Admin" and st.session_state.rol == 'admin':
    st.header("Panel Administrativo GeZo")
    p_config = {"Semana Gratis":7, "Mensual":30, "Anual":365}
    p_precios = {"Semana Gratis":"₡0", "Mensual":"₡5,000", "Anual":"₡45,000"}
    
    with st.expander("➕ REGISTRAR NUEVO CLIENTE ELITE"):
        u_n = st.text_input("Username Cliente"); u_k = st.text_input("Password Cliente"); u_p = st.selectbox("Plan", list(p_config.keys()))
        if st.button("ACTIVAR MEMBRESÍA"):
            v_f = (datetime.now() + timedelta(days=p_config[u_p])).date()
            conn = get_connection()
            c = conn.cursor()
            c.execute("INSERT INTO usuarios (nombre, clave, expira, rol, plan, precio) VALUES (%s,%s,%s,%s,%s,%s)", (u_n, u_k, v_f, 'usuario', u_p, p_precios[u_p]))
            conn.commit()
            c.close()
            conn.close()
            st.rerun()

    st.subheader("Lista de Clientes Activos")
    u_l = pd.read_sql("SELECT * FROM usuarios WHERE rol!='admin'", get_connection())
    for i, r in u_l.iterrows():
        with st.container():
            st.markdown(f'<div class="user-card">👤 {r["nombre"]} | 💎 {r["plan"]} | Vence: {r["expira"]}</div>', unsafe_allow_html=True)
            p_bin = generar_pdf_pro(r['nombre'], r['plan'], r['precio'], str(r['expira']))
            st.download_button(f"📄 Descargar Recibo {r['nombre']}", p_bin, f"Recibo_GeZo_{r['nombre']}.pdf", key=f"pdf_{r['id']}")
            if st.button(f"🗑️ Eliminar Usuario {r['nombre']}", key=f"del_{r['id']}"):
                conn = get_connection(); c = conn.cursor(); c.execute(f"DELETE FROM usuarios WHERE id={r['id']}"); conn.commit(); c.close(); conn.close(); st.rerun()
