import hashlib
import json
from pathlib import Path


def sha256(path):
    h=hashlib.sha256()
    with Path(path).open('rb') as f:
        for b in iter(lambda:f.read(1<<20),b''):h.update(b)
    return h.hexdigest()


def guardar(path, data):
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
    with path.open('x',encoding='utf-8') as f:
        json.dump(data,f,ensure_ascii=False,indent=2,allow_nan=False);f.write('\n')


def abrir_adn(pdf, adn):
    data=json.loads(Path(adn).read_text())
    if data['sha256_origen']!=sha256(pdf):raise ValueError('ADN no corresponde al documento')
    pages=data.get('paginas',[data])
    if not isinstance(pages,list):raise ValueError('ADN requiere páginas completas')
    return data,pages


def validar_documento(doc, propio):
    if not propio:raise ValueError('Declaración de documento propio/ejemplo autorizado requerida')
    if doc.needs_pass or doc.get_sigflags()>0:raise ValueError('Documento cifrado o firmado')
    for page in doc:
        if any(a.type[0]==13 for a in page.annots() or []):raise ValueError('Documento con sellos')
        if any(w.field_type==6 for w in page.widgets() or []):raise ValueError('Campo de firma')
    # Firmas/sellos rasterizados requieren delimitación humana de zonas excluidas.
