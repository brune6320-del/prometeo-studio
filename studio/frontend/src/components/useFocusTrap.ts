import { useEffect, type RefObject } from 'react';

const SELECTOR_FOCO = 'button:not([disabled]), [href], input:not([disabled]), select:not([disabled]), textarea:not([disabled]), [tabindex]:not([tabindex="-1"])';

/**
 * Atrapa el foco en un diálogo y lo devuelve al disparador al cerrarlo.
 * Tab y ⇧Tab ciclan; Esc lo maneja el cierre del tablero (no se duplica aquí).
 */
export function useFocusTrap(active: boolean, ref: RefObject<HTMLElement | null>): void {
  useEffect(() => {
    if (!active) return;
    const contenedor = ref.current;
    if (!contenedor) return;
    const previamenteEnfocado = document.activeElement as HTMLElement | null;

    const enfocables = () => Array.from(contenedor.querySelectorAll<HTMLElement>(SELECTOR_FOCO))
      .filter((element) => !element.hasAttribute('inert') && element.getClientRects().length > 0);
    const primero = enfocables()[0];
    if (primero) primero.focus();
    else {
      contenedor.setAttribute('tabindex', '-1');
      contenedor.focus();
    }

    const alTeclear = (event: KeyboardEvent) => {
      if (event.key !== 'Tab') return;
      const elementos = enfocables();
      if (!elementos.length) {
        event.preventDefault();
        contenedor.focus();
        return;
      }
      const actual = document.activeElement as HTMLElement | null;
      const primeroActual = elementos[0];
      const ultimo = elementos[elementos.length - 1];
      if (event.shiftKey && (actual === primeroActual || !contenedor.contains(actual))) {
        event.preventDefault();
        ultimo.focus();
      } else if (!event.shiftKey && (actual === ultimo || !contenedor.contains(actual))) {
        event.preventDefault();
        primeroActual.focus();
      }
    };
    document.addEventListener('keydown', alTeclear, true);
    return () => {
      document.removeEventListener('keydown', alTeclear, true);
      if (previamenteEnfocado && document.contains(previamenteEnfocado)) {
        previamenteEnfocado.focus();
      }
    };
  }, [active, ref]);
}
