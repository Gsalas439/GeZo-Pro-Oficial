import streamlit as st
import pandas as pd
import psycopg2
from datetime import datetime, timedelta
import plotly.express as px
import time

# --- 1. ESTÉTICA ELITE PRO + LIMPIEZA TOTAL ---
st.set_page_config(page_title="GeZo Elite Pro", page_icon="💎", layout="wide")

st.markdown("""
    <style>
    /* Ocultar interfaz nativa de Streamlit */
    #MainMenu {visibility: hidden;}
    header {visibility: hidden;}
    footer {visibility: hidden;}
    .stDeployButton {display:none;}
    [data-testid="stToolbar"] {display: none !important;}
    
    .main { background-color: #0b0e14; color: #e0e0e0; }
    [data-testid="stSidebar"] { background-color: #0f121a; border-right: 1px solid #1e2633; }
    
    div[data-testid="stMetric"] {
        background: rgba(0, 198, 255, 0.08); border-radius: 20px; padding: 25px; 
        border: 1px solid #00c6ff; box-shadow: 0px 8px 25px rgba(0, 198, 255, 0.15); border-left: 10px solid #00c6ff;
    }
    .user-card { background: rgba(255, 255, 255, 0.05); padding: 20px; border-radius: 15px; border: 1px solid #333; margin-bottom: 15px; border-left: 5px solid #00f2fe; }
    .alert-box { padding: 15px; background: rgba(255, 165, 0, 0.1); border: 1px solid orange; border-radius: 10px; color: orange; margin-bottom: 20px; }
    .sinpe-card { background: linear-gradient(135deg, #1e2633 0%, #0b0e14 100%); padding: 25px; border-radius: 20px; border: 1px solid #00f2fe; text-align: center; }
    .bank-btn { 
        background: #00f2fe; color: #000 !important; padding: 18px; border-radius: 15px; 
        text-align: center; display: block; text-decoration: none; font-weight: 900; 
        margin-top: 20px; font-size: 1.1em; transition: 0.3s;
    }
    </style>
    """, unsafe_allow_html=True)

# --- 2. BASE DE DATOS ---
@st.cache_resource
def get_connection():
    try: return psycopg2.connect(st.secrets["DB_URL"], connect_timeout=60)
    except Exception as e: st.error(f"Error DB: {e}"); st.stop()

def inicializar_db():
    conn = get_connection(); c = conn.cursor()
    c.execute("CREATE TABLE IF NOT EXISTS usuarios (id SERIAL PRIMARY KEY, nombre TEXT UNIQUE, clave TEXT, expira DATE, rol TEXT, plan TEXT, precio TEXT)")
    c.execute("CREATE TABLE IF NOT EXISTS movimientos (id SERIAL PRIMARY KEY, usuario_id INTEGER, fecha DATE, descrip TEXT, monto DECIMAL, tipo TEXT, cat TEXT, vence DATE)")
    c.execute("CREATE TABLE IF NOT EXISTS metas (id SERIAL PRIMARY KEY, usuario_id INTEGER, nombre TEXT, objetivo DECIMAL, actual DECIMAL DEFAULT 0)")
    c.execute("CREATE TABLE IF NOT EXISTS deudas (id SERIAL PRIMARY KEY, usuario_id INTEGER, nombre TEXT, monto_total DECIMAL, pagado DECIMAL DEFAULT 0, tipo_registro TEXT, fecha_inicio DATE, fecha_vence DATE)")
    c.execute("CREATE TABLE IF NOT EXISTS contactos (id SERIAL PRIMARY KEY, usuario_id INTEGER, nombre TEXT, telefono TEXT)")
    
    c.execute("SELECT * FROM usuarios WHERE nombre='admin'")
    if not c.fetchone():
        c.execute("INSERT INTO usuarios (nombre, clave, expira, rol, plan, precio) VALUES (%s,%s,%s,%s,%s,%s)", ('admin', 'admin123', '2099-12-31', 'admin', 'Master', '0'))
    conn.commit(); c.close()

inicializar_db()

# --- 3. LOGIN ---
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

# --- 4. NAVEGACIÓN ---
with st.sidebar:
    st.markdown(f"### 👑 {st.session_state.uname}")
    opciones = ["📊 Dashboard", "💸 Nuevo Registro", "📜 Historial / Borrar", "🎯 Metas", "🏦 Deudas y Cobros", "📱 SINPE Rápido"]
    if st.session_state.rol == 'admin': opciones.append("⚙️ Admin")
    menu = st.radio("NAVEGACIÓN", opciones)
    with st.expander("🔐 Seguridad"):
        nueva_p = st.text_input("Nueva Clave", type="password")
        if st.button("ACTUALIZAR"):
            conn = get_connection(); c = conn.cursor(); c.execute("UPDATE usuarios SET clave=%s WHERE id=%s",(nueva_p, st.session_state.uid)); conn.commit(); c.close(); st.success("Listo"); st.rerun()
    if st.button("CERRAR SESIÓN"): st.session_state.autenticado = False; st.rerun()

if st.session_state.rol != 'admin':
    st.markdown(f'<div class="alert-box">⚠️ <b>Suscripción {st.session_state.plan} Activa.</b> Cambia tu clave temporal en el menú lateral.</div>', unsafe_allow_html=True)

# --- 5. MÓDULOS ---

if menu == "📊 Dashboard":
    st.header("Dashboard Financiero")
    df = pd.read_sql(f"SELECT * FROM movimientos WHERE usuario_id={st.session_state.uid}", get_connection())
    if not df.empty:
        ing = float(df[df['tipo']=='Ingreso']['monto'].sum()); gas = float(df[df['tipo']=='Gasto']['monto'].sum())
        c1, c2, c3 = st.columns(3); c1.metric("INGRESOS", f"₡{ing:,.0f}"); c2.metric("GASTOS", f"₡{gas:,.0f}"); c3.metric("SALDO", f"₡{(ing-gas):,.0f}")
        st.plotly_chart(px.pie(df[df['tipo']=='Gasto'], values='monto', names='cat', hole=0.6, template="plotly_dark"), use_container_width=True)

elif menu == "💸 Nuevo Registro":
    st.header("Registrar Movimiento")
    tipo = st.radio("Tipo:", ["Gasto", "Ingreso"], horizontal=True)
    lista_g = ["⚖️ Pensión", "⚡ Luz", "💧 Agua", "🏠 Alquiler", "🛒 Súper", "📱 Celular", "🏦 Préstamo", "🚗 Gasolina", "📦 Otros"]
    lista_i = ["💵 Salario", "💰 Aguinaldo", "📱 SINPE", "📈 Negocio", "🧧 Comisiones", "🚜 Freelance", "🏢 Rentas", "🎁 Regalos", "💸 Cobros", "📦 Otros"]
    cat = st.selectbox("Categoría:", lista_i if tipo == "Ingreso" else lista_g)
    with st.form("f_reg"):
        monto = st.number_input("Monto (₡)", min_value=0.0); fecha = st.date_input("Fecha Pago:", datetime.now()); det = st.text_input("Nota:")
        if st.form_submit_button("GUARDAR"):
            conn = get_connection(); c = conn.cursor(); c.execute("INSERT INTO movimientos (usuario_id, fecha, descrip, monto, tipo, cat, vence) VALUES (%s,%s,%s,%s,%s,%s,%s)", (st.session_state.uid, datetime.now().date(), f"{cat}: {det}", monto, tipo, cat, fecha)); conn.commit(); c.close(); st.success("Guardado."); st.rerun()

elif menu == "🎯 Metas":
    st.header("Metas de Ahorro")
    with st.expander("➕ CREAR META"):
        with st.form("fm"):
            n = st.text_input("Nombre"); o = st.number_input("Objetivo (₡)", min_value=0.0)
            if st.form_submit_button("CREAR"):
                conn = get_connection(); c = conn.cursor(); c.execute("INSERT INTO metas (usuario_id, nombre, objetivo, actual) VALUES (%s,%s,%s,%s)", (st.session_state.uid, n, o, 0)); conn.commit(); c.close(); st.rerun()
    df_m = pd.read_sql(f"SELECT * FROM metas WHERE usuario_id={st.session_state.uid}", get_connection())
    for _, r in df_m.iterrows():
        st.markdown(f'<div class="user-card">🎯 {r["nombre"]} | ₡{float(r["actual"]):,.0f} / ₡{float(r["objetivo"]):,.0f}</div>', unsafe_allow_html=True)
        # Barra de progreso
        prog = min(float(r['actual'])/float(r['objetivo']), 1.0) if float(r['objetivo']) > 0 else 0
        st.progress(prog)
        c_a, c_b = st.columns([2,1]); ab = c_a.number_input("Sumar ahorro:", min_value=0.0, key=f"ab_{r['id']}")
        if c_b.button("AHORRAR", key=f"btn_{r['id']}"):
            conn = get_connection(); c = conn.cursor(); c.execute("UPDATE metas SET actual = actual + %s WHERE id = %s", (ab, r['id'])); conn.commit(); c.close(); st.rerun()

elif menu == "🏦 Deudas y Cobros":
    st.header("Compromisos")
    t1, t2 = st.tabs(["💸 Mis Deudas", "💰 Mis Cobros"])
    with t1:
        with st.expander("➕ NUEVA DEUDA"):
            with st.form("fd"):
                n = st.text_input("Acreedor"); m = st.number_input("Monto"); fv = st.date_input("Vence")
                if st.form_submit_button("GUARDAR"):
                    conn = get_connection(); c = conn.cursor(); c.execute("INSERT INTO deudas (usuario_id, nombre, monto_total, pagado, tipo_registro, fecha_vence) VALUES (%s,%s,%s,%s,%s,%s)", (st.session_state.uid, n, m, 0, 'DEUDA', fv)); conn.commit(); c.close(); st.rerun()
        df_d = pd.read_sql(f"SELECT * FROM deudas WHERE usuario_id={st.session_state.uid} AND tipo_registro='DEUDA'", get_connection())
        for _, r in df_d.iterrows():
            pend = float(r['monto_total']) - float(r['pagado'])
            st.markdown(f'<div class="user-card">🔴 {r["nombre"]} | Vence: {r["fecha_vence"]} | ₡{pend:,.0f}</div>', unsafe_allow_html=True)
            c_a, c_b = st.columns(2); ab = c_a.number_input("Abonar:", min_value=0.0, key=f"abd_{r['id']}")
            if c_b.button("PAGAR", key=f"btnd_{r['id']}"):
                conn = get_connection(); c = conn.cursor(); c.execute("UPDATE deudas SET pagado = pagado + %s WHERE id = %s", (ab, r['id'])); conn.commit(); c.close(); st.rerun()
    with t2:
        with st.expander("➕ NUEVO COBRO"):
            with st.form("fc"):
                n = st.text_input("Deudor"); m = st.number_input("Monto"); fv = st.date_input("Fecha Cobro")
                if st.form_submit_button("GUARDAR"):
                    conn = get_connection(); c = conn.cursor(); c.execute("INSERT INTO deudas (usuario_id, nombre, monto_total, pagado, tipo_registro, fecha_vence) VALUES (%s,%s,%s,%s,%s,%s)", (st.session_state.uid, n, m, 0, 'COBRO', fv)); conn.commit(); c.close(); st.rerun()
        df_c = pd.read_sql(f"SELECT * FROM deudas WHERE usuario_id={st.session_state.uid} AND tipo_registro='COBRO'", get_connection())
        for _, r in df_c.iterrows():
            pend = float(r['monto_total']) - float(r['pagado'])
            st.markdown(f'<div class="user-card">🟢 {r["nombre"]} | Vence: {r["fecha_vence"]} | ₡{pend:,.0f}</div>', unsafe_allow_html=True)
            c_a, c_b = st.columns(2); ab = c_a.number_input("Recibir:", min_value=0.0, key=f"abc_{r['id']}")
            if c_b.button("RECUPERAR", key=f"btnc_{r['id']}"):
                conn = get_connection(); c = conn.cursor(); c.execute("UPDATE deudas SET pagado = pagado + %s WHERE id = %s", (ab, r['id'])); conn.commit(); c.close(); st.rerun()

elif menu == "📱 SINPE Rápido":
    st.header("SINPE Móvil")
    df_cont = pd.read_sql(f"SELECT * FROM contactos WHERE usuario_id={st.session_state.uid}", get_connection())
    with st.expander("👤 AGENDA"):
        with st.form("c"):
            n = st.text_input("Nombre"); t = st.text_input("Teléfono")
            if st.form_submit_button("GUARDAR"):
                conn = get_connection(); c = conn.cursor(); c.execute("INSERT INTO contactos (usuario_id, nombre, telefono) VALUES (%s,%s,%s)", (st.session_state.uid, n, t)); conn.commit(); c.close(); st.rerun()
    sel = st.selectbox("Elegir:", ["Manual"] + [f"{r['nombre']} ({r['telefono']})" for _, r in df_cont.iterrows()])
    num = st.text_input("Número:") if sel == "Manual" else sel.split("(")[1].replace(")", "")
    monto = st.number_input("Monto (₡):", min_value=0.0)
    if num:
        st.markdown(f'<div class="sinpe-card"><h1 style="font-size: 3em;">{num}</h1><p>₡{monto:,.0f}</p><a href="https://www.google.com" target="_blank" class="bank-btn">🏦 IR AL BANCO</a></div>', unsafe_allow_html=True)

elif menu == "📜 Historial / Borrar":
    st.header("Historial")
    df_h = pd.read_sql(f"SELECT id, fecha, cat, monto, tipo FROM movimientos WHERE usuario_id={st.session_state.uid} ORDER BY id DESC", get_connection())
    for _, row in df_h.iterrows():
        c1, c2, c3, c4 = st.columns([1,3,2,1])
        c1.write("🟢" if row['tipo']=="Ingreso" else "🔴")
        c2.write(f"**{row['cat']}**\n{row['fecha']}")
        c3.write(f"₡{row['monto']:,.0f}")
        if c4.button("🗑️", key=f"del_{row['id']}"):
            conn = get_connection(); c = conn.cursor(); c.execute(f"DELETE FROM movimientos WHERE id={row['id']}"); conn.commit(); c.close(); st.rerun()

elif menu == "⚙️ Admin" and st.session_state.rol == 'admin':
    st.header("Admin")
    with st.form("fa"):
        un = st.text_input("Usuario"); uk = st.text_input("Clave"); up = st.selectbox("Plan", ["Mensual", "Anual"])
        if st.form_submit_button("CREAR"):
            vf = (datetime.now() + timedelta(days=30 if up=="Mensual" else 365)).date()
            conn = get_connection(); c = conn.cursor(); c.execute("INSERT INTO usuarios (nombre, clave, expira, rol, plan) VALUES (%s,%s,%s,%s,%s)", (un, uk, vf, 'usuario', up)); conn.commit(); c.close(); st.rerun()
    st.dataframe(pd.read_sql("SELECT nombre, plan, expira FROM usuarios WHERE rol!='admin'", get_connection()))
