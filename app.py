import streamlit as st
import pandas as pd
import psycopg2
from datetime import datetime, timedelta
import plotly.express as px
from fpdf import FPDF
import requests
import io

# --- 1. ESTÉTICA Y CONFIGURACIÓN ---
st.set_page_config(page_title="GeZo Elite Pro", page_icon="💎", layout="wide")

st.markdown("""
    <style>
    .main { background-color: #0b0e14; color: #e0e0e0; }
    div[data-testid="stMetric"] {
        background: rgba(0, 198, 255, 0.05);
        border-radius: 15px; padding: 20px; border: 1px solid #00c6ff;
    }
    .stButton>button {
        border-radius: 12px; background: linear-gradient(90deg, #00f2fe 0%, #4facfe 100%);
        color: black; font-weight: bold; width: 100%; border: none; height: 3.5em;
    }
    .coach-box { padding: 20px; border-radius: 15px; margin: 10px 0; border-left: 8px solid; line-height: 1.6; }
    .rojo { background-color: rgba(255, 75, 75, 0.1); border-color: #ff4b4b; color: #ff4b4b; }
    .verde { background-color: rgba(37, 211, 102, 0.1); border-color: #25d366; color: #25d366; }
    .alerta { background-color: rgba(241, 196, 15, 0.1); border-color: #f1c40f; color: #f1c40f; }
    .user-card {
        background: rgba(255, 255, 255, 0.05); padding: 15px; border-radius: 12px;
        border: 1px solid #333; margin-bottom: 10px; border-left: 4px solid #00c6ff;
    }
    </style>
    """, unsafe_allow_html=True)

# --- 2. BASE DE DATOS ---
def get_connection():
    return psycopg2.connect(st.secrets["DB_URL"])

def inicializar_db():
    conn = get_connection(); c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS usuarios 
                 (id SERIAL PRIMARY KEY, nombre TEXT UNIQUE, clave TEXT, expira DATE, rol TEXT, 
                  plan TEXT, precio TEXT, presupuesto DECIMAL DEFAULT 250000)''')
    c.execute('''CREATE TABLE IF NOT EXISTS movimientos 
                 (id SERIAL PRIMARY KEY, usuario_id INTEGER, fecha DATE, descrip TEXT, monto DECIMAL, tipo TEXT, cat TEXT, vence DATE)''')
    c.execute('''CREATE TABLE IF NOT EXISTS metas 
                 (id SERIAL PRIMARY KEY, usuario_id INTEGER, nombre TEXT, objetivo DECIMAL, actual DECIMAL DEFAULT 0)''')
    c.execute('''CREATE TABLE IF NOT EXISTS deudas 
                 (id SERIAL PRIMARY KEY, usuario_id INTEGER, nombre TEXT, monto_total DECIMAL, pagado DECIMAL DEFAULT 0, tipo TEXT)''')
    c.execute("SELECT * FROM usuarios WHERE nombre='admin'")
    if not c.fetchone():
        c.execute("INSERT INTO usuarios (nombre, clave, expira, rol, plan, precio) VALUES (%s,%s,%s,%s,%s,%s)", 
                  ('admin', 'admin123', '2099-12-31', 'admin', 'Dueño Master', 'N/A'))
    conn.commit(); c.close(); conn.close()

try: inicializar_db()
except Exception as e: st.error(f"Error de DB: {e}"); st.stop()

# --- 3. FUNCIONES ESPECIALES (PDF SIN ERRORES) ---
def limpiar_texto(texto):
    # Reemplaza caracteres que rompen el PDF estándar
    replacements = {'á':'a', 'é':'e', 'í':'i', 'ó':'o', 'ú':'u', 'ñ':'n', '₡':'CRC '}
    for k, v in replacements.items():
        texto = texto.replace(k, v)
    return texto.encode('latin-1', 'ignore').decode('latin-1')

def generar_pdf_pro(nombre, plan, monto, fecha):
    pdf = FPDF()
    pdf.add_page()
    pdf.set_fill_color(11, 14, 20); pdf.rect(0, 0, 210, 297, 'F')
    pdf.set_text_color(255, 255, 255); pdf.set_font("Arial", 'B', 24)
    pdf.cell(200, 30, "GEZO ELITE PRO 💎", ln=True, align='C')
    pdf.ln(10); pdf.set_font("Arial", 'B', 16)
    pdf.cell(200, 10, "COMPROBANTE DE PAGO", ln=True, align='C')
    pdf.ln(20); pdf.set_font("Arial", '', 14)
    pdf.cell(200, 10, f"Cliente: {limpiar_texto(nombre).upper()}", ln=True)
    pdf.cell(200, 10, f"Plan: {limpiar_texto(plan)}", ln=True)
    pdf.cell(200, 10, f"Monto: {limpiar_texto(str(monto))}", ln=True)
    pdf.cell(200, 10, f"Vence: {fecha}", ln=True)
    pdf.ln(30); pdf.set_font("Arial", 'I', 10)
    pdf.cell(200, 10, "Gracias por confiar en GeZo. Pura Vida.", ln=True, align='C')
    return pdf.output(dest='S').encode('latin-1', 'replace')

def get_tipo_cambio():
    return {"compra": 511.20, "venta": 520.45}

# --- 4. LOGIN ---
if 'autenticado' not in st.session_state: st.session_state.autenticado = False

if not st.session_state.autenticado:
    st.title("💎 GeZo Elite Pro")
    with st.form("login"):
        u = st.text_input("Usuario"); p = st.text_input("Clave", type="password")
        if st.form_submit_button("ENTRAR"):
            conn = get_connection(); c = conn.cursor()
            c.execute("SELECT id, nombre, rol, plan, expira FROM usuarios WHERE nombre=%s AND clave=%s", (u, p))
            res = c.fetchone()
            if res:
                if datetime.now().date() > res[4]: st.error("⚠️ Suscripción vencida."); st.stop()
                st.session_state.update({"autenticado":True, "uid":res[0], "uname":res[1], "rol":res[2], "plan":res[3]})
                st.rerun()
            else: st.error("❌ Datos incorrectos.")
            c.close(); conn.close()
    st.stop()

# --- 5. SIDEBAR ---
with st.sidebar:
    st.title(f"👑 {st.session_state.uname}")
    tc = get_tipo_cambio()
    st.metric("💵 Dólar Venta", f"₡{tc['venta']}")
    st.divider()
    menu = st.radio("Secciones:", ["📊 Dashboard IA", "💸 Registrar Cuentas", "📱 SINPE Rápido", "⚖️ Pensión y Aguinaldo", "🤝 Deudas y Metas", "💱 Conversor", "⚙️ Admin"])
    if st.button("Cerrar Sesión"): st.session_state.autenticado = False; st.rerun()

# --- 6. DASHBOARD CON COACH HÍBRIDO ---
if menu == "📊 Dashboard IA":
    st.header("Coach Financiero GeZo 🤖")
    df = pd.read_sql(f"SELECT * FROM movimientos WHERE usuario_id={st.session_state.uid}", get_connection())
    ing = float(df[df['tipo']=='Ingreso']['monto'].sum()) if not df.empty else 0
    gas = float(df[df['tipo']=='Gasto']['monto'].sum()) if not df.empty else 0
    bal = ing - gas
    
    c1, c2, c3 = st.columns(3)
    c1.metric("Ingresos", f"₡{ing:,.0f}"); c2.metric("Gastos", f"₡{gas:,.0f}", delta_color="inverse"); c3.metric("Saldo", f"₡{bal:,.0f}")

    if ing > 0:
        porc = (gas / ing) * 100
        if bal < 0:
            st.markdown(f'<div class="coach-box rojo"><h3>🚨 ¡ESTÁS EN ROJO!</h3><p>Gastaste <b>₡{abs(bal):,.0f}</b> extra. ¿En qué estás pensando? Dejá de gastar en tonteras o la deuda te va a comer. Cortá gastos hormiga hoy mismo.</p></div>', unsafe_allow_html=True)
        elif porc > 80:
            st.markdown(f'<div class="coach-box alerta"><h3>🧐 TENÉ CUIDADO</h3><p>Gastar el <b>{porc:.1f}%</b> es peligroso. Estás a un paso del abismo. ¡Guardá el 10% de lo que te queda antes de que desaparezca!</p></div>', unsafe_allow_html=True)
        else:
            st.markdown(f'<div class="coach-box verde"><h3>💎 ¡SOS UN CRACK!</h3><p>Gastás el <b>{porc:.1f}%</b>. Te sobran <b>₡{bal:,.0f}</b>. Pura vida, seguí así y meté ese excedente en una meta de inversión.</p></div>', unsafe_allow_html=True)
    
    if not df.empty:
        st.plotly_chart(px.pie(df[df['tipo']=='Gasto'], values='monto', names='cat', hole=.4, template="plotly_dark"))

# --- 7. REGISTRO DE CUENTAS + FECHA PAGO + ALERTAS ---
elif menu == "💸 Registrar Cuentas":
    st.header("Cuentas y Alertas de Pago")
    cats_g = ["⚖️ Pensión Alimentaria", "⚡ Recibo de Luz", "💧 Recibo de Agua", "📱 Plan Telefónico", "🏠 Alquiler/Hipoteca", "🏦 Préstamo", "🎓 Educación", "💡 Gastos Hormiga", "📦 Otros"]
    cats_i = ["💵 Salario Mensual", "📱 SINPE Recibido", "💰 Negocio", "📈 Inversiones", "💸 Remesas", "📦 Otros"]

    with st.form("reg_cuentas"):
        tipo = st.radio("Movimiento:", ["Gasto", "Ingreso"], horizontal=True)
        cat = st.selectbox("Categoría:", cats_g if tipo == "Gasto" else cats_i)
        monto = st.number_input("Monto (₡)", min_value=0.0)
        vence = st.date_input("Fecha de Pago/Vencimiento", datetime.now())
        alerta = st.checkbox("🔔 Alerta automática (1 día antes)")
        
        if st.form_submit_button("GUARDAR REGISTRO"):
            conn = get_connection(); c = conn.cursor()
            c.execute("INSERT INTO movimientos (usuario_id, fecha, descrip, monto, tipo, cat, vence) VALUES (%s,%s,%s,%s,%s,%s,%s)", 
                      (st.session_state.uid, datetime.now().date(), f"Registro {cat}", monto, tipo, cat, vence))
            conn.commit(); c.close(); conn.close()
            if alerta: st.info(f"📅 Recordatorio: Te avisaremos el {(vence - timedelta(days=1))}.")
            st.success("✅ Guardado.")

# --- 8. ADMIN (PDF, WHATSAPP, BORRADO) ---
elif menu == "⚙️ Admin" and st.session_state.rol == 'admin':
    st.header("Gestión de Clientes GeZo")
    conf = {"Mensual":30, "Trimestral":90, "Semestral":180, "Anual":365, "Eterno":36500}
    prec = {"Mensual":"₡5,000", "Trimestral":"₡13,500", "Semestral":"₡25,000", "Anual":"₡45,000", "Eterno":"₡100,000"}
    
    with st.expander("➕ Nuevo Cliente"):
        un = st.text_input("Usuario"); pn = st.text_input("Clave"); ps = st.selectbox("Plan", list(conf.keys()))
        if st.button("CREAR"):
            vf = (datetime.now() + timedelta(days=conf[ps])).date()
            conn = get_connection(); c = conn.cursor()
            c.execute("INSERT INTO usuarios (nombre, clave, expira, rol, plan, precio) VALUES (%s,%s,%s,%s,%s,%s)", (un, pn, vf, 'usuario', ps, prec[ps]))
            conn.commit(); c.close(); conn.close(); st.rerun()

    users = pd.read_sql("SELECT * FROM usuarios WHERE rol!='admin'", get_connection())
    for i, r in users.iterrows():
        with st.container():
            st.markdown(f'<div class="user-card"><b>👤 {r["nombre"]}</b> | {r["plan"]} | Vence: {r["expira"]}</div>', unsafe_allow_html=True)
            c1, c2, c3 = st.columns(3)
            with c1:
                p_bin = generar_pdf_pro(r['nombre'], r['plan'], r['precio'], str(r['expira']))
                st.download_button("📄 Recibo", p_bin, f"Recibo_{r['nombre']}.pdf")
            with c2:
                msg = f"Hola {r['nombre']}, tu membresia esta activa hasta {r['expira']}."
                st.markdown(f'<a href="https://wa.me/50663712477?text={msg.replace(" ","%20")}" target="_blank">📲 WhatsApp</a>', unsafe_allow_html=True)
            with c3:
                if st.button("🗑️ Borrar", key=f"d_{r['id']}"):
                    conn = get_connection(); c = conn.cursor()
                    c.execute(f"DELETE FROM usuarios WHERE id={r['id']}"); conn.commit(); c.close(); conn.close(); st.rerun()

# --- MÓDULOS RESTANTES ---
elif menu == "📱 SINPE Rápido":
    num = st.text_input("Número"); m = st.number_input("Monto", min_value=0)
    if st.button("PAGAR Y REGISTRAR"):
        st.markdown('<a href="https://www.baccredomatic.com/" target="_blank">🚀 Abrir App</a>', unsafe_allow_html=True)

elif menu == "⚖️ Pensión y Aguinaldo":
    sal = st.number_input("Salario Bruto", min_value=0.0)
    st.info(f"Pensión Est.: ₡{(sal*0.35):,.0f} | Aguinaldo: ₡{sal:,.0f}")

elif menu == "🤝 Deudas y Metas":
    st.header("Metas y Deudas")
    with st.form("metas"):
        n_meta = st.text_input("Meta"); o_meta = st.number_input("Objetivo", min_value=1.0)
        if st.form_submit_button("Crear Meta"):
            conn = get_connection(); c = conn.cursor()
            c.execute("INSERT INTO metas (usuario_id, nombre, objetivo) VALUES (%s,%s,%s)", (st.session_state.uid, n_meta, o_meta))
            conn.commit(); c.close(); conn.close(); st.success("Meta Creada.")

elif menu == "💱 Conversor":
    m_conv = st.number_input("Monto")
    st.write(f"Dólares: ${(m_conv/tc['venta']):,.2f} | Colones: ₡{(m_conv*tc['compra']):,.2f}")
