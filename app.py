import streamlit as st
import pandas as pd
import psycopg2
from datetime import datetime, timedelta, date
import plotly.express as px
import time

# --- 1. ESTÉTICA ELITE PRO ---
st.set_page_config(page_title="GeZo Elite Pro", page_icon="💎", layout="wide")

st.markdown("""
    <style>
    #MainMenu {visibility: hidden;} header {visibility: hidden;} footer {visibility: hidden;}
    .stDeployButton {display:none;} [data-testid="stToolbar"] {display: none !important;}
    .main { background-color: #0b0e14; color: #e0e0e0; }
    [data-testid="stSidebar"] { background-color: #0f121a; border-right: 1px solid #1e2633; }
    
    /* Tarjetas de Indicadores BAC */
    .bac-card {
        background: linear-gradient(135deg, #ff4b4b 0%, #a30000 100%);
        border-radius: 15px; padding: 15px; text-align: center; border: 1px solid #ff4b4b;
    }
    .balance-card {
        background: linear-gradient(135deg, #1e2633 0%, #0b0e14 100%);
        border-radius: 20px; padding: 20px; border: 1px solid #333; text-align: center;
    }
    .metric-value { font-size: 2.2em; font-weight: 900; color: #00f2fe; }
    .ia-box {
        background: rgba(0, 242, 254, 0.05); border: 1px solid #00f2fe;
        padding: 20px; border-radius: 20px; border-left: 10px solid #00f2fe; margin-top: 20px;
    }
    .user-card { background: rgba(255, 255, 255, 0.03); padding: 15px; border-radius: 12px; border-left: 5px solid #00f2fe; margin-bottom: 10px; }
    </style>
    """, unsafe_allow_html=True)

# --- 2. BASE DE DATOS Y FUNCIONES ---
@st.cache_resource
def get_connection():
    try: return psycopg2.connect(st.secrets["DB_URL"], connect_timeout=60)
    except Exception as e: st.error(f"Error DB: {e}"); st.stop()

def reg_mov(monto, tipo, cat, desc):
    if monto > 0:
        conn = get_connection(); c = conn.cursor()
        c.execute("INSERT INTO movimientos (usuario_id, fecha, descrip, monto, tipo, cat) VALUES (%s,%s,%s,%s,%s,%s)", 
                  (st.session_state.uid, date.today(), desc, monto, tipo, cat))
        conn.commit(); c.close()

# --- 3. LOGIN ---
if 'autenticado' not in st.session_state: st.session_state.autenticado = False
if not st.session_state.autenticado:
    st.title("💎 GeZo Elite Pro")
    with st.form("login"):
        u = st.text_input("Usuario"); p = st.text_input("Clave", type="password")
        if st.form_submit_button("INGRESAR"):
            conn = get_connection(); c = conn.cursor()
            c.execute("SELECT id, nombre, rol, plan, expira FROM usuarios WHERE nombre=%s AND clave=%s", (u, p))
            res = c.fetchone()
            if res and date.today() <= res[4]:
                st.session_state.update({"autenticado":True, "uid":res[0], "uname":res[1], "rol":res[2], "plan":res[3]}); st.rerun()
            else: st.error("Acceso denegado."); c.close()
    st.stop()

# --- 4. MÓDULO TIPO DE CAMBIO (BAC SIMULADO/ESTÁTICO PARA VELOCIDAD) ---
def mostrar_tipo_cambio():
    # En una implementación real, aquí se usaría un scraper o API.
    compra = 512.00 # Ejemplo BAC
    venta = 524.00  # Ejemplo BAC
    c1, c2 = st.columns(2)
    with c1: st.markdown(f'<div class="bac-card"><p style="margin:0; font-size:0.8em; color:white;">BAC COMPRA</p><h2 style="margin:0; color:white;">₡{compra}</h2></div>', unsafe_allow_html=True)
    with c2: st.markdown(f'<div class="bac-card"><p style="margin:0; font-size:0.8em; color:white;">BAC VENTA</p><h2 style="margin:0; color:white;">₡{venta}</h2></div>', unsafe_allow_html=True)

# --- 5. NAVEGACIÓN ---
with st.sidebar:
    st.markdown(f"### 👑 {st.session_state.uname}")
    menu = st.radio("MENÚ", ["📊 Dashboard IA", "💸 Registros", "🎯 Metas", "🏦 Deudas y Cobros", "📱 SINPE", "📜 Historial"])
    with st.expander("🔐 Seguridad"):
        nv_p = st.text_input("Nueva Clave", type="password")
        if st.button("CAMBIAR"):
            conn = get_connection(); c = conn.cursor(); c.execute("UPDATE usuarios SET clave=%s WHERE id=%s", (nv_p, st.session_state.uid)); conn.commit(); c.close(); st.success("Listo")
    if st.button("SALIR"): st.session_state.autenticado = False; st.rerun()

# --- 6. MÓDULOS ---

if menu == "📊 Dashboard IA":
    st.header("Indicadores BAC y Balance IA")
    
    # 🏦 Tipo de Cambio BAC incorporado arriba
    mostrar_tipo_cambio()
    st.divider()

    per = st.select_slider("Análisis de tiempo:", options=["Día", "Semana", "Mes"])
    dias = {"Día": 0, "Semana": 7, "Mes": 30}
    f_inicio = date.today() - timedelta(days=dias[per])
    
    df = pd.read_sql(f"SELECT * FROM movimientos WHERE usuario_id={st.session_state.uid} AND fecha >= '{f_inicio}'", get_connection())
    
    if not df.empty:
        ing = float(df[df['tipo']=='Ingreso']['monto'].sum())
        gas = float(df[df['tipo']=='Gasto']['monto'].sum())
        neto = ing - gas
        
        c1, c2, c3 = st.columns(3)
        with c1: st.markdown(f'<div class="balance-card"><p class="metric-label">Ingresos</p><p class="metric-value">₡{ing:,.0f}</p></div>', unsafe_allow_html=True)
        with c2: st.markdown(f'<div class="balance-card"><p class="metric-label">Gastos</p><p class="metric-value" style="color:#ff4b4b;">₡{gas:,.0f}</p></div>', unsafe_allow_html=True)
        with c3: st.markdown(f'<div class="balance-card"><p class="metric-label">Generación Neta</p><p class="metric-value" style="color:#2ecc71;">₡{neto:,.0f}</p></div>', unsafe_allow_html=True)
        
        # CONSEJO DE IA
        st.markdown('<div class="ia-box">', unsafe_allow_html=True)
        ahorro_liq = neto * 0.20 if neto > 0 else 0
        if neto < 0:
            st.warning(f"⚠️ **Atención {st.session_state.uname}:** Estás operando con un déficit de ₡{abs(neto):,.0f}. Evita compras en dólares con este tipo de cambio.")
        else:
            st.success(f"🚀 **Liquidez Perfecta:** De tus ganancias de hoy, reserva **₡{ahorro_liq:,.0f}** para tus metas. ¡Estás dominando tus finanzas!")
        st.markdown('</div>', unsafe_allow_html=True)
        
        st.plotly_chart(px.bar(df, x='cat', y='monto', color='tipo', template="plotly_dark", barmode='group'))
    else: st.info("Sin movimientos en este periodo.")

elif menu == "💸 Registros":
    st.header("Nuevo Movimiento")
    t = st.radio("Tipo:", ["Gasto", "Ingreso"], horizontal=True)
    cats = ["Pensión", "Salario", "Ventas", "Comida", "Luz/Agua", "Alquiler", "Gasolina", "Ocio", "Inversión", "Otros"]
    cat = st.selectbox("Categoría:", cats)
    with st.form("fr"):
        m = st.number_input("Monto (₡)", min_value=0.0); d = st.text_input("Nota")
        if st.form_submit_button("GUARDAR"):
            reg_mov(m, t, cat, d); st.success("Registrado"); time.sleep(0.5); st.rerun()

elif menu == "🎯 Metas":
    st.header("Ahorros y Proyectos")
    with st.expander("➕ Crear Nueva Meta"):
        with st.form("fm"):
            n = st.text_input("Nombre"); obj = st.number_input("Monto Objetivo")
            if st.form_submit_button("CREAR"):
                conn = get_connection(); c = conn.cursor(); c.execute("INSERT INTO metas (usuario_id, nombre, objetivo) VALUES (%s,%s,%s)", (st.session_state.uid, n, obj)); conn.commit(); c.close(); st.rerun()
    
    df_m = pd.read_sql(f"SELECT * FROM metas WHERE usuario_id={st.session_state.uid}", get_connection())
    for _, r in df_m.iterrows():
        st.markdown(f'<div class="user-card">🎯 {r["nombre"]} | ₡{float(r["actual"]):,.0f} / ₡{float(r["objetivo"]):,.0f}</div>', unsafe_allow_html=True)
        st.progress(min(float(r['actual'])/float(r['objetivo']), 1.0))
        c1, c2, c3 = st.columns([2,1,1])
        m_a = c1.number_input("Monto:", min_value=0.0, key=f"m{r['id']}")
        if c2.button("ABONAR", key=f"b{r['id']}"):
            conn = get_connection(); c = conn.cursor(); c.execute("UPDATE metas SET actual=actual+%s WHERE id=%s", (m_a, r['id'])); conn.commit(); c.close()
            reg_mov(m_a, "Gasto", "🎯 Ahorro", f"Meta: {r['nombre']}"); st.rerun()
        if c3.button("🗑️", key=f"d{r['id']}"):
            conn = get_connection(); c = conn.cursor(); c.execute(f"DELETE FROM metas WHERE id={r['id']}"); conn.commit(); c.close(); st.rerun()

elif menu == "🏦 Deudas y Cobros":
    st.header("Compromisos")
    t1, t2 = st.tabs(["💸 Mis Deudas (Egresos)", "💰 Mis Cobros (Ingresos)"])
    with t1:
        with st.expander("Registrar Deuda"):
            with st.form("fd"):
                n = st.text_input("Acreedor"); m = st.number_input("Monto Total"); fv = st.date_input("Vence")
                if st.form_submit_button("GUARDAR"):
                    conn = get_connection(); c = conn.cursor(); c.execute("INSERT INTO deudas (usuario_id, nombre, monto_total, tipo_registro, fecha_vence) VALUES (%s,%s,%s,'DEUDA',%s)", (st.session_state.uid, n, m, fv)); conn.commit(); c.close(); st.rerun()
        df_d = pd.read_sql(f"SELECT * FROM deudas WHERE usuario_id={st.session_state.uid} AND tipo_registro='DEUDA'", get_connection())
        for _, r in df_d.iterrows():
            pe = float(r['monto_total']) - float(r['pagado'])
            st.markdown(f'<div class="user-card">🔴 {r["nombre"]} | Pendiente: ₡{pe:,.0f}</div>', unsafe_allow_html=True)
            ca, cb = st.columns([2,1]); ab = ca.number_input("Pagar:", min_value=0.0, key=f"d{r['id']}")
            if cb.button("PAGAR", key=f"bd{r['id']}"):
                conn = get_connection(); c = conn.cursor(); c.execute("UPDATE deudas SET pagado=pagado+%s WHERE id=%s", (ab, r['id'])); conn.commit(); c.close()
                reg_mov(ab, "Gasto", "🏦 Deuda", f"Pago a {r['nombre']}"); st.rerun()
    with t2:
        # Lógica de Cobros similar (con reg_mov como 'Ingreso')
        df_c = pd.read_sql(f"SELECT * FROM deudas WHERE usuario_id={st.session_state.uid} AND tipo_registro='COBRO'", get_connection())
        for _, r in df_c.iterrows():
            pe = float(r['monto_total']) - float(r['pagado'])
            st.markdown(f'<div class="user-card">🟢 {r["nombre"]} | Pendiente: ₡{pe:,.0f}</div>', unsafe_allow_html=True)
            ca, cb = st.columns([2,1]); ab = ca.number_input("Recibir:", min_value=0.0, key=f"c{r['id']}")
            if cb.button("REGISTRAR", key=f"bc{r['id']}"):
                conn = get_connection(); c = conn.cursor(); c.execute("UPDATE deudas SET pagado=pagado+%s WHERE id=%s", (ab, r['id'])); conn.commit(); c.close()
                reg_mov(ab, "Ingreso", "💸 Cobro", f"De {r['nombre']}"); st.rerun()

elif menu == "📱 SINPE":
    st.header("SINPE Móvil")
    num = st.text_input("Número:"); mon = st.number_input("Monto")
    if st.button("PROCESAR"):
        reg_mov(mon, "Gasto", "📱 SINPE", f"A: {num}")
        st.markdown(f'<a href="https://www.google.com" target="_blank" class="bank-btn">🏦 ABRIR BANCO</a>', unsafe_allow_html=True)

elif menu == "📜 Historial":
    st.header("Historial de Movimientos")
    df_h = pd.read_sql(f"SELECT id, fecha, cat, monto, tipo FROM movimientos WHERE usuario_id={st.session_state.uid} ORDER BY id DESC", get_connection())
    for _, row in df_h.iterrows():
        c1, c2, c3 = st.columns([1,4,1])
        c1.write("🟢" if row['tipo']=="Ingreso" else "🔴")
        c2.write(f"**{row['cat']}** | ₡{row['monto']:,.0f}")
        if c3.button("🗑️", key=f"h{row['id']}"):
            conn = get_connection(); c = conn.cursor(); c.execute(f"DELETE FROM movimientos WHERE id={row['id']}"); conn.commit(); c.close(); st.rerun()
