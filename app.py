import streamlit as st
import pandas as pd
import psycopg2
from datetime import datetime, timedelta, date
import plotly.express as px
import re

# --- 1. CONFIGURACIÓN DE INTERFAZ ELITE ---
st.set_page_config(page_title="GeZo Elite Pro", page_icon="💎", layout="wide", initial_sidebar_state="collapsed")

st.markdown("""
    <style>
    header[data-testid="stHeader"], div[data-testid="stToolbar"], #MainMenu, footer, .stDeployButton {display: none !important;}
    .block-container {padding-top: 1.5rem !important;}
    .main { background-color: #0b0e14; color: #e0e0e0; font-family: 'Inter', sans-serif; }
    .balance-card { background: linear-gradient(135deg, #1e2633 0%, #0b0e14 100%); border-radius: 15px; padding: 20px; border: 1px solid #333; text-align: center; margin-bottom: 15px; box-shadow: 0 4px 10px rgba(0,0,0,0.5); }
    .metric-value { font-size: 2.2em; font-weight: 900; color: #00f2fe; margin: 0; }
    .metric-label { font-size: 0.85em; color: #888; text-transform: uppercase; font-weight: bold; margin: 0; }
    .bac-card { background: linear-gradient(135deg, #cc0000 0%, #8b0000 100%); border-radius: 12px; padding: 12px; text-align: center; border: 1px solid #ff4b4b; color: white; font-weight: bold; }
    .ia-box { background: rgba(0, 242, 254, 0.05); border: 1px solid #00f2fe; padding: 20px; border-radius: 15px; border-left: 8px solid #00f2fe; margin-top: 10px; }
    .alert-box { background: rgba(255, 75, 75, 0.1); border: 1px solid #ff4b4b; padding: 15px; border-radius: 10px; color: #ff4b4b; font-weight: bold; margin-bottom: 15px; }
    .user-card { background: rgba(255, 255, 255, 0.03); padding: 15px; border-radius: 12px; border: 1px solid #222; border-left: 5px solid #00f2fe; margin-bottom: 10px; }
    .btn-banco { background-color: #00f2fe; color: #000 !important; padding: 15px; border-radius: 10px; text-decoration: none; font-weight: 900; text-align: center; display: block; margin-top: 10px; transition: 0.3s; }
    .btn-banco:hover { background-color: #00c3cc; color: black !important; }
    </style>
    """, unsafe_allow_html=True)

# --- 2. BASE DE DATOS Y ACTUALIZACIONES AUTOMÁTICAS ---
def get_connection():
    try: return psycopg2.connect(st.secrets["DB_URL"])
    except: st.error("Reconectando a la base de datos..."); return psycopg2.connect(st.secrets["DB_URL"])

def inicializar_db():
    conn = get_connection(); c = conn.cursor()
    # Tablas base
    c.execute("CREATE TABLE IF NOT EXISTS contactos (id SERIAL PRIMARY KEY, usuario_id INTEGER, nombre TEXT, telefono TEXT)")
    # Parche de actualización "Silenciosa" para soportar Multi-Moneda sin borrar datos
    c.execute("ALTER TABLE movimientos ADD COLUMN IF NOT EXISTS moneda TEXT DEFAULT 'CRC'")
    c.execute("ALTER TABLE deudas ADD COLUMN IF NOT EXISTS moneda TEXT DEFAULT 'CRC'")
    conn.commit(); c.close(); conn.close()

inicializar_db()

# Valores de Divisas del BAC simulados en tiempo real
TIPO_CAMBIO_COMPRA = 512.00
TIPO_CAMBIO_VENTA = 524.00

def reg_mov(monto, tipo, cat, desc, moneda="CRC"):
    if monto > 0:
        conn = get_connection(); c = conn.cursor()
        c.execute("INSERT INTO movimientos (usuario_id, fecha, descrip, monto, tipo, cat, moneda) VALUES (%s,%s,%s,%s,%s,%s,%s)", 
                  (st.session_state.uid, date.today(), desc, monto, tipo, cat, moneda))
        conn.commit(); c.close(); conn.close()

# --- 3. LOGIN & SEGURIDAD (URL CLEANER) ---
if 'autenticado' not in st.session_state: st.session_state.autenticado = False

if not st.session_state.autenticado:
    token_url = st.query_params.get("session_token")
    if token_url:
        conn = get_connection(); c = conn.cursor()
        c.execute("SELECT id, nombre, rol, plan, expira FROM usuarios WHERE id=%s", (token_url,))
        res = c.fetchone(); c.close(); conn.close()
        if res and date.today() <= res[4]:
            st.session_state.update({"autenticado":True, "uid":res[0], "uname":res[1], "rol":res[2], "plan":res[3]})
            st.query_params.clear(); st.rerun()

if not st.session_state.autenticado:
    st.markdown("<h1 style='text-align: center; color: #00f2fe; margin-top: 10vh;'>💎 GeZo Elite Pro</h1>", unsafe_allow_html=True)
    c1, c2, c3 = st.columns([1,1.5,1])
    with c2:
        with st.form("login"):
            u = st.text_input("Usuario"); p = st.text_input("Contraseña", type="password")
            mantener = st.checkbox("Mantener sesión iniciada", value=True)
            if st.form_submit_button("ACCEDER AL SISTEMA", use_container_width=True):
                conn = get_connection(); c = conn.cursor()
                c.execute("SELECT id, nombre, rol, plan, expira FROM usuarios WHERE nombre=%s AND clave=%s", (u, p))
                res = c.fetchone(); c.close(); conn.close()
                if res:
                    st.session_state.update({"autenticado":True, "uid":res[0], "uname":res[1], "rol":res[2], "plan":res[3]})
                    if mantener: st.query_params["session_token"] = str(res[0])
                    st.rerun()
                else: st.error("Credenciales incorrectas.")
    st.stop()

# --- 4. MOTOR INTELIGENTE Y NAVEGACIÓN ---
st.markdown(f"### 👑 **{st.session_state.uname}** | Panel {st.session_state.plan}")

# 🔔 CENTRO DE ALERTAS PROACTIVAS (IA)
conn = get_connection()
df_alertas = pd.read_sql(f"SELECT nombre, fecha_vence, monto_total, pagado, moneda FROM deudas WHERE usuario_id={st.session_state.uid} AND tipo_registro='DEUDA' AND pagado < monto_total", conn)
conn.close()
for _, r in df_alertas.iterrows():
    dias_restantes = (r['fecha_vence'] - date.today()).days
    if 0 <= dias_restantes <= 2:
        st.markdown(f'<div class="alert-box">⚠️ ALERTA DE VENCIMIENTO: Tu deuda con **{r["nombre"]}** vence en {dias_restantes} días. Faltan {r["moneda"]} {float(r["monto_total"] - r["pagado"]):,.0f} por pagar.</div>', unsafe_allow_html=True)
    elif dias_restantes < 0:
        st.markdown(f'<div class="alert-box" style="background: rgba(200,0,0,0.2);">🚨 DEUDA VENCIDA: Tienes un atraso de {abs(dias_restantes)} días con **{r["nombre"]}**.</div>', unsafe_allow_html=True)

t1, t2, t3, t4, t5, t6, t7 = st.tabs(["📊 DASHBOARD", "💸 REGISTRO MÁGICO", "🎯 METAS", "🏦 DEUDAS", "📱 SINPE", "📜 REPORTES", "⚙️ AJUSTES"])

# --- DASHBOARD Y MULTI-MONEDA ---
with t1:
    c_bac1, c_bac2, c_bac3 = st.columns([1,1,2])
    c_bac1.markdown(f'<div class="bac-card"><small>BAC COMPRA (USD)</small><br>₡{TIPO_CAMBIO_COMPRA}</div>', unsafe_allow_html=True)
    c_bac2.markdown(f'<div class="bac-card"><small>BAC VENTA (USD)</small><br>₡{TIPO_CAMBIO_VENTA}</div>', unsafe_allow_html=True)
    
    st.divider()
    rango = st.radio("Filtro de Tiempo:", ["Hoy", "7 días", "30 días", "Histórico"], horizontal=True)
    dias = {"Hoy": 0, "7 días": 7, "30 días": 30, "Histórico": 9999}
    f_inicio = date.today() - timedelta(days=dias[rango])
    
    conn = get_connection()
    df = pd.read_sql(f"SELECT * FROM movimientos WHERE usuario_id={st.session_state.uid} AND fecha >= '{f_inicio}'", conn)
    conn.close()
    
    # Conversión a Colones en tiempo real
    def convertir_a_colones(fila):
        monto = float(fila['monto'])
        if fila['moneda'] == 'USD':
            # Si fue un ingreso en USD, se valora a la compra. Si fue un gasto, se valora a la venta.
            return monto * TIPO_CAMBIO_COMPRA if fila['tipo'] == 'Ingreso' else monto * TIPO_CAMBIO_VENTA
        return monto

    if not df.empty:
        df['monto_crc'] = df.apply(convertir_a_colones, axis=1)
        ing = df[df['tipo']=='Ingreso']['monto_crc'].sum()
        gas = df[df['tipo']=='Gasto']['monto_crc'].sum()
        neto = ing - gas
        
        col1, col2, col3 = st.columns(3)
        col1.markdown(f'<div class="balance-card"><p class="metric-label">Ingresos (Equiv. CRC)</p><p class="metric-value">₡{ing:,.0f}</p></div>', unsafe_allow_html=True)
        col2.markdown(f'<div class="balance-card"><p class="metric-label">Gastos (Equiv. CRC)</p><p class="metric-value" style="color:#ff4b4b;">₡{gas:,.0f}</p></div>', unsafe_allow_html=True)
        col3.markdown(f'<div class="balance-card"><p class="metric-label">Patrimonio Neto</p><p class="metric-value" style="color:#2ecc71;">₡{neto:,.0f}</p></div>', unsafe_allow_html=True)
        
        st.markdown('<div class="ia-box">', unsafe_allow_html=True)
        st.markdown("#### 🤖 GeZo Predictive AI")
        if neto > 0: st.write(f"Con tu flujo actual, tienes una liquidez real de **₡{neto:,.0f}**. Sugerimos mover **₡{neto*0.2:,.0f}** a tus metas de ahorro.")
        else: st.write("Estás en déficit. Frena los gastos variables y evita compras en Dólares debido al tipo de cambio actual.")
        st.markdown('</div>', unsafe_allow_html=True)
    else: st.info("No hay movimientos en este periodo.")

# --- REGISTRO & LECTOR MÁGICO ---
with t2:
    tab_manual, tab_magico = st.tabs(["✍️ Registro Manual", "🪄 Lector de SMS Bancario"])
    
    with tab_manual:
        tipo = st.radio("Tipo de Movimiento", ["Gasto", "Ingreso"], horizontal=True)
        cats = ["Súper/Comida", "Servicios", "Casa/Alquiler", "Transporte", "Ocio", "Salud", "Educación", "Otros"] if tipo == "Gasto" else ["Salario", "Venta", "Intereses", "Regalo", "Otros"]
        with st.form("f_registro"):
            col_m1, col_m2 = st.columns([1,3])
            moneda = col_m1.selectbox("Moneda", ["CRC", "USD"])
            m = col_m2.number_input("Monto", min_value=0.0, step=500.0)
            c = st.selectbox("Categoría", cats)
            d = st.text_input("Descripción / Nota opcional")
            if st.form_submit_button("GUARDAR REGISTRO", use_container_width=True):
                reg_mov(m, tipo, c, d, moneda); st.success("✅ Guardado."); st.rerun()
                
    with tab_magico:
        st.markdown("**Copia y pega el mensaje de texto de tu banco aquí:**")
        texto_sms = st.text_area("Ejemplo: 'BAC Credomatic: Compra aprobada por ₡15,000 en WALMART'")
        
        if st.button("🪄 Analizar y Extraer"):
            if texto_sms:
                # Extraer monto
                monto_match = re.search(r'[\$₡]?\s?(\d{1,3}(?:[.,]\d{3})*(?:[.,]\d{2})?)', texto_sms)
                moneda_detectada = "USD" if "$" in texto_sms or "USD" in texto_sms.upper() else "CRC"
                
                # Categoria IA simple
                cat_detectada = "Otros"
                texto_upper = texto_sms.upper()
                if any(word in texto_upper for word in ["WALMART", "MASXMENOS", "AUTO MERCADO", "PALI"]): cat_detectada = "Súper/Comida"
                elif any(word in texto_upper for word in ["UBER", "DIDDI", "GAS", "DELTA", "PUMA"]): cat_detectada = "Transporte"
                elif any(word in texto_upper for word in ["KFC", "MCDONALDS", "STARBUCKS", "RESTAURANTE"]): cat_detectada = "Ocio"
                
                if monto_match:
                    monto_limpio = float(monto_match.group(1).replace(',', ''))
                    st.success(f"IA Detectó: **{moneda_detectada} {monto_limpio}** (Categoría sugerida: {cat_detectada})")
                    if st.button(f"Confirmar Gasto de {moneda_detectada} {monto_limpio}"):
                        reg_mov(monto_limpio, "Gasto", cat_detectada, texto_sms[:30], moneda_detectada)
                        st.success("Registrado."); st.rerun()
                else:
                    st.error("No se detectó un monto válido en el mensaje.")

# --- METAS DE AHORRO ---
with t3:
    with st.expander("➕ Crear Nuevo Proyecto"):
        with st.form("f_metas"):
            n = st.text_input("Nombre de la meta"); o = st.number_input("Monto a alcanzar (CRC)", min_value=1.0)
            if st.form_submit_button("CREAR META"):
                conn = get_connection(); c = conn.cursor(); c.execute("INSERT INTO metas (usuario_id, nombre, objetivo) VALUES (%s,%s,%s)", (st.session_state.uid, n, o)); conn.commit(); c.close(); conn.close(); st.rerun()
    
    conn = get_connection(); df_m = pd.read_sql(f"SELECT * FROM metas WHERE usuario_id={st.session_state.uid} ORDER BY id DESC", conn); conn.close()
    for _, r in df_m.iterrows():
        st.markdown(f'<div class="user-card"><b>🎯 {r["nombre"]}</b><br>Llevas: ₡{float(r["actual"]):,.0f} de ₡{float(r["objetivo"]):,.0f}</div>', unsafe_allow_html=True)
        st.progress(min(float(r['actual'])/float(r['objetivo']), 1.0))
        ca, cb, cc = st.columns([2,1,1])
        m_a = ca.number_input("Depositar:", min_value=0.0, key=f"ma_{r['id']}")
        if cb.button("ABONAR", key=f"ba_{r['id']}", use_container_width=True):
            conn = get_connection(); c = conn.cursor(); c.execute("UPDATE metas SET actual=actual+%s WHERE id=%s", (m_a, r['id'])); conn.commit(); c.close(); conn.close()
            reg_mov(m_a, "Gasto", "🎯 Ahorro", f"Meta: {r['nombre']}"); st.rerun()
        if cc.button("🗑️", key=f"dm_{r['id']}"):
            conn = get_connection(); c = conn.cursor(); c.execute("DELETE FROM metas WHERE id=%s", (r['id'],)); conn.commit(); c.close(); conn.close(); st.rerun()

# --- DEUDAS Y COBROS (CON MULTIMONEDA) ---
with t4:
    tab_d, tab_c = st.tabs(["🔴 DEUDAS", "🟢 COBROS"])
    def render_cuentas(tipo_rec):
        with st.expander(f"➕ Añadir nuevo registro"):
            with st.form(f"f_{tipo_rec}"):
                nom = st.text_input("Nombre de la Entidad/Persona")
                col_m1, col_m2 = st.columns([1,3])
                md = col_m1.selectbox("Moneda", ["CRC", "USD"], key=f"mon_{tipo_rec}")
                mon = col_m2.number_input("Monto total", min_value=1.0)
                ven = st.date_input("Fecha límite")
                if st.form_submit_button("GUARDAR"):
                    conn = get_connection(); c = conn.cursor(); c.execute("INSERT INTO deudas (usuario_id, nombre, monto_total, tipo_registro, fecha_vence, moneda) VALUES (%s,%s,%s,%s,%s,%s)", (st.session_state.uid, nom, mon, tipo_rec, ven, md)); conn.commit(); c.close(); conn.close(); st.rerun()
        
        conn = get_connection(); df_x = pd.read_sql(f"SELECT * FROM deudas WHERE usuario_id={st.session_state.uid} AND tipo_registro='{tipo_rec}' ORDER BY fecha_vence ASC", conn); conn.close()
        for _, r in df_x.iterrows():
            pend = float(r['monto_total']) - float(r['pagado'])
            st.markdown(f'<div class="user-card"><b>{r["nombre"]}</b> | Pendiente: {r["moneda"]} {pend:,.0f}<br>Fecha límite: {r["fecha_vence"]}</div>', unsafe_allow_html=True)
            if pend > 0:
                c1, c2, c3 = st.columns([2,1,1])
                m_p = c1.number_input("Abono", min_value=0.0, max_value=pend, key=f"px_{r['id']}")
                if c2.button("REGISTRAR PAGO", key=f"bx_{r['id']}", use_container_width=True):
                    conn = get_connection(); c = conn.cursor(); c.execute("UPDATE deudas SET pagado=pagado+%s WHERE id=%s", (m_p, r['id'])); conn.commit(); c.close(); conn.close()
                    reg_mov(m_p, "Gasto" if tipo_rec=='DEUDA' else "Ingreso", f"🏦 {tipo_rec}", f"Abono a {r['nombre']}", r['moneda']); st.rerun()
                if c3.button("🗑️", key=f"del_{r['id']}"):
                    conn = get_connection(); c = conn.cursor(); c.execute("DELETE FROM deudas WHERE id=%s", (r['id'],)); conn.commit(); c.close(); conn.close(); st.rerun()
    with tab_d: render_cuentas('DEUDA')
    with tab_c: render_cuentas('COBRO')

# --- SINPE MÓVIL ---
with t5:
    conn = get_connection(); df_cnt = pd.read_sql(f"SELECT * FROM contactos WHERE usuario_id={st.session_state.uid} ORDER BY nombre", conn); conn.close()
    col_sinpe1, col_sinpe2 = st.columns([1.2, 1])
    
    with col_sinpe1:
        st.markdown("**1. Enviar Dinero**")
        opciones = ["✏️ Escribir número manualmente..."] + [f"{r['nombre']} - {r['telefono']}" for _, r in df_cnt.iterrows()]
        seleccion = st.selectbox("Seleccionar contacto:", opciones)
        with st.form("f_sinpe_pago"):
            es_manual = "✏️" in seleccion
            num_final = st.text_input("Número de Teléfono:", value="" if es_manual else seleccion.split(" - ")[1])
            monto_s = st.number_input("Monto (₡):", min_value=0.0, step=500.0)
            det_s = st.text_input("Detalle:")
            if st.form_submit_button("REGISTRAR Y ABRIR BANCO", use_container_width=True):
                if num_final and monto_s > 0:
                    nombre_destino = "Número Manual" if es_manual else seleccion.split(" - ")[0]
                    reg_mov(monto_s, "Gasto", "📱 SINPE", f"A: {nombre_destino} ({num_final}) - {det_s}", "CRC")
                    st.markdown('<a href="https://www.google.com" target="_blank" class="btn-banco">🏦 ABRIR APLICACIÓN DEL BANCO</a>', unsafe_allow_html=True)
                else: st.error("Ingresa número y monto.")

    with col_sinpe2:
        st.markdown("**2. Agenda**")
        with st.expander("➕ Nuevo contacto"):
            with st.form("f_nuevo_contacto"):
                n_c = st.text_input("Nombre"); t_c = st.text_input("Teléfono")
                if st.form_submit_button("GUARDAR"):
                    if n_c and t_c:
                        conn = get_connection(); c = conn.cursor(); c.execute("INSERT INTO contactos (usuario_id, nombre, telefono) VALUES (%s, %s, %s)", (st.session_state.uid, n_c, t_c)); conn.commit(); c.close(); conn.close(); st.rerun()
        if not df_cnt.empty:
            for _, r in df_cnt.iterrows():
                ca, cb = st.columns([4, 1])
                ca.markdown(f"👤 **{r['nombre']}** ({r['telefono']})", unsafe_allow_html=True)
                if cb.button("🗑️", key=f"del_c_{r['id']}"):
                    conn = get_connection(); c = conn.cursor(); c.execute("DELETE FROM contactos WHERE id=%s", (r['id'],)); conn.commit(); c.close(); conn.close(); st.rerun()

# --- HISTORIAL & EXPORTACIÓN ---
with t6:
    st.subheader("📜 Movimientos y Reportes")
    conn = get_connection()
    df_h = pd.read_sql(f"SELECT fecha, tipo, cat, monto, moneda, descrip FROM movimientos WHERE usuario_id={st.session_state.uid} ORDER BY id DESC", conn)
    conn.close()
    
    if not df_h.empty:
        # Botón de Descarga Excel/CSV
        csv = df_h.to_csv(index=False).encode('utf-8')
        st.download_button(
            label="📥 Descargar Estado de Cuenta (CSV)",
            data=csv,
            file_name=f'GeZo_Reporte_{date.today()}.csv',
            mime='text/csv',
        )
        st.divider()
        df_display = df_h.copy()
        df_display['monto'] = df_display.apply(lambda x: f"{x['moneda']} {float(x['monto']):,.2f}", axis=1)
        df_display = df_display.rename(columns={'fecha':'Fecha', 'tipo':'Tipo', 'cat':'Categoría', 'monto':'Monto', 'moneda':'Moneda', 'descrip':'Detalle'})
        st.dataframe(df_display, use_container_width=True, hide_index=True)
    else:
        st.info("Sin registros para exportar.")

# --- AJUSTES ---
with t7:
    st.subheader("⚙️ Configuración")
    with st.form("f_pass"):
        new_p = st.text_input("Cambiar contraseña", type="password")
        if st.form_submit_button("ACTUALIZAR CREDENCIALES"):
            if new_p:
                conn = get_connection(); c = conn.cursor(); c.execute("UPDATE usuarios SET clave=%s WHERE id=%s", (new_p, st.session_state.uid)); conn.commit(); c.close(); conn.close(); st.success("Actualizada.")
    st.divider()
    if st.button("🚪 CERRAR SESIÓN TOTAL", type="primary", use_container_width=True):
        st.session_state.autenticado = False; st.query_params.clear(); st.rerun()
