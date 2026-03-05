import streamlit as st
import pandas as pd
import psycopg2
from datetime import datetime, timedelta, date
import plotly.express as px
import time

# --- 1. ESTÉTICA ELITE PRO + LIMPIEZA TOTAL ---
st.set_page_config(page_title="GeZo Elite Pro", page_icon="💎", layout="wide")

st.markdown("""
    <style>
    #MainMenu {visibility: hidden;} header {visibility: hidden;} footer {visibility: hidden;}
    .stDeployButton {display:none;} [data-testid="stToolbar"] {display: none !important;}
    .main { background-color: #0b0e14; color: #e0e0e0; }
    [data-testid="stSidebar"] { background-color: #0f121a; border-right: 1px solid #1e2633; }
    
    .balance-card {
        background: linear-gradient(135deg, #1e2633 0%, #0b0e14 100%);
        border-radius: 20px; padding: 20px; border: 1px solid #333;
        text-align: center; box-shadow: 0 10px 30px rgba(0,0,0,0.5); margin-bottom: 20px;
    }
    .metric-value { font-size: 2.2em; font-weight: 900; color: #00f2fe; }
    .metric-label { font-size: 0.9em; color: #888; text-transform: uppercase; letter-spacing: 1px; }
    
    .user-card { background: rgba(255, 255, 255, 0.03); padding: 15px; border-radius: 12px; border: 1px solid #222; margin-bottom: 10px; border-left: 5px solid #00f2fe; }
    .alert-box { padding: 15px; background: rgba(255, 165, 0, 0.1); border: 1px solid orange; border-radius: 10px; color: orange; margin-bottom: 20px; }
    .bank-btn { 
        background: #00f2fe; color: #000 !important; padding: 15px; border-radius: 12px; 
        text-align: center; display: block; text-decoration: none; font-weight: 900; margin-top: 10px;
    }
    </style>
    """, unsafe_allow_html=True)

# --- 2. MOTOR DE BASE DE DATOS ---
@st.cache_resource
def get_connection():
    try: return psycopg2.connect(st.secrets["DB_URL"], connect_timeout=60)
    except Exception as e: st.error(f"Error DB: {e}"); st.stop()

def inicializar_db():
    conn = get_connection(); c = conn.cursor()
    c.execute("CREATE TABLE IF NOT EXISTS usuarios (id SERIAL PRIMARY KEY, nombre TEXT UNIQUE, clave TEXT, expira DATE, rol TEXT, plan TEXT)")
    c.execute("CREATE TABLE IF NOT EXISTS movimientos (id SERIAL PRIMARY KEY, usuario_id INTEGER, fecha DATE, descrip TEXT, monto DECIMAL, tipo TEXT, cat TEXT)")
    c.execute("CREATE TABLE IF NOT EXISTS metas (id SERIAL PRIMARY KEY, usuario_id INTEGER, nombre TEXT, objetivo DECIMAL, actual DECIMAL DEFAULT 0)")
    c.execute("CREATE TABLE IF NOT EXISTS deudas (id SERIAL PRIMARY KEY, usuario_id INTEGER, nombre TEXT, monto_total DECIMAL, pagado DECIMAL DEFAULT 0, tipo_registro TEXT, fecha_vence DATE)")
    c.execute("CREATE TABLE IF NOT EXISTS contactos (id SERIAL PRIMARY KEY, usuario_id INTEGER, nombre TEXT, telefono TEXT)")
    
    c.execute("SELECT * FROM usuarios WHERE nombre='admin'")
    if not c.fetchone():
        c.execute("INSERT INTO usuarios (nombre, clave, expira, rol, plan) VALUES ('admin', 'admin123', '2099-12-31', 'admin', 'Master')")
    conn.commit(); c.close()

inicializar_db()

# --- 3. FUNCIONES DE REGISTRO CONECTADO ---
def reg_mov(monto, tipo, cat, desc):
    if monto > 0:
        conn = get_connection(); c = conn.cursor()
        c.execute("INSERT INTO movimientos (usuario_id, fecha, descrip, monto, tipo, cat) VALUES (%s,%s,%s,%s,%s,%s)", 
                  (st.session_state.uid, date.today(), desc, monto, tipo, cat))
        conn.commit(); c.close()

# --- 4. LOGIN ---
if 'autenticado' not in st.session_state: st.session_state.autenticado = False
if not st.session_state.autenticado:
    st.title("💎 GeZo Elite Pro")
    with st.form("login"):
        u = st.text_input("Usuario"); p = st.text_input("Clave", type="password")
        if st.form_submit_button("INGRESAR"):
            conn = get_connection(); c = conn.cursor()
            c.execute("SELECT id, nombre, rol, plan, expira FROM usuarios WHERE nombre=%s AND clave=%s", (u, p))
            res = c.fetchone()
            if res:
                if date.today() > res[4]: st.error("Membresía vencida.")
                else: st.session_state.update({"autenticado":True, "uid":res[0], "uname":res[1], "rol":res[2], "plan":res[3]}); st.rerun()
            else: st.error("Acceso incorrecto.")
            c.close()
    st.stop()

# --- 5. NAVEGACIÓN ---
with st.sidebar:
    st.markdown(f"### 👑 {st.session_state.uname}")
    menu = st.radio("NAVEGACIÓN", ["📊 Balance General", "💸 Registros", "🎯 Metas", "🏦 Deudas y Cobros", "📱 SINPE Rápido", "📜 Historial / Borrar"])
    
    st.divider()
    with st.expander("🔐 Cambiar Contraseña"):
        nv_p = st.text_input("Nueva Clave", type="password")
        if st.button("ACTUALIZAR CLAVE"):
            conn = get_connection(); c = conn.cursor()
            c.execute("UPDATE usuarios SET clave=%s WHERE id=%s", (nv_p, st.session_state.uid))
            conn.commit(); c.close(); st.success("Clave actualizada correctamente"); time.sleep(1); st.rerun()

    if st.session_state.rol == 'admin':
        if st.checkbox("⚙️ Panel Admin"): menu = "⚙️ Admin"
    if st.button("CERRAR SESIÓN"): st.session_state.autenticado = False; st.rerun()

if st.session_state.rol != 'admin':
    st.markdown(f'<div class="alert-box">⚠️ <b>Suscripción {st.session_state.plan} Activa.</b> Recuerda cambiar tu clave por seguridad.</div>', unsafe_allow_html=True)

# --- 6. MÓDULOS ---

if menu == "📊 Balance General":
    st.header("Análisis de Generación")
    periodo = st.select_slider("Filtro de Tiempo", options=["Día", "Semana", "Mes"])
    rango = {"Día": 0, "Semana": 7, "Mes": 30}
    fecha_f = date.today() - timedelta(days=rango[periodo])
    
    df = pd.read_sql(f"SELECT * FROM movimientos WHERE usuario_id={st.session_state.uid} AND fecha >= '{fecha_f}'", get_connection())
    
    c1, c2, c3 = st.columns(3)
    if not df.empty:
        ing = float(df[df['tipo']=='Ingreso']['monto'].sum())
        gas = float(df[df['tipo']=='Gasto']['monto'].sum())
        neto = ing - gas
        with c1: st.markdown(f'<div class="balance-card"><p class="metric-label">Ingresos {periodo}</p><p class="metric-value">₡{ing:,.0f}</p></div>', unsafe_allow_html=True)
        with c2: st.markdown(f'<div class="balance-card"><p class="metric-label">Gastos {periodo}</p><p class="metric-value" style="color:#ff4b4b;">₡{gas:,.0f}</p></div>', unsafe_allow_html=True)
        with c3: st.markdown(f'<div class="balance-card"><p class="metric-label">Generación Neta</p><p class="metric-value" style="color:#2ecc71;">₡{neto:,.0f}</p></div>', unsafe_allow_html=True)
        
        st.plotly_chart(px.line(df.groupby('fecha')['monto'].sum().reset_index(), x='fecha', y='monto', title="Evolución de Flujo", template="plotly_dark"), use_container_width=True)
    else: st.info("No hay movimientos registrados en este periodo.")

elif menu == "💸 Registros":
    st.header("Nuevo Registro")
    t_mov = st.radio("Tipo:", ["Gasto", "Ingreso"], horizontal=True)
    cat_op = ["Salario", "Venta", "Luz", "Agua", "Comida", "Ocio", "Transporte", "Casa", "Otros"]
    cat = st.selectbox("Categoría:", cat_op)
    with st.form("f_mov"):
        m = st.number_input("Monto (₡)", min_value=0.0); d = st.text_input("Nota / Descripción")
        if st.form_submit_button("GUARDAR EN BALANCE"):
            reg_mov(m, t_mov, cat, d)
            st.success("Guardado con éxito"); time.sleep(0.5); st.rerun()

elif menu == "🎯 Metas":
    st.header("Tus Metas de Ahorro")
    with st.expander("➕ CREAR NUEVA META"):
        with st.form("f_meta"):
            n = st.text_input("¿Para qué es el ahorro?"); obj = st.number_input("Monto Objetivo", min_value=1.0)
            if st.form_submit_button("CREAR"):
                conn = get_connection(); c = conn.cursor(); c.execute("INSERT INTO metas (usuario_id, nombre, objetivo) VALUES (%s,%s,%s)", (st.session_state.uid, n, obj)); conn.commit(); c.close(); st.rerun()
    
    df_m = pd.read_sql(f"SELECT * FROM metas WHERE usuario_id={st.session_state.uid}", get_connection())
    for _, r in df_m.iterrows():
        st.markdown(f'<div class="user-card"><b>🎯 {r["nombre"]}</b><br>Progreso: ₡{float(r["actual"]):,.0f} / ₡{float(r["objetivo"]):,.0f}</div>', unsafe_allow_html=True)
        st.progress(min(float(r['actual'])/float(r['objetivo']), 1.0))
        c1, c2, c3 = st.columns([2,1,1])
        m_a = c1.number_input("Monto a ahorrar:", min_value=0.0, key=f"m_{r['id']}")
        if c2.button("ABONAR", key=f"b_{r['id']}"):
            conn = get_connection(); c = conn.cursor(); c.execute("UPDATE metas SET actual=actual+%s WHERE id=%s", (m_a, r['id'])); conn.commit(); c.close()
            reg_mov(m_a, "Gasto", "🎯 Ahorro", f"Meta: {r['nombre']}")
            st.rerun()
        if c3.button("🗑️", key=f"del_{r['id']}"):
            conn = get_connection(); c = conn.cursor(); c.execute(f"DELETE FROM metas WHERE id={r['id']}"); conn.commit(); c.close(); st.rerun()

elif menu == "🏦 Deudas y Cobros":
    st.header("Compromisos Financieros")
    t1, t2 = st.tabs(["💸 Lo que debo", "💰 Lo que me deben"])
    with t1:
        with st.expander("➕ REGISTRAR DEUDA"):
            with st.form("fd"):
                n = st.text_input("Acreedor"); m = st.number_input("Monto Total"); fv = st.date_input("Fecha Vencimiento")
                if st.form_submit_button("GUARDAR DEUDA"):
                    conn = get_connection(); c = conn.cursor(); c.execute("INSERT INTO deudas (usuario_id, nombre, monto_total, tipo_registro, fecha_vence) VALUES (%s,%s,%s,%s,%s)", (st.session_state.uid, n, m, 'DEUDA', fv)); conn.commit(); c.close(); st.rerun()
        df_d = pd.read_sql(f"SELECT * FROM deudas WHERE usuario_id={st.session_state.uid} AND tipo_registro='DEUDA'", get_connection())
        for _, r in df_d.iterrows():
            pende = float(r['monto_total']) - float(r['pagado'])
            st.markdown(f'<div class="user-card">🔴 {r["nombre"]} | Pendiente: ₡{pende:,.0f}</div>', unsafe_allow_html=True)
            ca, cb = st.columns([2,1]); ab_d = ca.number_input("Pago:", min_value=0.0, key=f"d_{r['id']}")
            if cb.button("PAGAR", key=f"bd_{r['id']}"):
                conn = get_connection(); c = conn.cursor(); c.execute("UPDATE deudas SET pagado=pagado+%s WHERE id=%s", (ab_d, r['id'])); conn.commit(); c.close()
                reg_mov(ab_d, "Gasto", "🏦 Pago Deuda", f"A: {r['nombre']}"); st.rerun()

    with t2:
        with st.expander("➕ REGISTRAR COBRO"):
            with st.form("fc"):
                n = st.text_input("Deudor"); m = st.number_input("Monto"); fv = st.date_input("Fecha Promesa")
                if st.form_submit_button("GUARDAR COBRO"):
                    conn = get_connection(); c = conn.cursor(); c.execute("INSERT INTO deudas (usuario_id, nombre, monto_total, tipo_registro, fecha_vence) VALUES (%s,%s,%s,%s,%s)", (st.session_state.uid, n, m, 'COBRO', fv)); conn.commit(); c.close(); st.rerun()
        df_c = pd.read_sql(f"SELECT * FROM deudas WHERE usuario_id={st.session_state.uid} AND tipo_registro='COBRO'", get_connection())
        for _, r in df_c.iterrows():
            pende = float(r['monto_total']) - float(r['pagado'])
            st.markdown(f'<div class="user-card">🟢 {r["nombre"]} | Pendiente: ₡{pende:,.0f}</div>', unsafe_allow_html=True)
            ca, cb = st.columns([2,1]); ab_c = ca.number_input("Recibido:", min_value=0.0, key=f"c_{r['id']}")
            if cb.button("RECIBIR", key=f"bc_{r['id']}"):
                conn = get_connection(); c = conn.cursor(); c.execute("UPDATE deudas SET pagado=pagado+%s WHERE id=%s", (ab_c, r['id'])); conn.commit(); c.close()
                reg_mov(ab_c, "Ingreso", "💸 Cobro", f"De: {r['nombre']}"); st.rerun()

elif menu == "📱 SINPE Rápido":
    st.header("SINPE Móvil")
    with st.expander("👤 MI AGENDA"):
        with st.form("f_cont"):
            n = st.text_input("Nombre"); t = st.text_input("Teléfono")
            if st.form_submit_button("GUARDAR CONTACTO"):
                conn = get_connection(); c = conn.cursor(); c.execute("INSERT INTO contactos (usuario_id, nombre, telefono) VALUES (%s,%s,%s)", (st.session_state.uid, n, t)); conn.commit(); c.close(); st.rerun()
    df_con = pd.read_sql(f"SELECT * FROM contactos WHERE usuario_id={st.session_state.uid}", get_connection())
    sel = st.selectbox("Elegir de agenda:", ["Manual"] + [f"{r['nombre']} ({r['telefono']})" for _, r in df_con.iterrows()])
    num = st.text_input("Número:") if sel == "Manual" else sel.split("(")[1].replace(")", "")
    mon_s = st.number_input("Monto ₡", min_value=0.0)
    if st.button("PROCESAR Y ABRIR BANCO"):
        reg_mov(mon_s, "Gasto", "📱 SINPE", f"A: {num}")
        st.markdown(f'<a href="https://www.google.com" target="_blank" class="bank-btn">🏦 IR AL BANCO</a>', unsafe_allow_html=True)

elif menu == "📜 Historial / Borrar":
    st.header("Historial de Movimientos")
    df_h = pd.read_sql(f"SELECT id, fecha, cat, monto, tipo, descrip FROM movimientos WHERE usuario_id={st.session_state.uid} ORDER BY id DESC", get_connection())
    for _, row in df_h.iterrows():
        c1, c2, c3, c4 = st.columns([1,4,2,1])
        c1.write("🟢" if row['tipo']=="Ingreso" else "🔴")
        c2.write(f"**{row['cat']}** - {row['descrip']}")
        c3.write(f"₡{row['monto']:,.0f}")
        if c4.button("🗑️", key=f"h_{row['id']}"):
            conn = get_connection(); c = conn.cursor(); c.execute(f"DELETE FROM movimientos WHERE id={row['id']}"); conn.commit(); c.close(); st.rerun()

elif menu == "⚙️ Admin" and st.session_state.rol == 'admin':
    st.header("Panel Admin")
    with st.form("f_ad"):
        un = st.text_input("Nuevo Usuario"); uk = st.text_input("Clave"); pl = st.selectbox("Plan", ["Mensual", "Anual"])
        if st.form_submit_button("CREAR"):
            vf = (date.today() + timedelta(days=30 if pl=="Mensual" else 365))
            conn = get_connection(); c = conn.cursor(); c.execute("INSERT INTO usuarios (nombre, clave, expira, rol, plan) VALUES (%s,%s,%s,%s,%s)", (un, uk, vf, 'usuario', pl)); conn.commit(); c.close(); st.success("Creado"); st.rerun()
