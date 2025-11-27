import fitz  # PyMuPDF
import os
from sentence_transformers import SentenceTransformer
from app.supabase_cliente import supabase

# -----------------------------
# CARGAR MODELO DE EMBEDDINGS
# -----------------------------
# Modelo recomendado: rápido, preciso y 100% gratuito
# Dimensión = 384
model = SentenceTransformer("all-MiniLM-L6-v2")


def extract_pdf_chunks(file_path: str, chunk_size=800, overlap=100):
    """
    Lee un PDF completo y lo divide en fragmentos (chunks) limpios.
    chunk_size = tamaño del fragmento en caracteres
    overlap = superposición entre fragmentos (para conservar contexto)
    """
    doc = fitz.open(file_path)
    full_text = ""

    for page in doc:
        full_text += page.get_text()

    # Limpiar texto
    full_text = full_text.replace("\n", " ").strip()

    chunks = []
    start = 0

    while start < len(full_text):
        end = start + chunk_size
        chunk = full_text[start:end]

        if len(chunk.strip()) > 0:
            chunks.append(chunk)

        start = end - overlap  # superposición

    return chunks


def get_embedding(text: str):
    """
    Genera un embedding usando el modelo gratuito all-MiniLM-L6-v2.
    Dimensión de salida: 384
    """
    try:
        emb = model.encode(text)
        return emb.tolist()  # convertir a lista para PGVector
    except Exception as e:
        print(f"❌ Error generando embedding: {e}")
        return None


def store_embeddings(chunks: list):
    """
    Guarda cada chunk y su embedding en Supabase.
    Usa la tabla lore_embeddings (embedding vector(384))
    """
    for chunk in chunks:
        emb = get_embedding(chunk)

        if emb is None:
            print("⚠️ Embedding falló. Chunk omitido.")
            continue

        supabase.table("lore_embeddings").insert({
            "chunk": chunk,
            "embedding": emb
        }).execute()

    print("✅ Embeddings guardados correctamente en Supabase.")
