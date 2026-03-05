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
        transition: 0.3s all; text-transform: uppercase;
    }
    .user-card { background: rgba(255, 255, 255, 0.05); padding: 20px; border-radius: 15px; border: 1px solid #333; margin-bottom: 15px; border-left: 5px solid #00f2fe; }
    .bank-btn { 
        background: #1a1d24; border: 2px solid #00c6ff; color: #00c6ff !important; 
        padding: 15px; border-radius: 12px; text-align: center; display: block; 
        text-decoration: none; font-weight: bold; margin-top: 10px; transition: 0.3s;
    }
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
    c.execute("CREATE TABLE IF NOT EXISTS deudas (id SERIAL PRIMARY KEY, usuario_id INTEGER, nombre TEXT, monto_total DECIMAL, pagado DECIMAL DEFAULT 0, tipo_registro TEXT, fecha_inicio DATE, fecha_vence DATE)")
    c.execute("CREATE TABLE IF NOT EXISTS contactos (id SERIAL PRIMARY KEY, usuario_id INTEGER, nombre TEXT, telefono TEXT)")
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

# --- 4. MENÚ ---
with st.sidebar:
    st.markdown(f"### 👑 {st.session_state.uname}")
    menu = st.radio("NAVEGACIÓN", ["📊 Dashboard", "💸 Nuevo Registro", "📜 Historial / Borrar", "🎯 Metas", "🏦 Deudas y Cobros", "📱 SINPE Rápido", "⚙️ Admin"])
    if st.button("CERRAR SESIÓN"): st.session_state.autenticado = False; st.rerun()

# --- 5. REGISTRO ---
if menu == "💸 Nuevo Registro":
    st.header("Entradas y Salidas")
    lista_g = ["⚖️ Pensión Alimentaria", "⚡ Recibo de Luz", "💧 Recibo de Agua", "🏠 Alquiler/Hipoteca", "🛒 Súper/Comida", "📱 Plan Celular/Net", "🏦 Cuota Préstamo", "🚗 Gasolina/Transporte", "📦 Otros Gastos"]
    lista_i = ["💵 Salario Mensual", "💰 Aguinaldo", "📱 SINPE Recibido", "📈 Ventas/Negocio", "🧧 Comisiones", "🚜 Freelance/Servicios", "🏢 Rentas/Alquileres", "🎁 Regalos", "💸 Cobros/Abonos Recibidos", "📦 Otros Ingresos"]
    tipo = st.radio("Tipo:", ["Gasto", "Ingreso"], horizontal=True)
    cat = st.selectbox("Categoría:", lista_i if tipo == "Ingreso" else lista_g)
    with st.form("f_reg"):
        monto = st.number_input("Monto (₡)", min_value=0.0); fecha = st.date_input("Fecha Pago:", datetime.now()); det = st.text_input("Nota:")
        if st.form_submit_button("GUARDAR"):
            conn = get_connection(); c = conn.cursor()
            c.execute("INSERT INTO movimientos (usuario_id, fecha, descrip, monto, tipo, cat, vence) VALUES (%s,%s,%s,%s,%s,%s,%s)", (st.session_state.uid, datetime.now().date(), f"{cat}: {det}", monto, tipo, cat, fecha))
            conn.commit(); c.close(); st.success("Guardado."); st.rerun()

# --- 6. MÓDULO: METAS (CORREGIDO Y POTENCIADO) ---
elif menu == "🎯 Metas":
    st.header("Objetivos de Ahorro y Proyectos")
    
    # Formulario para crear meta
    with st.expander("➕ CREAR NUEVA META"):
        with st.form("form_meta"):
            col1, col2 = st.columns(2)
            nombre_meta = col1.text_input("¿Para qué es el ahorro?", placeholder="Ej: Viaje, Carro, Fondo de Emergencia")
            monto_meta = col2.number_input("Monto Objetivo (₡)", min_value=0.0, step=5000.0)
            if st.form_submit_button("CREAR PROYECTO"):
                if nombre_meta and monto_meta > 0:
                    conn = get_connection(); c = conn.cursor()
                    c.execute("INSERT INTO metas (usuario_id, nombre, objetivo, actual) VALUES (%s,%s,%s,%s)", (st.session_state.uid, nombre_meta, monto_meta, 0))
                    conn.commit(); c.close(); st.success("Meta creada!"); st.rerun()
                else: st.warning("Completa los datos.")

    # Listado de Metas
    df_metas = pd.read_sql(f"SELECT * FROM metas WHERE usuario_id={st.session_state.uid}", get_connection())
    
    if not df_metas.empty:
        for _, r in df_metas.iterrows():
            objetivo = float(r['objetivo'])
            actual = float(r['actual'])
            progreso = (actual / objetivo) if objetivo > 0 else 0
            
            with st.container():
                st.markdown(f'<div class="user-card">', unsafe_allow_html=True)
                c1, c2 = st.columns([3, 1])
                c1.subheader(f"🎯 {r['nombre']}")
                c2.write(f"**{progreso*100:.1f}% Completado**")
                
                # Barra de progreso visual
                st.progress(min(progreso, 1.0))
                
                st.write(f"Ahorrado: **₡{actual:,.0f}** de **₡{objetivo:,.0f}**")
                
                # Acciones para la meta
                col_a, col_b, col_c = st.columns([2, 2, 1])
                monto_abono = col_a.number_input("Monto a sumar:", min_value=0.0, key=f"abono_m_{r['id']}")
                if col_b.button("SUMAR AL AHORRO", key=f"btn_m_{r['id']}"):
                    conn = get_connection(); c = conn.cursor()
                    c.execute("UPDATE metas SET actual = actual + %s WHERE id = %s", (monto_abono, r['id']))
                    conn.commit(); c.close(); st.success("¡Ahorro actualizado!"); time.sleep(0.5); st.rerun()
                
                if col_c.button("🗑️", key=f"del_m_{r['id']}"):
                    conn = get_connection(); c = conn.cursor(); c.execute(f"DELETE FROM metas WHERE id={r['id']}"); conn.commit(); c.close(); st.rerun()
                
                st.markdown('</div>', unsafe_allow_html=True)
                st.divider()
    else:
        st.info("Aún no tienes metas registradas. ¡Empieza creando una arriba!")

# --- 7. DEUDAS Y COBROS ---
elif menu == "🏦 Deudas y Cobros":
    st.header("Gestión de Compromisos")
    t1, t2 = st.tabs(["💸 Deudas", "💰 Cobros"])
    with t1:
        with st.expander("➕ REGISTRAR DEUDA"):
            with st.form("nd"):
                c1, c2 = st.columns(2); n_d = c1.text_input("Acreedor"); m_d = c2.number_input("Monto Total")
                f_i = c1.date_input("Fecha Adquisición"); f_v = c2.date_input("Fecha Vence")
                if st.form_submit_button("CREAR"):
                    conn = get_connection(); c = conn.cursor(); c.execute("INSERT INTO deudas (usuario_id, nombre, monto_total, pagado, tipo_registro, fecha_inicio, fecha_vence) VALUES (%s,%s,%s,%s,%s,%s,%s)", (st.session_state.uid, n_d, m_d, 0, 'DEUDA', f_i, f_v)); conn.commit(); c.close(); st.rerun()
        df_d = pd.read_sql(f"SELECT * FROM deudas WHERE usuario_id={st.session_state.uid} AND tipo_registro='DEUDA'", get_connection())
        for _, r in df_d.iterrows():
            saldo = float(r['monto_total']) - float(r['pagado'])
            st.markdown(f'<div class="user-card"><strong>{r["nombre"]}</strong> | Vence: {r["fecha_vence"]}<br>Pendiente: ₡{saldo:,.0f}</div>', unsafe_allow_html=True)
            col_a1, col_a2 = st.columns(2)
            ab = col_a1.number_input("Abono:", min_value=0.0, key=f"ab_{r['id']}")
            if col_a2.button("ABONAR", key=f"btn_d_{r['id']}"):
                conn = get_connection(); c = conn.cursor(); c.execute("UPDATE deudas SET pagado = pagado + %s WHERE id = %s", (ab, r['id'])); conn.commit(); c.close(); st.rerun()

    with t2:
        with st.expander("➕ REGISTRAR COBRO"):
            with st.form("nc"):
                c1, c2 = st.columns(2); n_c = c1.text_input("Deudor"); m_c = c2.number_input("Monto a cobrar")
                f_ic = c1.date_input("Fecha Préstamo"); f_vc = c2.date_input("Fecha Promesa")
                if st.form_submit_button("CREAR"):
                    conn = get_connection(); c = conn.cursor(); c.execute("INSERT INTO deudas (usuario_id, nombre, monto_total, pagado, tipo_registro, fecha_inicio, fecha_vence) VALUES (%s,%s,%s,%s,%s,%s,%s)", (st.session_state.uid, n_c, m_c, 0, 'COBRO', f_ic, f_vc)); conn.commit(); c.close(); st.rerun()
        df_c = pd.read_sql(f"SELECT * FROM deudas WHERE usuario_id={st.session_state.uid} AND tipo_registro='COBRO'", get_connection())
        for _, r in df_c.iterrows():
            saldo_c = float(r['monto_total']) - float(r['pagado'])
            st.markdown(f'<div class="user-card" style="border-left-color: #2ecc71;"><strong>{r["nombre"]}</strong> | Vence: {r["fecha_vence"]}<br>Por cobrar: ₡{saldo_c:,.0f}</div>', unsafe_allow_html=True)
            col_b1, col_b2 = st.columns(2)
            abc = col_b1.number_input("Recibir Pago:", min_value=0.0, key=f"abc_{r['id']}")
            if col_b2.button("RECIBIR", key=f"btnc_{r['id']}"):
                conn = get_connection(); c = conn.cursor(); c.execute("UPDATE deudas SET pagado = pagado + %s WHERE id = %s", (abc, r['id'])); conn.commit(); c.close(); st.rerun()

# --- 8. DASHBOARD Y OTROS ---
elif menu == "📊 Dashboard":
    st.header("Situación Financiera")
    df = pd.read_sql(f"SELECT * FROM movimientos WHERE usuario_id={st.session_state.uid}", get_connection())
    if not df.empty:
        ing = float(df[df['tipo']=='Ingreso']['monto'].sum()); gas = float(df[df['tipo']=='Gasto']['monto'].sum())
        c1, c2, c3 = st.columns(3); c1.metric("INGRESOS", f"₡{ing:,.0f}"); c2.metric("GASTOS", f"₡{gas:,.0f}"); c3.metric("SALDO", f"₡{(ing-gas):,.0f}")
        st.plotly_chart(px.pie(df[df['tipo']=='Gasto'], values='monto', names='cat', hole=0.6, template="plotly_dark"), use_container_width=True)

elif menu == "📜 Historial / Borrar":
    df_h = pd.read_sql(f"SELECT id, fecha, cat, monto, tipo, vence FROM movimientos WHERE usuario_id={st.session_state.uid} ORDER BY id DESC", get_connection())
    for _, row in df_h.iterrows():
        c1, c2, c3, c4 = st.columns([1, 3, 2, 1])
        c1.write("🟢" if row['tipo'] == "Ingreso" else "🔴")
        c2.write(f"**{row['cat']}**\n_{row['vence']}_")
        c3.write(f"₡{row['monto']:,.0f}")
        if c4.button("🗑️", key=f"del_h_{row['id']}"):
            conn = get_connection(); c = conn.cursor(); c.execute(f"DELETE FROM movimientos WHERE id={row['id']}"); conn.commit(); c.close(); st.rerun()
        st.divider()

elif menu == "📱 SINPE Rápido":
    st.header("SINPE Móvil Express")
    df_cont = pd.read_sql(f"SELECT * FROM contactos WHERE usuario_id={st.session_state.uid}", get_connection())
    with st.expander("👤 Gestionar Contactos"):
        with st.form("c"):
            n = st.text_input("Nombre"); t = st.text_input("Teléfono")
            if st.form_submit_button("Guardar"):
                conn = get_connection(); c = conn.cursor(); c.execute("INSERT INTO contactos (usuario_id, nombre, telefono) VALUES (%s,%s,%s)", (st.session_state.uid, n, t)); conn.commit(); c.close(); st.rerun()
    sel = st.selectbox("Contacto:", ["Manual"] + [f"{r['nombre']} ({r['telefono']})" for _, r in df_cont.iterrows()])
    num = st.text_input("Número:") if sel == "Manual" else sel.split("(")[1].replace(")", "")
    st.markdown(f'<a href="https://www.google.com" target="_blank" class="bank-btn">🏦 ABRIR BANCO PARA: {num}</a>', unsafe_allow_html=True)

elif menu == "⚙️ Admin" and st.session_state.rol == 'admin':
    with st.form("f_admin"):
        un = st.text_input("Usuario"); uk = st.text_input("Clave"); up = st.selectbox("Plan", ["Mensual", "Anual"]); um = st.text_input("Monto", "5000")
        if st.form_submit_button("ACTIVAR"):
            vf = (datetime.now() + timedelta(days=30 if up=="Mensual" else 365)).date()
            conn = get_connection(); c = conn.cursor(); c.execute("INSERT INTO usuarios (nombre, clave, expira, rol, plan, precio) VALUES (%s,%s,%s,%s,%s,%s)", (un, uk, vf, 'usuario', up, um)); conn.commit(); c.close(); st.rerun()
