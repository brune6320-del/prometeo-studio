//! Guarda de cierre con trabajo sin guardar (CAMP-002 · F1).
//!
//! La interfaz informa al host de si hay trabajo que se perdería (cambios preparados o una
//! copia verificada sin guardar). El host solo bloquea el cierre en ese caso y pide a la
//! interfaz que pregunte a la persona. Dos garantías:
//! - Nunca se pierde trabajo en silencio: con trabajo pendiente, cerrar pregunta primero.
//! - Nunca queda la app atrapada: si la interfaz no confirma que mostró el diálogo en
//!   `UNRESPONSIVE_GRACE` (contados desde el primer intento sin respuesta; los clics
//!   repetidos no reinician el reloj), el siguiente intento de cierre se permite.
//! - Los avisos de la interfaz llevan número de secuencia: un aviso viejo de «limpio»
//!   que llegue tarde no puede desactivar la guarda.

use std::time::{Duration, Instant};

/// Margen para que la interfaz confirme el diálogo (holgado: un documento grande puede tener
/// la interfaz ocupada unos segundos).
pub const UNRESPONSIVE_GRACE: Duration = Duration::from_secs(6);

#[derive(Debug, Default)]
pub struct UnsavedState {
    pub dirty: bool,
    pub kind: String,
    pub count: u32,
    /// Último número de secuencia aceptado de la interfaz.
    pub last_seq: u64,
    /// La persona ya decidió cerrar (guardó o descartó): no volver a preguntar.
    pub allow_close: bool,
    /// Momento del último cierre bloqueado cuyo diálogo aún no se confirmó.
    pub pending_since: Option<Instant>,
    /// La interfaz confirmó que mostró el diálogo del último cierre bloqueado.
    pub acked: bool,
}

#[derive(Debug, PartialEq, Eq)]
pub enum CloseDecision {
    /// Cerrar ya: no hay nada que perder, la persona lo decidió o la interfaz no responde.
    Allow,
    /// No cerrar todavía: pedir a la interfaz que pregunte.
    AskUser,
}

impl UnsavedState {
    /// Aplica un aviso de la interfaz. Devuelve `false` si es más viejo que el último aceptado.
    pub fn report(&mut self, seq: u64, dirty: bool, kind: &str, count: u32) -> bool {
        if seq < self.last_seq {
            return false;
        }
        self.last_seq = seq;
        self.dirty = dirty;
        self.kind = kind.chars().take(32).collect();
        self.count = count;
        if !dirty {
            self.pending_since = None;
            self.acked = false;
        }
        true
    }

    pub fn acknowledge(&mut self) {
        self.acked = true;
    }

    pub fn decide(&mut self, now: Instant) -> CloseDecision {
        if self.allow_close || !self.dirty {
            return CloseDecision::Allow;
        }
        match self.pending_since {
            // Ya hay una petición sin respuesta: no reiniciar el reloj.
            Some(since) if !self.acked => {
                if now.duration_since(since) >= UNRESPONSIVE_GRACE {
                    // La interfaz no mostró el diálogo: no atrapar a la persona.
                    CloseDecision::Allow
                } else {
                    CloseDecision::AskUser
                }
            }
            // Sin petición pendiente, o la interfaz ya mostró el diálogo: preguntar de nuevo.
            _ => {
                self.pending_since = Some(now);
                self.acked = false;
                CloseDecision::AskUser
            }
        }
    }
}

/// Script que el host evalúa en la página al bloquear un cierre. Si el manejador no existe
/// (la interfaz se reinició o falló), confirma el cierre directamente.
pub const CLOSE_REQUEST_SCRIPT: &str = "(function(){try{if(window.__prometeoCloseRequested){window.__prometeoCloseRequested();}else if(window.__TAURI_INTERNALS__){window.__TAURI_INTERNALS__.invoke('confirm_close');}}catch(e){if(window.__TAURI_INTERNALS__){window.__TAURI_INTERNALS__.invoke('confirm_close');}}})();";

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn clean_state_closes_immediately() {
        let mut s = UnsavedState::default();
        assert_eq!(s.decide(Instant::now()), CloseDecision::Allow);
    }

    #[test]
    fn unsaved_work_asks_first() {
        let mut s = UnsavedState::default();
        s.report(1, true, "verified_unsaved", 1);
        assert_eq!(s.decide(Instant::now()), CloseDecision::AskUser);
    }

    #[test]
    fn repeated_close_while_dialog_shown_keeps_asking() {
        let mut s = UnsavedState::default();
        s.report(1, true, "staged", 2);
        let t0 = Instant::now();
        assert_eq!(s.decide(t0), CloseDecision::AskUser);
        s.acknowledge();
        assert_eq!(s.decide(t0 + Duration::from_secs(10)), CloseDecision::AskUser);
    }

    #[test]
    fn unresponsive_interface_never_traps_the_user() {
        let mut s = UnsavedState::default();
        s.report(1, true, "staged", 1);
        let t0 = Instant::now();
        assert_eq!(s.decide(t0), CloseDecision::AskUser);
        // Sin acuse de la interfaz: un segundo intento pasado el margen cierra.
        assert_eq!(s.decide(t0 + UNRESPONSIVE_GRACE), CloseDecision::Allow);
    }

    #[test]
    fn second_click_within_grace_still_asks() {
        let mut s = UnsavedState::default();
        s.report(1, true, "staged", 1);
        let t0 = Instant::now();
        assert_eq!(s.decide(t0), CloseDecision::AskUser);
        assert_eq!(s.decide(t0 + Duration::from_millis(500)), CloseDecision::AskUser);
    }

    #[test]
    fn confirmed_close_is_allowed() {
        let mut s = UnsavedState::default();
        s.report(1, true, "verified_unsaved", 1);
        s.allow_close = true;
        assert_eq!(s.decide(Instant::now()), CloseDecision::Allow);
    }

    #[test]
    fn saving_clears_the_guard() {
        let mut s = UnsavedState::default();
        s.report(1, true, "verified_unsaved", 1);
        assert_eq!(s.decide(Instant::now()), CloseDecision::AskUser);
        s.report(2, false, "", 0);
        assert_eq!(s.decide(Instant::now()), CloseDecision::Allow);
    }

    #[test]
    fn repeated_clicks_do_not_extend_the_grace() {
        let mut s = UnsavedState::default();
        s.report(1, true, "staged", 1);
        let t0 = Instant::now();
        assert_eq!(s.decide(t0), CloseDecision::AskUser);
        // La interfaz no responde; la persona insiste cada segundo.
        for i in 1..6 {
            assert_eq!(s.decide(t0 + Duration::from_secs(i)), CloseDecision::AskUser);
        }
        // El margen cuenta desde el primer intento, no desde el último clic.
        assert_eq!(s.decide(t0 + UNRESPONSIVE_GRACE), CloseDecision::Allow);
    }

    #[test]
    fn stale_clean_report_cannot_disable_the_guard() {
        let mut s = UnsavedState::default();
        assert!(s.report(5, true, "verified_unsaved", 1));
        // Un aviso «limpio» anterior que llega tarde se ignora.
        assert!(!s.report(4, false, "", 0));
        assert_eq!(s.decide(Instant::now()), CloseDecision::AskUser);
    }

    #[test]
    fn kind_is_bounded() {
        let mut s = UnsavedState::default();
        s.report(1, true, &"x".repeat(500), 1);
        assert_eq!(s.kind.len(), 32);
    }
}
