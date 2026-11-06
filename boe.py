"""Lee el sumario diario del BOE (API de datos abiertos) y guarda en web/noticias.json
las disposiciones que afectan a pymes. Solo copia título, organismo, fecha y enlace oficial.
Uso: python scripts/boe.py            -> hoy
     python scripts/boe.py --dias 30  -> últimos 30 días (primera carga)"""
import json, re, sys, time, unicodedata, urllib.request, urllib.error
from datetime import date, timedelta
from pathlib import Path

SALIDA = Path(__file__).resolve().parent / "noticias.json"
MAX = 300
SECCIONES = {"1", "3"}  # I. Disposiciones generales, III. Otras disposiciones

def norm(t):
    t = unicodedata.normalize("NFD", t.lower())
    return "".join(c for c in t if unicodedata.category(c) != "Mn")

# Orden = prioridad. Cada categoría: patrones (sin tildes, en minúscula).
REGLAS = [
    ("Morosidad", [r"morosidad", r"plazos de pago", r"ley concursal", r"concurso de acreedores"]),
    ("Fiscal", [r"impuesto sobre el valor anadido", r"impuesto sobre sociedades", r"impuesto sobre la renta",
                r"agencia estatal de administracion tributaria.*modelo", r"\bmodelo \d{3}\b",
                r"factura", r"verifactu|veri\*factu", r"ley general tributaria", r"recargo de equivalencia"]),
    ("Laboral", [r"salario minimo", r"cotizacion", r"seguridad social.*(empresa|cotiz|base)",
                 r"convenio colectivo.*(metal|construccion|publicidad|panader|pasteler|confiter|"
                 r"instalac|electric|climatizacion|fontaner|obrador|comercio)",
                 r"jornada (laboral|de trabajo)", r"registro (horario|de jornada)", r"estatuto de los trabajadores"]),
    ("Ayudas", [r"(ayudas|subvenciones|convocatoria).*(pyme|pequenas y medianas|autonom|empresas|"
                r"digitaliz|kit digital|eficiencia energetica|industria|emprend)",
                r"linea(s)? (ico|de avales|de financiacion)", r"\bico\b", r"\benisa\b", r"kit digital"]),
    ("Energía", [r"autoconsumo", r"eficiencia energetica", r"instalaciones (electricas|termicas)",
                 r"baja tension", r"gases fluorados", r"reglamento de instalaciones termicas", r"bomba de calor"]),
]
EXCLUIR = [r"\bnombra", r"\bcese\b", r"oposicion", r"proceso selectivo", r"universidad", r"premio",
           r"\bbeca", r"corrige(n)? errores en la resolucion de.*(nombra|oposicion)"]

def categoria(titulo):
    t = norm(titulo)
    if any(re.search(p, t) for p in EXCLUIR):
        return None
    for cat, pats in REGLAS:
        if any(re.search(p, t) for p in pats):
            return cat
    return None

def lista(x):
    if x is None: return []
    return x if isinstance(x, list) else [x]

def sumario(d):
    url = f"https://www.boe.es/datosabiertos/api/boe/sumario/{d:%Y%m%d}"
    req = urllib.request.Request(url, headers={"Accept": "application/json", "User-Agent": "dirfisa-web"})
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return json.load(r)
    except urllib.error.HTTPError as e:
        if e.code == 404:  # día sin BOE (domingos)
            return None
        raise

def extraer(js, d):
    out = []
    for diario in lista(js["data"]["sumario"].get("diario")):
        for sec in lista(diario.get("seccion")):
            if str(sec.get("codigo")) not in SECCIONES:
                continue
            for dep in lista(sec.get("departamento")):
                items = lista(dep.get("item"))
                for ep in lista(dep.get("epigrafe")):
                    items += lista(ep.get("item"))
                for it in items:
                    cat = categoria(it.get("titulo", ""))
                    if not cat:
                        continue
                    out.append({
                        "id": it["identificador"],
                        "fecha": d.isoformat(),
                        "titulo": it["titulo"].strip(),
                        "organismo": dep.get("nombre", "").strip(),
                        "categoria": cat,
                        "url": it.get("url_html") or f"https://www.boe.es/diario_boe/txt.php?id={it['identificador']}",
                    })
    return out

def main():
    dias = int(sys.argv[sys.argv.index("--dias") + 1]) if "--dias" in sys.argv else 1
    actuales = json.loads(SALIDA.read_text(encoding="utf-8")) if SALIDA.exists() else []
    vistos = {n["id"] for n in actuales}
    nuevas = []
    for i in range(dias):
        d = date.today() - timedelta(days=i)
        js = sumario(d)
        if js:
            nuevas += [n for n in extraer(js, d) if n["id"] not in vistos]
            vistos.update(n["id"] for n in nuevas)
        time.sleep(0.5)
    todo = sorted(actuales + nuevas, key=lambda n: (n["fecha"], n["id"]), reverse=True)[:MAX]
    SALIDA.write_text(json.dumps(todo, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"{len(nuevas)} novedades nuevas, {len(todo)} en total")

if __name__ == "__main__":
    main()
