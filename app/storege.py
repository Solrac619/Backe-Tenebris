from app.supabase_cliente import supabase
from fastapi import UploadFile

def upload_file(user_id: str, file: UploadFile):
    filename = f"{user_id}/{file.filename}"

    content = file.file.read()

    supabase.storage.from_("uploads").upload(
        filename,
        content,
        file_options={"content-type": file.content_type},
    )

    # Obtener URL pública
    url = supabase.storage.from_("uploads").get_public_url(filename)

    return url
