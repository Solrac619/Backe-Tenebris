# app/supabase_cliente.py

import os
from dotenv import load_dotenv
from supabase import create_client

# Cargar variables del archivo .env
load_dotenv()

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_ANON_KEY = os.getenv("SUPABASE_ANON_KEY")

# Cliente supabase
supabase = create_client(SUPABASE_URL, SUPABASE_ANON_KEY)
