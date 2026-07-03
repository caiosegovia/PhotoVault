use serde_json::Value;
use std::io::Write;
use std::path::PathBuf;
use std::process::{Command, Stdio};

fn repo_root() -> PathBuf {
  PathBuf::from(env!("CARGO_MANIFEST_DIR"))
    .parent()
    .and_then(|p| p.parent())
    .expect("repo root")
    .to_path_buf()
}

fn python_path() -> PathBuf {
  repo_root().join(".venv").join("Scripts").join("python.exe")
}

#[tauri::command]
async fn bridge(command: String, payload: Value) -> Result<Value, String> {
  tauri::async_runtime::spawn_blocking(move || {
    let root = repo_root();
    let mut child = Command::new(python_path())
      .arg(root.join("bridge.py"))
      .arg(command)
      .current_dir(&root)
      .env("PYTHONUTF8", "1")
      .env("PYTHONIOENCODING", "utf-8")
      .stdin(Stdio::piped())
      .stdout(Stdio::piped())
      .stderr(Stdio::piped())
      .spawn()
      .map_err(|err| format!("Falha ao iniciar bridge Python: {err}"))?;

    if let Some(stdin) = child.stdin.as_mut() {
      let body = serde_json::to_vec(&payload).map_err(|err| err.to_string())?;
      stdin.write_all(&body).map_err(|err| err.to_string())?;
    }

    let output = child
      .wait_with_output()
      .map_err(|err| format!("Falha ao aguardar bridge Python: {err}"))?;
    let stdout = String::from_utf8_lossy(&output.stdout);
    let stderr = String::from_utf8_lossy(&output.stderr);
    if !output.status.success() {
      if let Ok(value) = serde_json::from_str::<Value>(&stdout) {
        return Err(value.get("error").and_then(Value::as_str).unwrap_or("Erro na bridge").to_string());
      }
      return Err(format!("Bridge falhou: {stderr}"));
    }
    serde_json::from_str::<Value>(&stdout).map_err(|err| format!("JSON invalido da bridge: {err}; stdout={stdout}"))
  })
  .await
  .map_err(|err| err.to_string())?
}

#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
  tauri::Builder::default()
    .invoke_handler(tauri::generate_handler![bridge])
    .setup(|app| {
      if cfg!(debug_assertions) {
        app.handle().plugin(
          tauri_plugin_log::Builder::default()
            .level(log::LevelFilter::Info)
            .build(),
        )?;
      }
      Ok(())
    })
    .run(tauri::generate_context!())
    .expect("error while running tauri application");
}
