""" Objeto coche con toda su información """

class Coche:
    def __init__(self):
        self.vin = None
        self.production_date = None
        self.delivery_date = None
        self.last_know_km = None
        self.engine_nr = None
        self.transmision_nr = None
        self.production_ilevel = None
        self.last_know_ilevel = None
        self.engine = None
        self.drive_steering = None
        self.body_doors = None
        self.upholstery_color = None
        self.key_system = None
        self.headunit = None
        self.headunit_serial = None
        self.fecha_km = None
        self.archivos_software = None
        self.color_texto = None
        self.mapa = None

    def __str__(self):
        # Formatear fecha de KM (ISO timestamp → solo fecha)
        fecha_km_str = self.fecha_km.split("T")[0] if self.fecha_km else "(no disponible)"
        
        # Formatear archivos software (lista → bullets indentados)
        if self.archivos_software:
            archivos_str = "\n        • " + "\n        • ".join(self.archivos_software)
        else:
            archivos_str = " (no disponible)"
        
        return f"""
    🚗 <b>INFORMACIÓN DEL VEHÍCULO</b>

    🔍 <b>VIN:</b> {self.vin}
    📅 <b>Fecha - Producción:</b> {self.production_date}
    📅 <b>Fecha - Lanzamiento:</b> {self.delivery_date}
    🛣️ <b>Ultimos KM registrados:</b> {self.last_know_km}
        - Fecha: {fecha_km_str}
    ⚙️ <b>Motor nº:</b> {self.engine_nr}
        - Archivos Software:{archivos_str}
    🔧 <b>Transmisión:</b> {self.transmision_nr}
    📡 <b>Producción iLevel:</b> {self.production_ilevel}
    📡 <b>Ultimo iLevel:</b> {self.last_know_ilevel}
    🔩 <b>Motor:</b> {self.engine}
    🧭 <b>Drive, Steering:</b> {self.drive_steering}
    🚪 <b>Body, Doors:</b> {self.body_doors}
    🎨 <b>Tapicería, Color:</b> {self.upholstery_color}
        - Color: {self.color_texto if self.color_texto else "(no disponible)"}
    🔑 <b>Key System:</b> {self.key_system}
    📻 <b>Head Unit:</b> {self.headunit}
    🔢 <b>Head Unit Serial:</b> {self.headunit_serial}
    🛣️ <b>Mapa:</b> {self.mapa if self.mapa else "(no disponible)"}
    ⚠️ <b>Campañas Tecnicas:</b> (proximamente)
    """