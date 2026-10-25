/**
 * Copia tipada de `docs/STUDIO/referentes-semilla.json` (24-oct, R-2).
 * URL y licencia verificadas; solo «マーク・シンボル» sigue con `verificar: true`.
 */
export interface ReferenteSemilla {
  id: string;
  nombre: string;
  url: string | null;
  licencia: string;
  que: string;
  video: string;
  verificar: boolean;
}

export const SEMILLA_REFERENTES: readonly ReferenteSemilla[] = [
  {
    id: 'letterform',
    nombre: 'Letterform Archive',
    url: 'https://letterformarchive.org',
    licencia: 'Solo consulta. Imágenes © Letterform Archive.',
    que: 'Objetos tipográficos fotografiados muy de cerca: carteles, especímenes, el mordisco de la tinta en el papel',
    video: 'media 11',
    verificar: false,
  },
  {
    id: 'medio-millon',
    nombre: 'Archivo de «half a million images», grabados japoneses sin atribución obligatoria',
    url: 'https://www.metmuseum.org/art/collection',
    licencia: 'CC0.',
    que: 'Medio millón de imágenes; grabados japoneses sin atribución obligatoria',
    video: 'media 11',
    verificar: false,
  },
  {
    id: '800k',
    nombre: 'Colección de «800,000 works in high resolution»',
    url: 'https://www.rijksmuseum.nl/en/collection',
    licencia: 'Dominio público / CC0 donde consta; CC BY 4.0 en algunos casos.',
    que: 'Ukiyo-e, láminas de mariposas, pavo real; alta resolución',
    video: 'media 11',
    verificar: false,
  },
  {
    id: 'archives-design',
    nombre: 'archives.design',
    url: 'https://archives.design',
    licencia: 'Solo consulta. Sitio © 2025, all rights reserved; derechos por pieza según Internet Archive.',
    que: 'Archivo digital de piezas de diseño gráfico en Internet Archive: folletos Olivetti, libros de color',
    video: 'media 11',
    verificar: false,
  },
  {
    id: 'nypl',
    nombre: 'NYPL Digital Collections',
    url: 'https://digitalcollections.nypl.org',
    licencia: 'Dominio público / «no known U.S. copyright restrictions».',
    que: 'Mapas, láminas, efímeros; búsqueda infinita',
    video: 'media 11',
    verificar: false,
  },
  {
    id: 'sva',
    nombre: 'SVA Archives (Milton Glaser, Sagmeister…)',
    url: 'https://glaserarchives.org',
    licencia: 'Solo consulta. © de sus respectivos dueños; fines educativos.',
    que: 'Archivos completos de diseñadores, gratis',
    video: 'media 13',
    verificar: false,
  },
  {
    id: 'cooper-hewitt',
    nombre: 'Cooper Hewitt, Smithsonian Design Museum',
    url: 'https://collection.cooperhewitt.org',
    licencia: 'Metadatos CC0; las imágenes no están incluidas ni cubiertas por CC0.',
    que: '30 siglos de diseño en una colección buscable',
    video: 'media 13',
    verificar: false,
  },
  {
    id: 'fonts-in-use',
    nombre: 'Fonts In Use',
    url: 'https://fontsinuse.com',
    licencia: 'Solo consulta. Fair use; licencia personal y no comercial.',
    que: 'Tipografías en marcas reales, no aisladas',
    video: 'media 13',
    verificar: false,
  },
  {
    id: 'design-reviewed',
    nombre: 'Design Reviewed',
    url: 'https://designreviewed.com',
    licencia: 'Solo consulta. Acceso libre; imágenes © de sus autores.',
    que: 'Archivo curado y documentado de diseño gráfico impreso',
    video: 'media 13',
    verificar: false,
  },
  {
    id: 'logos',
    nombre: 'Archivo de logos (libro rojo マーク・シンボル)',
    url: null,
    licencia: 'Sin identificar.',
    que: 'Marcas y símbolos; libro japonés de logotipos',
    video: 'media 13',
    verificar: true,
  },
  {
    id: 'pgda',
    nombre: "People's Graphic Design Archive",
    url: 'https://peoplesgdarchive.org',
    licencia: 'Solo consulta: uso educativo y de investigación; todo el material sujeto a copyright.',
    que: 'Archivo colectivo de historia del diseño',
    video: 'media 13',
    verificar: false,
  },
  {
    id: 'dover',
    nombre: 'Dover · Treasury of Animal Illustrations',
    url: 'https://store.doverpublications.com/products/9780486258058',
    licencia: 'Grabados del s. XVIII: dominio público en el original; la edición/recopilación Dover tiene copyright; no es CC0.',
    que: "Grabados de dominio público (vídeo O'Reilly)",
    video: 'media 5',
    verificar: false,
  },
];
