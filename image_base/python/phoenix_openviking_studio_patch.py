from pathlib import Path
import sysconfig


STUDIO_INDEX = (
    Path(sysconfig.get_path("purelib")) / "openviking" / "web_studio" / "dist" / "index.html"
)

BOOTSTRAP_SCRIPT = r'''<script id="phoenix-openviking-studio-bootstrap">
(function () {
  var hash = window.location.hash || "";
  if (hash.charAt(0) === "#") {
    hash = hash.slice(1);
  }

  var params = new URLSearchParams(hash);
  var encoded = params.get("phoenix_ov_bootstrap");
  if (!encoded) {
    return;
  }

  function decodeBase64Url(value) {
    var base64 = value.replace(/-/g, "+").replace(/_/g, "/");
    while (base64.length % 4) {
      base64 += "=";
    }
    var binary = window.atob(base64);
    var bytes = new Uint8Array(binary.length);
    for (var i = 0; i < binary.length; i += 1) {
      bytes[i] = binary.charCodeAt(i);
    }
    return JSON.parse(new TextDecoder().decode(bytes));
  }

  try {
    var payload = decodeBase64Url(encoded);
    if (
      !payload ||
      payload.v !== 1 ||
      typeof payload.baseUrl !== "string" ||
      typeof payload.apiKey !== "string" ||
      typeof payload.accountId !== "string" ||
      typeof payload.userId !== "string"
    ) {
      throw new Error("Invalid Phoenix OpenViking Studio bootstrap payload");
    }

    var agentId =
      typeof payload.agentId === "string" && payload.agentId.trim()
        ? payload.agentId
        : "hermes-memory";
    var connection = {
      baseUrl: payload.baseUrl,
      apiKey: payload.apiKey,
      adminApiKey: typeof payload.adminApiKey === "string" ? payload.adminApiKey : "",
      accountId: payload.accountId,
      userId: payload.userId,
      agentId: agentId
    };

    window.sessionStorage.setItem("ov_console_api_key", payload.apiKey);
    window.localStorage.setItem("ov_console_connection", JSON.stringify(connection));
  } finally {
    window.history.replaceState(
      window.history.state,
      document.title,
      window.location.pathname + window.location.search
    );
  }
})();
</script>'''


def main() -> None:
    source = STUDIO_INDEX.read_text(encoding="utf-8")

    if "phoenix-openviking-studio-bootstrap" in source:
        print(f"Phoenix OpenViking Studio bootstrap already patched: {STUDIO_INDEX}")
        return

    anchor = '<script type="module"'
    if anchor in source:
        source = source.replace(anchor, f"{BOOTSTRAP_SCRIPT}\n{anchor}", 1)
    elif "</head>" in source:
        source = source.replace("</head>", f"{BOOTSTRAP_SCRIPT}\n</head>", 1)
    else:
        raise RuntimeError(f"Could not find Studio bootstrap insertion point in {STUDIO_INDEX}")

    STUDIO_INDEX.write_text(source, encoding="utf-8")
    print(f"Patched Phoenix OpenViking Studio bootstrap: {STUDIO_INDEX}")


if __name__ == "__main__":
    main()
