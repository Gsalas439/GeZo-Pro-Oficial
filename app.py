import streamlit as st
import pandas as pd
import psycopg2
from datetime import datetime, timedelta
import plotly.express as px

# --- 1. CONFIGURACIÓN Y ESTÉTICA ---
st.set_page_config(page_title="GeZo Elite Pro", page_icon="💎", layout="wide")

st.markdown("""
    <style>
    .main { background-color: #0b0e14; color: #e0e0e0; }
    div[data-testid="stMetric"] {
        background: linear-gradient(135deg, rgba(0, 198, 255, 0.1) 0%, rgba(0, 114, 255, 0.1) 100%);
        border-radius: 15px; padding: 20px; border: 1px solid #00c6ff;
    }
    .stButton>button {
        border-radius: 12px; background: linear-gradient(90deg, #00f2fe 0%, #4facfe 100%);
        color: black; font-weight: bold; width: 100%; border: none; height: 3.5em;
    }
    .btn-danger>div>button {
        background: linear-gradient(90deg, #ff4b2b 0%, #ff416c 100%) !important;
        color: white !important; height: 2.5em !important;
    }
    .user-card {
        background: rgba(255, 255, 255, 0.05); padding: 20px; border-radius: 15px;
        border: 1px solid #333; margin-bottom: 10px; border-left: 5px solid #00c6ff;
    }
    .whatsapp-btn {
        background-color: #25d366; color: white; padding: 12px;
        border-radius: 10px; text-decoration: none; font-weight: bold; display: block; text-align: center;
    }
    </style>
    """, unsafe_allow_html=True)

# --- 2. MOTOR DE BASE DE DATOS ---
def get_connection():
    return psycopg2.connect(st.secrets["DB_URL"])

def inicializar_db():
    conn = get_connection()
    c = conn.cursor()
    # Creamos las tablas con la columna 'precio' incluida
    c.execute('''CREATE TABLE IF NOT EXISTS usuarios 
                 (id SERIAL PRIMARY KEY, nombre TEXT UNIQUE, clave TEXT, expira DATE, rol TEXT, 
                  plan TEXT, precio TEXT, presupuesto DECIMAL DEFAULT 250000)''')
    c.execute('''CREATE TABLE IF NOT EXISTS movimientos 
                 (id SERIAL PRIMARY KEY, usuario_id INTEGER, fecha DATE, descrip TEXT, monto DECIMAL, tipo TEXT, cat TEXT)''')
    c.execute('''CREATE TABLE IF NOT EXISTS metas 
                 (id SERIAL PRIMARY KEY, usuario_id INTEGER, nombre TEXT, objetivo DECIMAL, actual DECIMAL)''')
    c.execute('''CREATE TABLE IF NOT EXISTS deudas 
                 (id SERIAL PRIMARY KEY, usuario_id INTEGER, nombre TEXT, monto_total DECIMAL, pagado DECIMAL DEFAULT 0, tipo TEXT)''')
    
    # Crear Admin por defecto si no existe
    c.execute("SELECT * FROM usuarios WHERE nombre='admin'")
    if not c.fetchone():
        c.execute("INSERT INTO usuarios (nombre, clave, expira, rol, plan, precio) VALUES (%s, %s, %s, %s, %s, %s)", 
                  ('admin', 'admin123', '2099-12-31', 'admin', 'Dueño Master', 'N/A'))
    conn.commit()
    c.close()
    conn.close()

try:
    inicializar_db()
except Exception as e:
    st.error(f"Error de conexión: {e}")
    st.stop()

# --- 3. LOGICA DE SESIÓN Y LOGIN ---
WHATSAPP_NUM = "50663712477"
if 'autenticado' not in st.session_state: st.session_state.autenticado = False
if 'ver_montos' not in st.session_state: st.session_state.ver_montos = True

if not st.session_state.autenticado:
    st.title("💎 GeZo Elite Pro")
    with st.form("login_form"):
        u = st.text_input("Usuario")
        p = st.text_input("Contraseña", type="password")
        if st.form_submit_button("ENTRAR"):
            conn = get_connection(); c = conn.cursor()
            c.execute("SELECT id, nombre, rol, plan, expira FROM usuarios WHERE nombre=%s AND clave=%s", (u, p))
            res = c.fetchone()
            if res:
                if datetime.now().date() > res[4]:
                    st.error("❌ Suscripción vencida.")
                    st.markdown(f'<a href="https://wa.me/{WHATSAPP_NUM}" class="whatsapp-btn">📲 Renovar Membresía</a>', unsafe_allow_html=True)
                else:
                    st.session_state.update({"autenticado":True, "uid":res[0], "uname":res[1], "rol":res[2], "plan":res[3]})
                    st.rerun()
            else: st.error("Usuario o clave incorrectos.")
            c.close(); conn.close()
    st.stop()

def fmt(n): return f"₡{float(n):,.0f}" if st.session_state.ver_montos else "₡ *.*"

# --- 4. MENÚ LATERAL ---
with st.sidebar:
    st.title(f"👑 {st.session_state.uname}")
    st.caption(f"Plan: {st.session_state.plan}")
    if st.button("👁️ Privacidad"):
        st.session_state.ver_montos = not st.session_state.ver_montos
        st.rerun()
    menu = st.radio("Menú Principal", ["📊 Dashboard", "📱 SINPE Rápido", "💸 Registrar", "🤝 Deudas", "🎯 Metas", "⚙️ Admin"])
    if st.button("Cerrar Sesión"):
        st.session_state.autenticado = False
        st.rerun()

# --- 5. MÓDULOS DEL SISTEMA ---

if menu == "📊 Dashboard":
    st.header("Resumen de Cuentas")
    df = pd.read_sql(f"SELECT * FROM movimientos WHERE usuario_id={st.session_state.uid}", get_connection())
    ing = df[df['tipo']=='Ingreso']['monto'].sum() if not df.empty else 0
    gas = df[df['tipo']=='Gasto']['monto'].sum() if not df.empty else 0
    
    c1, c2, c3 = st.columns(3)
    c1.metric("Ingresos", fmt(ing))
    c2.metric("Gastos", fmt(gas), delta_color="inverse")
    c3.metric("Saldo Disponible", fmt(ing-gas))
    
    if not df.empty:
        fig = px.pie(df[df['tipo']=='Gasto'], values='monto', names='cat', hole=.4, template="plotly_dark")
        st.plotly_chart(fig, use_container_width=True)

elif menu == "📱 SINPE Rápido":
    st.header("Registro SINPE")
    with st.form("sinpe"):
        tel = st.text_input("Número (8 dígitos)")
        monto = st.number_input("Monto (₡)", min_value=0)
        banco = st.selectbox("Banco destino", ["BNCR", "BAC", "BCR", "BP"])
        if st.form_submit_button("GUARDAR Y ABRIR APP"):
            conn = get_connection(); c = conn.cursor()
            c.execute("INSERT INTO movimientos (usuario_id, fecha, descrip, monto, tipo, cat) VALUES (%s,%s,%s,%s,%s,%s)",
                      (st.session_state.uid, datetime.now().date(), f"SINPE a {tel}", monto, "Gasto", "📱 SINPE"))
            conn.commit(); c.close(); conn.close()
            links = {"BNCR": "https://www.bnmovil.fi.cr/", "BAC": "https://www.baccredomatic.com/", "BCR": "https://www.bancobcr.com/", "BP": "https://www.bancopopular.fi.cr/"}
            st.markdown(f'<a href="{links[banco]}" target="_blank" class="whatsapp-btn">🚀 Ir a {banco}</a>', unsafe_allow_html=True)

elif menu == "💸 Registrar":
    st.header("Nuevo Registro")
    with st.form("reg"):
        det = st.text_input("Detalle")
        mon = st.number_input("Monto", min_value=0.0)
        cat = st.selectbox("Categoría", ["⚖️ Pensión", "⛽ Gasolina", "🛒 Súper", "🏠 Casa", "⚡ Servicios", "💡 Gastos Hormiga", "🏦 Deudas", "💰 Ahorro", "💵 Salario", "📦 Otros"])
        tip = st.selectbox("Tipo", ["Gasto", "Ingreso"])
        if st.form_submit_button("CONFIRMAR"):
            conn = get_connection(); c = conn.cursor()
            c.execute("INSERT INTO movimientos (usuario_id, fecha, descrip, monto, tipo, cat) VALUES (%s,%s,%s,%s,%s,%s)",
                      (st.session_state.uid, datetime.now().date(), det, mon, tip, cat))
            conn.commit(); c.close(); conn.close()
            st.success("Registrado correctamente.")

elif menu == "⚙️ Admin":
    if st.session_state.rol == 'admin':
        st.header("💎 Control Maestro de Clientes")
        
        # Configuración de los planes con sus precios
        planes_config = {
            "Prueba (7 días)": {"d": 7, "p": "Gratis"},
            "Mensual": {"d": 30, "p": "₡5,000"},
            "Trimestral": {"d": 90, "p": "₡13,500"},
            "Semestral": {"d": 180, "p": "₡25,000"},
            "Anual": {"d": 365, "p": "₡45,000"},
            "Eterno (De por vida)": {"d": 36500, "p": "₡100,000"}
        }

        with st.expander("➕ REGISTRAR NUEVO CLIENTE"):
            u_n = st.text_input("Nombre de Usuario")
            p_n = st.text_input("Contraseña")
            p_s = st.selectbox("Elegir Plan", list(planes_config.keys()))
            st.info(f"💰 Precio a cobrar: {planes_config[p_s]['p']}")
            
            if st.button("✅ ACTIVAR MEMBRESÍA"):
                vencimiento = (datetime.now() + timedelta(days=planes_config[p_s]['d'])).date()
                conn = get_connection(); c = conn.cursor()
                try:
                    c.execute("INSERT INTO usuarios (nombre, clave, expira, rol, plan, precio) VALUES (%s,%s,%s,%s,%s,%s)", 
                              (u_n, p_n, vencimiento, 'usuario', p_s, planes_config[p_s]['p']))
                    conn.commit()
                    st.success(f"¡Usuario {u_n} creado con éxito!")
                except: st.error("Error: El usuario ya existe.")
                finally: c.close(); conn.close()
                st.rerun()

        st.divider()
        st.subheader("👥 Lista de Usuarios Activos")
        
        # Consultamos usuarios para mostrarlos con botón de eliminar
        usuarios_df = pd.read_sql("SELECT id, nombre, plan, precio, expira FROM usuarios WHERE rol!='admin' ORDER BY expira DESC", get_connection())
        
        for i, row in usuarios_df.iterrows():
            with st.container():
                st.markdown(f"""
                <div class="user-card">
                    <b>👤 Usuario: {row['nombre']}</b><br>
                    💎 Plan: {row['plan']} | 💰 Pagó: {row['precio']} <br>
                    📅 Vencimiento: {row['expira']}
                </div>
                """, unsafe_allow_html=True)
                
                # Botón de ELIMINAR con limpieza total
                col_del, col_empty = st.columns([1, 4])
                with col_del:
                    st.markdown('<div class="btn-danger">', unsafe_allow_html=True)
                    if st.button(f"🗑️ Eliminar", key=f"del_user_{row['id']}"):
                        conn = get_connection(); c = conn.cursor()
                        # Borrar todos sus datos vinculados
                        c.execute(f"DELETE FROM movimientos WHERE usuario_id={row['id']}")
                        c.execute(f"DELETE FROM metas WHERE usuario_id={row['id']}")
                        c.execute(f"DELETE FROM deudas WHERE usuario_id={row['id']}")
                        c.execute(f"DELETE FROM usuarios WHERE id={row['id']}")
                        conn.commit(); c.close(); conn.close()
                        st.success(f"Usuario {row['nombre']} eliminado.")
                        st.rerun()
                    st.markdown('</div>', unsafe_allow_html=True)
                st.write("")

elif menu == "🤝 Deudas":
    st.header("Préstamos y Cobros")
    with st.form("deud"):
        nom = st.text_input("Nombre de la persona")
        mon = st.number_input("Monto", min_value=0.0)
        tip = st.selectbox("Tipo", ["Me deben", "Yo debo"])
        if st.form_submit_button("GUARDAR DEUDA"):
            conn = get_connection(); c = conn.cursor()
            c.execute("INSERT INTO deudas (usuario_id, nombre, monto_total, pagado, tipo) VALUES (%s,%s,%s,%s,%s)", (st.session_state.uid, nom, mon, 0, tip))
            conn.commit(); c.close(); conn.close()
            st.rerun()

elif menu == "🎯 Metas":
    st.header("Metas de Ahorro")
    with st.form("met"):
        nom_m = st.text_input("Nombre de la meta")
        obj_m = st.number_input("Monto Objetivo", min_value=1.0)
        if st.form_submit_button("CREAR META"):
            conn = get_connection(); c = conn.cursor()
            c.execute("INSERT INTO metas (usuario_id, nombre, objetivo, actual) VALUES (%s,%s,%s,%s)", (st.session_state.uid, nom_m, obj_m, 0))
            conn.commit(); c.close(); conn.close()
            st.rerun()
