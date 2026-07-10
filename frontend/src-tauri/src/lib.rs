use serde_json::Value;
use std::io::Write;
use std::path::{Path, PathBuf};
use std::process::{Command, Stdio};
#[cfg(windows)]
use std::os::windows::process::CommandExt;
use tauri::Manager;

#[cfg(windows)]
const CREATE_NO_WINDOW: u32 = 0x08000000;

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

fn resource_path(app: &tauri::AppHandle, name: &str) -> Option<PathBuf> {
  let mut candidates = Vec::new();
  if let Ok(resource_dir) = app.path().resource_dir() {
    candidates.push(resource_dir.join(name));
  }
  if let Ok(exe) = std::env::current_exe() {
    if let Some(dir) = exe.parent() {
      candidates.push(dir.join(name));
    }
  }
  candidates.into_iter().find(|path| path.exists())
}

fn bridge_command(app: &tauri::AppHandle) -> (PathBuf, Vec<PathBuf>, PathBuf) {
  if let Some(sidecar) = resource_path(app, "photovault-bridge.exe") {
    return (sidecar, Vec::new(), std::env::current_exe().ok().and_then(|p| p.parent().map(Path::to_path_buf)).unwrap_or_else(repo_root));
  }
  let root = repo_root();
  (python_path(), vec![root.join("bridge.py")], root)
}

#[tauri::command]
async fn bridge(app: tauri::AppHandle, command: String, payload: Value) -> Result<Value, String> {
  tauri::async_runtime::spawn_blocking(move || {
    let (program, prefix_args, working_dir) = bridge_command(&app);
    let mut command_builder = Command::new(program);
    for arg in prefix_args {
      command_builder.arg(arg);
    }
    command_builder
      .arg(command)
      .current_dir(&working_dir)
      .env("PYTHONUTF8", "1")
      .env("PYTHONIOENCODING", "utf-8")
      .stdin(Stdio::piped())
      .stdout(Stdio::piped())
      .stderr(Stdio::piped());
    if let Some(ffmpeg) = resource_path(&app, "ffmpeg.exe") {
      command_builder.env("PHOTOVAULT_FFMPEG", ffmpeg);
    }
    if let Some(ffprobe) = resource_path(&app, "ffprobe.exe") {
      command_builder.env("PHOTOVAULT_FFPROBE", ffprobe);
    }
    if let Some(exiftool) = resource_path(&app, "exiftool/exiftool.exe") {
      command_builder.env("PHOTOVAULT_EXIFTOOL", exiftool);
    }
    #[cfg(windows)]
    command_builder.creation_flags(CREATE_NO_WINDOW);

    let mut child = command_builder
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

#[tauri::command]
async fn pick_folder_native(initial: Option<String>, title: Option<String>) -> Result<String, String> {
  tauri::async_runtime::spawn_blocking(move || {
    let mut dialog = rfd::FileDialog::new().set_title(title.as_deref().unwrap_or("Selecione uma pasta"));
    if let Some(initial_dir) = initial {
      let path = PathBuf::from(initial_dir);
      if path.exists() {
        dialog = dialog.set_directory(path);
      }
    }
    Ok(dialog.pick_folder().map(|path| path.to_string_lossy().to_string()).unwrap_or_default())
  })
  .await
  .map_err(|err| err.to_string())?
}

#[tauri::command]
async fn open_path_native(path: String) -> Result<(), String> {
  tauri::async_runtime::spawn_blocking(move || {
    let target = PathBuf::from(path);
    if !target.exists() {
      return Err(format!("Caminho nao existe: {}", target.display()));
    }
    Command::new("explorer.exe")
      .arg(target)
      .spawn()
      .map_err(|err| format!("Falha ao abrir no Explorer: {err}"))?;
    Ok(())
  })
  .await
  .map_err(|err| err.to_string())?
}

#[tauri::command]
async fn reveal_path_native(path: String) -> Result<(), String> {
  tauri::async_runtime::spawn_blocking(move || {
    let target = PathBuf::from(path);
    if !target.exists() {
      return Err(format!("Caminho nao existe: {}", target.display()));
    }
    let mut command = Command::new("explorer.exe");
    if target.is_file() {
      command.arg(format!("/select,{}", target.display()));
    } else {
      command.arg(target);
    }
    command
      .spawn()
      .map_err(|err| format!("Falha ao localizar no Explorer: {err}"))?;
    Ok(())
  })
  .await
  .map_err(|err| err.to_string())?
}

#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
  tauri::Builder::default()
    .invoke_handler(tauri::generate_handler![bridge, pick_folder_native, open_path_native, reveal_path_native])
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
