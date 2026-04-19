""" Funciones para comprobar compatibilidad con CarPlay"""

modulos_compatibles_carplay = ["NBTEVO", "ENAVEVO"]

def carplay_check(modulo_nbt:str):
    if modulo_nbt in modulos_compatibles_carplay:
        return True
    else:
        return False


