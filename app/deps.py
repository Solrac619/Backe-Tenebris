from fastapi import Header, HTTPException
from app.supabase_cliente import supabase

def get_current_user(authorization: str = Header(...)):
    if not authorization.startswith("Bearer "):
        raise HTTPException(401, "Invalid Authorization header")

    token = authorization.split(" ")[1]

    try:
        user = supabase.auth.get_user(token).user
        return user  # uid, email, etc
    except Exception as e:
        print("Auth error:", e)
        raise HTTPException(401, "Invalid or expired token")
