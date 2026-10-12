fn main() {
    // The two commands the hub's page may call (D38): check for an update, install it.
    tauri_build::try_build(
        tauri_build::Attributes::new()
            .app_manifest(tauri_build::AppManifest::new().commands(&["update_check", "update_install"])),
    )
    .expect("tauri build script failed");
}
