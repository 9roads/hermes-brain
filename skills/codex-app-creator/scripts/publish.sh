#!/usr/bin/env bash
set -euo pipefail

BASE_URL="https://here.now"
CLIENT="hermes"
SPA_MODE="false"
TARGET=""

usage() {
  cat <<'USAGE'
Usage: publish.sh <file-or-dir> [--client <name>] [--spa]

Creates a fresh anonymous here.now publish. Anonymous publishes expire in 24
hours unless the returned claim URL is used.
USAGE
  exit 1
}

die() {
  echo "error: $1" >&2
  exit 1
}

for cmd in curl file jq; do
  command -v "$cmd" >/dev/null 2>&1 || die "requires $cmd"
done

while [[ $# -gt 0 ]]; do
  case "$1" in
    --client)
      CLIENT="$2"
      shift 2
      ;;
    --spa)
      SPA_MODE="true"
      shift
      ;;
    --help | -h)
      usage
      ;;
    -*)
      die "unknown option: $1"
      ;;
    *)
      [[ -z "$TARGET" ]] || die "unexpected argument: $1"
      TARGET="$1"
      shift
      ;;
  esac
done

[[ -n "$TARGET" ]] || usage
[[ -e "$TARGET" ]] || die "path does not exist: $TARGET"

compute_sha256() {
  local f="$1"
  if command -v sha256sum >/dev/null 2>&1; then
    sha256sum "$f" | cut -d' ' -f1
  else
    shasum -a 256 "$f" | cut -d' ' -f1
  fi
}

guess_content_type() {
  local f="$1"
  case "${f##*.}" in
    html | htm) echo "text/html; charset=utf-8" ;;
    css) echo "text/css; charset=utf-8" ;;
    js | mjs) echo "text/javascript; charset=utf-8" ;;
    json) echo "application/json; charset=utf-8" ;;
    md | txt) echo "text/plain; charset=utf-8" ;;
    svg) echo "image/svg+xml" ;;
    png) echo "image/png" ;;
    jpg | jpeg) echo "image/jpeg" ;;
    gif) echo "image/gif" ;;
    webp) echo "image/webp" ;;
    pdf) echo "application/pdf" ;;
    mp4) echo "video/mp4" ;;
    mov) echo "video/quicktime" ;;
    mp3) echo "audio/mpeg" ;;
    wav) echo "audio/wav" ;;
    xml) echo "application/xml" ;;
    woff2) echo "font/woff2" ;;
    woff) echo "font/woff" ;;
    ttf) echo "font/ttf" ;;
    ico) echo "image/x-icon" ;;
    *) file --brief --mime-type "$f" 2>/dev/null || echo "application/octet-stream" ;;
  esac
}

add_file() {
  local publish_path="$1"
  local local_path="$2"
  local size content_type hash

  size=$(wc -c < "$local_path" | tr -d ' ')
  content_type=$(guess_content_type "$local_path")
  hash=$(compute_sha256 "$local_path")

  FILES_JSON=$(echo "$FILES_JSON" | jq \
    --arg p "$publish_path" \
    --argjson s "$size" \
    --arg c "$content_type" \
    --arg h "$hash" \
    '. + [{"path": $p, "size": $s, "contentType": $c, "hash": $h}]')

  FILE_MAP=$(echo "$FILE_MAP" | jq \
    --arg p "$publish_path" \
    --arg a "$local_path" \
    '. + {($p): $a}')
}

FILES_JSON="[]"
FILE_MAP="{}"

if [[ -f "$TARGET" ]]; then
  abs=$(cd "$(dirname "$TARGET")" && pwd)/$(basename "$TARGET")
  add_file "$(basename "$TARGET")" "$abs"
elif [[ -d "$TARGET" ]]; then
  while IFS= read -r -d '' file_path; do
    rel="${file_path#$TARGET/}"
    [[ "$rel" == ".DS_Store" ]] && continue
    [[ "$(basename "$rel")" == ".DS_Store" ]] && continue
    abs=$(cd "$(dirname "$file_path")" && pwd)/$(basename "$file_path")
    add_file "$rel" "$abs"
  done < <(find "$TARGET" -type f -print0 | sort -z)
else
  die "not a file or directory: $TARGET"
fi

file_count=$(echo "$FILES_JSON" | jq 'length')
[[ "$file_count" -gt 0 ]] || die "no files found"

BODY=$(echo "$FILES_JSON" | jq '{files: .}')
if [[ "$SPA_MODE" == "true" ]]; then
  BODY=$(echo "$BODY" | jq '.spaMode = true')
fi

normalized_client=$(echo "$CLIENT" | tr '[:upper:]' '[:lower:]' | tr -cs 'a-z0-9._-' '-')
normalized_client="${normalized_client#-}"
normalized_client="${normalized_client%-}"
if [[ -z "$normalized_client" ]]; then
  normalized_client="hermes"
fi
CLIENT_HEADER_VALUE="${normalized_client}/codex-app-creator-publish-sh"

echo "creating anonymous publish ($file_count files)..." >&2
RESPONSE=$(curl -sS -X POST "$BASE_URL/api/v1/publish" \
  -H "x-herenow-client: $CLIENT_HEADER_VALUE" \
  -H "content-type: application/json" \
  -d "$BODY")

if echo "$RESPONSE" | jq -e '.error' >/dev/null 2>&1; then
  err=$(echo "$RESPONSE" | jq -r '.error')
  details=$(echo "$RESPONSE" | jq -r '.details // empty')
  die "$err${details:+ ($details)}"
fi

OUT_SLUG=$(echo "$RESPONSE" | jq -r '.slug')
VERSION_ID=$(echo "$RESPONSE" | jq -r '.upload.versionId')
FINALIZE_URL=$(echo "$RESPONSE" | jq -r '.upload.finalizeUrl')
SITE_URL=$(echo "$RESPONSE" | jq -r '.siteUrl')
UPLOAD_COUNT=$(echo "$RESPONSE" | jq '.upload.uploads | length')
SKIPPED_COUNT=$(echo "$RESPONSE" | jq '.upload.skipped // [] | length')

[[ "$OUT_SLUG" != "null" && -n "$OUT_SLUG" ]] || die "unexpected response: $RESPONSE"
[[ "$VERSION_ID" != "null" && -n "$VERSION_ID" ]] || die "missing version id"
[[ "$FINALIZE_URL" == https://* ]] || die "missing finalize URL"
[[ "$SITE_URL" == https://* ]] || die "missing site URL"

if [[ "$SKIPPED_COUNT" -gt 0 ]]; then
  echo "uploading $UPLOAD_COUNT files ($SKIPPED_COUNT unchanged, skipped)..." >&2
else
  echo "uploading $UPLOAD_COUNT files..." >&2
fi

upload_errors=0
if [[ "$UPLOAD_COUNT" -gt 0 ]]; then
  for i in $(seq 0 $((UPLOAD_COUNT - 1))); do
    upload_path=$(echo "$RESPONSE" | jq -r ".upload.uploads[$i].path")
    upload_url=$(echo "$RESPONSE" | jq -r ".upload.uploads[$i].url")
    upload_ct=$(echo "$RESPONSE" | jq -r ".upload.uploads[$i].headers[\"Content-Type\"] // empty")
    local_file=$(echo "$FILE_MAP" | jq -r --arg p "$upload_path" '.[$p]')

    if [[ ! -f "$local_file" ]]; then
      echo "warning: missing local file for $upload_path" >&2
      upload_errors=$((upload_errors + 1))
      continue
    fi

    ct_args=()
    [[ -n "$upload_ct" ]] && ct_args=(-H "Content-Type: $upload_ct")

    http_code=$(curl -sS -o /dev/null -w "%{http_code}" -X PUT "$upload_url" \
      "${ct_args[@]+"${ct_args[@]}"}" \
      --data-binary "@$local_file")

    if [[ "$http_code" -lt 200 || "$http_code" -ge 300 ]]; then
      echo "warning: upload failed for $upload_path (HTTP $http_code)" >&2
      upload_errors=$((upload_errors + 1))
    fi
  done
fi

[[ "$upload_errors" -eq 0 ]] || die "$upload_errors file(s) failed to upload"

echo "finalizing..." >&2
FIN_RESPONSE=$(curl -sS -X POST "$FINALIZE_URL" \
  -H "x-herenow-client: $CLIENT_HEADER_VALUE" \
  -H "content-type: application/json" \
  -d "{\"versionId\":\"$VERSION_ID\"}")

if echo "$FIN_RESPONSE" | jq -e '.error' >/dev/null 2>&1; then
  err=$(echo "$FIN_RESPONSE" | jq -r '.error')
  die "finalize failed: $err"
fi

CLAIM_URL=$(echo "$RESPONSE" | jq -r '.claimUrl // empty')
EXPIRES_AT=$(echo "$RESPONSE" | jq -r '.expiresAt // empty')

echo "$SITE_URL"
echo "" >&2
echo "publish_result.site_url=$SITE_URL" >&2
echo "publish_result.slug=$OUT_SLUG" >&2
echo "publish_result.auth_mode=anonymous" >&2
echo "publish_result.persistence=expires_24h" >&2
[[ -n "$EXPIRES_AT" ]] && echo "publish_result.expires_at=$EXPIRES_AT" >&2
[[ "$CLAIM_URL" == https://* ]] && echo "publish_result.claim_url=$CLAIM_URL" >&2
