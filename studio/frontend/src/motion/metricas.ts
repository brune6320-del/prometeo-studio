/** Contadores de rendimiento del tablero. Solo lectura; no altera la app. */
export interface MetricasForja {
  rendersTarjeta: number;
  frames: number;
  reiniciar(): void;
}

export const metricas: MetricasForja = {
  rendersTarjeta: 0,
  frames: 0,
  reiniciar() {
    this.rendersTarjeta = 0;
    this.frames = 0;
  },
};

if (typeof window !== 'undefined') {
  (window as unknown as { __forjaMetricas?: MetricasForja }).__forjaMetricas = metricas;
}
