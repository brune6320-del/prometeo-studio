/**
 * PROMETEO Studio · errores tipados del cliente.
 *
 * Toda falla que llega a la interfaz es un ApiError con un `code` estable.
 * Un fallo de red de WebKit ("Load failed"), Chromium ("Failed to fetch") o
 * Firefox ("NetworkError…") se convierte en BACKEND_UNAVAILABLE: el texto
 * crudo del navegador nunca es la explicación que ve la persona.
 */

export type ErrorStage =
  | 'API'
  | 'AUTH'
  | 'BOOT'
  | 'DOCUMENT_LOAD'
  | 'RENDER'
  | 'OCR'
  | 'STAGING'
  | 'VERIFICATION'
  | 'EXPORT'
  | 'SESSION'
  | 'WORKSPACE';

export class ApiError extends Error {
  readonly code: string;
  readonly stage: ErrorStage | string;
  readonly status: number;
  readonly retryable: boolean;
  readonly details: Record<string, unknown>;

  constructor(opts: {
    code: string;
    message: string;
    stage?: ErrorStage | string;
    status?: number;
    retryable?: boolean;
    details?: Record<string, unknown>;
  }) {
    super(opts.message);
    this.name = 'ApiError';
    this.code = opts.code;
    this.stage = opts.stage ?? 'API';
    this.status = opts.status ?? 0;
    this.retryable = opts.retryable ?? false;
    this.details = opts.details ?? {};
  }
}

const NETWORK_MESSAGES = ['load failed', 'failed to fetch', 'networkerror', 'network request failed', 'network connection was lost'];

export function isCancellation(err: unknown): boolean {
  return err instanceof ApiError && err.code === 'CANCELLED';
}

/** Convierte cualquier excepción en ApiError conservando el texto original solo como detalle técnico. */
export function normalizeError(err: unknown, stage: ErrorStage | string = 'API'): ApiError {
  if (err instanceof ApiError) return err;
  if (err instanceof DOMException && err.name === 'AbortError') {
    const reason = (err as DOMException & { cause?: unknown }).cause;
    return reason === 'timeout'
      ? new ApiError({ code: 'REQUEST_TIMEOUT', message: 'La operación tardó demasiado.', stage, retryable: true })
      : new ApiError({ code: 'CANCELLED', message: 'Operación cancelada.', stage });
  }
  if (err instanceof Error) {
    const low = err.message.toLowerCase();
    if (err.name === 'TypeError' && NETWORK_MESSAGES.some((m) => low.includes(m))) {
      return new ApiError({
        code: 'BACKEND_UNAVAILABLE',
        message: 'No se pudo conectar con el motor local de PROMETEO.',
        stage,
        retryable: true,
        details: { browser_message: err.message },
      });
    }
    if (err.name === 'TimeoutError') {
      return new ApiError({ code: 'REQUEST_TIMEOUT', message: 'La operación tardó demasiado.', stage, retryable: true });
    }
    return new ApiError({ code: 'UNEXPECTED_ERROR', message: err.message, stage, details: { name: err.name } });
  }
  return new ApiError({ code: 'UNEXPECTED_ERROR', message: String(err), stage });
}

export interface ErrorCopy {
  title: string;
  message: string;
  action: string;
}

/** Texto para personas, por código. Nunca promete que el original está intacto: eso lo decide el contexto. */
const COPY: Record<string, ErrorCopy> = {
  BACKEND_UNAVAILABLE: {
    title: 'El motor de PROMETEO no responde',
    message: 'La interfaz no pudo comunicarse con el servicio local que abre y verifica documentos.',
    action: 'Pulsa «Reintentar». Si sigue igual, cierra PROMETEO y vuelve a abrirlo.',
  },
  BACKEND_EXITED: {
    title: 'El motor de PROMETEO se detuvo',
    message: 'El servicio local que abre y verifica documentos terminó inesperadamente.',
    action: 'Cierra PROMETEO y vuelve a abrirlo. Si se repite, comparte el registro técnico.',
  },
  HEALTH_TIMEOUT: {
    title: 'El motor tarda demasiado en arrancar',
    message: 'El servicio local no respondió en el tiempo esperado.',
    action: 'Pulsa «Reintentar». En el primer arranque tras instalar, macOS puede tardar más.',
  },
  RUNTIME_NOT_FOUND: {
    title: 'La instalación está incompleta',
    message: 'No se encontró el motor empaquetado dentro de la aplicación.',
    action: 'Vuelve a copiar PROMETEO Studio desde el instalador.',
  },
  SPAWN_FAILED: {
    title: 'No se pudo iniciar el motor',
    message: 'macOS no permitió iniciar el servicio local de PROMETEO.',
    action: 'Cierra PROMETEO y vuelve a abrirlo. Si se repite, comparte el registro técnico.',
  },
  WORKSPACE_UNAVAILABLE: {
    title: 'No hay dónde trabajar con documentos',
    message: 'PROMETEO no encontró una carpeta con permiso de escritura para guardar sus copias de trabajo.',
    action: 'Comprueba el espacio libre en disco y los permisos de tu carpeta de usuario.',
  },
  AUTHENTICATION_FAILED: {
    title: 'La interfaz y el motor no se reconocen',
    message: 'El motor rechazó la petición porque la credencial de esta sesión no coincide.',
    action: 'Cierra PROMETEO y vuelve a abrirlo para crear una sesión nueva.',
  },
  REQUEST_TIMEOUT: {
    title: 'La operación tardó demasiado',
    message: 'El motor no respondió a tiempo.',
    action: 'Pulsa «Reintentar». Los documentos largos pueden tardar más la primera vez.',
  },
  DOCUMENT_UNREADABLE: {
    title: 'El archivo no se pudo leer',
    message: 'No es un PDF válido o está dañado.',
    action: 'Comprueba que se abre en otra aplicación y vuelve a intentarlo con una copia sana.',
  },
  DOCUMENT_ENCRYPTED: {
    title: 'El PDF está protegido',
    message: 'El documento tiene contraseña o restricciones que impiden analizarlo.',
    action: 'Abre una copia sin protección.',
  },
  PDF_PARSE_TIMEOUT: {
    title: 'El PDF tardó demasiado en analizarse',
    message: 'PROMETEO lo analizó aparte y lo descartó al superar el tiempo máximo, para no bloquearse.',
    action: 'Tu archivo no se modificó. Prueba con una copia exportada de nuevo desde otra aplicación.',
  },
  PDF_TOO_COMPLEX: {
    title: 'El PDF supera los límites de análisis',
    message: 'Tiene demasiadas páginas o necesita demasiada memoria para analizarse con seguridad.',
    action: 'Tu archivo no se modificó. Divide el documento o abre solo las páginas que necesitas.',
  },
  PDF_REJECTED_UNSAFE: {
    title: 'El PDF hizo fallar el analizador',
    message: 'PROMETEO lo analizó en un proceso aparte, ese proceso falló y el archivo se descartó sin abrirlo.',
    action: 'Tu archivo no se modificó. Si el PDF es de confianza, prueba a guardarlo de nuevo desde otra aplicación.',
  },
  DOCUMENT_EMPTY: {
    title: 'El archivo está vacío',
    message: 'El archivo seleccionado no contiene datos.',
    action: 'Elige otro archivo.',
  },
  UPLOAD_TOO_LARGE: {
    title: 'El archivo es demasiado grande',
    message: 'Supera el tamaño máximo que PROMETEO admite por documento.',
    action: 'Divide el documento o reduce su tamaño.',
  },
  DOCUMENT_LOAD_FAILED: {
    title: 'No se pudo abrir el documento',
    message: 'El motor encontró un problema al preparar el documento.',
    action: 'Vuelve a intentarlo; si se repite con este archivo, prueba con otro.',
  },
  SAMPLE_NOT_INSTALLED: {
    title: 'Ese ejemplo no está incluido',
    message: 'La muestra elegida no forma parte de esta instalación.',
    action: 'Elige otro ejemplo o abre tu propio PDF.',
  },
  SESSION_NOT_FOUND: {
    title: 'La sesión de trabajo terminó',
    message: 'El documento ya no está abierto en el motor (por ejemplo, tras reiniciarlo).',
    action: 'Vuelve a abrir el documento.',
  },
  RENDER_FAILED: {
    title: 'No se pudo mostrar la página',
    message: 'El motor no logró dibujar esta página.',
    action: 'Pulsa «Reintentar» o cambia de página.',
  },
  PAGE_OUT_OF_RANGE: {
    title: 'Esa página no existe',
    message: 'El número de página está fuera del documento.',
    action: 'Vuelve a la primera página.',
  },
  OCR_FAILED: {
    title: 'No se pudo leer el texto de la imagen',
    message: 'El reconocimiento de texto (OCR) falló en esta página.',
    action: 'Pulsa «Reintentar». La página sigue visible aunque no haya capa OCR.',
  },
  OCR_TIMEOUT: {
    title: 'El reconocimiento de texto tardó demasiado',
    message: 'El OCR superó su tiempo máximo en esta página.',
    action: 'Pulsa «Reintentar» más tarde.',
  },
  OCR_UNAVAILABLE: {
    title: 'El reconocimiento de texto no está disponible',
    message: 'El motor OCR no está instalado en esta copia de PROMETEO.',
    action: 'Trabaja con PDFs de texto nativo o reinstala PROMETEO.',
  },
  MIXED_TRANSACTION_UNSUPPORTED: {
    title: 'No se pueden mezclar estos cambios',
    message: 'Un mismo lote no puede combinar cambios sobre texto nativo y sobre zonas escaneadas.',
    action: 'Verifica o descarta primero los cambios preparados.',
  },
  RASTER_PREFLIGHT_REJECTED: {
    title: 'Esta zona escaneada no se puede editar con seguridad',
    message: 'El fondo o la estructura de la región impiden un parche verificable.',
    action: 'Deja esta zona sin cambios o elige una región de fondo uniforme.',
  },
  STAGING_REJECTED: {
    title: 'No se pudo preparar el cambio',
    message: 'El motor no aceptó el cambio propuesto.',
    action: 'Revisa el texto y vuelve a intentarlo.',
  },
  OUTPUT_NOT_VERIFIED: {
    title: 'Todavía no hay una copia verificada',
    message: 'Solo se puede guardar una copia que haya superado la verificación.',
    action: 'Prepara un cambio y pulsa «Verificar y crear copia».',
  },
  SAVE_PERMISSION_DENIED: {
    title: 'macOS no permitió guardar el archivo',
    message: 'PROMETEO no tiene permiso para escribir en la carpeta Descargas.',
    action: 'Permite el acceso cuando macOS lo pida, o revísalo en Ajustes del Sistema › Privacidad y seguridad › Archivos y carpetas.',
  },
  SAVE_FAILED: {
    title: 'No se pudo guardar la copia',
    message: 'Ocurrió un problema al escribir el archivo verificado.',
    action: 'Comprueba el espacio libre en disco y vuelve a intentarlo.',
  },
  VERIFICATION_FAILED: {
    title: 'La verificación no se pudo completar',
    message: 'El motor falló mientras verificaba el documento.',
    action: 'Vuelve a intentarlo. No se creó ninguna copia.',
  },
  INTERNAL_ERROR: {
    title: 'Error interno del motor',
    message: 'El motor encontró un problema inesperado.',
    action: 'Vuelve a intentarlo. Si se repite, comparte los detalles técnicos.',
  },
};

const FALLBACK: ErrorCopy = {
  title: 'Algo no salió como se esperaba',
  message: 'La operación no se completó.',
  action: 'Vuelve a intentarlo. Si se repite, comparte los detalles técnicos.',
};

export function describeError(err: ApiError): ErrorCopy {
  return COPY[err.code] ?? FALLBACK;
}

export function technicalSummary(err: ApiError): string {
  const parts = [`código: ${err.code}`, `etapa: ${err.stage}`];
  if (err.status) parts.push(`HTTP ${err.status}`);
  if (err.message) parts.push(`mensaje: ${err.message}`);
  const raw = err.details?.browser_message;
  if (typeof raw === 'string') parts.push(`navegador: ${raw}`);
  return parts.join(' · ');
}
