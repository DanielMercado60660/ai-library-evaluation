#!/bin/sh
# Generate runtime config for the Angular app.
# Empty values mean the frontend will use relative paths (proxied through nginx).

cat <<EOF > /usr/share/nginx/html/env.js
window.__AI_LIBRARY_CONFIG__ = {
  serviceToken: "${SERVICE_AUTH_TOKEN:-dev-token-ai-librarian}",
  services: {
    agents: "${AGENTS_URL:-}",
    catalog: "${CATALOG_URL:-}",
    circulation: "${CIRCULATION_URL:-}",
    ill: "${ILL_URL:-}",
    registry: "${REGISTRY_URL:-}"
  }
};
EOF
