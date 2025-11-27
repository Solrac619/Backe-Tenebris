
from pydantic import BaseModel

class GameData(BaseModel):
    # gameSessionID será generado por el backend, no lo requerimos en el POST
    gameSessionID: str | None = None
    score: int = 0
    currentZone: str = "Level 1"
    deaths: int = 0
    
    # Configuración opcional para soportar GameData con campos adicionales
    class Config:
        extra = "ignore" # Ignora campos que Unity pueda enviar y que no estén en la lista.