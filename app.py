import streamlit as st
import pandas as pd
import psycopg2
from datetime import datetime, timedelta, date
import plotly.express as px

# --- 1. CONFIGURACIÓN DE INTERFAZ ELITE ---
st.set_page_config(page_title="GeZo Elite Pro", page_icon="💎", layout="wide", initial_sidebar_state="collapsed")

st.markdown("""
    <style>
    header[data-testid="stHeader"], div[data-testid="stToolbar"], #MainMenu, footer, .stDeployButton {display: none !important;}
    .block-container {padding-top: 1rem !important;}
    .main { background-color: #0b0e14; color: #e0e0e0; font-family: 'Inter', sans-serif; }
    
    /* Estilos de Tarjetas Dinámicas */
    .balance-card {
        background: linear-gradient(135deg, #1e2633 0%, #0b0e14 100%);
        border-radius: 15px; padding: 20px; border: 1px solid #333; text-align: center; margin-bottom: 15px;
    }
    .metric-value { font-size: 2.2em; font-weight: 900; color: #00f2fe; margin: 0; }
    .metric-label { font-size: 0.85em; color: #888; text-transform: uppercase; font-weight: bold; margin: 0; }
    
    .ia-box { 
        background: rgba(0, 242, 254, 0.05); border: 1px solid #00f2fe; 
        padding: 20px; border-radius: 15px; border-left: 8px solid #00f2fe; margin-top: 10px; 
    }
    
    .user-card { 
        background: rgba(255, 255, 255, 0.03); padding: 15px; border-radius: 12px; 
        border: 1px solid #222; border-left: 5px solid #00f2fe; margin-bottom: 10px;
    }
    .status-vence { color: #ff4b4b; font-size: 0.8em; font-weight: bold; }
    </style>
    """, unsafe_allow_html=True)

# --- 2. MOTOR DE BASE DE DATOS (CON RE-INTENTOS) ---
def get_connection():
    try:
        return psycopg2.connect(st.secrets["DB_URL"])
    except:
        st.error("Error de conexión. Reintentando...")
        return psycopg2.connect(st.secrets["DB_URL"])

def reg_mov(monto, tipo, cat, desc):
    if monto > 0:
        conn = get_connection(); c = conn.cursor()
        c.execute("INSERT INTO movimientos (usuario_id, fecha, descrip, monto, tipo, cat) VALUES (%s,%s,%s,%s,%s,%s)", 
                  (st.session_state.uid, date.today(), desc, monto, tipo, cat))
        conn.commit(); c.close(); conn.close()

# --- 3. LOGIN & SEGURIDAD DE SESIÓN ---
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
            st.query_params.clear(); st.rerun()

if not st.session_state.autenticado:
    st.markdown("<h1 style='text-align: center; color: #00f2fe;'>💎 GeZo Elite Pro</h1>", unsafe_allow_html=True)
    c1, c2, c3 = st.columns([1,1.5,1])
    with c2:
        with st.form("login"):
            u = st.text_input("Usuario"); p = st.text_input("Clave", type="password")
            if st.form_submit_button("ENTRAR", use_container_width=True):
                conn = get_connection(); c = conn.cursor()
                c.execute("SELECT id, nombre, rol, plan, expira FROM usuarios WHERE nombre=%s AND clave=%s", (u, p))
                res = c.fetchone(); c.close(); conn.close()
                if res:
                    st.session_state.update({"autenticado":True, "uid":res[0], "uname":res[1], "rol":res[2], "plan":res[3]})
                    st.query_params["session_token"] = str(res[0]); st.rerun()
                else: st.error("Acceso denegado.")
    st.stop()

# --- 4. DASHBOARD E INTELIGENCIA ---
st.markdown(f"### 👑 **{st.session_state.uname}**")
t1, t2, t3, t4, t5, t6, t7 = st.tabs(["📊 DASHBOARD", "💸 REGISTRO", "🎯 METAS", "🏦 CUENTAS", "📱 SINPE", "📜 HISTORIAL", "⚙️ SEGURIDAD"])

with t1:
    conn = get_connection()
    df = pd.read_sql(f"SELECT * FROM movimientos WHERE usuario_id={st.session_state.uid} AND fecha >= '{date.today() - timedelta(days=30)}'", conn)
    df_d = pd.read_sql(f"SELECT * FROM deudas WHERE usuario_id={st.session_state.uid} AND pagado < monto_total", conn)
    conn.close()

    ing = float(df[df['tipo']=='Ingreso']['monto'].sum()) if not df.empty else 0
    gas = float(df[df['tipo']=='Gasto']['monto'].sum()) if not df.empty else 0
    neto = ing - gas

    c1, c2, c3 = st.columns(3)
    c1.markdown(f'<div class="balance-card"><p class="metric-label">Ingresos Mes</p><p class="metric-value">₡{ing:,.0f}</p></div>', unsafe_allow_html=True)
    c2.markdown(f'<div class="balance-card"><p class="metric-label">Gastos Mes</p><p class="metric-value" style="color:#ff4b4b;">₡{gas:,.0f}</p></div>', unsafe_allow_html=True)
    c3.markdown(f'<div class="balance-card"><p class="metric-label">Generación Neta</p><p class="metric-value" style="color:#2ecc71;">₡{neto:,.0f}</p></div>', unsafe_allow_html=True)

    st.markdown('<div class="ia-box">', unsafe_allow_html=True)
    st.markdown("#### 🤖 GeZo Advisor")
    if not df_d.empty:
        st.warning(f"⚠️ Tienes {len(df_d)} deudas pendientes. Prioriza el pago antes de nuevos gastos.")
    st.write(f"Tu liquidez te permite ahorrar **₡{max(0, neto*0.2):,.0f}** este periodo.")
    st.markdown('</div>', unsafe_allow_html=True)
    
    if not df[df['tipo']=='Gasto'].empty:
        st.plotly_chart(px.pie(df[df['tipo']=='Gasto'], values='monto', names='cat', title="Análisis de Gastos", template="plotly_dark", hole=0.5), use_container_width=True)

# --- 5. REGISTRO Y OPERACIONES ---
with t2:
    tipo = st.radio("Acción", ["Gasto", "Ingreso"], horizontal=True)
    cats = ["Súper/Comida", "Servicios", "Casa/Alquiler", "Transporte", "Ocio", "Salud", "Otros"] if tipo == "Gasto" else ["Salario", "Venta", "Biz", "Regalo"]
    with st.form("f_reg"):
        m = st.number_input("Monto", min_value=0.0, step=100.0)
        c = st.selectbox("Categoría", cats)
        d = st.text_input("Nota")
        if st.form_submit_button("CONFIRMAR"):
            reg_mov(m, tipo, c, d); st.success("Registrado"); st.rerun()

with t3:
    with st.expander("🎯 Nueva Meta"):
        with st.form("f_meta"):
            n = st.text_input("Meta"); o = st.number_input("Objetivo", min_value=1.0)
            if st.form_submit_button("CREAR"):
                conn = get_connection(); c = conn.cursor(); c.execute("INSERT INTO metas (usuario_id, nombre, objetivo) VALUES (%s,%s,%s)", (st.session_state.uid, n, o)); conn.commit(); c.close(); conn.close(); st.rerun()
    
    conn = get_connection(); df_m = pd.read_sql(f"SELECT * FROM metas WHERE usuario_id={st.session_state.uid}", conn); conn.close()
    for _, r in df_m.iterrows():
        st.markdown(f'<div class="user-card"><b>{r["nombre"]}</b><br>₡{float(r["actual"]):,.0f} de ₡{float(r["objetivo"]):,.0f}</div>', unsafe_allow_html=True)
        st.progress(min(float(r['actual'])/float(r['objetivo']), 1.0))
        ca, cb, cc = st.columns([2,1,1])
        m_a = ca.number_input("Abonar", min_value=0.0, key=f"am_{r['id']}")
        if cb.button("DEPÓSITO", key=f"ab_{r['id']}", use_container_width=True):
            conn = get_connection(); c = conn.cursor(); c.execute("UPDATE metas SET actual=actual+%s WHERE id=%s", (m_a, r['id'])); conn.commit(); c.close(); conn.close()
            reg_mov(m_a, "Gasto", "🎯 Ahorro", f"Meta: {r['nombre']}"); st.rerun()
        if cc.button("🗑️", key=f"delm_{r['id']}"):
            conn = get_connection(); c = conn.cursor(); c.execute("DELETE FROM metas WHERE id=%s", (r['id'],)); conn.commit(); c.close(); conn.close(); st.rerun()

with t4:
    d_deb, d_cob = st.tabs(["🔴 DEUDAS", "🟢 COBROS"])
    def render_deudas(tipo_r):
        with st.expander(f"➕ Nuevo {tipo_r}"):
            with st.form(f"f_{tipo_r}"):
                per = st.text_input("Persona/Entidad"); mon = st.number_input("Monto", min_value=1.0); ven = st.date_input("Vencimiento")
                if st.form_submit_button("GUARDAR"):
                    conn = get_connection(); c = conn.cursor(); c.execute("INSERT INTO deudas (usuario_id, nombre, monto_total, tipo_registro, fecha_vence) VALUES (%s,%s,%s,%s,%s)", (st.session_state.uid, per, mon, tipo_r, ven)); conn.commit(); c.close(); conn.close(); st.rerun()
        
        conn = get_connection(); df_x = pd.read_sql(f"SELECT * FROM deudas WHERE usuario_id={st.session_state.uid} AND tipo_registro='{tipo_r}'", conn); conn.close()
        for _, r in df_x.iterrows():
            pen = float(r['monto_total']) - float(r['pagado'])
            vence_style = "status-vence" if r['fecha_vence'] <= date.today() and pen > 0 else ""
            st.markdown(f'<div class="user-card"><b>{r["nombre"]}</b> | Resta: ₡{pen:,.0f}<br><span class="{vence_style}">Vence: {r["fecha_vence"]}</span></div>', unsafe_allow_html=True)
            if pen > 0:
                c1, c2, c3 = st.columns([2,1,1])
                m_p = c1.number_input("Monto", min_value=0.0, max_value=pen, key=f"px_{r['id']}")
                if c2.button("ABONAR", key=f"bx_{r['id']}", use_container_width=True):
                    conn = get_connection(); c = conn.cursor(); c.execute("UPDATE deudas SET pagado=pagado+%s WHERE id=%s", (m_p, r['id'])); conn.commit(); c.close(); conn.close()
                    reg_mov(m_p, "Gasto" if tipo_r=='DEUDA' else "Ingreso", f"🏦 {tipo_r}", f"{r['nombre']}"); st.rerun()
                if c3.button("🗑️", key=f"delx_{r['id']}"):
                    conn = get_connection(); c = conn.cursor(); c.execute("DELETE FROM deudas WHERE id=%s", (r['id'],)); conn.commit(); c.close(); conn.close(); st.rerun()
    with d_deb: render_deudas('DEUDA')
    with d_cob: render_deudas('COBRO')

with t5:
    st.subheader("📱 SINPE Rápido")
    with st.form("f_sinpe"):
        t_s = st.text_input("Número Destino"); m_s = st.number_input("Monto", min_value=0.0)
        if st.form_submit_button("REGISTRAR Y ABRIR BANCO"):
            reg_mov(m_s, "Gasto", "📱 SINPE", f"A: {t_s}"); st.success("Gasto guardado.")
            st.markdown(f'<a href="https://www.google.com" target="_blank" style="text-decoration:none; color:#00f2fe;">🚀 CLIC AQUÍ PARA IR AL BANCO</a>', unsafe_allow_html=True)

with t6:
    st.subheader("Historial de Movimientos")
    conn = get_connection(); df_h = pd.read_sql(f"SELECT fecha, tipo, cat, monto, descrip FROM movimientos WHERE usuario_id={st.session_state.uid} ORDER BY id DESC LIMIT 100", conn); conn.close()
    st.dataframe(df_h, use_container_width=True, hide_index=True)

with t7:
    if st.button("🚪 CERRAR SESIÓN TOTAL", type="primary", use_container_width=True):
        st.session_state.autenticado = False; st.query_params.clear(); st.rerun()
