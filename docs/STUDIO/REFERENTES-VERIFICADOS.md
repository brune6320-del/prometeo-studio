# Referentes verificados

> R-2 · 24-oct-2026. Fuente: `referentes-semilla.json`. Solo se abrieron páginas; no se descargaron imágenes. «Sin identificar» = no se encontró con seguridad, no se inventa.

| # | Nombre | URL | Licencia que declara | API o descarga masiva oficial |
|---|---|---|---|---|
| 1 | Letterform Archive | https://letterformarchive.org | Solo consulta. Imágenes © Letterform Archive (Online Archive) | No. Online Archive sin API pública |
| 2 | «Half a million images» (grabados japoneses) | https://www.metmuseum.org/art/collection | CC0: 492.000 imágenes de dominio público | Sí: API REST y CSV en github.com/metmuseum/openaccess |
| 3 | «800,000 works in high resolution» | https://www.rijksmuseum.nl/en/collection | Dominio público / CC0 donde consta; CC BY 4.0 en algunos casos | Sí: data.rijksmuseum.nl, IIIF y OAI-PMH |
| 4 | archives.design | https://archives.design | Solo consulta. Sitio © 2025, all rights reserved; derechos por pieza según Internet Archive | No. Cada pieza remite a Internet Archive |
| 5 | NYPL Digital Collections | https://digitalcollections.nypl.org | Dominio público / «no known U.S. copyright restrictions» (casi 500.000) | API Repo retirada el 1-ago-2026, sin reemplazo; metadatos PD en GitHub (CSV/JSON); imágenes una a una |
| 6 | SVA Archives (Glaser) | https://glaserarchives.org | Solo consulta. © de sus respectivos dueños; fines educativos | No |
| 7 | Cooper Hewitt | https://collection.cooperhewitt.org | Metadatos CC0; las imágenes no están incluidas ni cubiertas por CC0 | Volcado JSON CC0 en GitHub; API de colección (no comprobada hoy: 403) |
| 8 | Fonts In Use | https://fontsinuse.com | Solo consulta. Fair use; licencia personal y no comercial | No (solo RSS) |
| 9 | Design Reviewed | https://designreviewed.com | Solo consulta. Acceso libre; imágenes © de sus autores | No |
| 10 | Archivo de logos (libro rojo マーク・シンボル) | Sin identificar | Sin identificar | Sin identificar |
| 11 | People's Graphic Design Archive | https://peoplesgdarchive.org | Solo consulta: uso educativo y de investigación; todo el material sujeto a copyright | No |
| 12 | Dover · Treasury of Animal Illustrations | https://store.doverpublications.com/products/9780486258058 | Grabados del s. XVIII: dominio público en el original; la edición/recopilación Dover tiene copyright; no es CC0 | No. Libro en venta |

## Notas de identificación

- **2 (medio millón).** La cifra encaja con las 492.000 imágenes del Met; Smithsonian declara 3 millones. Los candidatos de la semilla no cuadran con «medio millón». Identificación **H1**, no SPEC.
- **3 (800.000).** El Rijksmuseum declara «más de un millón de objetos» y descarga en alta resolución; no se encontró hoy una cifra oficial de 800.000. Encaje por ukiyo-e, mariposas y pavo real: **H1**.
- **6 (SVA).** `glaserarchives.org` es el Milton Glaser Design Study Center and Archives / SVA Archives, no una sección de `sva.edu`.
- **10 (logos).** No se localizó con seguridad el libro japonés «マーク・シンボル». Queda sin identificar.
- **12 (Dover).** ISBN 9780486258058; título completo: *Treasury of Animal Illustrations from Eighteenth-Century Sources* (Dover, 1988), ed. Carol Belanger Grafton.
- **Evidencia:** E1 en las páginas abiertas hoy; las identificaciones 2, 3 y 6 son H1. `archives.design` devolvió 403 a la lectura automática; su nota de copyright se leyó en `marier.design`.

Pendiente: confirmar la entrada 10 con una imagen del vídeo o el lomo del libro; y decidir si se sustituyen en la semilla las URL nulas por las de esta tabla.
