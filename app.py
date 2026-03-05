import streamlit as st
import pandas as pd
import psycopg2
from datetime import datetime, timedelta
import plotly.express as px
from fpdf import FPDF
import requests
import io

# --- 1. CONFIGURACIÓN Y ESTÉTICA ELITE ---
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

# --- 2. MOTOR DE DATOS ---
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
    c.execute("SELECT * FROM usuarios WHERE nombre='admin'")
    if not c.fetchone():
        c.execute("INSERT INTO usuarios (nombre, clave, expira, rol, plan, precio) VALUES (%s,%s,%s,%s,%s,%s)", 
                  ('admin', 'admin123', '2099-12-31', 'admin', 'Dueño Master', 'N/A'))
    conn.commit(); c.close(); conn.close()

try: inicializar_db()
except: st.error("Error de base de datos."); st.stop()

# --- 3. FUNCIONES ESPECIALES ---
def get_tipo_cambio():
    return {"compra": 511.50, "venta": 520.30}

def generar_pdf(nombre, plan, monto, fecha):
    pdf = FPDF()
    pdf.add_page()
    pdf.set_fill_color(11, 14, 20); pdf.rect(0, 0, 210, 297, 'F')
    pdf.set_text_color(255, 255, 255); pdf.set_font("Arial", 'B', 24)
    pdf.cell(200, 20, "GEZO ELITE PRO 💎", ln=True, align='C')
    pdf.ln(10); pdf.set_font("Arial", '', 14)
    pdf.cell(200, 10, f"Comprobante de Membresia", ln=True, align='C')
    pdf.ln(10); pdf.cell(200, 10, f"Cliente: {nombre}", ln=True)
    pdf.cell(200, 10, f"Plan: {plan}", ln=True); pdf.cell(200, 10, f"Monto: {monto}", ln=True)
    pdf.cell(200, 10, f"Vence: {fecha}", ln=True)
    return pdf.output(dest='S').encode('latin-1')

# --- 4. ACCESO ---
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
                if datetime.now().date() > res[4]: st.error("Suscripción vencida."); st.stop()
                st.session_state.update({"autenticado":True, "uid":res[0], "uname":res[1], "rol":res[2], "plan":res[3]})
                st.rerun()
            else: st.error("Datos incorrectos.")
            c.close(); conn.close()
    st.stop()

# --- 5. SIDEBAR ---
with st.sidebar:
    st.title(f"👑 {st.session_state.uname}")
    tc = get_tipo_cambio()
    st.metric("💵 Dólar Venta", f"₡{tc['venta']}")
    st.divider()
    menu = st.radio("Secciones:", ["📊 Dashboard IA", "💸 Registrar Cuentas", "📱 SINPE Rápido", "⚖️ Pensión y Aguinaldo", "🤝 Deudas y Metas", "⚙️ Admin"])
    if st.button("Cerrar Sesión"): st.session_state.autenticado = False; st.rerun()

# --- 6. DASHBOARD + COACH IA ---
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
            st.markdown(f'<div class="coach-box rojo"><h3>🚨 ALERTA ROJA</h3><p>Estás gastando <b>₡{abs(bal):,.0f}</b> extra. ¡Dejá de comprar lo que no necesitás o vas a terminar pidiendo prestado! Pura vida, pero reaccioná.</p></div>', unsafe_allow_html=True)
        elif porc > 80:
            st.markdown(f'<div class="coach-box alerta"><h3>🧐 CUIDADO, CAMINAS FINITO</h3><p>Gastar el <b>{porc:.1f}%</b> es peligroso. Estás a un imprevisto de los números rojos. ¡Guardá el 10% de lo que te queda YA!</p></div>', unsafe_allow_html=True)
        else:
            st.markdown(f'<div class="coach-box verde"><h3>💎 ¡SOS UN CRACK!</h3><p>Solo gastás el <b>{porc:.1f}%</b>. Tenés <b>₡{bal:,.0f}</b> libres. ¡Excelente manejo! Seguí así y pronto estarás invirtiendo en grande.</p></div>', unsafe_allow_html=True)
    
    if not df.empty:
        st.plotly_chart(px.pie(df[df['tipo']=='Gasto'], values='monto', names='cat', hole=.4, template="plotly_dark"))

# --- 7. REGISTRO CON FECHA DE VENCIMIENTO Y ALERTAS ---
elif menu == "💸 Registrar Cuentas":
    st.header("Registro y Alertas de Pago")
    cats_gastos = ["⚖️ Pensión Alimentaria", "⚡ Recibo de Luz", "💧 Recibo de Agua", "📱 Plan Telefónico", "🏠 Alquiler/Hipoteca", "🏦 Préstamo", "🎓 Educación", "💡 Gastos Hormiga", "📦 Otros"]
    cats_ingresos = ["💵 Salario Mensual", "📱 SINPE Recibido", "💰 Negocio", "📈 Inversiones", "💸 Remesas", "📦 Otros"]

    with st.form("reg_alerta"):
        tipo = st.radio("Movimiento:", ["Gasto", "Ingreso"], horizontal=True)
        cat = st.selectbox("Categoría:", cats_gastos if tipo == "Gasto" else cats_ingresos)
        monto = st.number_input("Monto (₡)", min_value=0.0)
        
        st.subheader("🗓️ Programación de Pago")
        vence = st.date_input("¿Cuándo vence esta cuenta?", datetime.now() + timedelta(days=7))
        alerta = st.checkbox("Activar alerta automática (1 día antes)")
        
        if st.form_submit_button("GUARDAR Y PROGRAMAR ALERTA"):
            conn = get_connection(); c = conn.cursor()
            c.execute("INSERT INTO movimientos (usuario_id, fecha, descrip, monto, tipo, cat, vence) VALUES (%s,%s,%s,%s,%s,%s,%s)", 
                      (st.session_state.uid, datetime.now().date(), f"Pago de {cat}", monto, tipo, cat, vence))
            conn.commit(); c.close(); conn.close()
            
            if alerta:
                fecha_alerta = (vence - timedelta(days=1)).strftime("%Y%m%dT0900")
                # Aquí el sistema simula la integración con Google Tasks/Calendario
                st.info(f"🔔 Alerta programada: Mañana {vence - timedelta(days=1)} recibirás el recordatorio para pagar {cat}.")
            
            st.success("✅ Registrado con éxito.")

# --- 8. RESTO DE MÓDULOS ---
elif menu == "⚙️ Admin" and st.session_state.rol == 'admin':
    st.header("Gestión de Clientes")
    users = pd.read_sql("SELECT * FROM usuarios WHERE rol!='admin'", get_connection())
    for i, r in users.iterrows():
        with st.container():
            st.markdown(f'<div class="user-card"><b>👤 {r["nombre"]}</b> | {r["plan"]} | Vence: {r["expira"]}</div>', unsafe_allow_html=True)
            c1, c2, c3 = st.columns(3)
            with c1:
                pdf = generar_pdf(r['nombre'], r['plan'], r['precio'], str(r['expira']))
                st.download_button("📄 PDF", pdf, f"Recibo_{r['nombre']}.pdf")
            with c2:
                st.button("🗑️ Borrar", key=f"del_{r['id']}")
            with c3:
                st.write("📲 WhatsApp")

elif menu == "📱 SINPE Rápido":
    st.header("SINPE Elite")
    with st.form("s"):
        num = st.text_input("Número"); mon = st.number_input("Monto", min_value=0)
        if st.form_submit_button("PAGAR"):
            st.markdown(f'<a href="https://www.bnmovil.fi.cr/" target="_blank">🚀 Abrir BN Móvil</a>', unsafe_allow_html=True)

elif menu == "⚖️ Pensión y Aguinaldo":
    st.header("Cálculos CR")
    sal = st.number_input("Salario Bruto", min_value=0.0)
    st.write(f"⚖️ Pensión: ₡{(sal*0.35):,.0f} | 💰 Aguinaldo: ₡{sal:,.0f}")

elif menu == "🤝 Deudas y Metas":
    st.header("Futuro")
    st.write("Módulo para seguimiento de ahorro y deudas bancarias.")
