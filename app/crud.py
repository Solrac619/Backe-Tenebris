# app/crud.py
from app.supabase_cliente import supabase
import requests
import os
from datetime import datetime


YOUTUBE_API_KEY = os.getenv("YOUTUBE_API_KEY")
YOUTUBE_CHANNEL_ID = os.getenv("YOUTUBE_CHANNEL_ID")

# ======================================================
# PROFILES
# ======================================================

def get_profile(user_id: str):
    res = supabase.table("profiles").select("*").eq("id", user_id).execute()

    if res.data:
        return res.data[0]

    default_profile = {
        "id": user_id,
        "display_name": "",
        "avatar_url": None
    }

    created = supabase.table("profiles").insert(default_profile).execute()
    return created.data[0]


def update_profile(user_id: str, data: dict):
    res = (
        supabase.table("profiles")
        .update(data)
        .eq("id", user_id)
        .execute()
    )
    return res.data[0] if res.data else None


def create_profile(user_id: str, display_name: str = "", avatar_url: str = None):
    payload = {
        "id": user_id,
        "display_name": display_name,
        "avatar_url": avatar_url
    }
    res = supabase.table("profiles").insert(payload).execute()
    return res.data[0]


# ======================================================
# MEDIA
# ======================================================

def create_media(data: dict):
    res = supabase.table("media").insert(data).execute()
    return res.data[0]


def get_media(media_id: str, user_id: str):
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

    if type == "youtube":
        query = query.eq("type", "youtube")
    else:
        query = query.eq("user_id", user_id)
        if type:
            query = query.eq("type", type)

    from_row = (page - 1) * pageSize
    to_row = from_row + pageSize - 1

    res = query.range(from_row, to_row).order("created_at", desc=True).execute()
    return res.data


def delete_media(media_id: str, user_id: str):
    res = (
        supabase.table("media")
        .delete()
        .eq("id", media_id)
        .eq("user_id", user_id)
        .execute()
    )
    return res.data


# ======================================================
# STORAGE
# ======================================================

def upload_file(user_id: str, file, type: str = None):
    safe_name = file.filename.replace(" ", "_").lower()

    if type == "avatar":
        filename = f"avatars/{safe_name}"
    elif type == "lore":
        filename = f"lore/{safe_name}"
    else:
        filename = f"{user_id}/{safe_name}"

    file_bytes = file.file.read()

    supabase.storage.from_("uploads").upload(
        filename,
        file_bytes,
        file_options={"content-type": file.content_type},
    )

    return supabase.storage.from_("uploads").get_public_url(filename)


# ======================================================
# YOUTUBE SYNC
# ======================================================

def sync_youtube_videos():
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
            "user_id": None,
        }

        inserted = supabase.table("media").insert(media).execute()
        new_items.append(inserted.data[0])

    return new_items


# ======================================================
# GAMES DATA
# ======================================================

def create_game_session(data: dict):
    try:
        res = supabase.table("games").insert(data).execute()
        return res.data[0] if res.data else None
    except Exception as e:
        print(f"Error creando sesión de juego: {e}")
        return None


def update_game_data(session_id: str, user_id: str, update_fields: dict):
    update_fields["updated_at"] = datetime.utcnow()

    try:
        res = (
            supabase.table("games")
            .update(update_fields)
            .eq("id", session_id)
            .eq("user_id", user_id)
            .execute()
        )
        return res.data[0] if res.data else None
    except Exception as e:
        print(f"Error actualizando datos de partida {session_id}: {e}")
        return None


def get_game_data_by_id(session_id: str, user_id: str):
    try:
        res = (
            supabase.table("games")
            .select("*")
            .eq("id", session_id)
            .eq("user_id", user_id)
            .single()
            .execute()
        )
        return res.data
    except Exception:
        return None
    
    
def get_latest_game_session(user_id: str):
    response = supabase.table("games") \
        .select("*") \
        .eq("user_id", user_id) \
        .order("created_at", desc=True) \
        .limit(1) \
        .execute()

    if response.data:
        return response.data[0]
    
    return None
