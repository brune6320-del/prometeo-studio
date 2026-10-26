import React, { useState } from 'react';

/** Panel opt-in D-14; servidor local aparte, el proyecto nunca sale de la máquina. */
export function TelaranaPanel() {
  const [input, setInput] = useState('');
  const [url, setUrl] = useState<string | null>(null);
  const [error, setError] = useState('');
  return <main style={{ height: '100vh', display: 'flex', flexDirection: 'column', background: '#f4f2ec' }}>
    <form style={{ display: 'flex', gap: 12, padding: 12 }} onSubmit={(event) => {
      event.preventDefault();
      try {
        const parsed = new URL(input);
        if (parsed.protocol !== 'http:' || parsed.hostname !== '127.0.0.1' || !parsed.searchParams.get('token')) {
          throw new Error('Usa la dirección local con token que muestra el servidor Telaraña.');
        }
        setUrl(parsed.href); setError('');
      } catch { setError('Usa la dirección http://127.0.0.1 con token que muestra Telaraña.'); }
    }}>
      <label htmlFor="telarana-url">Telaraña · proyecto local</label>
      <input id="telarana-url" style={{ flex: 1 }} value={input} onChange={event => setInput(event.target.value)} placeholder="Pega la dirección del proyecto" />
      <button type="submit">Abrir panel</button>
      <span role="alert">{error}</span>
    </form>
    {url ? <iframe title="Telaraña de regiones y decisiones" src={url} style={{ border: 0, flex: 1 }} />
      : <p style={{ padding: 24 }}>Abre un proyecto con el servidor D-14 y pega su dirección local. El PDF original no se modifica.</p>}
  </main>;
}
