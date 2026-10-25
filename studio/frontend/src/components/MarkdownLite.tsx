import React from 'react';

/**
 * Formato mínimo de una nota, sin dependencias: título, negrita, código en línea,
 * listas, cita y bloque de código. El texto guardado sigue siendo Markdown plano.
 */
const enLinea = (texto: string, key: string): React.ReactNode[] => {
  const partes: React.ReactNode[] = [];
  const patron = /(\*\*[^*]+\*\*|`[^`]+`|_[^_\n]+_)/g;
  let ultimo = 0;
  let match: RegExpExecArray | null;
  let indice = 0;
  while ((match = patron.exec(texto)) !== null) {
    if (match.index > ultimo) partes.push(texto.slice(ultimo, match.index));
    const token = match[0];
    if (token.startsWith('**')) partes.push(<strong key={`${key}-b${indice}`}>{token.slice(2, -2)}</strong>);
    else if (token.startsWith('`')) partes.push(<code key={`${key}-c${indice}`}>{token.slice(1, -1)}</code>);
    else partes.push(<em key={`${key}-i${indice}`}>{token.slice(1, -1)}</em>);
    ultimo = match.index + token.length;
    indice += 1;
  }
  if (ultimo < texto.length) partes.push(texto.slice(ultimo));
  return partes;
};

export const MarkdownLite: React.FC<{ value: string; placeholder?: string }> = ({ value, placeholder }) => {
  if (!value.trim()) return <div className="board-card-text is-empty">{placeholder}</div>;
  const lineas = value.split(/\r?\n/);
  const bloques: React.ReactNode[] = [];
  let lista: string[] = [];
  let codigo: string[] | null = null;
  let parrafo: string[] = [];

  const cerrarLista = () => {
    if (!lista.length) return;
    bloques.push(<ul key={`ul-${bloques.length}`}>{lista.map((item, i) => <li key={i}>{enLinea(item, `ul-${bloques.length}-${i}`)}</li>)}</ul>);
    lista = [];
  };
  const cerrarParrafo = () => {
    if (!parrafo.length) return;
    const texto = parrafo.join(' ');
    bloques.push(<p key={`p-${bloques.length}`}>{enLinea(texto, `p-${bloques.length}`)}</p>);
    parrafo = [];
  };

  for (const linea of lineas) {
    if (linea.trim().startsWith('```')) {
      cerrarLista();
      cerrarParrafo();
      if (codigo === null) codigo = [];
      else {
        bloques.push(<pre key={`pre-${bloques.length}`}><code>{codigo.join('\n')}</code></pre>);
        codigo = null;
      }
      continue;
    }
    if (codigo !== null) {
      codigo.push(linea);
      continue;
    }
    if (!linea.trim()) {
      cerrarLista();
      cerrarParrafo();
      continue;
    }
    if (/^#{1,3}\s+/.test(linea)) {
      cerrarLista();
      cerrarParrafo();
      const nivel = Math.min(3, (linea.match(/^#+/) ?? ['#'])[0].length);
      const contenido = enLinea(linea.replace(/^#{1,3}\s+/, ''), `h-${bloques.length}`);
      bloques.push(nivel === 1
        ? <h3 key={`h-${bloques.length}`}>{contenido}</h3>
        : nivel === 2
          ? <h4 key={`h-${bloques.length}`}>{contenido}</h4>
          : <h5 key={`h-${bloques.length}`}>{contenido}</h5>);
      continue;
    }
    if (/^>\s?/.test(linea)) {
      cerrarLista();
      cerrarParrafo();
      bloques.push(<blockquote key={`q-${bloques.length}`}>{enLinea(linea.replace(/^>\s?/, ''), `q-${bloques.length}`)}</blockquote>);
      continue;
    }
    const item = linea.match(/^\s*[-*]\s+(.*)$/);
    if (item) {
      cerrarParrafo();
      lista.push(item[1]);
      continue;
    }
    cerrarLista();
    parrafo.push(linea.trim());
  }
  if (codigo !== null) bloques.push(<pre key={`pre-${bloques.length}`}><code>{codigo.join('\n')}</code></pre>);
  cerrarLista();
  cerrarParrafo();
  return <div className="board-card-text board-markdown">{bloques}</div>;
};
