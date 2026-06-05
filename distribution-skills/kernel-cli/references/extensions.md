---
name: kernel-extensions
description: Upload, download, manage, and use Chrome extensions with Kernel browsers.
---

# Extensions

Use extensions for ad blocking, automation helpers, auth helpers, or extension
testing. Loading extensions changes browser behavior, so prefer explicit,
task-scoped extension use.

## List

```bash
kernel extensions list -o json
```

## Upload

```bash
kernel extensions upload ./my-extension -o json
kernel extensions upload ./my-extension --name my-ext -o json
```

## Download

```bash
kernel extensions download my-ext --to ./downloaded
kernel extensions download-web-store "https://chromewebstore.google.com/detail/extension-id" --to ./my-extension
kernel extensions download-web-store "https://chromewebstore.google.com/detail/extension-id" --to ./my-extension --os linux
```

Use `--os linux` when the extension will run in a Kernel browser.

## Delete

```bash
kernel extensions delete my-ext --yes
```

Confirm before deleting shared or user-owned extensions.

## Use With Browsers

```bash
SESSION=$(kernel browsers create --extension my-ext -o json | jq -r '.session_id')
kernel browsers playwright execute "$SESSION" 'await page.goto("https://example.com")'
kernel browsers delete "$SESSION" -y
```

You can also upload one or more unpacked extensions into a running browser:

```bash
kernel browsers extensions upload <session_id> ./extension-one ./extension-two
```
