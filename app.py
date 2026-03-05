import streamlit as st
import pandas as pd
import psycopg2
from datetime import datetime, timedelta, date
import plotly.express as px
import re
import base64

# ==========================================
# 1. CONFIGURACIÓN ELITE Y UI NATIVA
# ==========================================
st.set_page_config(page_title="GeZo Elite Pro", page_icon="💎", layout="wide", initial_sidebar_state="collapsed")

st.markdown("""
    <style>
    /* Bloqueo total de Streamlit UI */
    header[data-testid="stHeader"], div[data-testid="stToolbar"], #MainMenu, footer, .stDeployButton {display: none !important;}
    .block-container {padding-top: 1.5rem !important;}
    .main { background-color: #0b0e14; color: #e0e0e0; font-family: 'Inter', sans-serif; }
    
    /* Componentes Visuales Elite */
    .balance-card { background: linear-gradient(135deg, #1e2633 0%, #0b0e14 100%); border-radius: 12px; padding: 20px; border: 1px solid #333; text-align: center; margin-bottom: 10px; box-shadow: 0 4px 10px rgba(0,0,0,0.5); }
    .metric-value { font-size: 2em; font-weight: 900; color: #00f2fe; margin: 0; }
    .metric-label { font-size: 0.8em; color: #888; text-transform: uppercase; font-weight: bold; margin: 0; }
    .bac-card { background: linear-gradient(135deg, #cc0000 0%, #8b0000 100%); border-radius: 10px; padding: 10px; text-align: center; border: 1px solid #ff4b4b; color: white; font-weight: bold; }
    .ia-box { background: rgba(0, 242, 254, 0.05); border: 1px solid #00f2fe; padding: 20px; border-radius: 12px; border-left: 5px solid #00f2fe; margin-top: 10px; margin-bottom: 15px; }
    .user-card { background: rgba(255, 255, 255, 0.03); padding: 15px; border-radius: 10px; border: 1px solid #222; border-left: 4px solid #00f2fe; margin-bottom: 10px; }
    .alert-box { background: rgba(255, 75, 75, 0.1); border: 1px solid #ff4b4b; padding: 15px; border-radius: 10px; color: #ff4b4b; font-weight: bold; margin-bottom: 15px; }
    .btn-banco { background-color: #00f2fe; color: #000 !important; padding: 15px; border-radius: 8px; text-decoration: none; font-weight: 900; text-align: center; display: block; margin-top: 10px; transition: 0.3s; }
    .btn-banco:hover { background-color: #00c3cc; color: black !important; }
    </style>
""", unsafe_allow_html=True)

# ==========================================
# 2. MOTOR DE BASE DE DATOS Y ARQUITECTURA
# ==========================================
def get_connection():
    try:
        return psycopg2.connect(st.secrets["DB_URL"])
    except Exception:
        st.error("Conectando con Servidor Seguro...")
        return psycopg2.connect(st.secrets["DB_URL"])

def inicializar_db():
    conn = get_connection(); c = conn.cursor()
    # Creación de Tablas Core y ERP
    tablas = [
        "usuarios (id SERIAL PRIMARY KEY, nombre TEXT UNIQUE, clave TEXT, expira DATE, rol TEXT, plan TEXT)",
        "movimientos (id SERIAL PRIMARY KEY, usuario_id INTEGER, fecha DATE, descrip TEXT, monto DECIMAL, tipo TEXT, cat TEXT)",
        "metas (id SERIAL PRIMARY KEY, usuario_id INTEGER, nombre TEXT, objetivo DECIMAL, actual DECIMAL DEFAULT 0)",
        "deudas (id SERIAL PRIMARY KEY, usuario_id INTEGER, nombre TEXT, monto_total DECIMAL, pagado DECIMAL DEFAULT 0, tipo_registro TEXT, fecha_vence DATE)",
        "contactos (id SERIAL PRIMARY KEY, usuario_id INTEGER, nombre TEXT, telefono TEXT)",
        "presupuestos (id SERIAL PRIMARY KEY, usuario_id INTEGER, cat TEXT, limite DECIMAL)",
        "suscripciones (id SERIAL PRIMARY KEY, usuario_id INTEGER, nombre TEXT, monto DECIMAL, dia_cobro INTEGER, cat TEXT, moneda TEXT)",
        "historial_suscripciones (id SERIAL PRIMARY KEY, suscripcion_id INTEGER, mes_anio TEXT)",
        "billeteras (id SERIAL PRIMARY KEY, usuario_id INTEGER, nombre TEXT, tipo TEXT, moneda TEXT)",
        "proyectos (id SERIAL PRIMARY KEY, usuario_id INTEGER, nombre TEXT)"
    ]
    for t in tablas:
        c.execute(f"CREATE TABLE IF NOT EXISTS {t}")
    
    # Inyección de Columnas (Actualizaciones seguras)
    cols_mov = ["moneda TEXT DEFAULT 'CRC'", "comprobante TEXT DEFAULT NULL", "billetera_id INTEGER DEFAULT 0", "proyecto_id INTEGER DEFAULT 0", "impuesto_reserva DECIMAL DEFAULT 0"]
    for col in cols_mov:
        c.execute(f"ALTER TABLE movimientos ADD COLUMN IF NOT EXISTS {col}")
    
    cols_deu = ["moneda TEXT DEFAULT 'CRC'", "tasa_interes DECIMAL DEFAULT 0", "plazo_meses INTEGER DEFAULT 1"]
    for col in cols_deu:
        c.execute(f"ALTER TABLE deudas ADD COLUMN IF NOT EXISTS {col}")
    
    # Administrador Maestro
    c.execute("SELECT * FROM usuarios WHERE nombre='admin'")
    if not c.fetchone():
        c.execute("INSERT INTO usuarios (nombre, clave, expira, rol, plan) VALUES ('admin', 'admin123', '2099-12-31', 'admin', 'Dueño SaaS')")
    
    conn.commit(); c.close(); conn.close()

inicializar_db()

# Variables Globales de Negocio
TIPO_CAMBIO_COMPRA = 512.00
TIPO_CAMBIO_VENTA = 524.00
PLANES = ["🎁 Prueba Gratis (1 Mes) - ₡0", "🥉 Mensual - ₡2,500", "🥈 Trimestral - ₡6,500", "🥇 Semestral - ₡12,000", "💎 Anual - ₡20,000", "👑 Vitalicio - ₡50,000"]
DIAS_PLAN = {PLANES[0]: 30, PLANES[1]: 30, PLANES[2]: 90, PLANES[3]: 180, PLANES[4]: 365, PLANES[5]: 27000}

# Funciones Financieras
def calcular_cuota_nivelada(monto, tasa_anual, meses):
    if tasa_anual == 0 or meses == 0: return monto / max(1, meses)
    tasa_mensual = (tasa_anual / 100) / 12
    return monto * (tasa_mensual * (1 + tasa_mensual)**meses) / ((1 + tasa_mensual)**meses - 1)

def reg_mov(monto, tipo, cat, desc, moneda="CRC", comprobante=None, b_id=0, p_id=0, imp=0):
    if monto > 0:
        conn = get_connection(); c = conn.cursor()
        c.execute("""INSERT INTO movimientos 
                     (usuario_id, fecha, descrip, monto, tipo, cat, moneda, comprobante, billetera_id, proyecto_id, impuesto_reserva) 
                     VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)""", 
                  (st.session_state.uid, date.today(), desc, monto, tipo, cat, moneda, comprobante, b_id, p_id, imp))
        conn.commit(); c.close(); conn.close()

def procesar_suscripciones():
    hoy = date.today()
    mes_actual = hoy.strftime("%Y-%m")
    conn = get_connection(); c = conn.cursor()
    c.execute("SELECT id, nombre, monto, dia_cobro, cat, moneda FROM suscripciones WHERE usuario_id=%s", (st.session_state.uid,))
    for sub_id, nombre, monto, dia_cobro, cat, moneda in c.fetchall():
        # Lógica para meses cortos (ej. Febrero 28)
        ultimo_dia_mes = ((hoy.replace(day=28) + timedelta(days=4)).replace(day=1) - timedelta(days=1)).day
        dia_efectivo = min(dia_cobro, ultimo_dia_mes)
        
        if hoy.day >= dia_efectivo:
            c.execute("SELECT id FROM historial_suscripciones WHERE suscripcion_id=%s AND mes_anio=%s", (sub_id, mes_actual))
            if not c.fetchone():
                c.execute("INSERT INTO movimientos (usuario_id, fecha, descrip, monto, tipo, cat, moneda) VALUES (%s,%s,%s,%s,%s,%s,%s)", 
                          (st.session_state.uid, hoy, f"Auto-Cobro: {nombre}", monto, "Gasto", cat, moneda))
                c.execute("INSERT INTO historial_suscripciones (suscripcion_id, mes_anio) VALUES (%s,%s)", (sub_id, mes_actual))
    conn.commit(); c.close(); conn.close()

# ==========================================
# 3. SEGURIDAD Y LOGIN (SHADOW STATE)
# ==========================================
if 'autenticado' not in st.session_state:
    st.session_state.autenticado = False

if not st.session_state.autenticado:
    if "session_token" in st.query_params:
        conn = get_connection(); c = conn.cursor()
        c.execute("SELECT id, nombre, rol, plan, expira FROM usuarios WHERE id=%s", (st.query_params["session_token"],))
        res = c.fetchone(); c.close(); conn.close()
        if res and date.today() <= res[4]:
            st.session_state.update({"autenticado":True, "uid":res[0], "uname":res[1], "rol":res[2], "plan":res[3]})
            st.query_params.clear(); st.rerun()

if not st.session_state.autenticado:
    st.markdown("<h1 style='text-align: center; color: #00f2fe; margin-top: 10vh;'>💎 GeZo Elite Pro</h1>", unsafe_allow_html=True)
    c1, c2, c3 = st.columns([1,1.5,1])
    with c2:
        with st.form("login_form"):
            st.markdown("### Acceso al Sistema")
            u = st.text_input("Usuario")
            p = st.text_input("Contraseña", type="password")
            mantener = st.checkbox("Mantener sesión iniciada", value=True)
            if st.form_submit_button("INICIAR SESIÓN", use_container_width=True):
                conn = get_connection(); c = conn.cursor()
                c.execute("SELECT id, nombre, rol, plan, expira FROM usuarios WHERE nombre=%s AND clave=%s", (u, p))
                res = c.fetchone(); c.close(); conn.close()
                if res:
                    if date.today() <= res[4]:
                        st.session_state.update({"autenticado":True, "uid":res[0], "uname":res[1], "rol":res[2], "plan":res[3]})
                        if mantener: st.query_params["session_token"] = str(res[0])
                        st.rerun()
                    else:
                        st.error("Membresía expirada. Contacta al administrador para renovar tu plan.")
                else:
                    st.error("Credenciales incorrectas.")
    st.stop()

# Procesar cobros automáticos transparentemente
procesar_suscripciones()

# ==========================================
# 4. NAVEGACIÓN Y PANEL ADMIN SAAS
# ==========================================
st.markdown(f"### 👑 **{st.session_state.uname}** | {st.session_state.plan}")

lista_tabs = ["📊 DASHBOARD", "💸 REGISTRO", "💼 BILLETERAS & PROYECTOS", "🚧 FIJOS & PRESUPUESTOS", "🎯 METAS", "🏦 DEUDAS", "📱 SINPE", "📜 HISTORIAL"]

# Inyectar pestaña de Admin si el rol es correcto
if st.session_state.rol == "admin":
    lista_tabs.insert(0, "🏢 PANEL ADMIN SAAS")
    tabs = st.tabs(lista_tabs)
    t_admin = tabs[0]
    t1, t2, t3, t4, t5, t6, t7, t8 = tabs[1:]
    
    # ---------------- MÓDULO ADMIN ----------------
    with t_admin:
        st.markdown("### 💼 Gestión Comercial y Facturación")
        with st.expander("➕ Vender Licencia a Nuevo Cliente"):
            with st.form("f_nuevo_usuario"):
                cu1, cu2 = st.columns(2)
                n_user = cu1.text_input("Nombre de Usuario (Login)")
                n_pass = cu2.text_input("Contraseña Temporal")
                plan_sel = st.selectbox("Seleccionar Plan Comercial:", PLANES)
                
                if st.form_submit_button("CREAR CLIENTE Y ACTIVAR", use_container_width=True):
                    if n_user and n_pass:
                        f_vence = date.today() + timedelta(days=DIAS_PLAN[plan_sel])
                        try:
                            conn = get_connection(); c = conn.cursor()
                            c.execute("INSERT INTO usuarios (nombre, clave, expira, rol, plan) VALUES (%s, %s, %s, 'user', %s)", 
                                      (n_user, n_pass, f_vence, plan_sel.split(" - ")[0]))
                            conn.commit(); c.close(); conn.close()
                            st.success(f"Cliente '{n_user}' creado exitosamente. Su acceso expira el {f_vence}.")
                            st.rerun()
                        except:
                            st.error("El nombre de usuario ya existe en la base de datos.")
                    else:
                        st.error("Por favor, completa usuario y contraseña.")
        
        st.markdown("### 👥 Cartera de Clientes Activos e Inactivos")
        conn = get_connection()
        df_cli = pd.read_sql("SELECT id, nombre, plan, expira FROM usuarios WHERE rol != 'admin' ORDER BY expira ASC", conn)
        conn.close()
        
        if not df_cli.empty:
            for _, ru in df_cli.iterrows():
                activo = ru['expira'] >= date.today()
                borde = "#2ecc71" if activo else "#ff4b4b"
                estado = "🟢 Activo" if activo else "🔴 Bloqueado (Falta de Pago)"
                
                st.markdown(f'<div class="user-card" style="border-left: 5px solid {borde};"><b>{ru["nombre"]}</b> | Plan actual: {ru["plan"]} | Fecha de corte: {ru["expira"]} | {estado}</div>', unsafe_allow_html=True)
                
                cr1, cr2, cr3 = st.columns([2, 1, 1])
                ren_plan = cr1.selectbox("Opciones de Renovación:", PLANES, key=f"rp_{ru['id']}")
                if cr2.button("RENOVAR ACCESO", key=f"rbtn_{ru['id']}", use_container_width=True):
                    nueva_f = date.today() + timedelta(days=DIAS_PLAN[ren_plan])
                    conn = get_connection(); c = conn.cursor()
                    c.execute("UPDATE usuarios SET expira=%s, plan=%s WHERE id=%s", (nueva_f, ren_plan.split(" - ")[0], ru['id']))
                    conn.commit(); c.close(); conn.close()
                    st.success("Licencia renovada con éxito."); st.rerun()
                    
                if cr3.button("🗑️ Eliminar", key=f"dbtn_{ru['id']}", use_container_width=True):
                    conn = get_connection(); c = conn.cursor()
                    c.execute("DELETE FROM usuarios WHERE id=%s", (ru['id'],))
                    conn.commit(); c.close(); conn.close(); st.rerun()
        else:
            st.info("Aún no tienes clientes registrados en tu plataforma.")
else:
    tabs = st.tabs(lista_tabs)
    t1, t2, t3, t4, t5, t6, t7, t8 = tabs

# ==========================================
# 5. MÓDULOS DEL ERP FINANCIERO (USUARIOS)
# ==========================================

# --- ALERTAS GLOBALES DE VENCIMIENTO ---
conn = get_connection()
df_alertas = pd.read_sql("SELECT nombre, fecha_vence, monto_total, pagado, moneda FROM deudas WHERE usuario_id=%s AND tipo_registro='DEUDA' AND pagado < monto_total", conn, params=(st.session_state.uid,))
conn.close()
if not df_alertas.empty:
    for _, r in df_alertas.iterrows():
        dias = (r['fecha_vence'] - date.today()).days
        if 0 <= dias <= 2:
            st.markdown(f'<div class="alert-box">⚠️ ALERTA DE PAGO: Tu obligación con **{r["nombre"]}** vence en {dias} días.</div>', unsafe_allow_html=True)

# --- T1: DASHBOARD ---
with t1:
    cb1, cb2, cb3 = st.columns([1,1,2])
    cb1.markdown(f'<div class="bac-card"><small>BAC COMPRA (USD)</small><br>₡{TIPO_CAMBIO_COMPRA}</div>', unsafe_allow_html=True)
    cb2.markdown(f'<div class="bac-card"><small>BAC VENTA (USD)</small><br>₡{TIPO_CAMBIO_VENTA}</div>', unsafe_allow_html=True)
    
    st.divider()
    rango = st.radio("Filtro de Tiempo:", ["Mes Actual", "Histórico"], horizontal=True)
    f_inicio = date.today().replace(day=1) if rango == "Mes Actual" else date.today() - timedelta(days=9999)
    
    conn = get_connection()
    df = pd.read_sql("SELECT * FROM movimientos WHERE usuario_id=%s AND fecha >= %s", conn, params=(st.session_state.uid, f_inicio))
    df_proy = pd.read_sql("SELECT * FROM proyectos WHERE usuario_id=%s", conn, params=(st.session_state.uid,))
    df_pres = pd.read_sql("SELECT * FROM presupuestos WHERE usuario_id=%s", conn, params=(st.session_state.uid,))
    conn.close()
    
    if not df.empty:
        # Conversión Multimoneda Segura
        df['monto_crc'] = df.apply(lambda f: float(f['monto']) * TIPO_CAMBIO_COMPRA if f['moneda']=='USD' and f['tipo']=='Ingreso' else (float(f['monto']) * TIPO_CAMBIO_VENTA if f['moneda']=='USD' else float(f['monto'])), axis=1)
        df['impuesto_reserva'] = df['impuesto_reserva'].fillna(0)
        
        imp_total = df['impuesto_reserva'].sum()
        ing_total = df[df['tipo']=='Ingreso']['monto_crc'].sum()
        gas_total = df[df['tipo']=='Gasto']['monto_crc'].sum()
        neto_libre = (ing_total - gas_total) - imp_total
        
        col1, col2, col3 = st.columns(3)
        col1.markdown(f'<div class="balance-card"><p class="metric-label">Ingresos Brutos</p><p class="metric-value">₡{ing_total:,.0f}</p></div>', unsafe_allow_html=True)
        col2.markdown(f'<div class="balance-card"><p class="metric-label">Gastos Operativos</p><p class="metric-value" style="color:#ff4b4b;">₡{gas_total:,.0f}</p></div>', unsafe_allow_html=True)
        col3.markdown(f'<div class="balance-card"><p class="metric-label">Capital Real Libre</p><p class="metric-value" style="color:#2ecc71;">₡{neto_libre:,.0f}</p></div>', unsafe_allow_html=True)
        
        st.markdown(f'<div class="ia-box">🤖 <b>GeZo CFO AI:</b> Tienes <b>₡{imp_total:,.0f}</b> congelados en reservas de impuestos. Este dinero no se contempla en tu capital libre. Sugerimos ahorrar ₡{max(0, neto_libre*0.2):,.0f} a tus metas.</div>', unsafe_allow_html=True)
        
        # 1. Semáforo de Presupuestos
        if not df_pres.empty and rango == "Mes Actual":
            st.markdown("### 🚧 Control de Presupuestos (Mes Actual)")
            g_mes = df[df['tipo']=='Gasto'].groupby('cat')['monto_crc'].sum().reset_index()
            for _, rp in df_pres.iterrows():
                serie = g_mes[g_mes['cat'] == rp['cat']]['monto_crc']
                gastado = serie.sum() if not serie.empty else 0
                limite = float(rp['limite'])
                pct = min(gastado / limite, 1.0) if limite > 0 else 1.0
                st.write(f"**{rp['cat']}** | Ejecutado: ₡{gastado:,.0f} de ₡{limite:,.0f}")
                st.progress(pct)
                if pct >= 0.9: st.error(f"⚠️ Has consumido el 90% o más de tu presupuesto para {rp['cat']}")

        # 2. Rentabilidad de Proyectos
        if not df_proy.empty:
            st.markdown("### 🏢 Rentabilidad de Centros de Costo")
            for _, rp in df_proy.iterrows():
                df_p = df[df['proyecto_id'] == rp['id']]
                i_p = df_p[df_p['tipo']=='Ingreso']['monto_crc'].sum() if not df_p.empty else 0
                g_p = df_p[df_p['tipo']=='Gasto']['monto_crc'].sum() if not df_p.empty else 0
                margen = i_p - g_p
                color_m = "#2ecc71" if margen >= 0 else "#ff4b4b"
                st.markdown(f'<div class="user-card"><b>{rp["nombre"]}</b> | Ingresos: ₡{i_p:,.0f} | Egresos: ₡{g_p:,.0f} | <span style="color:{color_m};">Margen Neto: ₡{margen:,.0f}</span></div>', unsafe_allow_html=True)
    else:
        st.info("Aún no tienes movimientos financieros registrados en este periodo.")

# --- T2: REGISTRO MÁGICO ---
with t2:
    tm, tmg = st.tabs(["✍️ Registro Manual y Bóveda", "🪄 Lector Mágico de SMS"])
    
    with tm:
        conn = get_connection()
        df_bill = pd.read_sql("SELECT id, nombre, moneda FROM billeteras WHERE usuario_id=%s", conn, params=(st.session_state.uid,))
        df_pry = pd.read_sql("SELECT id, nombre FROM proyectos WHERE usuario_id=%s", conn, params=(st.session_state.uid,))
        conn.close()
        
        b_op = [{"label": f"{r['nombre']} ({r['moneda']})", "id": r['id']} for _, r in df_bill.iterrows()] if not df_bill.empty else [{"label": "Efectivo Principal (CRC)", "id": 0}]
        p_op = [{"label": "Ninguno (Gasto Personal)", "id": 0}] + [{"label": r['nombre'], "id": r['id']} for _, r in df_pry.iterrows()]
        
        tipo = st.radio("Selecciona el tipo de transacción:", ["Gasto", "Ingreso"], horizontal=True)
        cats = ["Súper/Comida", "Servicios", "Casa/Alquiler", "Transporte", "Ocio", "Salud", "Educación", "Insumos Negocio", "Otros"] if tipo == "Gasto" else ["Ventas", "Servicios Profesionales", "Salario Fijo", "Otros"]
        
        with st.form("f_reg_manual"):
            col_sel1, col_sel2 = st.columns(2)
            b_sel = col_sel1.selectbox("¿Billetera / Cuenta bancaria?", [x['label'] for x in b_op])
            p_sel = col_sel2.selectbox("Asignar a Centro de Costo (Proyecto):", [x['label'] for x in p_op])
            
            b_id = next(b['id'] for b in b_op if b['label'] == b_sel)
            p_id = next(p['id'] for p in p_op if p['label'] == p_sel)
            
            m_reg = st.number_input("Monto de la transacción", min_value=0.0, step=1000.0)
            c_reg = st.selectbox("Clasificación (Categoría)", cats)
            
            imp_reg = 0.0
            if tipo == "Ingreso" and p_id != 0:
                if st.checkbox("🛡️ Aplicar Escudo Fiscal (Retener automáticamente 13% para impuestos)"):
                    imp_reg = m_reg * 0.13
                    
            d_reg = st.text_input("Nota o descripción (Opcional)")
            foto_reg = st.file_uploader("📸 Adjuntar Factura / Recibo físico", type=["jpg", "png", "jpeg"])
            
            if st.form_submit_button("REGISTRAR EN EL LIBRO MAYOR", use_container_width=True):
                moneda_trans = "USD" if "USD" in b_sel else "CRC"
                img_encoded = base64.b64encode(foto_reg.read()).decode('utf-8') if foto_reg else None
                reg_mov(m_reg, tipo, c_reg, d_reg, moneda_trans, img_encoded, b_id, p_id, imp_reg)
                st.success("✅ Transacción guardada con éxito en la base de datos."); st.rerun()

    with tmg:
        st.markdown("Copia el texto del mensaje que te envía el banco y pégalo aquí para registrarlo en 2 segundos.")
        txt_sms = st.text_area("Ejemplo: 'BAC Credomatic: Compra aprobada por ₡15,000 en WALMART'")
        if st.button("🪄 Analizar SMS con IA", use_container_width=True):
            if txt_sms:
                mt = re.search(r'[\$₡]?\s?(\d{1,3}(?:[.,]\d{3})*(?:[.,]\d{2})?)', txt_sms)
                if mt:
                    ml = float(mt.group(1).replace(',', ''))
                    md = "USD" if "USD" in txt_sms.upper() else "CRC"
                    
                    cat_sug = "Otros"
                    if any(w in txt_sms.upper() for w in ["WALMART", "MASXMENOS", "AUTO MERCADO", "PALI"]): cat_sug = "Súper/Comida"
                    elif any(w in txt_sms.upper() for w in ["UBER", "DIDDI", "GAS", "DELTA", "PUMA"]): cat_sug = "Transporte"
                    elif any(w in txt_sms.upper() for w in ["KFC", "MCDONALDS", "STARBUCKS"]): cat_sug = "Ocio"
                    
                    st.success(f"Detección exitosa: **{md} {ml:,.2f}** (Sugerencia: {cat_sug})")
                    if st.button(f"Confirmar Registro de Gasto"):
                        reg_mov(ml, "Gasto", cat_sug, txt_sms[:40], md)
                        st.success("Gasto automatizado registrado."); st.rerun()
                else:
                    st.error("La Inteligencia Artificial no logró extraer un monto válido del mensaje.")

# --- T3: BILLETERAS Y PROYECTOS ---
with t3:
    col_bill, col_proy = st.columns(2)
    with col_bill:
        st.markdown("### 💳 Mis Billeteras")
        with st.form("fb_form"):
            n_b = st.text_input("Nombre (Ej: Tarjeta Débito BAC)")
            t_b = st.selectbox("Tipo de Cuenta", ["Efectivo / Débito", "Tarjeta de Crédito (Pasivo)"])
            m_b = st.selectbox("Moneda Principal", ["CRC", "USD"])
            if st.form_submit_button("AÑADIR BILLETERA", use_container_width=True):
                conn = get_connection(); c = conn.cursor()
                c.execute("INSERT INTO billeteras (usuario_id, nombre, tipo, moneda) VALUES (%s,%s,%s,%s)", (st.session_state.uid, n_b, t_b, m_b))
                conn.commit(); c.close(); conn.close(); st.rerun()
        
        conn = get_connection(); df_b = pd.read_sql("SELECT * FROM billeteras WHERE usuario_id=%s", conn, params=(st.session_state.uid,)); conn.close()
        for _, r in df_b.iterrows():
            st.markdown(f'<div class="user-card">💳 <b>{r["nombre"]}</b> | {r["tipo"]} | Moneda: {r["moneda"]}</div>', unsafe_allow_html=True)
            
    with col_proy:
        st.markdown("### 🏢 Mis Proyectos Comerciales")
        with st.form("fp_form"):
            n_p = st.text_input("Nombre del Proyecto o Negocio")
            if st.form_submit_button("CREAR CENTRO DE COSTO", use_container_width=True):
                conn = get_connection(); c = conn.cursor()
                c.execute("INSERT INTO proyectos (usuario_id, nombre) VALUES (%s,%s)", (st.session_state.uid, n_p))
                conn.commit(); c.close(); conn.close(); st.rerun()
                
        conn = get_connection(); df_p = pd.read_sql("SELECT * FROM proyectos WHERE usuario_id=%s", conn, params=(st.session_state.uid,)); conn.close()
        for _, r in df_p.iterrows():
            st.markdown(f'<div class="user-card">🏢 <b>{r["nombre"]}</b></div>', unsafe_allow_html=True)

# --- T4: FIJOS Y PRESUPUESTOS ---
with t4:
    tab_presup, tab_subs = st.tabs(["🚧 Control de Presupuestos", "🔁 Gestor de Suscripciones Fijas"])
    
    with tab_presup:
        with st.form("f_pre_form"):
            c_p = st.selectbox("Categoría a limitar", ["Súper/Comida", "Transporte", "Ocio", "Casa/Alquiler", "Otros"])
            l_p = st.number_input("Límite de Gasto Mensual (CRC)", min_value=1.0)
            if st.form_submit_button("FIJAR LÍMITE"):
                conn = get_connection(); cr = conn.cursor()
                cr.execute("DELETE FROM presupuestos WHERE usuario_id=%s AND cat=%s", (st.session_state.uid, c_p))
                cr.execute("INSERT INTO presupuestos (usuario_id, cat, limite) VALUES (%s,%s,%s)", (st.session_state.uid, c_p, l_p))
                conn.commit(); cr.close(); conn.close(); st.rerun()
                
        conn = get_connection(); df_pr = pd.read_sql("SELECT * FROM presupuestos WHERE usuario_id=%s", conn, params=(st.session_state.uid,)); conn.close()
        for _, r in df_pr.iterrows():
            st.markdown(f'<div class="user-card">🚧 <b>{r["cat"]}</b> | Límite Activo: ₡{float(r["limite"]):,.0f}</div>', unsafe_allow_html=True)
            if st.button("🗑️ Eliminar Límite", key=f"dp_{r['id']}"):
                conn = get_connection(); c = conn.cursor(); c.execute("DELETE FROM presupuestos WHERE id=%s", (r['id'],)); conn.commit(); c.close(); conn.close(); st.rerun()

    with tab_subs:
        st.write("Registra tus pagos automáticos. El sistema los deducirá de tu balance el día correspondiente sin que hagas nada.")
        with st.form("f_sub_form"):
            n_s = st.text_input("Nombre de la Obligación (Ej: Netflix, Préstamo Carro)")
            col_s1, col_s2 = st.columns(2)
            m_s = col_s1.selectbox("Moneda", ["CRC", "USD"])
            v_s = col_s2.number_input("Monto Fijo", min_value=1.0)
            d_s = st.number_input("Día de cobro en el mes (1-31)", min_value=1, max_value=31)
            cat_s = st.selectbox("Clasificación", ["Servicios", "Ocio", "Casa/Alquiler", "Educación", "Otros"])
            if st.form_submit_button("ACTIVAR SUSCRIPCIÓN", use_container_width=True):
                conn = get_connection(); cr = conn.cursor()
                cr.execute("INSERT INTO suscripciones (usuario_id, nombre, monto, dia_cobro, cat, moneda) VALUES (%s,%s,%s,%s,%s,%s)", 
                           (st.session_state.uid, n_s, v_s, d_s, cat_s, m_s))
                conn.commit(); cr.close(); conn.close(); st.rerun()
                
        conn = get_connection(); df_sub = pd.read_sql("SELECT * FROM suscripciones WHERE usuario_id=%s", conn, params=(st.session_state.uid,)); conn.close()
        for _, r in df_sub.iterrows():
            st.markdown(f'<div class="user-card">🔁 <b>{r["nombre"]}</b> | {r["moneda"]} {float(r["monto"]):,.0f} | Se debita el día {r["dia_cobro"]} del mes.</div>', unsafe_allow_html=True)
            if st.button("🗑️ Cancelar Auto-Pago", key=f"ds_{r['id']}"):
                conn = get_connection(); c = conn.cursor(); c.execute("DELETE FROM suscripciones WHERE id=%s", (r['id'],)); conn.commit(); c.close(); conn.close(); st.rerun()

# --- T5: METAS ---
with t5:
    with st.expander("➕ Crear Nuevo Proyecto de Ahorro"):
        with st.form("fm_form"):
            n_m = st.text_input("¿Para qué estás ahorrando?")
            o_m = st.number_input("Monto Total Objetivo", min_value=1.0)
            if st.form_submit_button("CREAR META", use_container_width=True):
                conn = get_connection(); c = conn.cursor()
                c.execute("INSERT INTO metas (usuario_id, nombre, objetivo) VALUES (%s,%s,%s)", (st.session_state.uid, n_m, o_m))
                conn.commit(); c.close(); conn.close(); st.rerun()
                
    conn = get_connection(); df_m = pd.read_sql("SELECT * FROM metas WHERE usuario_id=%s ORDER BY id DESC", conn, params=(st.session_state.uid,)); conn.close()
    for _, r in df_m.iterrows():
        st.markdown(f'<div class="user-card"><b>🎯 {r["nombre"]}</b><br>Progreso: ₡{float(r["actual"]):,.0f} de ₡{float(r["objetivo"]):,.0f}</div>', unsafe_allow_html=True)
        st.progress(min(float(r['actual'])/float(r['objetivo']), 1.0))
        
        col_ma1, col_ma2, col_ma3 = st.columns([2, 1, 1])
        monto_abono = col_ma1.number_input("Monto a depositar", min_value=0.0, key=f"am_{r['id']}")
        if col_ma2.button("ABONAR", key=f"bm_{r['id']}", use_container_width=True):
            conn = get_connection(); c = conn.cursor()
            c.execute("UPDATE metas SET actual=actual+%s WHERE id=%s", (monto_abono, r['id']))
            conn.commit(); c.close(); conn.close()
            reg_mov(monto_abono, "Gasto", "🎯 Ahorro", f"Meta: {r['nombre']}")
            st.rerun()
        if col_ma3.button("🗑️ Eliminar", key=f"delm_{r['id']}", use_container_width=True):
            conn = get_connection(); c = conn.cursor(); c.execute("DELETE FROM metas WHERE id=%s", (r['id'],)); conn.commit(); c.close(); conn.close(); st.rerun()

# --- T6: DEUDAS Y AMORTIZACIÓN ---
with t6:
    t_deu, t_cob = st.tabs(["🏦 Obligaciones Bancarias y Deudas", "🟢 Cuentas por Cobrar"])
    
    with t_deu:
        with st.expander("➕ Adquirir Préstamo o Deuda"):
            with st.form("fd_form"):
                n_banco = st.text_input("Acreedor / Entidad Bancaria")
                cd1, cd2, cd3 = st.columns(3)
                m_total = cd1.number_input("Capital Prestado", min_value=1.0)
                int_anual = cd2.number_input("Tasa Interés Anual (%)", min_value=0.0)
                plazo_m = cd3.number_input("Plazo en Meses", min_value=1)
                mon_prest = st.selectbox("Moneda del Préstamo", ["CRC", "USD"])
                if st.form_submit_button("REGISTRAR PRÉSTAMO", use_container_width=True):
                    vence_p = date.today() + timedelta(days=plazo_m*30)
                    conn = get_connection(); c = conn.cursor()
                    c.execute("INSERT INTO deudas (usuario_id, nombre, monto_total, tipo_registro, fecha_vence, moneda, tasa_interes, plazo_meses) VALUES (%s,%s,%s,'DEUDA',%s,%s,%s,%s)", 
                              (st.session_state.uid, n_banco, m_total, vence_p, mon_prest, int_anual, plazo_m))
                    conn.commit(); c.close(); conn.close(); st.rerun()
                    
        conn = get_connection(); df_d = pd.read_sql("SELECT * FROM deudas WHERE usuario_id=%s AND tipo_registro='DEUDA' ORDER BY fecha_vence", conn, params=(st.session_state.uid,)); conn.close()
        for _, r in df_d.iterrows():
            pend_deuda = float(r['monto_total']) - float(r['pagado'])
            cuota_sug = calcular_cuota_nivelada(float(r['monto_total']), float(r['tasa_interes']), int(r['plazo_meses']))
            st.markdown(f'<div class="user-card">🏦 <b>{r["nombre"]}</b> | Saldo Vivo: {r["moneda"]} {pend_deuda:,.0f}<br>Tasa: {r["tasa_interes"]}% | Cuota Nivelada Sugerida: <b>{r["moneda"]} {cuota_sug:,.0f}</b></div>', unsafe_allow_html=True)
            
            if pend_deuda > 0:
                cp1, cp2, cp3 = st.columns([2,1,1])
                abono_d = cp1.number_input("Monto a pagar", min_value=0.0, value=min(cuota_sug, pend_deuda), key=f"ab_{r['id']}")
                if cp2.button("PAGAR CUOTA", key=f"pg_{r['id']}", use_container_width=True):
                    conn = get_connection(); c = conn.cursor()
                    c.execute("UPDATE deudas SET pagado=pagado+%s WHERE id=%s", (abono_d, r['id']))
                    conn.commit(); c.close(); conn.close()
                    reg_mov(abono_d, "Gasto", "🏦 Préstamo", f"Abono a {r['nombre']}", r['moneda'])
                    st.rerun()
                if cp3.button("🗑️ Borrar", key=f"bd_{r['id']}", use_container_width=True):
                    conn = get_connection(); c = conn.cursor(); c.execute("DELETE FROM deudas WHERE id=%s", (r['id'],)); conn.commit(); c.close(); conn.close(); st.rerun()

    with t_cob:
        with st.expander("➕ Registrar Nueva Cuenta por Cobrar"):
            with st.form("fc_form"):
                n_deudor = st.text_input("Nombre de la persona que te debe")
                cc1, cc2 = st.columns([1,3])
                mon_c = cc1.selectbox("Moneda", ["CRC", "USD"])
                m_c = cc2.number_input("Monto Total", min_value=1.0)
                v_c = st.date_input("Fecha promesa de pago")
                if st.form_submit_button("GUARDAR REGISTRO", use_container_width=True):
                    conn = get_connection(); c = conn.cursor()
                    c.execute("INSERT INTO deudas (usuario_id, nombre, monto_total, tipo_registro, fecha_vence, moneda) VALUES (%s,%s,%s,'COBRO',%s,%s)", 
                              (st.session_state.uid, n_deudor, m_c, v_c, mon_c))
                    conn.commit(); c.close(); conn.close(); st.rerun()
                    
        conn = get_connection(); df_c = pd.read_sql("SELECT * FROM deudas WHERE usuario_id=%s AND tipo_registro='COBRO' ORDER BY fecha_vence", conn, params=(st.session_state.uid,)); conn.close()
        for _, r in df_c.iterrows():
            pend_cobro = float(r['monto_total']) - float(r['pagado'])
            st.markdown(f'<div class="user-card">🟢 <b>{r["nombre"]}</b> | Falta que te paguen: {r["moneda"]} {pend_cobro:,.0f}</div>', unsafe_allow_html=True)
            
            if pend_cobro > 0:
                ccb1, ccb2, ccb3 = st.columns([2,1,1])
                ingreso_c = ccb1.number_input("Monto recibido", min_value=0.0, max_value=pend_cobro, key=f"ic_{r['id']}")
                if ccb2.button("RECIBIR DINERO", key=f"rc_{r['id']}", use_container_width=True):
                    conn = get_connection(); c = conn.cursor()
                    c.execute("UPDATE deudas SET pagado=pagado+%s WHERE id=%s", (ingreso_c, r['id']))
                    conn.commit(); c.close(); conn.close()
                    reg_mov(ingreso_c, "Ingreso", "💸 Cobro", f"Pago recibido de {r['nombre']}", r['moneda'])
                    st.rerun()
                if ccb3.button("🗑️ Borrar", key=f"bc_{r['id']}", use_container_width=True):
                    conn = get_connection(); c = conn.cursor(); c.execute("DELETE FROM deudas WHERE id=%s", (r['id'],)); conn.commit(); c.close(); conn.close(); st.rerun()

# --- T7: AGENDA Y SINPE ---
with t7:
    conn = get_connection()
    df_contactos = pd.read_sql("SELECT * FROM contactos WHERE usuario_id=%s ORDER BY nombre", conn, params=(st.session_state.uid,))
    conn.close()
    
    cs1, cs2 = st.columns([1.2, 1])
    with cs1:
        st.markdown("### 💸 Enviar SINPE Rápido")
        opc_sinpe = ["✏️ Escribir número manualmente..."] + [f"{r['nombre']} - {r['telefono']}" for _, r in df_contactos.iterrows()]
        sel_sinpe = st.selectbox("Seleccionar contacto frecuente:", opc_sinpe)
        
        with st.form("f_envio_sinpe"):
            es_man = "✏️" in sel_sinpe
            num_destino = st.text_input("Número de Teléfono a transferir:", value="" if es_man else sel_sinpe.split(" - ")[1])
            monto_sinpe = st.number_input("Monto a enviar (₡):", min_value=0.0, step=1000.0)
            det_sinpe = st.text_input("Detalle de la transferencia:")
            
            if st.form_submit_button("REGISTRAR GASTO Y ABRIR BANCO", use_container_width=True):
                if num_destino and monto_sinpe > 0:
                    nom_dest = "Transferencia Manual" if es_man else sel_sinpe.split(" - ")[0]
                    reg_mov(monto_sinpe, "Gasto", "📱 SINPE", f"Enviado a: {nom_dest} ({num_destino}) - {det_sinpe}", "CRC")
                    st.markdown('<a href="https://www.google.com" target="_blank" class="btn-banco">🏦 CLICK AQUÍ PARA ABRIR TU BANCO</a>', unsafe_allow_html=True)
                else:
                    st.error("Es obligatorio digitar un número y un monto.")

    with cs2:
        st.markdown("### 📖 Mi Agenda")
        with st.expander("➕ Guardar nuevo contacto"):
            with st.form("f_add_contacto"):
                nom_cnt = st.text_input("Nombre Completo")
                tel_cnt = st.text_input("Número de Teléfono")
                if st.form_submit_button("GUARDAR EN AGENDA", use_container_width=True):
                    if nom_cnt and tel_cnt:
                        conn = get_connection(); c = conn.cursor()
                        c.execute("INSERT INTO contactos (usuario_id, nombre, telefono) VALUES (%s, %s, %s)", (st.session_state.uid, nom_cnt, tel_cnt))
                        conn.commit(); c.close(); conn.close(); st.rerun()
        
        if not df_contactos.empty:
            for _, r in df_contactos.iterrows():
                ccnt1, ccnt2 = st.columns([4, 1])
                ccnt1.markdown(f"👤 **{r['nombre']}** ({r['telefono']})")
                if ccnt2.button("🗑️", key=f"dcnt_{r['id']}"):
                    conn = get_connection(); c = conn.cursor(); c.execute("DELETE FROM contactos WHERE id=%s", (r['id'],)); conn.commit(); c.close(); conn.close(); st.rerun()
        else:
            st.info("Agenda vacía.")

# --- T8: HISTORIAL Y AJUSTES ---
with t8:
    st.subheader("📜 Libro Mayor Contable (Auditoría)")
    conn = get_connection()
    df_historial = pd.read_sql("SELECT id, fecha, tipo, cat, monto, moneda, descrip, impuesto_reserva, comprobante FROM movimientos WHERE usuario_id=%s ORDER BY id DESC LIMIT 100", conn, params=(st.session_state.uid,))
    conn.close()
    
    if not df_historial.empty:
        # Generación de CSV limpio para descargar
        df_csv = df_historial.drop(columns=['comprobante']).rename(columns={'fecha':'Fecha', 'tipo':'Tipo', 'cat':'Categoría', 'monto':'Monto', 'moneda':'Divisa', 'descrip':'Detalle', 'impuesto_reserva':'Impuesto_Retenido'})
        csv_data = df_csv.to_csv(index=False).encode('utf-8')
        st.download_button("📥 Descargar Libro Mayor en Excel (.CSV)", data=csv_data, file_name=f'GeZo_Contabilidad_{date.today()}.csv', mime='text/csv')
        st.divider()
        
        # Visor Interactivo y Bóveda de Recibos
        for _, r in df_historial.head(50).iterrows():
            with st.expander(f"{r['fecha']} | {r['tipo']} | {r['moneda']} {float(r['monto']):,.0f} | {r['cat']}"):
                st.write(f"**Descripción Completa:** {r['descrip']}")
                if pd.notnull(r['impuesto_reserva']) and float(r['impuesto_reserva']) > 0: 
                    st.write(f"🛡️ **Escudo Fiscal (Impuesto Retenido):** ₡{float(r['impuesto_reserva']):,.0f}")
                
                if r['comprobante']: 
                    try:
                        st.image(base64.b64decode(r['comprobante']), caption="Factura / Recibo Adjunto", use_container_width=True)
                    except:
                        st.warning("⚠️ El recibo adjunto no se pudo cargar.")
                        
                if st.button("🗑️ Eliminar este registro del balance", key=f"dh_{r['id']}"):
                    conn = get_connection(); c = conn.cursor()
                    c.execute("DELETE FROM movimientos WHERE id=%s", (r['id'],))
                    conn.commit(); c.close(); conn.close(); st.rerun()
    else: 
        st.info("El libro mayor está limpio. No hay movimientos registrados.")
    
    st.divider()
    st.markdown("### ⚙️ Configuración y Seguridad")
    with st.form("f_cambio_clave"):
        nva_clave = st.text_input("Ingresa tu nueva contraseña", type="password")
        if st.form_submit_button("ACTUALIZAR CREDENCIALES"):
            if nva_clave:
                conn = get_connection(); c = conn.cursor()
                c.execute("UPDATE usuarios SET clave=%s WHERE id=%s", (nva_clave, st.session_state.uid))
                conn.commit(); c.close(); conn.close()
                st.success("✅ Contraseña actualizada correctamente.")
                
    if st.button("🚪 CERRAR SESIÓN DE FORMA SEGURA", type="primary", use_container_width=True):
        st.session_state.autenticado = False
        st.query_params.clear()
        st.rerun()
