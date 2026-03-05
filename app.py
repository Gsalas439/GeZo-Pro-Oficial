import streamlit as st
import pandas as pd
import psycopg2
from datetime import datetime, timedelta, date
import plotly.express as px

# --- 1. CONFIGURACIÓN DE INTERFAZ ---
st.set_page_config(page_title="GeZo Elite Pro", page_icon="💎", layout="wide", initial_sidebar_state="collapsed")

st.markdown("""
    <style>
    header[data-testid="stHeader"], div[data-testid="stToolbar"], #MainMenu, footer, .stDeployButton {display: none !important;}
    .block-container {padding-top: 1.5rem !important;}
    .main { background-color: #0b0e14; color: #e0e0e0; font-family: 'Inter', sans-serif; }
    .balance-card {
        background: linear-gradient(135deg, #1e2633 0%, #0b0e14 100%);
        border-radius: 15px; padding: 20px; border: 1px solid #333; text-align: center; margin-bottom: 15px;
    }
    .metric-value { font-size: 2.2em; font-weight: 900; color: #00f2fe; margin: 0; }
    .metric-label { font-size: 0.85em; color: #888; text-transform: uppercase; font-weight: bold; margin: 0; }
    .bac-card { background: linear-gradient(135deg, #cc0000 0%, #8b0000 100%); border-radius: 12px; padding: 12px; text-align: center; border: 1px solid #ff4b4b; }
    .ia-box { background: rgba(0, 242, 254, 0.05); border: 1px solid #00f2fe; padding: 20px; border-radius: 15px; border-left: 8px solid #00f2fe; margin-top: 10px; }
    .user-card { background: rgba(255, 255, 255, 0.03); padding: 15px; border-radius: 12px; border: 1px solid #222; border-left: 5px solid #00f2fe; margin-bottom: 10px; }
    </style>
    """, unsafe_allow_html=True)

# --- 2. MOTOR DB ---
def get_connection():
    return psycopg2.connect(st.secrets["DB_URL"])

def reg_mov(monto, tipo, cat, desc):
    if monto > 0:
        conn = get_connection(); c = conn.cursor()
        c.execute("INSERT INTO movimientos (usuario_id, fecha, descrip, monto, tipo, cat) VALUES (%s,%s,%s,%s,%s,%s)", 
                  (st.session_state.uid, date.today(), desc, monto, tipo, cat))
        conn.commit(); c.close(); conn.close()

# --- 3. LOGIN & SEGURIDAD (TOKEN EFÍMERO) ---
if 'autenticado' not in st.session_state: st.session_state.autenticado = False

if not st.session_state.autenticado:
    token_url = st.query_params.get("session_token")
    if token_url:
        conn = get_connection(); c = conn.cursor()
        c.execute("SELECT id, nombre, rol, plan, expira FROM usuarios WHERE id=%s", (token_url,))
        res = c.fetchone()
        c.close(); conn.close()
        if res and date.today() <= res[4]:
            st.session_state.update({"autenticado":True, "uid":res[0], "uname":res[1], "rol":res[2], "plan":res[3]})
            st.query_params.clear()
            st.rerun()

if not st.session_state.autenticado:
    st.markdown("<h1 style='text-align: center; color: #00f2fe;'>💎 GeZo Elite Pro</h1>", unsafe_allow_html=True)
    c1, c2, c3 = st.columns([1,1.5,1])
    with c2:
        with st.form("login_form"):
            u = st.text_input("Usuario"); p = st.text_input("Clave", type="password")
            mantener = st.checkbox("Recordarme en este dispositivo", value=True)
            if st.form_submit_button("INGRESAR", use_container_width=True):
                conn = get_connection(); c = conn.cursor()
                c.execute("SELECT id, nombre, rol, plan, expira FROM usuarios WHERE nombre=%s AND clave=%s", (u, p))
                res = c.fetchone()
                c.close(); conn.close()
                if res:
                    st.session_state.update({"autenticado":True, "uid":res[0], "uname":res[1], "rol":res[2], "plan":res[3]})
                    if mantener: st.query_params["session_token"] = str(res[0])
                    st.rerun()
                else: st.error("Error de acceso")
    st.stop()

# --- 4. PANEL DE CONTROL (PESTAÑAS) ---
st.markdown(f"### 👑 **{st.session_state.uname}** | {st.session_state.plan}")
t_dash, t_reg, t_metas, t_deudas, t_sinpe, t_hist, t_ajustes = st.tabs([
    "📊 DASHBOARD", "💸 REGISTRO", "🎯 METAS", "🏦 DEUDAS/COBROS", "📱 SINPE", "📜 HISTORIAL", "⚙️ AJUSTES"
])

# --- DASHBOARD ---
with t_dash:
    cb1, cb2, cb3 = st.columns([1,1,2])
    cb1.markdown('<div class="bac-card"><small>BAC COMPRA</small><br><b>₡512.00</b></div>', unsafe_allow_html=True)
    cb2.markdown('<div class="bac-card"><small>BAC VENTA</small><br><b>₡524.00</b></div>', unsafe_allow_html=True)
    
    st.divider()
    conn = get_connection()
    df = pd.read_sql(f"SELECT * FROM movimientos WHERE usuario_id={st.session_state.uid} AND fecha >= '{date.today() - timedelta(days=30)}'", conn)
    conn.close()
    
    if not df.empty:
        ing = float(df[df['tipo']=='Ingreso']['monto'].sum())
        gas = float(df[df['tipo']=='Gasto']['monto'].sum())
        neto = ing - gas
        
        c1, c2, c3 = st.columns(3)
        c1.markdown(f'<div class="balance-card"><p class="metric-label">Ingresos</p><p class="metric-value">₡{ing:,.0f}</p></div>', unsafe_allow_html=True)
        c2.markdown(f'<div class="balance-card"><p class="metric-label">Gastos</p><p class="metric-value" style="color:#ff4b4b;">₡{gas:,.0f}</p></div>', unsafe_allow_html=True)
        c3.markdown(f'<div class="balance-card"><p class="metric-label">Neto</p><p class="metric-value" style="color:#2ecc71;">₡{neto:,.0f}</p></div>', unsafe_allow_html=True)
        
        st.markdown(f'<div class="ia-box">#### 🤖 GeZo AI Advisor<br>Tu ahorro ideal hoy (20%): **₡{max(0, neto*0.2):,.0f}**.</div>', unsafe_allow_html=True)
        st.plotly_chart(px.pie(df[df['tipo']=='Gasto'], values='monto', names='cat', template="plotly_dark", hole=0.4), use_container_width=True)
    else: st.info("Sin datos registrados.")

# --- REGISTRO ---
with t_reg:
    tipo = st.radio("Tipo", ["Gasto", "Ingreso"], horizontal=True)
    cats = ["Salario", "Venta", "Intereses"] if tipo == "Ingreso" else ["Servicios", "Comida", "Transporte", "Ocio", "Salud", "Educación", "Otros"]
    with st.form("f_reg"):
        m = st.number_input("Monto (₡)", min_value=0.0)
        c = st.selectbox("Categoría", cats)
        d = st.text_input("Nota/Detalle")
        if st.form_submit_button("GUARDAR"):
            reg_mov(m, tipo, c, d); st.success("¡Guardado!"); st.rerun()

# --- METAS ---
with t_metas:
    with st.expander("➕ Nueva Meta"):
        with st.form("f_meta"):
            n = st.text_input("¿Qué quieres comprar?"); o = st.number_input("Precio objetivo", min_value=1.0)
            if st.form_submit_button("CREAR"):
                conn = get_connection(); c = conn.cursor(); c.execute("INSERT INTO metas (usuario_id, nombre, objetivo) VALUES (%s,%s,%s)", (st.session_state.uid, n, o)); conn.commit(); c.close(); conn.close(); st.rerun()
    
    conn = get_connection(); df_m = pd.read_sql(f"SELECT * FROM metas WHERE usuario_id={st.session_state.uid}", conn); conn.close()
    for _, r in df_m.iterrows():
        st.markdown(f'<div class="user-card"><b>🎯 {r["nombre"]}</b><br>₡{float(r["actual"]):,.0f} / ₡{float(r["objetivo"]):,.0f}</div>', unsafe_allow_html=True)
        st.progress(min(float(r['actual'])/float(r['objetivo']), 1.0))
        ca, cb = st.columns([2,1]); m_a = ca.number_input("Abonar", min_value=0.0, key=f"am_{r['id']}")
        if cb.button("DEPOSITAR", key=f"ab_{r['id']}", use_container_width=True):
            conn = get_connection(); c = conn.cursor(); c.execute("UPDATE metas SET actual=actual+%s WHERE id=%s", (m_a, r['id'])); conn.commit(); c.close(); conn.close()
            reg_mov(m_a, "Gasto", "🎯 Ahorro", f"Meta: {r['nombre']}"); st.rerun()

# --- DEUDAS Y COBROS ---
with t_deudas:
    d_deb, d_cob = st.tabs(["🔴 Lo que debo", "🟢 Lo que me deben"])
    with d_deb:
        with st.expander("Registrar Deuda"):
            with st.form("fd"):
                a = st.text_input("Acreedor"); m = st.number_input("Monto total", min_value=1.0); v = st.date_input("Fecha vencimiento")
                if st.form_submit_button("GUARDAR"):
                    conn = get_connection(); c = conn.cursor(); c.execute("INSERT INTO deudas (usuario_id, nombre, monto_total, tipo_registro, fecha_vence) VALUES (%s,%s,%s,'DEUDA',%s)", (st.session_state.uid, a, m, v)); conn.commit(); c.close(); conn.close(); st.rerun()
        conn = get_connection(); df_d = pd.read_sql(f"SELECT * FROM deudas WHERE usuario_id={st.session_state.uid} AND tipo_registro='DEUDA'", conn); conn.close()
        for _, r in df_d.iterrows():
            pen = float(r['monto_total']) - float(r['pagado'])
            st.markdown(f'<div class="user-card">🔴 <b>{r["nombre"]}</b> | Pendiente: ₡{pen:,.0f} (Vence: {r["fecha_vence"]})</div>', unsafe_allow_html=True)
            if pen > 0:
                c1, c2 = st.columns([2,1]); p_d = c1.number_input("Pagar", min_value=0.0, max_value=pen, key=f"pd_{r['id']}")
                if c2.button("ABONAR", key=f"bd_{r['id']}", use_container_width=True):
                    conn = get_connection(); c = conn.cursor(); c.execute("UPDATE deudas SET pagado=pagado+%s WHERE id=%s", (p_d, r['id'])); conn.commit(); c.close(); conn.close()
                    reg_mov(p_d, "Gasto", "🏦 Deuda", f"A: {r['nombre']}"); st.rerun()
    with d_cob:
        with st.expander("Registrar Cobro"):
            with st.form("fc"):
                p = st.text_input("Deudor"); m = st.number_input("Monto", min_value=1.0); v = st.date_input("Fecha promesa")
                if st.form_submit_button("GUARDAR"):
                    conn = get_connection(); c = conn.cursor(); c.execute("INSERT INTO deudas (usuario_id, nombre, monto_total, tipo_registro, fecha_vence) VALUES (%s,%s,%s,'COBRO',%s)", (st.session_state.uid, p, m, v)); conn.commit(); c.close(); conn.close(); st.rerun()
        conn = get_connection(); df_c = pd.read_sql(f"SELECT * FROM deudas WHERE usuario_id={st.session_state.uid} AND tipo_registro='COBRO'", conn); conn.close()
        for _, r in df_c.iterrows():
            pen = float(r['monto_total']) - float(r['pagado'])
            st.markdown(f'<div class="user-card">🟢 <b>{r["nombre"]}</b> | Falta que paguen: ₡{pen:,.0f}</div>', unsafe_allow_html=True)
            if pen > 0:
                c1, c2 = st.columns([2,1]); p_c = c1.number_input("Recibir", min_value=0.0, max_value=pen, key=f"pc_{r['id']}")
                if c2.button("REGISTRAR PAGO", key=f"bc_{r['id']}", use_container_width=True):
                    conn = get_connection(); c = conn.cursor(); c.execute("UPDATE deudas SET pagado=pagado+%s WHERE id=%s", (p_c, r['id'])); conn.commit(); c.close(); conn.close()
                    reg_mov(p_c, "Ingreso", "💸 Cobro", f"De: {r['nombre']}"); st.rerun()

# --- SINPE ---
with t_sinpe:
    st.subheader("📱 SINPE Móvil")
    with st.form("fs"):
        tel = st.text_input("Número destino"); mon = st.number_input("Monto (₡)")
        if st.form_submit_button("REGISTRAR GASTO"):
            reg_mov(mon, "Gasto", "📱 SINPE", f"A: {tel}"); st.success("Registrado.")
    st.markdown('<br><a href="https://www.google.com" target="_blank" style="background-color: #00f2fe; color: black; padding: 15px; border-radius: 10px; text-decoration: none; font-weight: bold; text-align: center; display: block;">🏦 ABRIR BANCO</a>', unsafe_allow_html=True)

# --- HISTORIAL ---
with t_hist:
    conn = get_connection(); df_h = pd.read_sql(f"SELECT fecha, tipo, cat, monto, descrip FROM movimientos WHERE usuario_id={st.session_state.uid} ORDER BY id DESC LIMIT 100", conn); conn.close()
    st.dataframe(df_h, use_container_width=True, hide_index=True)

# --- AJUSTES ---
with t_ajustes:
    if st.button("🚪 CERRAR SESIÓN TOTAL", type="primary", use_container_width=True):
        st.session_state.autenticado = False; st.query_params.clear(); st.rerun()
