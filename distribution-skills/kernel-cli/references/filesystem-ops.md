---
name: kernel-filesystem-ops
description: Read, write, upload, download, and manage files in Kernel browser VM filesystems.
---

# Filesystem Operations

Use filesystem operations to transfer fixtures, scripts, screenshots, generated
reports, and other artifacts between Hermes and a Kernel browser VM.

All remote `--path`, `--src`, and `--dest` values should be absolute paths.

## Directories

```bash
kernel browsers fs new-directory <session_id> --path /tmp/work
kernel browsers fs new-directory <session_id> --path /tmp/work --mode 0755
kernel browsers fs list-files <session_id> --path /tmp -o json
kernel browsers fs file-info <session_id> --path /tmp/work -o json
kernel browsers fs delete-directory <session_id> --path /tmp/work
```

## Files

```bash
kernel browsers fs read-file <session_id> --path /tmp/file.txt
kernel browsers fs read-file <session_id> --path /tmp/file.txt -o /tmp/local-file.txt
kernel browsers fs write-file <session_id> --path /tmp/remote.txt --source local.txt
kernel browsers fs write-file <session_id> --path /tmp/remote.txt --source local.txt --mode 0644
kernel browsers fs move <session_id> --src /tmp/old.txt --dest /tmp/new.txt
kernel browsers fs delete-file <session_id> --path /tmp/new.txt
kernel browsers fs set-permissions <session_id> --path /tmp/script.sh --mode 0755
```

## Uploads

```bash
kernel browsers fs upload <session_id> --file "local.txt:/tmp/remote.txt"
kernel browsers fs upload <session_id> --file "file1.txt:/tmp/file1.txt" --file "file2.txt:/tmp/file2.txt"
kernel browsers fs upload <session_id> --dest-dir /tmp --paths "file1.txt,file2.txt"
kernel browsers fs upload-zip <session_id> --zip archive.zip --dest-dir /tmp/extracted
```

## Downloads

```bash
kernel browsers fs download-dir-zip <session_id> --path /tmp/results -o /tmp/results.zip
```
