import { FileUp, ImagePlus } from 'lucide-react';
import { createCard, type BoardCard } from '../model';
import type { BoardTool } from './registry';
import { esTarjetaDe } from './guard';
import { CuerpoTexto } from './parts';

export const mediaTool: BoardTool<BoardCard> = {
  id: 'media',
  nombre: 'Multimedia',
  tipo: 'tarjeta',
  icono: ImagePlus,
  crear: (x, y) => createCard('media', x, y),
  validar: esTarjetaDe('media'),
  Vista: ({ datos, editar }) => (
    <>
      {datos.media && (
        <div className="board-card-media">
          {datos.media.kind === 'image' && <img src={datos.media.dataUrl} alt={datos.title} draggable={false} />}
          {datos.media.kind === 'video' && <video src={datos.media.dataUrl} controls preload="metadata" />}
          {datos.media.kind === 'audio' && <audio src={datos.media.dataUrl} controls preload="metadata" />}
          {datos.media.kind === 'file' && <a className="board-attachment" href={datos.media.dataUrl} download={datos.media.name}><FileUp size={17} />{datos.media.name}</a>}
        </div>
      )}
      <CuerpoTexto datos={datos} editar={editar} placeholder="Añade un comentario…" />
    </>
  ),
};
