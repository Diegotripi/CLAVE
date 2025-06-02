from __future__ import annotations
import base64
from pathlib import Path
from collections import OrderedDict
from typing import Dict, List, Tuple

import pandas as pd
import requests
import streamlit as st

# Para ejecutar este archivo:  streamlit run web.py

# RECURSOS – logo y fondo oscuro

LOGO_PATH = "logo_clave.png"
BG_PATH   = "dark_background.png"


# CONFIGURACIÓN THINGSPEAK


WRITE_API_KEY_USERS  = "3UGWIIJ540HY5GMT"
READ_API_KEY_USERS   = "LU6Z7ZBGVF0H49OX"
ID_CANAL_USERS       = "2968196"

WRITE_API_KEY_ACCESS = "YE5B61469RDB8F80"
READ_API_KEY_ACCESS  = "Q1DSHLY8CZBBLOG2"
ID_CANAL_ACCESS      = "2977309"

BASE_URL = "https://api.thingspeak.com"
HEADERS  = {"Content-Type": "application/x-www-form-urlencoded"}
TIMEOUT  = 8


# UTILIDADES DE IMAGEN / CSS



def _b64_encode(img_path: str | Path) -> str:
    """Codifica una imagen a base-64 (cadena vacía si no existe)"""
    data = Path(img_path).read_bytes() if Path(img_path).is_file() else b""
    return base64.b64encode(data).decode()


def inject_global_css() -> None:
    """Aplica fondo, favicon y fuerza todo texto a blanco + negritas"""
    bg_b64   = _b64_encode(BG_PATH)
    logo_b64 = _b64_encode(LOGO_PATH)

    st.markdown(
        f"""
        <style>
        /* Fondo principal y estilo global de texto */
        .stApp {{
            background: url('data:image/png;base64,{bg_b64}') center/cover fixed;
            color: #ffffff;             /* texto blanco */
            font-weight: 700;           /* negritas */
        }}
        /* Aseguramos que absolutamente todo el texto sea blanco y bold */
        html, body, input, label, textarea, select, button, [class^="css"] {{
            color: #ffffff !important;
            font-weight: 700 !important;
        }}

        /* Header transparente para continuidad del fondo */
        [data-testid="stHeader"] {{background: transparent;}}

        /* Pestañas (cintillo) */
        .stTabs [role="tab"] > div {{
            color: #ffffff !important;
            font-weight: 700 !important;
        }}
        .stTabs [aria-selected="true"] > div {{
            color: #0aa9ff !important;  /* resalta la activa */
        }}

        /* Botones */
        .stButton>button {{
            background-color:#0aa9ff;
            color:#ffffff;
            font-weight:700;
            border:0;
        }}
        .stButton>button:hover {{background-color:#007acc;}}

        /* DataFrame */
        .css-1d391kg tbody td, .css-1d391kg thead th {{
            color: #ffffff !important;
            font-weight: 700 !important;
        }}
        </style>
        """,
        unsafe_allow_html=True,
    )

    if logo_b64:
        st.markdown(
            f"<link rel=\"icon\" href=\"data:image/png;base64,{logo_b64}\">",
            unsafe_allow_html=True,
        )

# FUNCIÓN DE AUTENTICACIÓN



def require_login() -> None:
    """Muestra una pantalla de inicio de sesión y detiene la app si no ha iniciado sesión"""
    # Credenciales fijas
    VALID_USER = "mdet"
    VALID_PASS = "diego"

    if "authenticated" not in st.session_state:
        st.session_state["authenticated"] = False

    if st.session_state["authenticated"]:
        # (opcional) permitir cerrar sesión desde el sidebar
        if st.sidebar.button("Cerrar sesión"):
            st.session_state["authenticated"] = False
            st.experimental_rerun()
        return  # usuario ya autenticado

    # Caso no autenticado: mostramos formulario
    st.markdown("""
    <div style='text-align:center;margin-top:8rem;'>
        <h2>Identificación de Usuario</h2>
    </div>""", unsafe_allow_html=True)

    user = st.text_input("Usuario", key="login_user")
    pwd  = st.text_input("Contraseña", type="password", key="login_pass")

    col1, col2, col3 = st.columns([1,2,1])
    with col2:
        if st.button("Acceder", type="primary"):
            if user == VALID_USER and pwd == VALID_PASS:
                st.session_state["authenticated"] = True
                st.rerun()
            else:
                st.error("Credenciales inválidas. Intenta de nuevo.")

    st.stop()  # detiene el script para que no se ejecute el resto mientras no se valide


# REST CLIENT



def post_user(user_id: str, name: str, lastname: str, available: int) -> bool:
    data = {
        "api_key": WRITE_API_KEY_USERS,
        "field1": user_id,
        "field2": name,
        "field3": lastname,
        "field4": available,
    }
    r = requests.post(f"{BASE_URL}/update.json", data=data, headers=HEADERS, timeout=TIMEOUT)
    return r.ok and r.text != "0"


def _get_feeds(channel_id: str, read_key: str, results: int = 8000) -> List[dict]:
    params = {"api_key": read_key, "results": results}
    try:
        r = requests.get(f"{BASE_URL}/channels/{channel_id}/feeds.json", params=params, timeout=TIMEOUT)
        r.raise_for_status()
        return r.json().get("feeds", [])
    except Exception:
        return []


def get_all_users() -> List[dict]:
    return _get_feeds(ID_CANAL_USERS, READ_API_KEY_USERS)


def get_last_accesses(n: int = 30) -> List[dict]:
    return _get_feeds(ID_CANAL_ACCESS, READ_API_KEY_ACCESS, n)


def latest_users_dict() -> "OrderedDict[str, Tuple[str, str, int]]":
    feeds = get_all_users()
    feeds.sort(key=lambda x: x["created_at"], reverse=True)
    latest: "OrderedDict[str, Tuple[str, str, int]]" = OrderedDict()
    for f in feeds:
        uid = f.get("field1")
        if uid and uid not in latest:
            latest[uid] = (
                f.get("field2", ""),
                f.get("field3", ""),
                int(f.get("field4") or 0),
            )
    return latest


# CACHÉ STREAMLIT

@st.cache_data(ttl=30, show_spinner=False)
def cached_latest_users() -> "OrderedDict[str, Tuple[str, str, int]]":
    return latest_users_dict()

@st.cache_data(ttl=30, show_spinner=False)
def cached_last_accesses(n: int = 30) -> List[dict]:
    return get_last_accesses(n)


# PÁGINAS


def page_create():
    st.header("Crear nuevo usuario")
    with st.form("frm_create", clear_on_submit=False):
        col1, col2 = st.columns(2)
        with col1:
            uid  = st.text_input("ID", key="create_id")
            name = st.text_input("Nombre", key="create_name")
        with col2:
            last   = st.text_input("Apellido", key="create_last")
            acc_opt = st.radio("Acceso", ["Sí", "No"], horizontal=True, key="create_acc")
        if st.form_submit_button("Crear usuario", type="primary"):
            if not (uid and name and last):
                st.warning("Completa todos los campos.")
            else:
                ok = post_user(uid.strip(), name.strip(), last.strip(), 1 if acc_opt == "Sí" else 0)
                if ok:
                    st.success("Usuario creado correctamente.")
                    st.cache_data.clear()
                else:
                    st.error("No se pudo crear el usuario. Intenta de nuevo.")


def page_modify():
    st.header("Modificar usuario")
    users = cached_latest_users()
    if not users:
        st.info("No hay usuarios cargados.")
        return

    options = [f"{uid} – {v[0]} {v[1]}" for uid, v in users.items()]
    sel = st.selectbox("Selecciona usuario", options, key="modify_sel")
    uid = sel.split(" – ")[0]
    name, last, acc = users[uid]

    st.write(f"**Acceso actual**: {'Sí' if acc else 'No'}")
    new_acc = st.radio("Nuevo acceso", ["Sí", "No"], index=0 if acc else 1, horizontal=True, key="modify_acc")
    if st.button("Guardar cambios", key="btn_modify", type="primary"):
        ok = post_user(uid, name, last, 1 if new_acc == "Sí" else 0)
        if ok:
            st.success("Estado actualizado.")
            st.cache_data.clear()
        else:
            st.error("No se pudo actualizar. Intenta de nuevo.")


def page_users():
    st.header("Lista de usuarios")
    if st.button("Actualizar", key="refresh_users"):
        st.cache_data.clear()
    users = cached_latest_users()
    df = pd.DataFrame([
        {"ID": uid, "Nombre": n, "Apellido": a, "Acceso": "Sí" if ac else "No"}
        for uid, (n, a, ac) in users.items()
    ])
    st.dataframe(df, use_container_width=True, hide_index=True)


def page_access():
    st.header("Accesos recientes")
    if st.button("Actualizar", key="refresh_access"):
        st.cache_data.clear()

    accesses  = cached_last_accesses(30)
    users_map = cached_latest_users()

    accesses.sort(key=lambda x: x["created_at"], reverse=True)
    data: List[Dict[str, str]] = []
    for acc in accesses:
        ts = acc["created_at"].replace("T", " ")[:19]
        uid = acc.get("field1", "")
        name, last, *_ = users_map.get(uid, ("-", "-", 0))
        data.append({"Fecha": ts, "ID": uid, "Nombre": name, "Apellido": last})
    df = pd.DataFrame(data)
    st.dataframe(df, use_container_width=True, hide_index=True)


# MAIN


def main():
    # Configuración general de la página
    st.set_page_config(
        page_title="C.L.A.V.E • Gestión de Usuarios",
        page_icon=LOGO_PATH if Path(LOGO_PATH).is_file() else "🔑",
        layout="centered",
        initial_sidebar_state="collapsed",
    )

    inject_global_css()

    #  Autenticacion
    require_login()  # detiene el script si el usuario no ha iniciado sesión

    #  Interfaz principal 

    if Path(LOGO_PATH).is_file():
        st.image(LOGO_PATH, width=220)
    st.markdown("<h2 style='text-align:center;margin-top:-1rem;'>Gestión de Usuarios</h2>", unsafe_allow_html=True)
    st.markdown("<br>", unsafe_allow_html=True)

    tabs = st.tabs(["Crear", "Modificar", "Usuarios", "Accesos"])
    with tabs[0]:
        page_create()
    with tabs[1]:
        page_modify()
    with tabs[2]:
        page_users()
    with tabs[3]:
        page_access()

    st.markdown(
        """<hr style='margin-top:3rem;margin-bottom:1rem;border-top:1px solid #666;'>
        <div style='text-align:center;font-size:0.8rem;color:#aaa;'>
        &copy; 2025 Proyecto C.L.A.V.E - Construido con Streamlit
        </div>""",
        unsafe_allow_html=True,
    )


if __name__ == "__main__":
    main()
