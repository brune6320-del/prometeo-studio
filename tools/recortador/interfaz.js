'use strict';
const $ = id => document.getElementById(id);
const canvas = $('lienzo'), ctx = canvas.getContext('2d');
let imagen = null, actual = {puntos: [], etiquetas: []}, piezas = [], inicio = null, ocupado = false, archivoCargado = null;
const token = document.querySelector('meta[name="recortador-token"]').content;
function estado(texto, error = false) { $('estado').textContent = texto; $('estado').classList.toggle('error', error); }
function bloquear(valor) { ocupado = valor; document.querySelectorAll('button').forEach(b => b.disabled = valor); $('recortar').disabled = valor || !imagen; $('proponer').disabled = valor || !imagen; }
async function api(ruta, datos) {
  const r = await fetch(ruta, {method: 'POST', headers: {'Content-Type': 'application/json', 'X-Recortador-Token': token}, body: JSON.stringify(datos)});
  const cuerpo = await r.json(); if (!r.ok) throw new Error(cuerpo.error || `Error ${r.status}`); return cuerpo;
}
function dibujar() {
  ctx.clearRect(0, 0, canvas.width, canvas.height); if (imagen) ctx.drawImage(imagen, 0, 0);
  for (const p of [...piezas, actual]) {
    ctx.lineWidth = Math.max(2, canvas.width / 400); ctx.strokeStyle = '#dc7500';
    if (p.caja) { const [x0,y0,x1,y1] = p.caja; ctx.strokeRect(x0,y0,x1-x0,y1-y0); }
    (p.puntos || []).forEach(([x,y],i) => {ctx.beginPath(); ctx.fillStyle = p.etiquetas[i] ? '#18884d' : '#cc302b'; ctx.arc(x,y,Math.max(4,canvas.width/180),0,2*Math.PI); ctx.fill();});
  }
}
function coordenada(evento) {const r = canvas.getBoundingClientRect(); return [Math.max(0,Math.min(canvas.width-1,(evento.clientX-r.left)*canvas.width/r.width)),Math.max(0,Math.min(canvas.height-1,(evento.clientY-r.top)*canvas.height/r.height))];}
canvas.addEventListener('pointerdown', e => {if (!imagen || ocupado) return; inicio = coordenada(e); canvas.setPointerCapture(e.pointerId);});
canvas.addEventListener('pointerup', e => {
  if (!inicio || ocupado) return; const fin = coordenada(e);
  if ($('herramienta').value === 'caja') { if (Math.abs(fin[0]-inicio[0]) >= 2 && Math.abs(fin[1]-inicio[1]) >= 2) actual.caja = [Math.min(inicio[0],fin[0]),Math.min(inicio[1],fin[1]),Math.max(inicio[0],fin[0]),Math.max(inicio[1],fin[1])]; }
  else { actual.puntos.push(fin); actual.etiquetas.push($('herramienta').value === 'positivo' ? 1 : 0); }
  inicio = null; dibujar();
});
function tieneSeleccion() {return actual.caja || actual.puntos.length;}
function guardar() {
  if (!tieneSeleccion()) return;
  piezas.push({...actual, tipo:$('tipo').value, nombre:`${$('tipo').selectedOptions[0].text} ${piezas.length+1}`});
  actual = {puntos:[],etiquetas:[]}; $('lista').replaceChildren();
  piezas.forEach(p => {const li = document.createElement('li'); li.textContent = p.nombre; $('lista').append(li);}); dibujar();
}
$('agregar').onclick = guardar;
$('limpiar').onclick = () => {actual={puntos:[],etiquetas:[]};piezas=[];$('lista').replaceChildren();dibujar();};
$('cargar').onclick = async () => {
  const file = $('archivo').files[0]; if (!file) return estado('Selecciona un archivo.',true);
  bloquear(true); estado('Preparando imagen…');
  try {
    const datos = {pagina:Number($('pagina').value),ppp:Number($('ppp').value),tesela:Number($('tesela').value)};
    if (file !== archivoCargado) {
      if (file.size > 20*1024*1024) throw new Error('El archivo supera 20 MiB.');
      datos.nombre=file.name; datos.contenido=await new Promise((resolve,reject) => {const lector=new FileReader();lector.onload=()=>resolve(lector.result.split(',')[1]);lector.onerror=reject;lector.readAsDataURL(file);});
    }
    const r = await api('/api/preparar',datos); const img = new Image(); img.src=r.imagen; await img.decode();
    imagen=img;archivoCargado=file;canvas.width=img.width;canvas.height=img.height;
    $('limpiar').onclick(); $('resultados').replaceChildren(); $('descargas').replaceChildren();
    $('documento').checked=r.fuente.tipo==='pdf';$('tipo').value=r.fuente.tipo==='pdf'?'bloque':'objeto';
    $('info').textContent=`${img.width} × ${img.height} px · Tesela ${r.fuente.tesela} de ${r.fuente.total_teselas} · ${r.fuente.coordenadas}`;
    estado('Lista. Marca una pieza o propone con la rejilla.');
  } catch(e) {estado(e.message,true);} finally {bloquear(false);}
};
async function recortar(datos) {
  if (!imagen) return estado('Carga una imagen primero.',true);
  bloquear(true); estado('SAM está recortando en esta Mac. La primera ejecución carga el modelo…');
  try {
    const r=await api('/api/recortar',{...datos,documento:$('documento').checked});$('resultados').replaceChildren();$('descargas').replaceChildren();
    for(const nombre of ['piezas.json','tablero.json']) {const a=document.createElement('a');a.href=`${r.ruta}/${nombre}`;a.download=nombre;a.textContent=`Descargar ${nombre}`;a.style.marginRight='18px';$('descargas').append(a);}
    for(const pieza of r.resultado.piezas) {
      const card=document.createElement('article');card.className='pieza';const img=document.createElement('img');img.src=`${r.ruta}/${pieza.archivo}`;img.alt=pieza.nombre;
      const texto=document.createElement('p');texto.textContent=`${pieza.nombre} · ${pieza.area} px · puntuación SAM ${pieza.puntuacion.toFixed(3)}${pieza.toca_borde_tesela?' · toca borde: revisar':''}`;
      const a=document.createElement('a');a.href=img.src;a.download=pieza.archivo;a.textContent='Descargar PNG';card.append(img,texto,a);$('resultados').append(card);
    }
    const cantidad = r.resultado.piezas.length;
    estado(`${cantidad} ${cantidad === 1 ? 'pieza exportada' : 'piezas exportadas'}. Revisa los recortes antes de usarlos.`);
  }catch(e){estado(e.message,true);}finally{bloquear(false);}
}
$('recortar').onclick=()=>{guardar();recortar({prompts:{coordenadas:'imagen_px',piezas}});};
$('proponer').onclick=()=>recortar({rejilla:Number($('rejilla').value)});
$('usarjson').onclick=()=>{try{recortar({prompts:JSON.parse($('indicaciones').value)});}catch(e){estado(e.message,true);}};
$('json').onclick=()=>{guardar();const blob=new Blob([JSON.stringify({coordenadas:'imagen_px',piezas},null,2)],{type:'application/json'});const url=URL.createObjectURL(blob);const a=document.createElement('a');a.href=url;a.download='indicaciones.json';a.click();setTimeout(()=>URL.revokeObjectURL(url),1000);};
