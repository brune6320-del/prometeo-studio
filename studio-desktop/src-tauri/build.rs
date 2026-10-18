fn main() {
  println!("cargo:rerun-if-changed=../../studio/frontend/dist");
  tauri_build::build()
}
