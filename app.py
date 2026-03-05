import streamlit as st
import pandas as pd
import psycopg2
from datetime import datetime, timedelta
import plotly.express as px
from fpdf import FPDF
import io
import time

# --- 1. ESTÉTICA ELITE PRO ---
st.set_page_config(page_title="GeZo Elite Pro", page_icon="💎", layout="wide")

st.markdown("""
    <style>
    .main { background-color: #0b0e14; color: #e0e0e0; }
    [data-testid="stSidebar"] { background-color: #0f121a; border-right: 1px solid #1e2633; }
    div[data-testid="stMetric"] {
        background: rgba(0, 198, 255, 0.08); border-radius: 20px; padding: 25px; 
        border: 1px solid #00c6ff; box-shadow: 0px 8px 25px rgba(0, 198, 255, 0.15); border-left: 10px solid #00c6ff;
    }
    .stButton>button {
        border-radius: 12px; background: linear-gradient(135deg, #00f2fe 0%, #4facfe 100%);
        color: #000 !important; font-weight: 800; width: 100%; border: none; height: 3em;
        transition: 0.3s all; text-transform: uppercase; font-size: 0.9em;
    }
    .stButton>button:hover { transform: translateY(-2px); box-shadow: 0px 5px 15px #00c6ff; color: #fff !important; }
    .user-card { background: rgba(255, 255, 255, 0.05); padding: 20px; border-radius: 15px; border: 1px solid #333; margin-bottom: 15px; border-left: 5px solid #00f2fe; }
    .status-badge { padding: 5px 10px; border-radius: 10px; font-size: 0.8em; font-weight: bold; }
    </style>
    """, unsafe_allow_html=True)

# --- 2. MOTOR DE BASE DE DATOS ---
@st.cache_resource
def get_connection():
    try:
        return psycopg2.connect(st.secrets["DB_URL"], connect_timeout=60)
    except Exception as e:
        st.error(f"Error de conexión: {e}"); st.stop()

def inicializar_db():
    conn = get_connection(); c = conn.cursor()
    c.execute("CREATE TABLE IF NOT EXISTS usuarios (id SERIAL PRIMARY KEY, nombre TEXT UNIQUE, clave TEXT, expira DATE, rol TEXT, plan TEXT, precio TEXT)")
    c.execute("CREATE TABLE IF NOT EXISTS movimientos (id SERIAL PRIMARY KEY, usuario_id INTEGER, fecha DATE, descrip TEXT, monto DECIMAL, tipo TEXT, cat TEXT, vence DATE)")
    c.execute("CREATE TABLE IF NOT EXISTS metas (id SERIAL PRIMARY KEY, usuario_id INTEGER, nombre TEXT, objetivo DECIMAL, actual DECIMAL DEFAULT 0)")
    c.execute('''CREATE TABLE IF NOT EXISTS deudas 
                 (id SERIAL PRIMARY KEY, usuario_id INTEGER, nombre TEXT, monto_total DECIMAL, pagado DECIMAL DEFAULT 0, 
                  tipo_registro TEXT, fecha_inicio DATE, fecha_vence DATE)''')
    
    # Parches para columnas de fechas si no existen
    try:
        c.execute("ALTER TABLE deudas ADD COLUMN IF NOT EXISTS fecha_inicio DATE")
        c.execute("ALTER TABLE deudas ADD COLUMN IF NOT EXISTS fecha_vence DATE")
        c.execute("ALTER TABLE deudas ADD COLUMN IF NOT EXISTS pagado DECIMAL DEFAULT 0")
    except: conn.rollback()
    
    c.execute("SELECT * FROM usuarios WHERE nombre='admin'")
    if not c.fetchone():
        c.execute("INSERT INTO usuarios (nombre, clave, expira, rol, plan, precio) VALUES (%s,%s,%s,%s,%s,%s)", ('admin', 'admin123', '2099-12-31', 'admin', 'Master', '0'))
    conn.commit(); c.close()

inicializar_db()

# --- 3. FUNCIONES AUXILIARES ---
def limpiar_texto(texto):
    if not texto: return ""
    acentos = {"á":"a","é":"e","í":"i","ó":"o","ú":"u","ñ":"n","₡":"CRC ","Á":"A","É":"E","Í":"I","Ó":"O","Ú":"U","Ñ":"N"}
    for k, v in acentos.items(): texto = str(texto).replace(k, v)
    return texto.encode('latin-1', 'ignore').decode('latin-1')

def generar_pdf(nombre, plan, monto, vence):
    pdf = FPDF(); pdf.add_page(); pdf.set_fill_color(11, 14, 20); pdf.rect(0, 0, 210, 297, 'F')
    pdf.set_text_color(0, 242, 254); pdf.set_font("Arial", 'B', 30)
    pdf.cell(200, 50, limpiar_texto("GEZO ELITE PRO 💎"), ln=True, align='C')
    pdf.set_text_color(255, 255, 255); pdf.set_font("Arial", '', 14); pdf.ln(10)
    pdf.cell(200, 10, f"CLIENTE: {limpiar_texto(nombre.upper())}", ln=True)
    pdf.cell(200, 10, f"PLAN: {limpiar_texto(plan)}", ln=True)
    pdf.cell(200, 10, f"MONTO: CRC {monto}", ln=True)
    pdf.cell(200, 10, f"EXPIRA: {vence}", ln=True)
    return pdf.output(dest='S').encode('latin-1', errors='replace')

# --- 4. ACCESO ---
if 'autenticado' not in st.session_state: st.session_state.autenticado = False
if not st.session_state.autenticado:
    st.title("💎 GeZo Elite Pro Access")
    with st.form("login"):
        u = st.text_input("Usuario"); p = st.text_input("Clave", type="password")
        if st.form_submit_button("INGRESAR"):
            conn = get_connection(); c = conn.cursor()
            c.execute("SELECT id, nombre, rol, plan, expira FROM usuarios WHERE nombre=%s AND clave=%s", (u, p))
            res = c.fetchone()
            if res:
                if datetime.now().date() > res[4]: st.error("Membresía vencida.")
                else: st.session_state.update({"autenticado":True, "uid":res[0], "uname":res[1], "rol":res[2], "plan":res[3]}); st.rerun()
            else: st.error("Acceso incorrecto.")
            c.close()
    st.stop()

# --- 5. MENÚ ---
with st.sidebar:
    st.markdown(f"### 👑 {st.session_state.uname}")
    menu = st.radio("NAVEGACIÓN", ["📊 Dashboard", "💸 Nuevo Registro", "📜 Historial / Borrar", "🎯 Metas", "🏦 Deudas y Cobros", "⚙️ Admin"])
    if st.button("CERRAR SESIÓN"): st.session_state.autenticado = False; st.rerun()

# --- 6. REGISTRO DE MOVIMIENTOS ---
if menu == "💸 Nuevo Registro":
    st.header("Entradas y Salidas de Capital")
    lista_g = ["⚖️ Pensión Alimentaria", "⚡ Recibo de Luz", "💧 Recibo de Agua", "🏠 Alquiler/Hipoteca", "🛒 Súper/Comida", "📱 Plan Celular/Net", "🏦 Cuota Préstamo", "🚗 Gasolina/Transporte", "📦 Otros Gastos"]
    lista_i = ["💵 Salario Mensual", "💰 Aguinaldo", "📱 SINPE Recibido", "📈 Ventas/Negocio", "🧧 Comisiones", "🚜 Freelance/Servicios", "🏢 Rentas/Alquileres", "🎁 Regalos", "💸 Cobros/Abonos Recibidos", "📦 Otros Ingresos"]
    tipo = st.radio("Tipo:", ["Gasto", "Ingreso"], horizontal=True)
    cat = st.selectbox("Categoría:", lista_i if tipo == "Ingreso" else lista_g)
    with st.form("f_reg"):
        monto = st.number_input("Monto (₡)", min_value=0.0); fecha = st.date_input("Fecha Pago:", datetime.now()); det = st.text_input("Nota:")
        if st.form_submit_button("GUARDAR"):
            conn = get_connection(); c = conn.cursor()
            c.execute("INSERT INTO movimientos (usuario_id, fecha, descrip, monto, tipo, cat, vence) VALUES (%s,%s,%s,%s,%s,%s,%s)", (st.session_state.uid, datetime.now().date(), f"{cat}: {det}", monto, tipo, cat, fecha))
            conn.commit(); c.close(); st.success("Guardado."); time.sleep(1); st.rerun()

# --- 7. MÓDULO: DEUDAS Y COBROS (ELITE UPDATE) ---
elif menu == "🏦 Deudas y Cobros":
    st.header("Gestión de Compromisos y Cuentas por Cobrar")
    t1, t2 = st.tabs(["💸 Lo que debo (Deudas)", "💰 Lo que me deben (Cobros)"])
    
    with t1:
        with st.expander("➕ REGISTRAR NUEVA DEUDA"):
            with st.form("new_deuda"):
                col1, col2 = st.columns(2)
                nombre_d = col1.text_input("Acreedor (A quién le debo)")
                monto_d = col2.number_input("Monto Total", min_value=0.0)
                f_ini = col1.date_input("Fecha en que se adquirió:", datetime.now())
                f_ven = col2.date_input("Fecha límite de pago:", datetime.now() + timedelta(days=30))
                if st.form_submit_button("CREAR REGISTRO"):
                    conn = get_connection(); c = conn.cursor()
                    c.execute("INSERT INTO deudas (usuario_id, nombre, monto_total, pagado, tipo_registro, fecha_inicio, fecha_vence) VALUES (%s,%s,%s,%s,%s,%s,%s)", 
                              (st.session_state.uid, nombre_d, monto_d, 0, 'DEUDA', f_ini, f_ven))
                    conn.commit(); c.close(); st.rerun()
        
        df_d = pd.read_sql(f"SELECT * FROM deudas WHERE usuario_id={st.session_state.uid} AND tipo_registro='DEUDA' ORDER BY fecha_vence ASC", get_connection())
        for _, r in df_d.iterrows():
            saldo = float(r['monto_total']) - float(r['pagado'])
            estado = "🔴 PENDIENTE" if saldo > 0 else "✅ CANCELADA"
            with st.container():
                st.markdown(f"""<div class="user-card"><strong>{r['nombre']}</strong> | Adquirida: {r['fecha_inicio']} | <b>Vence: {r['fecha_vence']}</b><br>
                Monto: ₡{r['monto_total']:,.0f} | Pendiente: ₡{saldo:,.0f} <span class="status-badge">{estado}</span></div>""", unsafe_allow_html=True)
                col_a1, col_a2, col_a3 = st.columns([2, 2, 1])
                abono = col_a1.number_input("Abonar monto:", min_value=0.0, key=f"ab_d_{r['id']}")
                if col_a2.button("REGISTRAR ABONO", key=f"btn_d_{r['id']}"):
                    conn = get_connection(); c = conn.cursor()
                    c.execute("UPDATE deudas SET pagado = pagado + %s WHERE id = %s", (abono, r['id']))
                    conn.commit(); c.close(); st.rerun()
                if col_a3.button("🗑️", key=f"del_d_{r['id']}"):
                    conn = get_connection(); c = conn.cursor(); c.execute(f"DELETE FROM deudas WHERE id={r['id']}"); conn.commit(); c.close(); st.rerun()

    with t2:
        with st.expander("➕ REGISTRAR NUEVO COBRO"):
            with st.form("new_cobro"):
                col1, col2 = st.columns(2)
                nombre_c = col1.text_input("Deudor (Quién me debe)")
                monto_c = col2.number_input("Monto a cobrar", min_value=0.0)
                f_ini_c = col1.date_input("Fecha del préstamo:", datetime.now())
                f_ven_c = col2.date_input("Fecha prometida de pago:", datetime.now() + timedelta(days=30))
                if st.form_submit_button("CREAR REGISTRO"):
                    conn = get_connection(); c = conn.cursor()
                    c.execute("INSERT INTO deudas (usuario_id, nombre, monto_total, pagado, tipo_registro, fecha_inicio, fecha_vence) VALUES (%s,%s,%s,%s,%s,%s,%s)", 
                              (st.session_state.uid, nombre_c, monto_c, 0, 'COBRO', f_ini_c, f_ven_c))
                    conn.commit(); c.close(); st.rerun()

        df_c = pd.read_sql(f"SELECT * FROM deudas WHERE usuario_id={st.session_state.uid} AND tipo_registro='COBRO' ORDER BY fecha_vence ASC", get_connection())
        for _, r in df_c.iterrows():
            saldo_c = float(r['monto_total']) - float(r['pagado'])
            estado_c = "🟠 POR COBRAR" if saldo_c > 0 else "✅ RECUPERADO"
            with st.container():
                st.markdown(f"""<div class="user-card" style="border-left-color: #2ecc71;"><strong>{r['nombre']}</strong> | Prestado: {r['fecha_inicio']} | <b>Vence: {r['fecha_vence']}</b><br>
                Monto: ₡{r['monto_total']:,.0f} | Pendiente: ₡{saldo_c:,.0f} <span class="status-badge">{estado_c}</span></div>""", unsafe_allow_html=True)
                col_b1, col_b2, col_b3 = st.columns([2, 2, 1])
                abono_c = col_b1.number_input("Recibir abono:", min_value=0.0, key=f"ab_c_{r['id']}")
                if col_b2.button("REGISTRAR ABONO", key=f"btn_c_{r['id']}"):
                    conn = get_connection(); c = conn.cursor()
                    c.execute("UPDATE deudas SET pagado = pagado + %s WHERE id = %s", (abono_c, r['id']))
                    conn.commit(); c.close(); st.rerun()
                if col_b3.button("🗑️", key=f"del_c_{r['id']}"):
                    conn = get_connection(); c = conn.cursor(); c.execute(f"DELETE FROM deudas WHERE id={r['id']}"); conn.commit(); c.close(); st.rerun()

# --- 8. RESTO DE MÓDULOS (Dashboard, Historial, Metas, Admin) ---
elif menu == "📊 Dashboard":
    st.header("Situación Financiera")
    df = pd.read_sql(f"SELECT * FROM movimientos WHERE usuario_id={st.session_state.uid}", get_connection())
    if not df.empty:
        ing = float(df[df['tipo']=='Ingreso']['monto'].sum()); gas = float(df[df['tipo']=='Gasto']['monto'].sum())
        col1, col2, col3 = st.columns(3)
        col1.metric("INGRESOS", f"₡{ing:,.0f}"); col2.metric("GASTOS", f"₡{gas:,.0f}"); col3.metric("SALDO", f"₡{(ing-gas):,.0f}")
        st.plotly_chart(px.pie(df[df['tipo']=='Gasto'], values='monto', names='cat', hole=0.6, template="plotly_dark"), use_container_width=True)

elif menu == "📜 Historial / Borrar":
    st.header("Control de Registros")
    df_h = pd.read_sql(f"SELECT id, fecha, cat, monto, tipo, vence FROM movimientos WHERE usuario_id={st.session_state.uid} ORDER BY id DESC", get_connection())
    if not df_h.empty:
        for idx, row in df_h.iterrows():
            c1, c2, c3, c4 = st.columns([1, 3, 2, 1])
            c1.write("🟢" if row['tipo'] == "Ingreso" else "🔴")
            c2.write(f"**{row['cat']}** \n_{row['vence']}_")
            c3.write(f"₡{row['monto']:,.0f}")
            if c4.button("🗑️", key=f"del_m_{row['id']}"):
                conn = get_connection(); c = conn.cursor(); c.execute(f"DELETE FROM movimientos WHERE id={row['id']}"); conn.commit(); c.close(); st.rerun()
            st.divider()

elif menu == "🎯 Metas":
    st.header("Metas de Ahorro")
    with st.form("f_meta"):
        n = st.text_input("Meta"); o = st.number_input("Objetivo", min_value=0.0)
        if st.form_submit_button("AÑADIR"):
            conn = get_connection(); c = conn.cursor(); c.execute("INSERT INTO metas (usuario_id, nombre, objetivo) VALUES (%s,%s,%s)", (st.session_state.uid, n, o)); conn.commit(); c.close(); st.rerun()
    df_m = pd.read_sql(f"SELECT id, nombre, objetivo FROM metas WHERE usuario_id={st.session_state.uid}", get_connection())
    for _, r in df_m.iterrows():
        c_m1, c_m2 = st.columns([4, 1])
        c_m1.write(f"🎯 **{r['nombre']}**: ₡{r['objetivo']:,.0f}")
        if c_m2.button("🗑️", key=f"del_meta_{r['id']}"):
            conn = get_connection(); c = conn.cursor(); c.execute(f"DELETE FROM metas WHERE id={r['id']}"); conn.commit(); c.close(); st.rerun()

elif menu == "⚙️ Admin" and st.session_state.rol == 'admin':
    st.header("Panel Maestro")
    with st.form("f_admin"):
        un = st.text_input("Usuario"); uk = st.text_input("Clave"); up = st.selectbox("Plan", ["Mensual", "Anual"]); um = st.text_input("Monto", "5000")
        if st.form_submit_button("ACTIVAR"):
            vf = (datetime.now() + timedelta(days=30 if up=="Mensual" else 365)).date()
            conn = get_connection(); c = conn.cursor(); c.execute("INSERT INTO usuarios (nombre, clave, expira, rol, plan, precio) VALUES (%s,%s,%s,%s,%s,%s)", (un, uk, vf, 'usuario', up, um)); conn.commit(); c.close(); st.rerun()
    u_list = pd.read_sql("SELECT * FROM usuarios WHERE rol!='admin'", get_connection())
    for _, r in u_list.iterrows():
        with st.container():
            st.markdown(f'<div class="user-card"><strong>{r["nombre"]}</strong> | Plan: {r["plan"]}</div>', unsafe_allow_html=True)
            pdf = generar_pdf(r['nombre'], r['plan'], r['precio'], str(r['expira']))
            st.download_button(f"📄 Recibo {r['nombre']}", pdf, f"Recibo_{r['nombre']}.pdf", key=f"p_{r['id']}")
            if st.button(f"🗑️ Eliminar Acceso", key=f"d_u_{r['id']}"):
                conn = get_connection(); c = conn.cursor(); c.execute(f"DELETE FROM usuarios WHERE id={r['id']}"); conn.commit(); c.close(); st.rerun()
