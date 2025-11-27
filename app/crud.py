# app/crud.py
from app.supabase_cliente import supabase
import requests
import os

YOUTUBE_API_KEY = os.getenv("YOUTUBE_API_KEY")
YOUTUBE_CHANNEL_ID = os.getenv("YOUTUBE_CHANNEL_ID")

# ======================================================
# PROFILES (opcional, si manejas perfil extra del usuario)
# ======================================================

def get_profile(user_id: str):
    # Intentar obtener perfil
    res = supabase.table("profiles").select("*").eq("id", user_id).execute()

    if res.data and len(res.data) > 0:
        return res.data[0]

    # Si no existe → crearlo automáticamente
    default_profile = {
        "id": user_id,
        "display_name": "",
        "avatar_url": None
    }

    created = supabase.table("profiles").insert(default_profile).execute()

    return created.data[0]


def update_profile(user_id: str, data: dict):
    """
    Actualiza campos del perfil del usuario.
    """
    res = (
        supabase.table("profiles")
        .update(data)
        .eq("id", user_id)
        .execute()
    )
    return res.data[0] if res.data else None


def create_profile(user_id: str, display_name: str = "", avatar_url: str = None):
    """
    Crea el perfil del usuario después del registro.
    """
    payload = {
        "id": user_id,
        "display_name": display_name,
        "avatar_url": avatar_url
    }

    res = supabase.table("profiles").insert(payload).execute()
    return res.data[0]

# ======================================================
# MEDIA (wiki, personajes, escenarios, videos, etc.)
# ======================================================

def create_media(data: dict):
    """
    Inserta un registro en la tabla media.
    data: {
        "user_id": str,
        "url": str,
        "title": str | None,
        "description": str | None,
        "type": str,
        "thumb_url": str | None,
        "mime_type": str | None,
        "width": int | None,
        "height": int | None,
        "size_bytes": int | None
    }
    """
    res = supabase.table("media").insert(data).execute()
    return res.data[0]


def get_media(media_id: str, user_id: str):
    """
    Obtiene un media específico que pertenece a un usuario.
    """
    res = (
        supabase.table("media")
        .select("*")
        .eq("id", media_id)
        .eq("user_id", user_id)
        .single()
        .execute()
    )
    return res.data


def list_media(user_id: str, page: int, pageSize: int, type: str | None):
    query = supabase.table("media").select("*")

    # 🔥 Caso especial: videos públicos de YouTube
    if type == "youtube":
        query = query.eq("type", "youtube")
    else:
        # Usar user_id solo en uploads personales
        query = query.eq("user_id", user_id)

        if type:
            query = query.eq("type", type)

    # Paginación
    from_row = (page - 1) * pageSize
    to_row = from_row + pageSize - 1

    res = query.range(from_row, to_row).order("created_at", desc=True).execute()

    return res.data



def delete_media(media_id: str, user_id: str):
    """
    Elimina un media si pertenece al usuario.
    """
    res = (
        supabase.table("media")
        .delete()
        .eq("id", media_id)
        .eq("user_id", user_id)
        .execute()
    )
    return res.data


# ======================================================
# STORAGE (uploads)
# ======================================================

def upload_file(user_id: str, file, type: str = None):
    """
    Sube un archivo al bucket 'uploads' y retorna la URL pública.

    Si type == 'avatar' → lo guarda en uploads/avatars/
    Si no → uploads/<user_id>/
    """

    # Limpia el nombre del archivo
    safe_name = file.filename.replace(" ", "_").lower()

    # --- DESTINO SEGÚN TYPE ---
    if type == "avatar":
        filename = f"avatars/{safe_name}" 
    elif type == "lore":
        filename = f"lore/{safe_name}"  # Carpeta lore del usuario
    else:
        filename = f"{user_id}/{safe_name}"  # Carpeta del usuario

    file_bytes = file.file.read()

    # Subida al bucket
    supabase.storage.from_("uploads").upload(
        filename,
        file_bytes,
        file_options={"content-type": file.content_type},
    )

    # URL pública
    public_url = supabase.storage.from_("uploads").get_public_url(filename)
    return public_url



def sync_youtube_videos():
    """
    Obtiene videos del canal de YouTube y sincroniza con la tabla media.
    Solo inserta los que no existan.
    """

    url = (
        f"https://www.googleapis.com/youtube/v3/search?"
        f"key={YOUTUBE_API_KEY}&channelId={YOUTUBE_CHANNEL_ID}"
        f"&part=snippet,id&order=date&maxResults=20"
    )

    res = requests.get(url).json()

    if "items" not in res:
        return []

    new_items = []

    for item in res["items"]:
        if item["id"]["kind"] != "youtube#video":
            continue

        video_id = item["id"]["videoId"]
        youtube_url = f"https://youtu.be/{video_id}"

        # ¿Ya existe?
        exists = supabase.table("media").select("id").eq("url", youtube_url).execute()

        if exists.data:
            continue

        snippet = item["snippet"]

        thumbnail = snippet["thumbnails"]["high"]["url"]

        media = {
            "url": youtube_url,
            "thumb_url": thumbnail,
            "title": snippet["title"],
            "description": snippet.get("description", ""),
            "type": "youtube",
            "mime_type": "youtube",
            "user_id": None,  # viene de YouTube, no es de usuario
        }

        inserted = supabase.table("media").insert(media).execute()
        new_items.append(inserted.data[0])

        # ======================================================
# GAMES DATA
# ======================================================

def create_game_session(data: dict):
    """
    Inserta un nuevo registro de partida en la tabla 'games'.
    data debe incluir 'id' (UUID generado en main.py) y 'user_id'.
    Retorna el registro creado.
    """
    try:
        # El cliente de Supabase por defecto solo retorna los datos insertados
        res = supabase.table("games").insert(data).execute()
        return res.data[0] if res.data else None
    except Exception as e:
        print(f"Error creando sesión de juego: {e}")
        return None


def update_game_data(session_id: str, user_id: str, update_fields: dict):
    """
    Actualiza los campos (score, currentZone, deaths) de una partida existente.
    Asegura que la partida pertenezca al user_id autenticado.
    Retorna el registro actualizado o None.
    """
    try:
        res = (
            supabase.table("games")
            .update(update_fields)
            .eq("id", session_id)  # Busca por ID de partida
            .eq("user_id", user_id)  # Restringe la actualización al dueño
            .execute()
        )
        return res.data[0] if res.data else None
    except Exception as e:
        print(f"Error actualizando datos de partida {session_id}: {e}")
        return None


def get_game_data_by_id(session_id: str, user_id: str):
    """
    Obtiene los datos de una partida específica usando su ID.
    Asegura que la partida pertenezca al user_id autenticado.
    Retorna los datos del registro o None.
    """
    try:
        res = (
            supabase.table("games")
            .select("*")
            .eq("id", session_id)  # Busca por ID de partida
            .eq("user_id", user_id)  # Restringe la consulta al dueño
            .single() # Espera un único resultado
            .execute()
        )
        # El método .single() de la librería de Supabase retorna el 'data' directamente
        return res.data
    except Exception:
        # El cliente levanta una excepción si no encuentra el registro, 
        # lo que indica que no existe o el usuario no es el dueño.
        return None

    return new_items
