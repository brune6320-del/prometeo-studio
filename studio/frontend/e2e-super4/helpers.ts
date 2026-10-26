import path from 'node:path';
import { abrirTableroSembrado, leerTablero, mockReadyBackend, nota, sembrar, tablero } from '../e2e-forja4/helpers';

export { abrirTableroSembrado, leerTablero, mockReadyBackend, nota, sembrar, tablero };

export const CAPTURAS = path.resolve(process.cwd(), '../../REPORTES/capturas-super4');

/** Referente completo: los tableros viejos no lo traían y el normalizador lo completa. */
export function referente(id: string, x: number, y: number, url = 'https://example.com/diseno') {
  return {
    id,
    type: 'referente',
    title: 'Referente de prueba',
    body: '',
    x,
    y,
    width: 320,
    color: 'paper',
    datos: {
      nombre: 'Referente de prueba',
      url,
      archivoOrigen: 'example.com',
      autor: '',
      anio: '',
      licencia: '',
      porQue: '',
      etiquetas: [],
      imagenes: [],
      adjuntos: [],
      vistoEn: [],
      lecturas: [],
    },
  };
}
