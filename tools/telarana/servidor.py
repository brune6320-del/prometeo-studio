"""Panel local opt-in. Token de sesión y mismo origen para correcciones."""
import argparse
import hashlib
import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
import secrets
from urllib.parse import parse_qs, urlparse
from .grafo import Proyecto, sha


def servir(root, port=8765, habilitar=False):
    if not habilitar: raise ValueError('Panel deshabilitado: requiere --habilitar-telarana')
    root = Path(root).resolve(); project = Proyecto(root/'proyecto.json')
    if not project.path.is_file(): raise ValueError('Crear un proyecto antes de abrir panel')
    token = secrets.token_urlsafe(24)

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args): pass  # No registrar tokens ni texto privado.

        def reply(self, body, code=200, kind='application/json'):
            if not isinstance(body, bytes): body=json.dumps(body,ensure_ascii=False).encode()
            self.send_response(code);self.send_header('Content-Type',kind)
            self.send_header('Cache-Control','no-store');self.send_header('X-Content-Type-Options','nosniff')
            self.send_header('Content-Length',str(len(body)));self.end_headers();self.wfile.write(body)

        def autorizado(self):
            supplied = parse_qs(urlparse(self.path).query).get('token',[''])[0]
            return secrets.compare_digest(supplied, token)

        def do_GET(self):
            if not self.autorizado(): return self.reply({'error':'Sesión no autorizada'},403)
            url=urlparse(self.path)
            if url.path=='/':
                return self.reply((Path(__file__).parent/'panel.html').read_bytes(),kind='text/html; charset=utf-8')
            if url.path=='/estado':
                state=project.estado();return self.reply(dict(estado=state,sha256=sha(state)))
            if url.path=='/imagen':
                file=parse_qs(url.query).get('archivo',[''])[0]
                allowed={'pagina.png':None}
                for node in project.estado()['fichas'].values():
                    data=node['contenido']
                    if data.get('imagen'):allowed[data['imagen']]=data.get('sha256_imagen')
                target=(root/file).resolve()
                if file not in allowed or root not in target.parents or target.suffix!='.png':
                    return self.reply({'error':'Recurso no permitido'},403)
                data=target.read_bytes()
                if allowed[file] and hashlib.sha256(data).hexdigest()!=allowed[file]:
                    return self.reply({'error':'Imagen alterada'},409)
                return self.reply(data,kind='image/png')
            return self.reply({'error':'No encontrado'},404)

        def do_POST(self):
            host=f'http://127.0.0.1:{self.server.server_port}'
            if not self.autorizado() or self.headers.get('Origin')!=host:
                return self.reply({'error':'Origen o sesión no autorizados'},403)
            if urlparse(self.path).path!='/corregir':return self.reply({'error':'No encontrado'},404)
            try:
                size=int(self.headers.get('Content-Length','0'))
                if not 0<size<=8192:raise ValueError('Tamaño inválido')
                data=json.loads(self.rfile.read(size));node=project.estado()['fichas'][data['id']]
                label=data['etiqueta']
                if not isinstance(label,str) or not 1<=len(label.strip())<=200:raise ValueError('Etiqueta vacía o muy larga')
                content={**node['contenido'],'etiqueta':label.strip()}
                state=project.corregir(data['id'],data['revision'],content,'Corrección desde el panel por el operador')
                return self.reply(dict(estado=state,sha256=sha(state)))
            except (ValueError,KeyError,TypeError):
                return self.reply({'error':'Corrección inválida u obsoleta; recargar estado'},409)

    server=ThreadingHTTPServer(('127.0.0.1',port),Handler)
    print(f'http://127.0.0.1:{server.server_port}/?token={token}',flush=True)
    try:server.serve_forever()
    finally:server.server_close()


if __name__=='__main__':
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('proyecto')
    ap.add_argument('--port',type=int,default=8765);ap.add_argument('--habilitar-telarana',action='store_true')
    a=ap.parse_args();servir(a.proyecto,a.port,a.habilitar_telarana)
