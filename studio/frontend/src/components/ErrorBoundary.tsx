import React from 'react';
import { BrandMark } from './ui';
import { CLOSE_REQUEST_HANDLER, acknowledgeCloseDialog, confirmClose } from '../api/host';

interface State {
  error: Error | null;
  closeAsked: boolean;
}

/** Si la interfaz falla al dibujarse, se muestra una salida clara en lugar de una ventana vacía. */
export class ErrorBoundary extends React.Component<{ children: React.ReactNode }, State> {
  state: State = { error: null, closeAsked: false };

  static getDerivedStateFromError(error: Error): Partial<State> {
    return { error };
  }

  componentDidCatch(error: Error, info: React.ErrorInfo) {
    console.error('PROMETEO UI error', error, info.componentStack);
    // Con la interfaz caída, el trabajo sigue en el motor y «Recargar» lo recupera. Al primer
    // intento de cierre se avisa; al segundo se cierra (nunca se atrapa a la persona).
    (window as unknown as Record<string, unknown>)[CLOSE_REQUEST_HANDLER] = () => {
      void acknowledgeCloseDialog();
      if (this.state.closeAsked) void confirmClose();
      else this.setState({ closeAsked: true });
    };
  }

  render() {
    if (!this.state.error) return this.props.children;
    return (
      <main className="boot" role="alert">
        <section className="boot-card">
          <div className="boot-brand">
            <BrandMark size={30} />
            <h1 style={{ margin: 0, fontSize: 'var(--fs-xl)' }}>La interfaz encontró un error</h1>
          </div>
          <p>Tus documentos no se modificaron: PROMETEO trabaja sobre copias y solo guarda lo que tú decides guardar.</p>
          <p className="muted">
            Recarga la interfaz para continuar: si tenías cambios o una copia verificada sin guardar, se recuperan. Si se repite, comparte el
            detalle técnico.
          </p>
          {this.state.closeAsked && (
            <p role="alert" style={{ color: 'var(--st-reject)' }}>
              Si cierras ahora, se pierde el trabajo sin guardar. Pulsa «Recargar la interfaz» para recuperarlo, o vuelve a cerrar para salir.
            </p>
          )}
          <button className="btn btn-primary" onClick={() => window.location.reload()}>
            Recargar la interfaz
          </button>
          <div className="notice-tech" style={{ marginTop: 'var(--sp-4)' }}>
            {this.state.error.name}: {this.state.error.message}
          </div>
        </section>
      </main>
    );
  }
}
