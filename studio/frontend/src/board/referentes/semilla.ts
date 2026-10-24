/**
 * Copia tipada de `docs/STUDIO/referentes-semilla.json` (24-oct).
 * Las entradas con `verificar: true` todavía no se abrieron en R-1/R-3:
 * se importan con la etiqueta «por verificar» y sin URL inventada.
 */
export interface ReferenteSemilla {
  id: string;
  nombre: string;
  url: string | null;
  que: string;
  video: string;
  verificar: boolean;
}

export const SEMILLA_REFERENTES: readonly ReferenteSemilla[] = [
  {
    id: 'letterform',
    nombre: 'Letterform Archive',
    url: 'https://letterformarchive.org',
    que: 'Objetos tipográficos fotografiados muy de cerca: carteles, especímenes, el mordisco de la tinta en el papel',
    video: 'media 11',
    verificar: false,
  },
  {
    id: 'medio-millon',
    nombre: 'Archivo de «half a million images», grabados japoneses sin atribución obligatoria',
    url: null,
    que: 'Medio millón de imágenes; candidatos: Smithsonian Open Access o Art Institute of Chicago',
    video: 'media 11',
    verificar: true,
  },
  {
    id: '800k',
    nombre: 'Colección de «800,000 works in high resolution»',
    url: null,
    que: 'Ukiyo-e, láminas de mariposas, pavo real; candidatos: Rijksmuseum, Met Open Access',
    video: 'media 11',
    verificar: true,
  },
  {
    id: 'archives-design',
    nombre: 'archives.design',
    url: 'https://archives.design',
    que: 'Archivo digital de piezas de diseño gráfico en Internet Archive: folletos Olivetti, libros de color',
    video: 'media 11',
    verificar: false,
  },
  {
    id: 'nypl',
    nombre: 'NYPL Digital Collections',
    url: 'https://digitalcollections.nypl.org',
    que: 'Mapas, láminas, efímeros; búsqueda infinita',
    video: 'media 11',
    verificar: false,
  },
  {
    id: 'sva',
    nombre: 'SVA Archives (Milton Glaser, Sagmeister…)',
    url: 'https://glaserarchives.org',
    que: 'Archivos completos de diseñadores, gratis',
    video: 'media 13',
    verificar: true,
  },
  {
    id: 'cooper-hewitt',
    nombre: 'Cooper Hewitt, Smithsonian Design Museum',
    url: 'https://collection.cooperhewitt.org',
    que: '30 siglos de diseño en una colección buscable',
    video: 'media 13',
    verificar: false,
  },
  {
    id: 'fonts-in-use',
    nombre: 'Fonts In Use',
    url: 'https://fontsinuse.com',
    que: 'Tipografías en marcas reales, no aisladas',
    video: 'media 13',
    verificar: false,
  },
  {
    id: 'design-reviewed',
    nombre: 'Design Reviewed',
    url: 'https://designreviewed.com',
    que: 'Archivo curado y documentado de diseño gráfico impreso',
    video: 'media 13',
    verificar: false,
  },
  {
    id: 'logos',
    nombre: 'Archivo de logos (libro rojo マーク・シンボル)',
    url: null,
    que: 'Marcas y símbolos; libro japonés de logotipos',
    video: 'media 13',
    verificar: true,
  },
  {
    id: 'pgda',
    nombre: "People's Graphic Design Archive",
    url: 'https://peoplesgdarchive.org',
    que: 'Archivo colectivo de historia del diseño',
    video: 'media 13',
    verificar: false,
  },
  {
    id: 'dover',
    nombre: 'Dover · Treasury of Animal Illustrations',
    url: null,
    que: "Grabados de dominio público (vídeo O'Reilly)",
    video: 'media 5',
    verificar: true,
  },
];
