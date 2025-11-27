# app/main.py
from fastapi import FastAPI, Depends, HTTPException, UploadFile, File, Form
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.deps import get_current_user
from app import crud

from pathlib import Path
from datetime import datetime
import uuid

from tempfile import NamedTemporaryFile
import shutil
import os

import requests
from fastapi import Body

from app.supabase_cliente import supabase
from app.ai_embeddings import extract_pdf_chunks, store_embeddings, get_embedding

import os
GROQ_API_KEY = os.getenv("GROQ_API_KEY")


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

# IA / EMBEDDINGS

@app.post("/v1/lore/process_pdf")
async def process_pdf(pdf: UploadFile = File(...)):
    """
    1. Recibe el PDF
    2. Lo trocea
    3. Genera embeddings
    4. Guarda en Supabase
    """
    # Guardar temporalmente
    temp = NamedTemporaryFile(delete=False)
    shutil.copyfileobj(pdf.file, temp)
    temp.close()

    # Extraer chunks del PDF
    chunks = extract_pdf_chunks(temp.name)

    # Guardarlos con embeddings
    store_embeddings(chunks)

    return {"chunks": len(chunks), "status": "ok"}



GROQ_CHAT_MODEL = "llama-3.1-8b-instant"



@app.post("/v1/lore/chat")
async def lore_chat(question: str = Body(..., embed=True)):
    q_emb = get_embedding(question)

    query = supabase.rpc(
        "match_embeddings",
        {"query_embedding": q_emb, "match_count": 5}
    ).execute()

    if not query.data:
        return {"answer": "No hay datos en el lore. Debes cargar un PDF primero."}

    context_chunks = " ".join([r["chunk"] for r in query.data])

    headers = {"Authorization": f"Bearer {GROQ_API_KEY}"}
    payload = {
        "model": GROQ_CHAT_MODEL,
        "messages": [
            {
                "role": "system",
                "content": "Eres la Guía de los Lamentos. Hablas con un tono místico, oscuro y poético. No inventes lore nuevo, solo usa el contexto."
            },
            {
                "role": "user",
                "content": f"Contexto del lore:\n{context_chunks}\n\nPregunta: {question}"
            }
        ]
    }

    r = requests.post(
        "https://api.groq.com/openai/v1/chat/completions",
        json=payload,
        headers=headers
    ).json()

    if "choices" not in r:
        return {"answer": f"Groq falló: {r}"}

    return {"answer": r["choices"][0]["message"]["content"]}


# ---------------------------------------------------------
# FINAL
# ---------------------------------------------------------

@app.get("/")
def root():
    return {"message": "Tenebris API running with Supabase 🚀"}
