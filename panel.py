# panel.py — muestra en el navegador las corridas de banco.py
#
# Uso: python panel.py [--puerto 8765]    y abrir http://localhost:8765
#
# Solo lee evaluaciones/banco.sqlite y solo escucha en esta computadora. No usa ningún framework
# ni importa rag.py: arranca al instante y no necesita el modelo ni la base vectorial.

import argparse
import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlsplit

import banco

PAGINA = r"""<!doctype html>
<html lang="es">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Banco de pruebas</title>
<style>
  :root { color-scheme: light dark; --fondo: #f7f7f5; --panel: #fff; --texto: #1f2328; --suave: #636c76;
          --borde: #d9dce0; --bien: #1a7f37; --mal: #c62f37; --marca: #e8f0fe; }
  @media (prefers-color-scheme: dark) {
    :root { --fondo: #15181c; --panel: #1e2227; --texto: #e6e8ea; --suave: #9aa3ad; --borde: #363c44;
            --bien: #4ac26b; --mal: #ff7b72; --marca: #24344d; }
  }
  * { box-sizing: border-box; }
  body { margin: 0; background: var(--fondo); color: var(--texto);
         font: 15px/1.5 system-ui, -apple-system, "Segoe UI", sans-serif; }
  main { max-width: 1180px; margin: 0 auto; padding: 24px 16px 48px; }
  h1 { font-size: 22px; margin: 0 0 4px; }
  h2 { font-size: 16px; margin: 28px 0 8px; }
  p { margin: 0 0 12px; color: var(--suave); }
  .marco { background: var(--panel); border: 1px solid var(--borde); border-radius: 8px; overflow-x: auto; }
  table { border-collapse: collapse; width: 100%; font-size: 14px; }
  th, td { padding: 8px 10px; text-align: left; border-bottom: 1px solid var(--borde); white-space: nowrap; }
  th { color: var(--suave); font-weight: 600; }
  tr:last-child td { border-bottom: 0; }
  td.num, th.num { text-align: right; font-variant-numeric: tabular-nums; }
  td.largo { white-space: normal; min-width: 240px; }
  tr.elegida td { background: var(--marca); }
  .bien { color: var(--bien); font-weight: 600; }
  .mal { color: var(--mal); font-weight: 600; }
  .suave { color: var(--suave); }
  label { cursor: pointer; padding: 4px; }
  #vacio { padding: 16px; }
</style>
</head>
<body>
<main>
  <h1>Banco de pruebas de NeuroClerk</h1>
  <p>Elige la corrida A y la B para ver qué casos cambian. La fila más reciente está arriba.</p>
  <div class="marco"><table>
    <thead><tr>
      <th>A</th><th>B</th><th class="num">#</th><th>Fecha</th><th>Corrida</th><th>Versión</th>
      <th class="num">Tabla</th><th class="num">Fuente</th><th class="num">F. dosis</th><th class="num">Contexto</th>
      <th class="num">Resp.</th><th class="num">Abst.</th><th class="num">Dosis</th><th class="num">Respaldo</th>
      <th class="num">Frag.</th><th class="num">Seg.</th>
    </tr></thead>
    <tbody id="corridas"></tbody>
  </table><div id="vacio" class="suave" hidden>Todavía no hay corridas. Usa: python banco.py correr</div></div>
  <div id="comparacion"></div>
  <div id="detalle"></div>
</main>
<script>
const COLUMNAS = ["tabla", "fuente", "fuente_dosis", "contexto", "respuesta", "abstencion", "dosis", "respaldo"];
let corridas = [], a = null, b = null;

function celda(fila, texto, clase) {
  const td = document.createElement("td");
  td.textContent = texto;
  if (clase) td.className = clase;
  fila.append(td);
  return td;
}

function selector(fila, grupo, id, elegido) {
  const td = document.createElement("td");
  const entrada = document.createElement("input");
  entrada.type = "radio"; entrada.name = grupo; entrada.checked = elegido;
  entrada.setAttribute("aria-label", "Corrida " + grupo.toUpperCase() + " " + id);
  entrada.addEventListener("change", () => { if (grupo === "a") a = id; else b = id; dibujar(); });
  td.append(entrada); fila.append(td);
}

function dibujarCorridas() {
  const cuerpo = document.getElementById("corridas");
  cuerpo.replaceChildren();
  document.getElementById("vacio").hidden = corridas.length > 0;
  for (const c of corridas) {
    const fila = document.createElement("tr");
    if (c.id === a || c.id === b) fila.className = "elegida";
    selector(fila, "a", c.id, c.id === a);
    selector(fila, "b", c.id, c.id === b);
    celda(fila, c.id, "num");
    celda(fila, c.fecha.replace("T", " ").slice(0, 16));
    celda(fila, c.nombre, "largo");
    celda(fila, c.version);
    for (const col of COLUMNAS) {
      const r = c.resumen[col];
      if (!r) { celda(fila, "–", "num suave"); continue; }
      celda(fila, r.aciertos + "/" + r.casos, "num " + (r.aciertos === r.casos ? "bien" : ""));
    }
    celda(fila, c.resumen.fragmentos_promedio, "num");
    celda(fila, c.segundos, "num");
    cuerpo.append(fila);
  }
}

function tabla(encabezados, filas) {
  const marco = document.createElement("div"); marco.className = "marco";
  const t = document.createElement("table");
  const cabeza = document.createElement("tr");
  for (const e of encabezados) { const th = document.createElement("th"); th.textContent = e; cabeza.append(th); }
  const thead = document.createElement("thead"); thead.append(cabeza); t.append(thead);
  const tbody = document.createElement("tbody"); filas.forEach(f => tbody.append(f)); t.append(tbody);
  marco.append(t); return marco;
}

function titulo(texto) { const h = document.createElement("h2"); h.textContent = texto; return h; }

function marca(valor) {
  if (valor === null) return ["–", "suave"];
  return valor ? ["sí", "bien"] : ["no", "mal"];
}

async function dibujarComparacion() {
  const zona = document.getElementById("comparacion");
  zona.replaceChildren();
  if (a === null || b === null || a === b) return;
  const r = await fetch(`/api/comparar?a=${a}&b=${b}`);
  if (!r.ok) return;
  const cambios = await r.json();
  const filas = [];
  for (const [lista, texto, clase] of [[cambios.empeoran, "empeora", "mal"], [cambios.mejoras, "mejora", "bien"]]) {
    for (const c of lista) {
      const fila = document.createElement("tr");
      celda(fila, texto, clase); celda(fila, c.medida); celda(fila, c.grupo); celda(fila, c.pregunta, "largo");
      filas.push(fila);
    }
  }
  zona.append(titulo(`De #${a} a #${b}: ${cambios.mejoras.length} mejoran, ${cambios.empeoran.length} empeoran`));
  if (filas.length) zona.append(tabla(["Cambio", "Medida", "Grupo", "Pregunta"], filas));
}

async function dibujarDetalle() {
  const zona = document.getElementById("detalle");
  zona.replaceChildren();
  if (b === null) return;
  const r = await fetch(`/api/casos?corrida=${b}`);
  if (!r.ok) return;
  const casos = await r.json();
  const filas = casos.map(c => {
    const fila = document.createElement("tr");
    celda(fila, c.n, "num"); celda(fila, c.grupo); celda(fila, c.pregunta, "largo");
    for (const m of [c.tabla_ok, c.fuente_ok, c.contexto_ok, c.respuesta_ok]) {
      const [texto, clase] = marca(m); celda(fila, texto, clase);
    }
    celda(fila, c.n_fragmentos, "num");
    celda(fila, c.fragmentos.slice(0, 3).map(f => `${f.archivo} p.${f.pagina}`).join(", "), "largo suave");
    return fila;
  });
  zona.append(titulo(`Casos de la corrida #${b}`));
  zona.append(tabla(["#", "Grupo", "Pregunta", "Tabla", "Fuente", "Contexto", "Respuesta", "Frag.", "Primeros fragmentos"], filas));
}

function dibujar() { dibujarCorridas(); dibujarComparacion(); dibujarDetalle(); }

fetch("/api/corridas").then(r => r.json()).then(datos => {
  corridas = datos;
  if (corridas.length) { b = corridas[0].id; a = corridas[corridas.length - 1].id; }
  dibujar();
});
</script>
</body>
</html>
"""


def _entero(consulta, nombre):
    return int(consulta[nombre][0])


class Manejador(BaseHTTPRequestHandler):
    def _enviar(self, cuerpo, tipo, estado=200):
        datos = cuerpo.encode("utf-8")
        self.send_response(estado)
        self.send_header("Content-Type", f"{tipo}; charset=utf-8")
        self.send_header("Content-Length", str(len(datos)))
        self.end_headers()
        self.wfile.write(datos)

    def _json(self, datos):
        self._enviar(json.dumps(datos, ensure_ascii=False), "application/json")

    def do_GET(self):
        ruta = urlsplit(self.path)
        consulta = parse_qs(ruta.query)
        try:
            if ruta.path == "/":
                self._enviar(PAGINA, "text/html")
                return
            conexion = banco.abrir()
            try:
                if ruta.path == "/api/corridas":
                    self._json(banco.leer_corridas(conexion))
                elif ruta.path == "/api/casos":
                    self._json(banco.leer_casos(conexion, _entero(consulta, "corrida")))
                elif ruta.path == "/api/comparar":
                    self._json(banco.comparar_casos(banco.leer_casos(conexion, _entero(consulta, "a")),
                                                    banco.leer_casos(conexion, _entero(consulta, "b"))))
                else:
                    self._enviar("No existe", "text/plain", 404)
            finally:
                conexion.close()
        except (KeyError, ValueError):
            self._enviar("Parámetros no válidos", "text/plain", 400)

    def log_message(self, *_args):
        pass   # sin una línea por petición en el registro del servicio


def main():
    parser = argparse.ArgumentParser(description="Panel de las corridas de banco.py.")
    parser.add_argument("--puerto", type=int, default=8765)
    args = parser.parse_args()
    servidor = ThreadingHTTPServer(("127.0.0.1", args.puerto), Manejador)
    print(f"Panel en http://localhost:{args.puerto}", flush=True)
    servidor.serve_forever()


if __name__ == "__main__":
    main()
