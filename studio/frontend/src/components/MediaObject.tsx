import React, { useEffect, useRef } from 'react';
import type { BoardCard } from '../board/model';

/**
 * Pieza de medio con reproducción ligada a `playing`.
 *
 * La usan las vistas que muestran varias diapositivas a la vez: solo la activa
 * reproduce vídeo/audio; las demás se pausan al cambiar. No toca el modelo ni
 * duplica datos: lee la tarjeta y la pinta.
 */
export const MediaObject: React.FC<{
  card: BoardCard;
  playing?: boolean;
  className?: string;
  controls?: boolean;
}> = ({ card, playing = false, className, controls = false }) => {
  const videoRef = useRef<HTMLVideoElement | null>(null);
  const audioRef = useRef<HTMLAudioElement | null>(null);
  const media = card.media;
  const label = card.title.trim() || media?.name || 'Medio';

  useEffect(() => {
    const element = videoRef.current ?? audioRef.current;
    if (!element) return;
    if (playing) {
      const intent = element.play();
      if (intent && typeof intent.catch === 'function') intent.catch(() => {});
    } else {
      element.pause();
    }
  }, [playing]);

  if (!media) {
    return <span className={join('media-object', 'media-object-missing', className)}>{label}</span>;
  }

  if (media.kind === 'image') {
    return <img className={join('media-object', className)} src={media.dataUrl} alt={label} draggable={false} />;
  }

  if (media.kind === 'video') {
    return (
      <video
        ref={videoRef}
        className={join('media-object', className)}
        src={media.dataUrl}
        muted
        loop
        playsInline
        preload="metadata"
        aria-label={label}
        controls={controls}
      />
    );
  }

  if (media.kind === 'audio') {
    return (
      <span className={join('media-object', 'media-object-file', className)}>
        <span>{media.name}</span>
        <audio ref={audioRef} src={media.dataUrl} controls preload="metadata" />
      </span>
    );
  }

  return (
    <span className={join('media-object', 'media-object-file', className)}>
      <a href={media.dataUrl} download={media.name}>{media.name}</a>
    </span>
  );
};

function join(...values: Array<string | undefined>): string {
  return values.filter(Boolean).join(' ');
}
