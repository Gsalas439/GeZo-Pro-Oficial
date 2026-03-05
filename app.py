import streamlit as st
import pandas as pd
import psycopg2
from datetime import datetime, timedelta, date
import plotly.express as px

# --- 1. CONFIGURACIÓN Y BLOQUEO TOTAL DE STREAMLIT ---
# Layout 'wide' para aprovechar toda la pantalla
st.set_page_config(page_title="GeZo Elite Pro", page_icon="💎", layout="wide", initial_sidebar_state="collapsed")

# CSS "Fuerza Bruta" para esconder Streamlit y dar estilo Dark Pro
st.markdown("""
    <style>
    /* Ocultar TODO el rastro de Streamlit (Manage app, menús, header) */
    header[data-testid="stHeader"] {display: none !important;}
    div[data-testid="stToolbar"] {display: none !important;}
    #MainMenu {display: none !important;}
    footer {display: none !important;}
    .stDeployButton {display: none !important;}
    
    /* Subir el contenido para que no quede un espacio en blanco arriba */
    .block-container {padding-top: 2rem !important;}
    
    /* Estética General Dark Elite */
    .main { background-color: #0b0e14; color: #e0e0e0; font-family: 'Inter', sans-serif; }
    
    /* Tarjetas de Balance */
    .balance-card {
        background: linear-gradient(135deg, #1e2633 0%, #0b0e14 100%);
        border-radius: 15px; padding: 20px; border: 1px solid #333; text-align: center;
        box-shadow: 0 4px 15px rgba(0,0,0,0.3); margin-bottom: 15px;
    }
    .metric-value { font-size: 2.5em; font-weight: 900; color: #00f2fe; margin: 0; }
    .metric-label { font-size: 0.9em; color: #888; text-transform: uppercase; font-weight: bold; margin: 0; }
    
    /* Tarjetas BAC */
    .bac-card {
        background: linear-gradient(135deg, #cc0000 0%, #8b0000 100%);
        border-radius: 12px; padding: 15px; text-align: center; border: 1px solid #ff4b4b;
    }
    
    /* Caja de IA */
    .ia-box {
        background: rgba(0, 242, 254, 0.05); border: 1px solid #00f2fe;
        padding: 20px; border-radius: 15px; border-left: 8px solid #00f2fe; margin-top: 15px;
    }
    
    /* Tarjetas de Listas (Metas, Deudas) */
    .user-card { 
        background: rgba(255, 255, 255, 0.03); padding: 15px; border-radius: 12px; 
        border-left: 5px solid #00f2fe; margin-bottom: 10px; border-top: 1px solid #222; border-right: 1px solid #222; border-bottom: 1px solid #222;
    }
    </style>
    """, unsafe_allow_html=True)

# --- 2. MOTOR DE BASE DE DATOS (CONEXIÓN SEGURA) ---
# Usamos una función directa para evitar que la conexión se duerma en la nube
def get_connection():
    try:
        return psycopg2.connect(st.secrets["DB_URL"])
    except Exception as e:
        st.error(f"Error crítico DB: {e}")
        st.stop()

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
    conn.commit(); c.close(); conn.close()

inicializar_db()

# Función central de registro para mantener el balance perfecto
def reg_mov(monto, tipo, cat, desc):
    if monto > 0:
        conn = get_connection(); c = conn.cursor()
        c.execute("INSERT INTO movimientos (usuario_id, fecha, descrip, monto, tipo, cat) VALUES (%s,%s,%s,%s,%s,%s)", 
                  (st.session_state.uid, date.today(), desc, monto, tipo, cat))
        conn.commit(); c.close(); conn.close()

# --- 3. SISTEMA DE LOGIN ---
if 'autenticado' not in st.session_state:
    st.session_state.autenticado = False

if not st.session_state.autenticado:
    st.markdown("<h1 style='text-align: center; color: #00f2fe;'>💎 GeZo Elite Pro</h1>", unsafe_allow_html=True)
    c1, c2, c3 = st.columns([1,2,1])
    with c2:
        with st.form("login_form"):
            st.subheader("Acceso al Sistema")
            u = st.text_input("Usuario")
            p = st.text_input("Contraseña", type="password")
            if st.form_submit_button("INICIAR SESIÓN", use_container_width=True):
                conn = get_connection(); c = conn.cursor()
                c.execute("SELECT id, nombre, rol, plan, expira FROM usuarios WHERE nombre=%s AND clave=%s", (u, p))
                res = c.fetchone()
                c.close(); conn.close()
                if res:
                    if date.today() <= res[4]:
                        st.session_state.update({"autenticado":True, "uid":res[0], "uname":res[1], "rol":res[2], "plan":res[3]})
                        st.rerun()
                    else: st.error("Tu membresía ha expirado.")
                else: st.error("Credenciales incorrectas.")
    st.stop()

# --- 4. NAVEGACIÓN PRINCIPAL (PESTAÑAS INQUEBRANTABLES) ---
st.markdown(f"### 👑 Bienvenido, **{st.session_state.uname}**")

# Estas pestañas SIEMPRE serán visibles en la parte superior
tab_dash, tab_reg, tab_metas, tab_deudas, tab_sinpe, tab_hist, tab_ajustes = st.tabs([
    "📊 DASHBOARD & IA", 
    "💸 REGISTRO", 
    "🎯 METAS", 
    "🏦 DEUDAS / COBROS", 
    "📱 SINPE", 
    "📜 HISTORIAL",
    "⚙️ AJUSTES"
])

# --- 5. MÓDULOS DE LA APLICACIÓN ---

# ==========================================
# PESTAÑA 1: DASHBOARD, BAC E INTELIGENCIA ARTIFICIAL
# ==========================================
with tab_dash:
    # Monitor de Divisas BAC
    c_bac1, c_bac2, c_bac3 = st.columns([1,1,2])
    with c_bac1: st.markdown('<div class="bac-card"><p style="margin:0; color:white; font-size:0.8em;">BAC COMPRA</p><h3 style="margin:0; color:white;">₡512.00</h3></div>', unsafe_allow_html=True)
    with c_bac2: st.markdown('<div class="bac-card"><p style="margin:0; color:white; font-size:0.8em;">BAC VENTA</p><h3 style="margin:0; color:white;">₡524.00</h3></div>', unsafe_allow_html=True)
    
    st.divider()
    
    # Filtro de tiempo
    rango = st.radio("Analizar Periodo:", ["Hoy", "Últimos 7 días", "Últimos 30 días"], horizontal=True)
    dias = {"Hoy": 0, "Últimos 7 días": 7, "Últimos 30 días": 30}
    f_inicio = date.today() - timedelta(days=dias[rango])
    
    conn = get_connection()
    df = pd.read_sql(f"SELECT * FROM movimientos WHERE usuario_id={st.session_state.uid} AND fecha >= '{f_inicio}'", conn)
    conn.close()
    
    if not df.empty:
        ing = float(df[df['tipo']=='Ingreso']['monto'].sum())
        gas = float(df[df['tipo']=='Gasto']['monto'].sum())
        neto = ing - gas
        
        # Tarjetas Financieras
        col1, col2, col3 = st.columns(3)
        with col1: st.markdown(f'<div class="balance-card"><p class="metric-label">Ingresos</p><p class="metric-value">₡{ing:,.0f}</p></div>', unsafe_allow_html=True)
        with col2: st.markdown(f'<div class="balance-card"><p class="metric-label">Gastos</p><p class="metric-value" style="color:#ff4b4b;">₡{gas:,.0f}</p></div>', unsafe_allow_html=True)
        with col3: st.markdown(f'<div class="balance-card"><p class="metric-label">Generación Neta</p><p class="metric-value" style="color:#2ecc71;">₡{neto:,.0f}</p></div>', unsafe_allow_html=True)
        
        # GeZo AI Advisor
        st.markdown('<div class="ia-box">', unsafe_allow_html=True)
        st.markdown("#### 🤖 GeZo AI Advisor")
        if neto < 0:
            st.markdown(f"**🔴 ALERTA ROJA:** Has gastado ₡{abs(neto):,.0f} más de lo que ganaste. Con el tipo de cambio actual, **evita asumir deudas en dólares**. Frena los gastos variables inmediatamente.")
        elif neto > 0:
            ahorro = neto * 0.20
            st.markdown(f"**🟢 LIQUIDEZ PERFECTA:** Tu balance es saludable. Para asegurar tu futuro y aplicar la regla de oro, debes mover **₡{ahorro:,.0f}** a tus metas de ahorro hoy mismo.")
        else:
            st.markdown("**⚪ PUNTO DE EQUILIBRIO:** No has ganado ni perdido. Busca generar un ingreso extra.")
        st.markdown('</div>', unsafe_allow_html=True)
        
        # Gráfica de distribución de gastos
        df_gastos = df[df['tipo'] == 'Gasto']
        if not df_gastos.empty:
            st.plotly_chart(px.pie(df_gastos, values='monto', names='cat', title="Distribución de tus Gastos", template="plotly_dark", hole=0.4), use_container_width=True)
    else:
        st.info("No hay movimientos registrados en este periodo.")

# ==========================================
# PESTAÑA 2: REGISTRO INTELIGENTE
# ==========================================
with tab_reg:
    st.subheader("Entrada de Capital / Gasto")
    
    # Categorías Inteligentes separadas
    tipo_mov = st.radio("Tipo de Movimiento:", ["Gasto", "Ingreso"], horizontal=True)
    if tipo_mov == "Ingreso":
        lista_cat = ["💵 Salario", "📈 Ventas", "🧧 Comisiones", "🎁 Regalo", "➕ Otros Ingresos"]
    else:
        lista_cat = ["🛒 Súper/Comida", "⚡ Servicios (Luz/Agua/Net)", "🏠 Alquiler/Hipoteca", "🚗 Transporte/Gasolina", "⚖️ Pensión Alimenticia", "🎉 Ocio/Salidas", "📦 Otros Gastos"]
    
    with st.form("form_registro"):
        monto_mov = st.number_input("Monto (₡)", min_value=0.0)
        cat_mov = st.selectbox("Categoría", lista_cat)
        desc_mov = st.text_input("Descripción o Nota (Opcional)")
        
        if st.form_submit_button("GUARDAR EN BALANCE", use_container_width=True):
            reg_mov(monto_mov, tipo_mov, cat_mov, desc_mov)
            st.success("¡Movimiento registrado exitosamente!")
            st.rerun() # Recarga para actualizar gráficos

# ==========================================
# PESTAÑA 3: METAS DE AHORRO
# ==========================================
with tab_metas:
    st.subheader("Tus Proyectos")
    with st.expander("➕ Crear Nueva Meta"):
        with st.form("form_meta"):
            n_meta = st.text_input("¿Para qué estás ahorrando? (Ej. Viaje, Carro)")
            obj_meta = st.number_input("Monto total a alcanzar (₡)", min_value=1.0)
            if st.form_submit_button("CREAR META"):
                conn = get_connection(); c = conn.cursor()
                c.execute("INSERT INTO metas (usuario_id, nombre, objetivo) VALUES (%s,%s,%s)", (st.session_state.uid, n_meta, obj_meta))
                conn.commit(); c.close(); conn.close(); st.rerun()
    
    conn = get_connection()
    df_m = pd.read_sql(f"SELECT * FROM metas WHERE usuario_id={st.session_state.uid}", conn)
    conn.close()
    
    for _, r in df_m.iterrows():
        st.markdown(f'<div class="user-card"><b>🎯 {r["nombre"]}</b><br>Progreso: ₡{float(r["actual"]):,.0f} de ₡{float(r["objetivo"]):,.0f}</div>', unsafe_allow_html=True)
        st.progress(min(float(r['actual']) / float(r['objetivo']), 1.0))
        
        # Botones de acción
        col_abono, col_btn, col_del = st.columns([2, 1, 1])
        monto_abono = col_abono.number_input("Monto a depositar:", min_value=0.0, key=f"abono_{r['id']}")
        
        if col_btn.button("ABONAR", key=f"btn_{r['id']}", use_container_width=True):
            conn = get_connection(); c = conn.cursor()
            c.execute("UPDATE metas SET actual=actual+%s WHERE id=%s", (monto_abono, r['id']))
            conn.commit(); c.close(); conn.close()
            # Un abono es dinero que sale de tu flujo diario, se registra como Gasto
            reg_mov(monto_abono, "Gasto", "🎯 Ahorro/Metas", f"Abono a {r['nombre']}")
            st.rerun()
            
        if col_del.button("🗑️ Eliminar", key=f"del_{r['id']}", use_container_width=True):
            conn = get_connection(); c = conn.cursor()
            c.execute("DELETE FROM metas WHERE id=%s", (r['id'],))
            conn.commit(); c.close(); conn.close(); st.rerun()

# ==========================================
# PESTAÑA 4: DEUDAS Y COBROS
# ==========================================
with tab_deudas:
    st.subheader("Gestión de Compromisos")
    sub_tab_deudas, sub_tab_cobros = st.tabs(["🔴 Lo que YO DEBO (Deudas)", "🟢 Lo que ME DEBEN (Cobros)"])
    
    # 🔴 DEUDAS
    with sub_tab_deudas:
        with st.expander("➕ Registrar nueva Deuda"):
            with st.form("form_deuda"):
                acreedor = st.text_input("¿A quién le debes?")
                monto_deuda = st.number_input("Monto total de la deuda (₡)", min_value=1.0)
                vence_d = st.date_input("Fecha límite de pago")
                if st.form_submit_button("GUARDAR DEUDA"):
                    conn = get_connection(); c = conn.cursor()
                    c.execute("INSERT INTO deudas (usuario_id, nombre, monto_total, tipo_registro, fecha_vence) VALUES (%s,%s,%s,'DEUDA',%s)", (st.session_state.uid, acreedor, monto_deuda, vence_d))
                    conn.commit(); c.close(); conn.close(); st.rerun()
                    
        conn = get_connection()
        df_d = pd.read_sql(f"SELECT * FROM deudas WHERE usuario_id={st.session_state.uid} AND tipo_registro='DEUDA'", conn)
        conn.close()
        
        for _, r in df_d.iterrows():
            pendiente = float(r['monto_total']) - float(r['pagado'])
            st.markdown(f'<div class="user-card">🔴 <b>{r["nombre"]}</b> | Vence: {r["fecha_vence"]}<br>Total: ₡{float(r["monto_total"]):,.0f} | <b>Pendiente: ₡{pendiente:,.0f}</b></div>', unsafe_allow_html=True)
            if pendiente > 0:
                cd1, cd2 = st.columns([2,1])
                pago_d = cd1.number_input("Monto a pagar:", min_value=0.0, max_value=pendiente, key=f"pago_d_{r['id']}")
                if cd2.button("PROCESAR PAGO", key=f"btn_d_{r['id']}", use_container_width=True):
                    conn = get_connection(); c = conn.cursor()
                    c.execute("UPDATE deudas SET pagado=pagado+%s WHERE id=%s", (pago_d, r['id']))
                    conn.commit(); c.close(); conn.close()
                    # Pagar una deuda es un gasto
                    reg_mov(pago_d, "Gasto", "🏦 Pago de Deuda", f"Abono a {r['nombre']}")
                    st.rerun()

    # 🟢 COBROS
    with sub_tab_cobros:
        with st.expander("➕ Registrar nuevo Cobro"):
            with st.form("form_cobro"):
                deudor = st.text_input("¿Quién te debe?")
                monto_cobro = st.number_input("Monto que te deben (₡)", min_value=1.0)
                vence_c = st.date_input("Fecha promesa de pago")
                if st.form_submit_button("GUARDAR COBRO"):
                    conn = get_connection(); c = conn.cursor()
                    c.execute("INSERT INTO deudas (usuario_id, nombre, monto_total, tipo_registro, fecha_vence) VALUES (%s,%s,%s,'COBRO',%s)", (st.session_state.uid, deudor, monto_cobro, vence_c))
                    conn.commit(); c.close(); conn.close(); st.rerun()
                    
        conn = get_connection()
        df_c = pd.read_sql(f"SELECT * FROM deudas WHERE usuario_id={st.session_state.uid} AND tipo_registro='COBRO'", conn)
        conn.close()
        
        for _, r in df_c.iterrows():
            pendiente_c = float(r['monto_total']) - float(r['pagado'])
            st.markdown(f'<div class="user-card">🟢 <b>{r["nombre"]}</b> | Promesa: {r["fecha_vence"]}<br>Total: ₡{float(r["monto_total"]):,.0f} | <b>Falta que te paguen: ₡{pendiente_c:,.0f}</b></div>', unsafe_allow_html=True)
            if pendiente_c > 0:
                cc1, cc2 = st.columns([2,1])
                recibo_c = cc1.number_input("Monto recibido:", min_value=0.0, max_value=pendiente_c, key=f"recibo_c_{r['id']}")
                if cc2.button("RECIBIR DINERO", key=f"btn_c_{r['id']}", use_container_width=True):
                    conn = get_connection(); c = conn.cursor()
                    c.execute("UPDATE deudas SET pagado=pagado+%s WHERE id=%s", (recibo_c, r['id']))
                    conn.commit(); c.close(); conn.close()
                    # Recibir dinero de un cobro es un Ingreso
                    reg_mov(recibo_c, "Ingreso", "💸 Dinero Cobrado", f"Pago recibido de {r['nombre']}")
                    st.rerun()

# ==========================================
# PESTAÑA 5: SINPE MÓVIL
# ==========================================
with tab_sinpe:
    st.subheader("Registro Rápido SINPE")
    st.write("Registra el gasto aquí y luego abre tu app bancaria para ejecutarlo.")
    
    with st.form("form_sinpe"):
        num_sinpe = st.text_input("Número de Teléfono destino:")
        monto_sinpe = st.number_input("Monto a enviar (₡):", min_value=0.0)
        nota_sinpe = st.text_input("Detalle del SINPE:")
        
        if st.form_submit_button("REGISTRAR SINPE EN BALANCE", use_container_width=True):
            reg_mov(monto_sinpe, "Gasto", "📱 SINPE Rápido", f"A: {num_sinpe} - {nota_sinpe}")
            st.success("SINPE registrado en tus gastos.")
    
    # Botón visual falso que simula redirigir (HTML seguro)
    st.markdown('<br><a href="https://www.google.com" target="_blank" style="background-color: #00f2fe; color: black; padding: 15px; border-radius: 10px; text-decoration: none; font-weight: bold; text-align: center; display: block;">🏦 ABRIR APP BANCARIA AHORA</a>', unsafe_allow_html=True)

# ==========================================
# PESTAÑA 6: HISTORIAL
# ==========================================
with tab_hist:
    st.subheader("Historial de Movimientos")
    conn = get_connection()
    df_h = pd.read_sql(f"SELECT id, fecha, cat, descrip, monto, tipo FROM movimientos WHERE usuario_id={st.session_state.uid} ORDER BY id DESC", conn)
    conn.close()
    
    if not df_h.empty:
        for _, row in df_h.iterrows():
            col_icon, col_det, col_mon, col_del = st.columns([0.5, 4, 2, 1])
            col_icon.write("🟢" if row['tipo'] == "Ingreso" else "🔴")
            col_det.write(f"**{row['cat']}** | {row['descrip']} ({row['fecha']})")
            col_mon.write(f"₡{float(row['monto']):,.0f}")
            if col_del.button("🗑️", key=f"del_h_{row['id']}"):
                conn = get_connection(); c = conn.cursor()
                c.execute("DELETE FROM movimientos WHERE id=%s", (row['id'],))
                conn.commit(); c.close(); conn.close()
                st.rerun()
    else:
        st.info("No tienes movimientos en tu historial.")

# ==========================================
# PESTAÑA 7: AJUSTES Y SEGURIDAD
# ==========================================
with tab_ajustes:
    st.subheader("Seguridad de la Cuenta")
    with st.expander("🔑 Cambiar Contraseña"):
        with st.form("form_clave"):
            nueva_clave = st.text_input("Escribe tu nueva clave:", type="password")
            if st.form_submit_button("ACTUALIZAR CLAVE"):
                conn = get_connection(); c = conn.cursor()
                c.execute("UPDATE usuarios SET clave=%s WHERE id=%s", (nueva_clave, st.session_state.uid))
                conn.commit(); c.close(); conn.close()
                st.success("¡Clave actualizada correctamente!")
    
    st.divider()
    if st.button("🚪 CERRAR SESIÓN", type="primary", use_container_width=True):
        st.session_state.autenticado = False
        st.rerun()
