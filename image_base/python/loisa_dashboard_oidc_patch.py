from pathlib import Path
import py_compile


PLUGIN = Path("/opt/hermes/plugins/dashboard_auth/self_hosted/__init__.py")

USER_AGENT_CONSTANT = '''
_OIDC_HTTP_USER_AGENT = (
    os.getenv("HERMES_DASHBOARD_OIDC_HTTP_USER_AGENT", "Hermes-Dashboard-OIDC/1.0").strip()
    or "Hermes-Dashboard-OIDC/1.0"
)
'''

CONSTANT_ANCHOR = "_JWKS_CACHE_SECONDS = 300\n"
JWKS_CLIENT_BEFORE = '''            self._jwks_client = PyJWKClient(
                disco["jwks_uri"],
                cache_keys=True,
                lifespan=_JWKS_CACHE_SECONDS,
            )
'''
JWKS_CLIENT_AFTER = '''            self._jwks_client = PyJWKClient(
                disco["jwks_uri"],
                cache_keys=True,
                lifespan=_JWKS_CACHE_SECONDS,
                headers={"User-Agent": _OIDC_HTTP_USER_AGENT},
            )
'''


def main() -> None:
    source = PLUGIN.read_text(encoding="utf-8")

    if "_OIDC_HTTP_USER_AGENT" not in source:
        if CONSTANT_ANCHOR not in source:
            raise RuntimeError(f"Could not find JWKS cache constant in {PLUGIN}")

        source = source.replace(CONSTANT_ANCHOR, f"{CONSTANT_ANCHOR}{USER_AGENT_CONSTANT}", 1)

    if 'headers={"User-Agent": _OIDC_HTTP_USER_AGENT}' not in source:
        if JWKS_CLIENT_BEFORE not in source:
            raise RuntimeError(f"Could not find PyJWKClient construction in {PLUGIN}")

        source = source.replace(JWKS_CLIENT_BEFORE, JWKS_CLIENT_AFTER, 1)

    PLUGIN.write_text(source, encoding="utf-8")
    py_compile.compile(str(PLUGIN), doraise=True)
    print(f"Patched Hermes self-hosted OIDC JWKS User-Agent: {PLUGIN}")


if __name__ == "__main__":
    main()
