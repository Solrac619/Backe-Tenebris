# app/main.py
from fastapi import FastAPI, Depends, HTTPException, UploadFile, File, Form
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.deps import get_current_user
from app import crud

from pathlib import Path
from datetime import datetime
import uuid

# ---------------------------------------------------------
# CONFIG FASTAPI
# ---------------------------------------------------------

app = FastAPI(
    title="Tenebris API",
    version="2.0.0",
    description="Backend migrado completamente a Supabase"
)

# CORS (permite frontend acceder)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], 
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---------------------------------------------------------
# RUTAS
# ---------------------------------------------------------

@app.get("/v1/health")
def health():
    return {"status": "ok"}


# ============================
# USERS / PROFILE
# ============================

@app.get("/v1/users/me")
def me(user = Depends(get_current_user)):
    """
    Devuelve información del usuario autenticado desde Supabase Auth.
    """
    return user


@app.get("/v1/users/profile")
def get_profile(user = Depends(get_current_user)):
    profile = crud.get_profile(user.id)
    return profile


@app.patch("/v1/users/profile")
def update_profile(
    display_name: str | None = Form(None),
    avatar_url: str | None = Form(None),
    user = Depends(get_current_user)
):
    data = {}

    if display_name is not None:
        data["display_name"] = display_name

    if avatar_url is not None:
        data["avatar_url"] = avatar_url

    if not data:
        raise HTTPException(400, "No fields to update")

    updated = crud.update_profile(user.id, data)
    return updated


# ============================
# MEDIA (upload / list / delete)
# ============================

@app.post("/v1/gallery/youtube/sync")
def sync_youtube():
    new_items = crud.sync_youtube_videos()
    return {"added": len(new_items), "items": new_items}


@app.post("/v1/gallery/upload")
async def upload_media(
    file: UploadFile = File(...),
    title: str | None = Form(None),
    description: str | None = Form(None),
    type: str = Form("wiki"),
    user = Depends(get_current_user)
):
    # 1. Subir archivo
    url = crud.upload_file(user.id, file, type)

    # 2. Insertar en tabla media
    media = crud.create_media({
        "user_id": user.id,
        "url": url,
        "thumb_url": None,
        "title": title,
        "description": description,
        "type": type,
        "mime_type": file.content_type,
    })

    return media


@app.get("/v1/gallery")
def list_gallery(
    page: int = 1,
    pageSize: int = 20,
    type: str | None = None,
    user = Depends(get_current_user)
):
    """
    Obtiene media paginado con filtro opcional por type.
    """
    items = crud.list_media(user.id, page, pageSize, type)
    return {
        "page": page,
        "pageSize": pageSize,
        "total": len(items),
        "items": items,
    }


@app.get("/v1/gallery/{media_id}")
def get_media(media_id: str, user = Depends(get_current_user)):
    media = crud.get_media(media_id, user.id)
    if not media:
        raise HTTPException(404, "Media not found")
    return media


@app.delete("/v1/gallery/{media_id}")
def delete_media(media_id: str, user = Depends(get_current_user)):
    deleted = crud.delete_media(media_id, user.id)
    if not deleted:
        raise HTTPException(404, "Media not found or not allowed")
    return {"deleted": True}

    # ---------------------------------------------------------
# GAMES DATA
# ---------------------------------------------------------

# Importar el esquema Pydantic (asumiendo que se llama GameData)
# from app.schemas import GameData 
# Si no usas schemas.py, debes definir Pydantic.GameData en main.py

@app.post("/v1/games")
def create_game_session(
    data: GameData, 
    user = Depends(get_current_user)
):
    """
    Crea un nuevo registro de partida en Supabase. 
    Unity enviará un POST al inicio de la sesión.
    """
    # 1. Generar un UUID único para la partida
    session_id = str(uuid.uuid4())
    
    # 2. Preparar los datos iniciales
    game_data_to_insert = {
        "id": session_id,
        "user_id": user.id, # Asocia la partida al usuario autenticado
        "score": data.score,
        "currentZone": data.currentZone,
        "deaths": data.deaths,
        # Puedes añadir "created_at": datetime.now() si lo necesita Supabase
    }

    # 3. Insertar en la BD y manejar errores (función a crear en crud.py)
    created_game = crud.create_game_session(game_data_to_insert)

    if created_game is None:
        raise HTTPException(500, "Error creating game session in database.")

    # 4. Devolver el objeto GameData completo, incluyendo el ID
    # Esto es crucial para que Unity asigne el ID que usará para las actualizaciones (PUT)
    response_data = GameData(
        gameSessionID=session_id,
        score=created_game['score'],
        currentZone=created_game['currentZone'],
        deaths=created_game['deaths']
    )
    return response_data

@app.put("/v1/games/{session_id}")
def update_game_data(
    session_id: str,
    data: GameData,
    user = Depends(get_current_user)
):
    """
    Actualiza la puntuación, zona y muertes para una partida existente (ID único).
    Unity enviará un PUT cada vez que se actualice un valor.
    """
    # Preparar solo los campos que Unity actualiza
    update_fields = {
        "score": data.score,
        "currentZone": data.currentZone,
        "deaths": data.deaths,
        # Puedes añadir "updated_at": datetime.now()
    }

    # 1. Actualizar en la BD (función a crear en crud.py)
    updated_game = crud.update_game_data(session_id, user.id, update_fields)

    if not updated_game:
        # Se lanza error 404 si la partida no existe o el user_id no coincide
        raise HTTPException(404, "Game session not found or access denied.")

    return {"message": "Game data updated successfully"}


@app.get("/v1/games/{session_id}")
def get_game_data(session_id: str, user = Depends(get_current_user)):
    """
    Consulta los datos de una partida específica usando su ID.
    Útil para reanudar una partida guardada.
    """
    game_data = crud.get_game_data_by_id(session_id, user.id)

    if not game_data:
        raise HTTPException(404, "Game session not found or access denied.")

    # Formatear la respuesta para Unity
    response_data = GameData(
        gameSessionID=game_data['id'],
        score=game_data['score'],
        currentZone=game_data['currentZone'],
        deaths=game_data['deaths']
    )
    return response_data


# ---------------------------------------------------------
# FINAL
# ---------------------------------------------------------

@app.get("/")
def root():
    return {"message": "Tenebris API running with Supabase 🚀"}
