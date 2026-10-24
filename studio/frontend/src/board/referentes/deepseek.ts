import { studioApi } from '../../api/client';
import type { Ojos } from './ojos';
import type { ReferenteElegido } from './mirar';

export interface LecturaPedida {
  texto: string;
  modelo: string;
}

export interface ResultadoMirada {
  /** false = ritual en blanco para escribir a mano (sin clave o sin red). */
  disponible: boolean;
  motivo: string;
  lecturas: LecturaPedida[];
}

function vacias(cantidad: number): LecturaPedida[] {
  return Array.from({ length: cantidad }, () => ({ texto: '', modelo: '' }));
}

/**
 * La llamada sale del frontend hacia el backend local. El backend lee
 * DEEPSEEK_API_KEY de su propio entorno y nunca devuelve la clave.
 */
export async function pedirLecturas(
  proyecto: string,
  ojos: Ojos,
  elegidos: readonly ReferenteElegido[],
): Promise<ResultadoMirada> {
  if (elegidos.length === 0) return { disponible: false, motivo: 'No hay referentes para mirar.', lecturas: [] };

  try {
    const respuesta = await studioApi.mirarReferentes({
      proyecto,
      ojos: ojos.nombre,
      ojos_descripcion: ojos.comoMira,
      preguntas: ojos.preguntas,
      referentes: elegidos.map((elegido) => ({
        id: elegido.cardId,
        nombre: elegido.nombre,
        por_que: elegido.referente.porQue,
        archivo_origen: elegido.referente.archivoOrigen,
        etiquetas: elegido.referente.etiquetas,
        url: elegido.referente.url,
      })),
    });

    const recibidas = (respuesta.lecturas ?? []).map((lectura) => ({
      texto: typeof lectura.texto === 'string' ? lectura.texto.trim() : '',
      modelo: typeof lectura.modelo === 'string' ? lectura.modelo : '',
    }));
    while (recibidas.length < elegidos.length) recibidas.push({ texto: '', modelo: '' });

    return {
      disponible: respuesta.disponible !== false,
      motivo: respuesta.motivo ?? '',
      lecturas: recibidas.slice(0, elegidos.length),
    };
  } catch {
    return {
      disponible: false,
      motivo: 'Sin conexión con el motor local. El ritual sigue igual: escribe la lectura a mano.',
      lecturas: vacias(elegidos.length),
    };
  }
}
