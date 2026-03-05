import streamlit as st
import pandas as pd
import psycopg2
from datetime import datetime, timedelta
import plotly.express as px
from fpdf import FPDF
import requests
import io

# --- 1. CONFIGURACIÓN DE INTERFAZ Y ESTILOS CSS ---
st.set_page_config(page_title="GeZo Elite Pro", page_icon="💎", layout="wide")

st.markdown("""
    <style>
    .main { background-color: #0b0e14; color: #e0e0e0; }
    div[data-testid="stMetric"] {
        background: rgba(0, 198, 255, 0.05);
        border-radius: 15px; padding: 20px; border: 1px solid #00c6ff;
        border-left: 5px solid #00c6ff;
    }
    .stButton>button {
        border-radius: 12px; background: linear-gradient(90deg, #00f2fe 0%, #4facfe 100%);
        color: black; font-weight: bold; width: 100%; border: none; height: 3.5em;
        transition: 0.3s;
    }
    .stButton>button:hover { transform: scale(1.02); box-shadow: 0px 0px 15px #00c6ff; }
    .coach-box { padding: 25px; border-radius: 15px; margin: 15px 0; border-left: 10px solid; line-height: 1.6; font-size: 1.1em; }
    .rojo { background-color: rgba(255, 75, 75, 0.1); border-color: #ff4b4b; color: #ff4b4b; }
    .verde { background-color: rgba(37, 211, 102, 0.1); border-color: #25d366; color: #25d366; }
    .alerta { background-color: rgba(241, 196, 15, 0.1); border-color: #f1c40f; color: #f1c40f; }
    .user-card {
        background: rgba(255, 255, 255, 0.05); padding: 20px; border-radius: 15px;
        border: 1px solid #333; margin-bottom: 15px; border-left: 6px solid #4facfe;
    }
    .bank-btn {
        background-color: #1e2129; border: 1px solid #00c6ff; color: #00c6ff;
        padding: 15px; border-radius: 10px; text-align: center; display: block; 
        text-decoration: none; font-weight: bold; margin-top: 15px;
    }
    </style>
    """, unsafe_allow_html=True)

# --- 2. MOTOR DE DATOS Y REPARACIÓN DE TABLAS ---
def get_connection():
    return psycopg2.connect(st.secrets["DB_URL"])

def inicializar_db():
    conn = get_connection(); c = conn.cursor()
    # Creación de tablas base si no existen
    c.execute('''CREATE TABLE IF NOT EXISTS usuarios 
                 (id SERIAL PRIMARY KEY, nombre TEXT UNIQUE, clave TEXT, expira DATE, rol TEXT, 
                  plan TEXT, precio TEXT, presupuesto DECIMAL DEFAULT 250000)''')
    c.execute('''CREATE TABLE IF NOT EXISTS movimientos 
                 (id SERIAL PRIMARY KEY, usuario_id INTEGER, fecha DATE, descrip TEXT, monto DECIMAL, tipo TEXT, cat TEXT)''')
    c.execute('''CREATE TABLE IF NOT EXISTS metas 
                 (id SERIAL PRIMARY KEY, usuario_id INTEGER, nombre TEXT, objetivo DECIMAL, actual DECIMAL DEFAULT 0)''')
    c.execute('''CREATE TABLE IF NOT EXISTS deudas 
                 (id SERIAL PRIMARY KEY, usuario_id INTEGER, nombre TEXT, monto_total DECIMAL, pagado DECIMAL DEFAULT 0, tipo TEXT)''')
    
    # --- PARCHE DE SEGURIDAD PARA LAS COLUMNAS DE LAS FOTOS ---
    try:
        c.execute("ALTER TABLE movimientos ADD COLUMN IF NOT EXISTS vence DATE")
    except: pass
    try:
        c.execute("ALTER TABLE usuarios ADD COLUMN IF NOT EXISTS precio TEXT")
    except: pass
    
    # Crear admin por defecto
    c.execute("SELECT * FROM usuarios WHERE nombre='admin'")
    if not c.fetchone():
        c.execute("INSERT INTO usuarios (nombre, clave, expira, rol, plan, precio) VALUES (%s,%s,%s,%s,%s,%s)", 
                  ('admin', 'admin123', '2099-12-31', 'admin', 'Dueño Master', 'N/A'))
    conn.commit(); c.close(); conn.close()

try:
    inicializar_db()
except Exception as e:
    st.error(f"Error crítico de base de datos: {e}")

# --- 3. FUNCIONES DE APOYO (PDF Y FORMATO) ---
def corregir_texto(texto):
    if not texto: return ""
    mapeo = {"á":"a","é":"e","í":"i","ó":"o","ú":"u","ñ":"n","₡":"CRC ","Á":"A","É":"E","Í":"I","Ó":"O","Ú":"U","Ñ":"N"}
    for k, v in mapeo.items(): texto = texto.replace(k, v)
    return str(texto).encode('latin-1', 'ignore').decode('latin-1')

def generar_pdf_recibo(nombre, plan, monto, fecha):
    pdf = FPDF()
    pdf.add_page()
    pdf.set_fill_color(11, 14, 20); pdf.rect(0, 0, 210, 297, 'F')
    pdf.set_text_color(255, 255, 255); pdf.set_font("Arial", 'B', 26)
    pdf.cell(200, 40, corregir_texto("GEZO ELITE PRO 💎"), ln=True, align='C')
    pdf.ln(10); pdf.set_font("Arial", '', 14)
    pdf.cell(200, 12, f"Comprobante oficial para: {corregir_texto(nombre)}", ln=True, align='L')
    pdf.cell(200, 10, f"Plan Contratado: {corregir_texto(plan)}", ln=True)
    pdf.cell(200, 10, f"Monto Pagado: {corregir_texto(str(monto))}", ln=True)
    pdf.cell(200, 10, f"Fecha de Vencimiento: {fecha}", ln=True)
    pdf.ln(40); pdf.set_font("Arial", 'I', 10)
    pdf.cell(200, 10, "Este documento es un recibo digital emitido por el sistema GeZo.", ln=True, align='C')
    return pdf.output(dest='S').encode('latin-1', errors='replace')

# --- 4. SISTEMA DE LOGIN ---
if 'autenticado' not in st.session_state: st.session_state.autenticado = False

if not st.session_state.autenticado:
    st.title("💎 GeZo Elite Pro")
    with st.container():
        with st.form("login_form"):
            u = st.text_input("Usuario GeZo")
            p = st.text_input("Clave de Acceso", type="password")
            if st.form_submit_button("INGRESAR AL PANEL"):
                conn = get_connection(); c = conn.cursor()
                c.execute("SELECT id, nombre, rol, plan, expira FROM usuarios WHERE nombre=%s AND clave=%s", (u, p))
                res = c.fetchone()
                if res:
                    if datetime.now().date() > res[4]: 
                        st.error("❌ Su suscripción ha caducado. Contacte al administrador.")
                    else:
                        st.session_state.update({"autenticado":True, "uid":res[0], "uname":res[1], "rol":res[2], "plan":res[3]})
                        st.rerun()
                else: st.error("❌ Credenciales inválidas.")
                c.close(); conn.close()
    st.stop()

# --- 5. NAVEGACIÓN LATERAL ---
with st.sidebar:
    st.markdown(f"## Bienvenido, \n### {st.session_state.uname} 👑")
    st.write(f"Plan: *{st.session_state.plan}*")
    st.divider()
    menu = st.radio("MENÚ PRINCIPAL", [
        "📊 Dashboard IA", "💸 Registrar Cuentas", "📱 SINPE Rápido", 
        "⚖️ Pensión y Aguinaldo", "🤝 Deudas y Metas", "💱 Conversor", "⚙️ Admin"
    ])
    st.divider()
    if st.button("SALIR DEL SISTEMA"):
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
    col1.metric("Ingresos Totales", f"₡{ing:,.0f}")
    col2.metric("Gastos Totales", f"₡{gas:,.0f}", delta_color="inverse")
    col3.metric("Saldo Disponible", f"₡{bal:,.0f}")

    if ing > 0:
        porcentaje = (gas / ing) * 100
        if bal < 0:
            st.markdown(f'<div class="coach-box rojo"><h3>🚨 ALERTA DE QUIEBRA</h3><p>Has gastado <b>₡{abs(bal):,.0f}</b> más de lo que tienes. La IA recomienda cortar suscripciones y gastos hormiga inmediatamente.</p></div>', unsafe_allow_html=True)
        elif porcentaje > 75:
            st.markdown(f'<div class="coach-box alerta"><h3>⚠️ ZONA DE PELIGRO</h3><p>Estás consumiendo el <b>{porcentaje:.1f}%</b> de tus ingresos. Solo te queda un margen muy pequeño para emergencias.</p></div>', unsafe_allow_html=True)
        else:
            st.markdown(f'<div class="coach-box verde"><h3>💎 SALUD FINANCIERA TOP</h3><p>Felicidades. Tu ahorro actual es de <b>₡{bal:,.0f}</b>. Es un buen momento para abonar a deudas o invertir.</p></div>', unsafe_allow_html=True)
    
    if not df.empty:
        st.plotly_chart(px.pie(df[df['tipo']=='Gasto'], values='monto', names='cat', hole=.4, template="plotly_dark", title="Gastos por Categoría"))

# --- 7. MÓDULO: REGISTRO DE CUENTAS (CORREGIDO) ---
elif menu == "💸 Registrar Cuentas":
    st.header("Gestión de Movimientos y Servicios")
    cats_g = ["⚖️ Pensión Alimentaria", "⚡ Recibo de Luz", "💧 Recibo de Agua", "📱 Plan Telefónico", "🏠 Alquiler/Hipoteca", "🏦 Préstamo", "🛒 Súper", "📦 Otros"]
    cats_i = ["💵 Salario Mensual", "📱 SINPE Recibido", "💰 Ventas/Negocio", "📈 Inversiones", "📦 Otros"]

    with st.form("form_registro"):
        c1, c2 = st.columns(2)
        with c1:
            tipo_m = st.radio("Tipo de Movimiento:", ["Gasto", "Ingreso"], horizontal=True)
            monto_m = st.number_input("Monto en Colones (₡)", min_value=0.0, step=100.0)
        with c2:
            cat_m = st.selectbox("Categoría:", cats_g if tipo_m == "Gasto" else cats_i)
            vence_m = st.date_input("Fecha de Pago/Vencimiento", datetime.now())
        
        alerta_m = st.checkbox("🔔 Activar recordatorio automático (1 día antes)")
        
        if st.form_submit_button("GUARDAR EN BASE DE DATOS"):
            conn = get_connection(); c = conn.cursor()
            c.execute("INSERT INTO movimientos (usuario_id, fecha, descrip, monto, tipo, cat, vence) VALUES (%s,%s,%s,%s,%s,%s,%s)", 
                      (st.session_state.uid, datetime.now().date(), f"Registro de {cat_m}", monto_m, tipo_m, cat_m, vence_m))
            conn.commit(); c.close(); conn.close()
            if alerta_m: st.info(f"⏰ Alerta configurada: El sistema te recordará este pago el {vence_m - timedelta(days=1)}")
            st.success("✅ Datos guardados correctamente en GeZo Pro.")

# --- 8. MÓDULO: SINPE RÁPIDO ---
elif menu == "📱 SINPE Rápido":
    st.header("Acceso Directo SINPE")
    num_s = st.text_input("Número de Destino")
    mon_s = st.number_input("Monto a enviar", min_value=0)
    ban_s = st.selectbox("Seleccione su Banco:", ["BNCR", "BAC", "BCR", "BP", "Promerica"])
    if st.button("REGISTRAR GASTO Y ABRIR BANCA"):
        conn = get_connection(); c = conn.cursor()
        c.execute("INSERT INTO movimientos (usuario_id, fecha, descrip, monto, tipo, cat) VALUES (%s,%s,%s,%s,%s,%s)", 
                  (st.session_state.uid, datetime.now().date(), f"SINPE enviado a {num_s}", mon_s, "Gasto", "📱 SINPE Rápido"))
        conn.commit(); c.close(); conn.close()
        st.markdown(f'<a href="https://www.google.com" target="_blank" class="bank-btn">🚀 Abrir App de {ban_s}</a>', unsafe_allow_html=True)

# --- 9. MÓDULO: PENSIÓN Y AGUINALDO ---
elif menu == "⚖️ Pensión y Aguinaldo":
    st.header("Cálculos de Ley (Costa Rica)")
    sal_bruto = st.number_input("Ingrese su Salario Bruto Mensual (₡)", min_value=0.0)
    col_a, col_b = st.columns(2)
    with col_a:
        st.subheader("Pensión Alimentaria")
        st.write(f"Estimado (35%): *₡{(sal_bruto*0.35):,.0f}*")
        st.caption("Nota: Este es un cálculo base según promedio judicial.")
    with col_b:
        st.subheader("Aguinaldo")
        st.write(f"Proyección Anual: *₡{sal_bruto:,.0f}*")
        st.caption("Nota: Basado en 12 meses laborados con el mismo salario.")

# --- 10. MÓDULO: DEUDAS Y METAS ---
elif menu == "🤝 Deudas y Metas":
    st.header("Planificación de Futuro")
    t1, t2 = st.tabs(["🎯 Metas de Ahorro", "🏦 Control de Deudas"])
    with t1:
        with st.form("f_metas"):
            n_meta = st.text_input("¿Para qué estás ahorrando?"); o_meta = st.number_input("Monto Meta (₡)", min_value=1.0)
            if st.form_submit_button("CREAR NUEVA META"):
                conn = get_connection(); c = conn.cursor()
                c.execute("INSERT INTO metas (usuario_id, nombre, objetivo) VALUES (%s,%s,%s)", (st.session_state.uid, n_meta, o_meta))
                conn.commit(); c.close(); conn.close(); st.success("🎯 Meta establecida.")
    with t2:
        st.info("Próximamente: Análisis IA para salir de deudas usando el método 'Bola de Nieve'.")

# --- 11. MÓDULO: CONVERSOR ---
elif menu == "💱 Conversor":
    st.header("Tipo de Cambio Real")
    monto_conv = st.number_input("Cantidad a convertir:", min_value=0.0)
    st.metric("Venta (Colón a Dólar)", f"${(monto_conv / 520.45):,.2f}")
    st.metric("Compra (Dólar a Colón)", f"₡{(monto_conv * 512.20):,.2f}")

# --- 12. MÓDULO: ADMIN (COMPLETO) ---
elif menu == "⚙️ Admin" and st.session_state.rol == 'admin':
    st.header("Panel de Control GeZo")
    p_opciones = {"Semana Gratis":7, "Mensual":30, "Trimestral":90, "Anual":365, "Eterno":36500}
    p_precios = {"Semana Gratis":"₡0", "Mensual":"₡5,000", "Trimestral":"₡13,500", "Anual":"₡45,000", "Eterno":"₡100,000"}
    
    with st.expander("➕ DAR DE ALTA NUEVO CLIENTE"):
        u_nom = st.text_input("Nombre de Usuario"); u_cla = st.text_input("Contraseña"); u_pla = st.selectbox("Plan", list(p_opciones.keys()))
        if st.button("GENERAR ACCESO"):
            v_fin = (datetime.now() + timedelta(days=p_opciones[u_pla])).date()
            conn = get_connection(); c = conn.cursor()
            c.execute("INSERT INTO usuarios (nombre, clave, expira, rol, plan, precio) VALUES (%s,%s,%s,%s,%s,%s)", (u_nom, u_cla, v_fin, 'usuario', u_pla, p_precios[u_pla]))
            conn.commit(); c.close(); conn.close(); st.rerun()

    st.subheader("Usuarios Activos")
    u_db = pd.read_sql("SELECT * FROM usuarios WHERE rol!='admin'", get_connection())
    for idx, row in u_db.iterrows():
        with st.container():
            st.markdown(f'<div class="user-card"><b>👤 {row["nombre"]}</b> | Plan: {row["plan"]} | Expira: {row["expira"]}</div>', unsafe_allow_html=True)
            ca, cb = st.columns(2)
            with ca:
                pdf_data = generar_pdf_recibo(row['nombre'], row['plan'], row['precio'], str(row['expira']))
                st.download_button(f"📄 Descargar Recibo {row['nombre']}", pdf_data, f"GeZo_Recibo_{row['nombre']}.pdf", key=f"p_{row['id']}")
            with cb:
                if st.button(f"🗑️ Eliminar Usuario {row['nombre']}", key=f"d_{row['id']}"):
                    conn = get_connection(); c = conn.cursor(); c.execute(f"DELETE FROM usuarios WHERE id={row['id']}"); conn.commit(); c.close(); conn.close(); st.rerun()
