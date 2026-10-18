//! macOS: ⌘Q, «Salir» del Dock y el cierre de sesión llaman a `-[NSApplication terminate:]`, que
//! consulta `applicationShouldTerminate:` del delegado. tao no implementa ese método, así que la
//! app terminaba sin pasar por la guarda de cierre (hallazgo P0 de la revisión crítica de F1).
//! Aquí se añade el método al delegado de tao en tiempo de ejecución:
//! - con trabajo sin guardar: devuelve NSTerminateCancel y pide a la interfaz que pregunte;
//! - si no: NSTerminateNow (comportamiento normal).
//! Si tao llegara a implementar el método, `class_addMethod` no lo sustituye y se registra.

use std::ffi::CStr;
use std::sync::OnceLock;

use objc2::runtime::{AnyClass, AnyObject, Imp, Sel};
use objc2::{class, msg_send, sel};

use crate::close_guard::CloseDecision;

static APP: OnceLock<tauri::AppHandle> = OnceLock::new();

const NS_TERMINATE_CANCEL: usize = 0;
const NS_TERMINATE_NOW: usize = 1;

extern "C-unwind" fn application_should_terminate(_this: &AnyObject, _cmd: Sel, _sender: *mut AnyObject) -> usize {
    match APP.get() {
        Some(app) if crate::guard_exit(app, "salida (⌘Q/Dock)") == CloseDecision::AskUser => NS_TERMINATE_CANCEL,
        _ => NS_TERMINATE_NOW,
    }
}

pub fn install(app: &tauri::AppHandle) {
    let _ = APP.set(app.clone());
    unsafe {
        let ns_app: *mut AnyObject = msg_send![class!(NSApplication), sharedApplication];
        if ns_app.is_null() {
            eprintln!("[PROMETEO HOST] guarda ⌘Q: NSApplication no disponible");
            return;
        }
        let delegate: *mut AnyObject = msg_send![ns_app, delegate];
        if delegate.is_null() {
            eprintln!("[PROMETEO HOST] guarda ⌘Q: la app no tiene delegado");
            return;
        }
        let cls: &AnyClass = (*delegate).class();
        let imp: Imp = std::mem::transmute(
            application_should_terminate as extern "C-unwind" fn(&AnyObject, Sel, *mut AnyObject) -> usize,
        );
        // Tipos: devuelve NSUInteger (Q), recibe self (@), _cmd (:), sender (@).
        let types: &CStr = c"Q@:@";
        let added = objc2::ffi::class_addMethod(
            cls as *const AnyClass as *mut AnyClass,
            sel!(applicationShouldTerminate:),
            imp,
            types.as_ptr(),
        );
        if added.as_bool() {
            eprintln!("[PROMETEO HOST] guarda ⌘Q instalada");
        } else {
            eprintln!("[PROMETEO HOST] guarda ⌘Q: el delegado ya define applicationShouldTerminate:; no se sustituye");
        }
    }
}
