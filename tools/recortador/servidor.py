"""Interfaz local sin dependencias web: HTTP de loopback, solicitudes seriales."""
import argparse
import base64
import io
import json
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
import re
import secrets
import shutil
import tempfile
from urllib.parse import urlsplit
import uuid

from recortador import ROOT, MotorSAM, abrir_fuente, ejecutar, exclusivo

MAX_BODY = 28 * 1024 * 1024


class Servidor(HTTPServer):
    def __init__(self, direccion, dispositivo='cpu'):
        super().__init__(direccion, Handler)
        self.token = secrets.token_urlsafe(32)
        self.dispositivo = dispositivo
        self.motor = None
        self.fuente_path = None
        self.config = {}
        (ROOT / '.tmp').mkdir(exist_ok=True)
        self.trabajo = Path(tempfile.mkdtemp(prefix='web-', dir=ROOT / '.tmp'))

    def server_close(self):
        super().server_close()
        if hasattr(self, 'trabajo'):
            shutil.rmtree(self.trabajo, ignore_errors=True)


class Handler(BaseHTTPRequestHandler):
    def responder(self, status, contenido, tipo='application/json; charset=utf-8'):
        if isinstance(contenido, dict):
            contenido = json.dumps(contenido, ensure_ascii=False, allow_nan=False).encode()
        self.send_response(status)
        self.send_header('Content-Type', tipo)
        self.send_header('Content-Length', str(len(contenido)))
        self.send_header('Cache-Control', 'no-store')
        self.send_header('X-Content-Type-Options', 'nosniff')
        self.send_header('Content-Security-Policy', "default-src 'self'; img-src 'self' data: blob:; style-src 'self' 'unsafe-inline'; script-src 'self'; connect-src 'self'; frame-ancestors 'none'")
        self.end_headers()
        self.wfile.write(contenido)

    def origen_valido(self):
        host = f'127.0.0.1:{self.server.server_port}'
        return self.headers.get('Host') == host and self.headers.get('Origin', f'http://{host}') == f'http://{host}'

    def do_GET(self):
        if not self.origen_valido():
            return self.responder(403, {'error': 'Origen no permitido.'})
        path = urlsplit(self.path).path
        if path == '/':
            html = (ROOT / 'index.html').read_text().replace('__TOKEN__', self.server.token)
            return self.responder(200, html.encode(), 'text/html; charset=utf-8')
        if path == '/interfaz.js':
            return self.responder(200, (ROOT / 'interfaz.js').read_bytes(), 'text/javascript; charset=utf-8')
        if re.fullmatch(r'/salidas/[a-f0-9]{32}/(pieza-\d{3}\.png|piezas\.json|tablero\.json)', path):
            fichero = ROOT / path.lstrip('/')
            if fichero.is_file():
                tipo = 'image/png' if fichero.suffix == '.png' else 'application/json; charset=utf-8'
                return self.responder(200, fichero.read_bytes(), tipo)
        self.responder(404, {'error': 'No encontrado.'})

    def do_POST(self):
        if not self.origen_valido() or not secrets.compare_digest(self.headers.get('X-Recortador-Token', ''), self.server.token):
            return self.responder(403, {'error': 'Token u origen no permitido.'})
        try:
            longitud = int(self.headers.get('Content-Length', '0'))
            if not 0 < longitud <= MAX_BODY:
                return self.responder(413, {'error': 'Archivo/solicitud demasiado grande (máximo 20 MiB antes de base64).'})
            self.connection.settimeout(120)
            datos = json.loads(self.rfile.read(longitud))
            if not isinstance(datos, dict):
                raise ValueError('Se requiere un objeto JSON.')
            if self.path == '/api/preparar':
                return self.preparar(datos)
            if self.path == '/api/recortar':
                return self.recortar(datos)
            return self.responder(404, {'error': 'Ruta no encontrada.'})
        except (ValueError, OSError, RuntimeError, TypeError, KeyError) as exc:
            self.responder(400, {'error': str(exc)})

    def preparar(self, datos):
        config = {k: datos.get(k, v) for k, v in [('pagina', 1), ('ppp', 150), ('tesela', 1)]}
        if any(type(config[k]) is not int for k in config):
            raise ValueError('Página, ppp y tesela deben ser enteros.')
        candidato = self.server.fuente_path
        nuevo = 'contenido' in datos
        if nuevo:
            nombre = Path(datos.get('nombre', 'imagen.png')).name
            if Path(nombre).suffix.lower() not in ('.png', '.jpg', '.jpeg', '.webp', '.pdf'):
                raise ValueError('Selecciona PNG, JPG, WebP o PDF.')
            raw = base64.b64decode(datos['contenido'], validate=True)
            if len(raw) > 20 * 1024 * 1024:
                raise ValueError('Archivo mayor de 20 MiB.')
            carpeta = self.server.trabajo / uuid.uuid4().hex
            carpeta.mkdir()
            candidato = carpeta / nombre[:180]
            candidato.write_bytes(raw)
        if candidato is None:
            raise ValueError('Carga una imagen o PDF primero.')
        try:
            fuente = abrir_fuente(candidato, **config)
            buffer = io.BytesIO()
            fuente.imagen.save(buffer, format='PNG')
            respuesta = {'imagen': 'data:image/png;base64,' + base64.b64encode(buffer.getvalue()).decode(),
                         'fuente': fuente.procedencia}
        except BaseException:
            if nuevo:
                shutil.rmtree(candidato.parent)
            raise
        anterior = self.server.fuente_path
        self.server.fuente_path, self.server.config = candidato, config
        if nuevo and anterior is not None:
            shutil.rmtree(anterior.parent)
        self.responder(200, respuesta)

    def recortar(self, datos):
        if self.server.fuente_path is None:
            raise ValueError('Carga una imagen primero.')
        if self.server.motor is None:
            with exclusivo():
                self.server.motor = MotorSAM(self.server.dispositivo)
        identificador = uuid.uuid4().hex
        resultado = ejecutar(self.server.fuente_path, ROOT / 'salidas' / identificador,
                             prompts=datos.get('prompts'), rejilla=datos.get('rejilla', 0),
                             documento=bool(datos.get('documento', False)),
                             dispositivo=self.server.dispositivo, motor=self.server.motor, **self.server.config)
        self.responder(200, {'ruta': '/salidas/' + identificador, 'resultado': resultado})


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--puerto', type=int, default=8765)
    parser.add_argument('--dispositivo', choices=['cpu', 'mps'], default='cpu')
    args = parser.parse_args()
    with Servidor(('127.0.0.1', args.puerto), args.dispositivo) as server:
        print(f'Recortador: http://127.0.0.1:{server.server_port}', flush=True)
        try:
            server.serve_forever()
        except KeyboardInterrupt:
            pass


if __name__ == '__main__':
    main()
