// Prevents an extra console window on Windows, including local debug builds.
#![cfg_attr(windows, windows_subsystem = "windows")]

fn main() {
  app_lib::run();
}
