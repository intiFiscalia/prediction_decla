# Taxonomía versionada de fenómenos criminales — GIC
# Todas las expresiones se aplican sobre texto en minúsculas y sin tildes.
TAXONOMIA_VERSION = "v1.0 (2026-11-18)"

# Mapeo de TematicaPriorizada (registrado) -> fenómeno de la taxonomía
TEMATICA_A_FENOMENO = {
    "lavado de activos": "Lavado de activos",
    "narcotrafico": "Narcotráfico",
    "captacion masiva": "Captación masiva e ilegal",
    "corrupcion": "Corrupción",
    "enriquecimiento ilicito": "Enriquecimiento ilícito",
    "organizaciones criminales": "Crimen organizado / concierto",
    "concierto para delinquir": "Crimen organizado / concierto",
    "extorsion": "Extorsión",
    "contrabando": "Contrabando",
    "tributario": "Delitos tributarios",
    "estafa": "Estafa y fraude",
    "fraude": "Estafa y fraude",
    "trata de personas": "Trata y tráfico de personas",
    "medio ambiente": "Delitos ambientales y minería ilegal",
    "mineria ilegal": "Delitos ambientales y minería ilegal",
    "explotacion ilicita de yacimiento minero": "Delitos ambientales y minería ilegal",
    "financiacion del terrorismo": "Financiación de grupos armados / terrorismo",
    "trafico, fabricacion y porte ilegal de armas": "Tráfico de armas",
    "hurto": "Hurto",
    "hurtos": "Hurto",
    "trafico, fabricacion o porte de estupefacientes": "Narcotráfico",
    "trafico ilicito de migrantes": "Trata y tráfico de personas",
}
# Temáticas registradas que en la taxonomía son mecanismos de lavado, no fenómenos
TEMATICA_A_MECANISMO = {"criptoactivos": "Criptoactivos", "empresa fachada": "Empresas fachada o de papel"}

FENOMENOS = {
    "Lavado de activos": [r"lavado de (activos|dinero|capitales)", r"blanqueo"],
    "Narcotráfico": [r"narcotrafic", r"estupefaciente", r"cocaina", r"marihuana", r"clorhidrato", r"alcaloide", r"\bdrogas?\b", r"cartel"],
    "Captación masiva e ilegal": [r"captacion (masiva|ilegal|habitual|no autorizada)", r"esquema (ponzi|piramidal)", r"\bpiramide", r"captacion de (recursos|dineros)"],
    "Corrupción": [r"corrupci", r"peculado", r"cohecho", r"interes indebido", r"soborno", r"celebracion indebida", r"prevaricato", r"concusion"],
    "Enriquecimiento ilícito": [r"enriquecimiento ilicito", r"incremento patrimonial (injustificado|no justificado)", r"incremento (patrimonial )?injustificado"],
    "Extorsión": [r"extorsi", r"\bvacunas?\b", r"cobro de cuotas"],
    "Usura (gota a gota)": [r"gota a gota", r"\busura", r"prestamos? informal"],
    "Contrabando": [r"contrabando", r"evasion aduanera", r"fraude aduanero", r"mercancia(s)? (ilegal|de contrabando)"],
    "Delitos tributarios": [r"evasion (fiscal|tributaria)", r"defraudacion (fiscal|tributaria)", r"omision de agente retenedor", r"facturas? (falsas|ficticias)", r"factura(cion)? ficticia"],
    "Estafa y fraude": [r"\bestafa", r"\bfraude", r"suplantaci", r"phishing", r"\bfalsedad"],
    "Financiación de grupos armados / terrorismo": [r"financiacion del terrorismo", r"financiacion de grupos", r"grupo armado", r"disidencia", r"clan del golfo", r"\beln\b", r"\bfarc\b", r"\bgao\b"],
    "Crimen organizado / concierto": [r"concierto para delinquir", r"organizacion criminal", r"banda criminal", r"red criminal", r"estructura criminal", r"grupo delincuencial", r"\bgdo\b"],
    "Delitos ambientales y minería ilegal": [r"mineria ilegal", r"explotacion ilicita", r"yacimiento minero", r"deforestaci", r"trafico de fauna", r"\bambiental"],
    "Trata y tráfico de personas": [r"trata de personas", r"trafico de migrantes", r"explotacion sexual", r"proxenet"],
    "Tráfico de armas": [r"trafico de armas", r"porte de armas", r"armas de fuego", r"municiones"],
    "Hurto": [r"\bhurto", r"fleteo", r"\brobos?\b"],
}

# Patrones adicionales (tomados de la taxonomía de "delito fuente" que antes vivía aparte, en la sección 10).
# pipeline.py solo los aplica a relatos cuyo único fenómeno es "Lavado de activos", para intentar segregarlos
# en un fenómeno ya existente arriba, sin tocar los relatos que ya tenían otro fenómeno identificado.
FENOMENOS_LAVADO_EXTRA = {
    "Narcotráfico": [r"\bnarco", r"doble fondo", r"sustancias? (ilicitas|estupefacientes)"],
    "Delitos ambientales y minería ilegal": [r"mineria (ilicita|criminal)", r"\byacimiento\b", r"\bminerales\b", r"\boro\b", r"trafico de madera", r"\bdragas?\b"],
    "Contrabando": [r"aduaner", r"\bdian\b.*mercanc", r"mercanc[ia]+s? sin declarar", r"sobrefacturaci", r"subfacturaci", r"importaciones? (ficticias|ilegales)", r"exportaciones? (ficticias|ilegales)"],
    "Usura (gota a gota)": [r"prestamos? ilegales"],
    "Trata y tráfico de personas": [r"trafico ilicito de migrantes"],
    "Crimen organizado / concierto": [r"tren de aragua"],
    "Corrupción": [r"contrato(s)? (estatal|public)", r"contratacion (estatal|publica|directa)", r"recursos publicos", r"\bsecop", r"adjudicacion", r"\balcald", r"gobernaci", r"(ex)?funcionari[oa]s? public", r"servidor(es)? public", r"exministr", r"\bconcejal", r"congresista"],
    "Enriquecimiento ilícito": [r"incremento patrimonial", r"patrimonio (injustificado|no justificado)", r"desbalance patrimonial"],
    "Captación masiva e ilegal": [r"captacion", r"capatacion", r"dineros? del publico", r"intervencion (administrativa|judicial|por)", r"medida de intervencion", r"rentabilidad(es)? (del|de hasta|mensual)", r"inversionistas"],
    "Estafa y fraude": [r"medios informaticos", r"\bciber", r"documentos? falsos?"],
    "Delitos tributarios": [r"proveedores ficticios", r"devolucion(es)? (de )?iva", r"\bevasion\b"],
}

# Mecanismos de lavado de activos (subtaxonomía)
MECANISMOS = {
    "Empresas fachada o de papel": [r"(empresa|sociedad|compania)s? (de )?(fachada|papel|pantalla|fantasma)", r"reciente constitucion", r"sin (operacion|actividad|infraestructura)", r"fachada"],
    "Testaferrato": [r"testaferr", r"interpuesta persona", r"presta ?nombres?"],
    "Fraccionamiento (pitufeo)": [r"fraccionad", r"fraccionamiento", r"pitufeo", r"pitufos"],
    "Mercado cambiario y giros": [r"mercado cambiario", r"\bdivisas", r"\bgiros?\b", r"remesas", r"casa de cambio", r"moneda extranjera", r"operaciones? cambiarias?", r"dolares"],
    "Criptoactivos": [r"cripto", r"bitcoin", r"\busdt\b", r"binance", r"tether", r"blockchain"],
    "Comercio exterior (TBML)": [r"importaci", r"exportaci", r"comercio exterior", r"sobrefacturaci", r"subfacturaci", r"zona franca", r"declaraciones? de importacion"],
    "Uso de efectivo": [r"efectivo"],
    "Transferencias y cuentas bancarias": [r"transferencias?", r"cuentas? (bancarias|de ahorro|corriente)", r"consignaci", r"\bach\b"],
    "Cheques": [r"cheques?"],
    "Contratación estatal": [r"contrato(s)? (estatal|public)", r"contratacion (estatal|publica|directa)", r"\bsecop", r"licitaci", r"recursos publicos"],
    "Juegos de suerte y azar": [r"casino", r"apuestas?", r"juegos? de (suerte|azar)", r"loteria", r"\bchance\b"],
    "Pasarelas de pago y fintech": [r"pasarela(s)? de pago", r"billetera", r"\bnequi\b", r"daviplata", r"fintech", r"payment"],
    "Entidades sin ánimo de lucro": [r"fundacion", r"sin animo de lucro", r"\besal\b", r"cooperativa"],
    "Productos de inversión y valores": [r"fiducia", r"\bcdt", r"\bacciones\b", r"fondo de inversion", r"titulos valores"],
}

# Bienes (activos) mencionados
BIENES = {
    "Inmuebles": [r"inmueble", r"apartamento", r"\bfinca", r"\blotes?\b", r"predio", r"bodega", r"\bcasas?\b"],
    "Vehículos": [r"vehiculo", r"camioneta", r"automotor", r"motocicleta", r"\bcarros?\b"],
    "Aeronaves y embarcaciones": [r"aeronave", r"avioneta", r"helicoptero", r"embarcacion", r"\blancha", r"semisumergible", r"\byate"],
    "Oro y metales preciosos": [r"\boro\b", r"metales preciosos", r"esmeralda"],
    "Ganado": [r"ganad", r"semoviente", r"bovino", r"\breses\b"],
    "Criptoactivos": [r"cripto", r"bitcoin", r"\busdt\b"],
    "Efectivo y divisas": [r"efectivo", r"\bdivisas", r"dolares", r"\beuros?\b"],
    "Participaciones societarias": [r"\bacciones\b", r"cuotas (sociales|partes)", r"participacion(es)? (accionaria|societaria)"],
    "Joyas y arte": [r"\bjoyas?", r"obras? de arte", r"relojes"],
}

# Sectores económicos — secciones CIIU Rev. 4 A.C. (DANE)
SECTORES = {
    "A": ("Agropecuario", [r"agricol", r"agropecuar", r"ganader", r"cultivo", r"\bpalma\b", r"pecuari", r"avicola", r"agroindustri"]),
    "B": ("Minas y canteras", [r"\bminer", r"\bmina\b", r"\boro\b", r"carbon", r"esmeralda", r"hidrocarburo", r"petrole", r"yacimiento"]),
    "C": ("Industria manufacturera", [r"manufactur", r"fabricacion", r"textil", r"confecci", r"\bcalzado"]),
    "F": ("Construcción", [r"construcci", r"constructora", r"obras? civil", r"urbaniz", r"edificio"]),
    "G": ("Comercio", [r"comercializadora", r"comercio (al por|de)", r"importador", r"exportador", r"distribuidora", r"almacen", r"compraventa", r"estanco"]),
    "H": ("Transporte y logística", [r"transporte", r"logistic", r"\bcarga\b", r"naviera", r"courier", r"mensajeria"]),
    "I": ("Alojamiento y comida", [r"hotel", r"restaurante", r"turism", r"discoteca", r"hostal", r"\bbar\b"]),
    "J": ("Información y TIC", [r"software", r"informatic", r"telecomunic", r"plataforma digital", r"procesamiento de datos", r"call center"]),
    "K": ("Financiero y seguros", [r"entidad(es)? financiera", r"sector financiero", r"fintech", r"pasarela", r"casa de cambio", r"profesional(es)? de (compra y venta de )?divisas", r"cooperativa", r"fiducia", r"aseguradora", r"fondo de inversion", r"plataforma de inversion", r"exchange", r"captacion", r"rentista de capital"]),
    "L": ("Inmobiliario", [r"inmobiliari", r"finca raiz", r"bienes raices", r"arrendamiento"]),
    "M": ("Profesionales y consultoría", [r"consultor", r"asesori", r"abogad", r"contador", r"servicios profesionales", r"administracion empresarial"]),
    "N": ("Servicios administrativos y de apoyo", [r"agencia de viajes", r"seguridad privada", r"vigilancia", r"servicio(s)? de apoyo"]),
    "O": ("Administración pública", [r"alcald", r"gobernaci", r"entidad(es)? public", r"servidor(es)? public", r"funcionario(s)? public", r"concejal", r"\bsecop"]),
    "P": ("Educación", [r"universidad", r"colegio", r"educaci"]),
    "Q": ("Salud", [r"\bsalud\b", r"\beps\b", r"\bips\b", r"hospital", r"clinica", r"farmac", r"medicamento"]),
    "R": ("Entretenimiento, deporte y azar", [r"casino", r"apuesta", r"juegos? de (suerte|azar)", r"futbol", r"deportiv", r"espectaculo", r"artista"]),
    "S": ("Otros servicios / ESAL", [r"fundacion", r"sin animo de lucro", r"iglesia", r"asociacion"]),
}

def ciiu_seccion(cod4: str):
    d = int(cod4[:2])
    if cod4 in ("0010", "0020", "0081", "0082", "0090"):
        return None  # códigos DIAN de no actividad (asalariado, pensionado, rentista) -> se tratan aparte
    rangos = [(1, 3, "A"), (5, 9, "B"), (10, 33, "C"), (35, 35, "D"), (36, 39, "E"), (41, 43, "F"), (45, 47, "G"),
              (49, 53, "H"), (55, 56, "I"), (58, 63, "J"), (64, 66, "K"), (68, 68, "L"), (69, 75, "M"), (77, 82, "N"),
              (84, 84, "O"), (85, 85, "P"), (86, 88, "Q"), (90, 93, "R"), (94, 96, "S"), (97, 98, "T"), (99, 99, "U")]
    for a, b, s in rangos:
        if a <= d <= b:
            return s
    return None

SECCION_NOMBRE_EXTRA = {"D": "Energía", "E": "Agua y residuos", "T": "Hogares", "U": "Organismos extraterritoriales"}

# Organizaciones criminales: patrón -> (nombre canónico, tipología)
ORGANIZACIONES = [
    (r"clan del golfo|autodefensas gaitanistas|\bagc\b|\begc\b|ejercito gaitanista|urabenos|otoniel", "Clan del Golfo (EGC/AGC)", "GAO"),
    (r"\beln\b|ejercito de liberacion nacional", "ELN", "Guerrilla"),
    (r"calarca|estado mayor de bloques|\bembf\b|jorge (suarez )?bri[cs]eno", "Disidencias FARC – EMBF (Calarcá / Bloque Jorge Suárez Briceño)", "GAOr (disidencia)"),
    (r"estado mayor central|\bemc\b|mordisco", "Disidencias FARC – EMC (Iván Mordisco)", "GAOr (disidencia)"),
    (r"segunda marquetalia|comandos de la frontera", "Segunda Marquetalia / Comandos de la Frontera", "GAOr (disidencia)"),
    (r"tren de aragua", "Tren de Aragua", "Transnacional"),
    (r"rastrojos", "Los Rastrojos", "GDO / GAO"),
    (r"autodefensas conquistadoras|pachenca|\bacsn\b", "ACSN (Los Pachenca)", "GAO"),
    (r"oficina de envigado", "La Oficina (Envigado)", "GDO"),
    (r"la cordillera|gdo.cordillera", "La Cordillera", "GDO"),
    (r"caparr", "Los Caparros", "GAO"),
    (r"los mexicanos", "Los Mexicanos", "GDO"),
    (r"los costenos", "Los Costeños", "GDO"),
    (r"los del alto|altos de aranjuez", "Los del Alto (Aranjuez)", "GDO"),
    (r"banda la r\b", "La R", "GDO"),
    (r"rhenals", "Banda Rhenals", "GDO"),
    (r"norte del valle", "Cartel del Norte del Valle (histórico)", "Narcotráfico histórico"),
    (r"sinaloa|zambada", "Cartel de Sinaloa", "Transnacional"),
    (r"jalisco nueva generacion|\bcjng\b", "CJNG", "Transnacional"),
    (r"carteles mexicanos", "Carteles mexicanos (sin especificar)", "Transnacional"),
    (r"cartel de los soles", "Cartel de los Soles", "Transnacional"),
    (r"comando vermelho", "Comando Vermelho", "Transnacional"),
    (r"choneros|los lobos", "Los Choneros / Los Lobos", "Transnacional"),
    (r"ndrangheta|mafia italiana", "Mafia italiana", "Transnacional"),
    (r"clan isaza|autodefensas campesinas del magdalena", "ACMM (Clan Isaza)", "GAO"),
]
# Disidencia genérica (solo si no se identificó una específica)
ORG_GENERICA_DISIDENCIA = (r"disidencia(s)? (de (las )?)?farc|\bgaor\b|disidencias", "Disidencias FARC (sin especificar)", "GAOr (disidencia)")
ORG_GENERICA_FARC = (r"\bfarc\b", "FARC-EP (referencia histórica)", "Guerrilla (histórica)")
ORG_SIN_NOMBRE = (r"organizacion criminal|estructura criminal|red criminal|banda criminal|grupo delincuencial|\bgdo\b|grupo armado organizado", "Organización mencionada sin nombre", "No identificada")

# Registrado: GrupoEstructura / Estructura
ORG_REGISTRADA = {
    "AGC-CLAN DEL GOLFO": ("Clan del Golfo (EGC/AGC)", "GAO"),
    "ELN": ("ELN", "Guerrilla"),
    "GAOR/DISIDENCIAS": ("Disidencias FARC (sin especificar)", "GAOr (disidencia)"),
    "TREN DE ARAGUA": ("Tren de Aragua", "Transnacional"),
    "GAOR JORGE BRICENO": ("Disidencias FARC – EMBF (Calarcá / Bloque Jorge Suárez Briceño)", "GAOr (disidencia)"),
    "LOS RASTROJOS": ("Los Rastrojos", "GDO / GAO"),
    "GDO/GDCO": ("GDO/GDCO (sin nombre registrado)", "GDO"),
}
