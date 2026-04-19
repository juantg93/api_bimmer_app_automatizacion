""" Funciones para comprobar compatibilidad con CarPlay"""

modulos_compatibles_carplay = ["NBTEVO", "ENAVEVO"]

def carplay_check(modulo_nbt:str):
    print("Comprobando compatibilidad de carplay")
    print(f"Modulo HeadUnit del vehículo: {modulo_nbt}")

    if modulo_nbt in modulos_compatibles_carplay:
        print("El vehiculo es compatible con Carplay")
        return True
    else:
        print("El vehiculo no es compatible")
        return False


