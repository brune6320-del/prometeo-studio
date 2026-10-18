import React, { useState } from 'react';
import { Send } from 'lucide-react';
import { StatusBadge } from './ui';

export interface AgentMessage {
  from: 'user' | 'assistant';
  text: string;
  status?: string;
}

interface AgentPanelProps {
  messages: AgentMessage[];
  thinking: boolean;
  disabled: boolean;
  onSend: (text: string) => void;
}

/** Asistente experimental: analizador determinista, sin modelo de lenguaje. Solo prepara cambios. */
export const AgentPanel: React.FC<AgentPanelProps> = ({ messages, thinking, disabled, onSend }) => {
  const [text, setText] = useState('');
  return (
    <div className="chat">
      <div style={{ display: 'flex', gap: 'var(--sp-2)', alignItems: 'center', flexWrap: 'wrap' }}>
        <StatusBadge kind="experimental">Experimental · sin IA</StatusBadge>
        <span className="hint">Entiende «Cambia texto actual por texto nuevo». Solo prepara cambios: tú los revisas y la verificación decide.</span>
      </div>
      <div className="chat-log" aria-live="polite" aria-label="Conversación con el asistente">
        {messages.length === 0 && <p className="muted">Ejemplo: Cambia «Juan Perez» por «Ana Ruiz».</p>}
        {messages.map((m, i) => (
          <div key={i} className={`msg ${m.from === 'user' ? 'msg-user' : ''}`}>
            <span className="sr-only">{m.from === 'user' ? 'Tú: ' : 'Asistente: '}</span>
            {m.text}
          </div>
        ))}
        {thinking && <div className="msg muted">Buscando…</div>}
      </div>
      <form
        className="chat-form"
        onSubmit={(e) => {
          e.preventDefault();
          if (!text.trim() || disabled) return;
          onSend(text.trim());
          setText('');
        }}
      >
        <label htmlFor="assistant-input" className="sr-only">
          Mensaje para el asistente
        </label>
        <input id="assistant-input" className="input" value={text} onChange={(e) => setText(e.target.value)} disabled={disabled || thinking} placeholder="Cambia «…» por «…»" />
        <button className="btn btn-outline" type="submit" disabled={disabled || thinking || !text.trim()} aria-label="Enviar">
          <Send size={15} />
        </button>
      </form>
    </div>
  );
};
