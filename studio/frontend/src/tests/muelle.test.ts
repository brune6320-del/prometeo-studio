import { describe, expect, it } from 'vitest';
import {
  FRICCION_INERCIA,
  MUELLES,
  Muelle,
  PARADA_INERCIA,
  crearEstado,
  envolvente,
  movimientoReducido,
  pasoInercia,
  pasoMuelle,
  resortar,
  rubberBand,
  seguir,
  tauPorMasa,
  velocidadDeMuestras,
} from '../motion/muelle';

function avanzar(estado = crearEstado(0), objetivo = 100, ms = 1000, paso = 16.67) {
  let actual = estado;
  for (let t = 0; t < ms; t += paso) actual = pasoMuelle(actual, objetivo, paso / 1000, MUELLES.firme);
  return actual;
}

describe('muelle', () => {
  it('llega al objetivo y se queda quieto sin rebote', () => {
    const estado = avanzar();
    expect(estado.posicion).toBeCloseTo(100, 5);
    expect(estado.velocidad).toBe(0);
  });

  it('es sobreamortiguado: nunca pasa del objetivo', () => {
    let estado = crearEstado(0);
    for (let i = 0; i < 120; i += 1) {
      estado = pasoMuelle(estado, 100, 1 / 60, MUELLES.firme);
      expect(estado.posicion).toBeLessThanOrEqual(100.0001);
    }
  });

  it('el muelle suave tarda más que el firme', () => {
    let firme = crearEstado(0);
    let suave = crearEstado(0);
    for (let i = 0; i < 12; i += 1) {
      firme = pasoMuelle(firme, 100, 1 / 60, MUELLES.firme);
      suave = pasoMuelle(suave, 100, 1 / 60, MUELLES.suave);
    }
    expect(firme.posicion).toBeGreaterThan(suave.posicion);
  });

  it('no explota con dt grandes ni valores no finitos', () => {
    const estado = pasoMuelle(crearEstado(0, 10), 100, 5, MUELLES.firme);
    expect(Number.isFinite(estado.posicion)).toBe(true);
    expect(Number.isFinite(estado.velocidad)).toBe(true);
    expect(pasoMuelle(crearEstado(3, 1), Number.NaN, 0.016, MUELLES.firme)).toEqual({ posicion: 3, velocidad: 1 });
  });

  it('interrumpir con un gesto nuevo no conserva el destino viejo', () => {
    const muelle = new Muelle(0);
    muelle.irA(100);
    for (let i = 0; i < 5; i += 1) muelle.paso(1 / 60);
    const enMedio = muelle.posicion;
    expect(enMedio).toBeGreaterThan(0);
    muelle.saltarA(40);
    expect(muelle.posicion).toBe(40);
    expect(muelle.destino).toBe(40);
    expect(muelle.enReposo).toBe(true);
  });

  it('tauPorMasa va de 35 a 160 ms', () => {
    expect(tauPorMasa(0.2)).toBeCloseTo(0.035, 6);
    expect(tauPorMasa(1.2)).toBeCloseTo(0.16, 6);
    expect(tauPorMasa(5)).toBeCloseTo(0.16, 6);
  });
});

describe('seguir (ley de Sala Oscura)', () => {
  it('avanza la fracción 1 − e^(−dt/τ)', () => {
    const pos = seguir(0, 100, 0.035, 0.035);
    expect(pos).toBeCloseTo(100 * (1 - Math.exp(-1)), 8);
  });

  it('se pega al objetivo dentro del imán', () => {
    expect(seguir(99.999, 100, 0.016, 0.035, 0.0018)).toBe(100);
  });

  it('con dt 0 o tau 0 no inventa movimiento', () => {
    expect(seguir(4, 10, 0, 0.035)).toBe(4);
    expect(seguir(4, 10, 0.016, 0)).toBe(10);
  });

  it('la envolvente ataca en 40 ms y suelta en 220 ms', () => {
    const ataque = envolvente(0, true, 0.04);
    expect(ataque).toBeCloseTo(1 - Math.exp(-1), 6);
    const release = envolvente(1, false, 0.22);
    expect(release).toBeCloseTo(Math.exp(-1), 6);
  });
});

describe('inercia', () => {
  it('calcula velocidad desde las muestras recientes', () => {
    const v = velocidadDeMuestras([
      { t: 0, x: 0, y: 0 },
      { t: 50, x: 50, y: 25 },
      { t: 100, x: 100, y: 50 },
    ]);
    expect(v.x).toBeCloseTo(1000, 5);
    expect(v.y).toBeCloseTo(500, 5);
  });

  it('decae y se detiene a 0.02 px/ms', () => {
    let estado = { x: 0, y: 0, vx: 2000, vy: 0 };
    for (let i = 0; i < 600; i += 1) estado = pasoInercia(estado, 1 / 60);
    expect(estado.vx).toBe(0);
    expect(estado.vy).toBe(0);
    expect(estado.x).toBeGreaterThan(0);
    expect(estado.x).toBeLessThan(FRICCION_INERCIA * 1000);
    expect(PARADA_INERCIA).toBe(0.02);
  });

  it('una muestra sola no genera velocidad', () => {
    expect(velocidadDeMuestras([{ t: 0, x: 10, y: 10 }])).toEqual({ x: 0, y: 0 });
  });
});

describe('rubber-band', () => {
  it('cede menos que el desborde', () => {
    const cedido = rubberBand(300, 400);
    expect(cedido).toBeGreaterThan(0);
    expect(cedido).toBeLessThan(300);
  });

  it('es monótona, simétrica y nunca alcanza la dimensión', () => {
    const valores = [1, 10, 100, 300, 1000].map((x) => rubberBand(x, 400));
    for (let i = 1; i < valores.length; i += 1) expect(valores[i]).toBeGreaterThan(valores[i - 1]);
    expect(valores[valores.length - 1]).toBeLessThan(400);
    expect(rubberBand(-300, 400)).toBeCloseTo(-rubberBand(300, 400), 8);
  });

  it('resortar deja intacto lo que está dentro', () => {
    expect(resortar(50, 0, 100)).toBe(50);
    expect(resortar(-10, 0, 100)).toBeLessThan(0);
    expect(resortar(110, 0, 100)).toBeGreaterThan(100);
  });

  it('sin desborde o sin dimensión no hay desplazamiento', () => {
    expect(rubberBand(0, 100)).toBe(0);
    expect(rubberBand(10, 0)).toBe(0);
  });
});

describe('prefers-reduced-motion', () => {
  it('sin matchMedia en el entorno de pruebas no reduce', () => {
    expect(movimientoReducido()).toBe(false);
  });
});
