# app/crud.py
from app.supabase_cliente import supabase


# ======================================================
# PROFILES (opcional, si manejas perfil extra del usuario)
# ======================================================

def get_profile(user_id: str):
    """
    Obtiene el perfil (tabla profiles).
    """
    res = supabase.table("profiles").select("*").eq("id", user_id).single().execute()
    return res.data


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


def list_media(user_id: str, page: int = 1, page_size: int = 20, type: str | None = None):
    """
    Lista media paginado.
    Soporta filtro por type ("wiki", "character", "stage", "youtube", etc.)
    """
    query = supabase.table("media").select("*").eq("user_id", user_id)

    if type:
        query = query.eq("type", type)

    start = (page - 1) * page_size
    end = start + page_size - 1

    res = (
        query
        .order("created_at", desc=True)
        .range(start, end)
        .execute()
    )

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

def upload_file(user_id: str, file):
    """
    Sube un archivo al bucket 'uploads' y retorna la URL pública.
    El archivo debe ser un `UploadFile` de FastAPI.
    """
    filename = f"{user_id}/{file.filename}"

    file_bytes = file.file.read()

    supabase.storage.from_("uploads").upload(
        filename,
        file_bytes,
        file_options={"content-type": file.content_type},
    )

    public_url = supabase.storage.from_("uploads").get_public_url(filename)

    return public_url
