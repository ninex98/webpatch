(
  set -eu
  webpatch_tmp=$(mktemp -d)
  trap 'rm -rf "$webpatch_tmp"' EXIT
  curl -4 --http1.1 -fsSL --retry 5 --retry-all-errors --retry-max-time 180 \
    --connect-timeout 15 --max-time 60 \
    --proto '=https' --proto-redir '=https' --tlsv1.2 \
    https://github.com/ninex98/webpatch/releases/download/v0.2.0/webpatch_0.2.0_all.deb \
    -o "$webpatch_tmp/webpatch_0.2.0_all.deb"
  printf '%s  %s\n' \
    '6cb409a579e05407b296fb6794ae912356cbaaeae0f31aa04d6e08247156b5e6' \
    "$webpatch_tmp/webpatch_0.2.0_all.deb" | sha256sum -c -
  chmod 0711 "$webpatch_tmp"
  chmod 0644 "$webpatch_tmp/webpatch_0.2.0_all.deb"
  if [ "$(id -u)" -eq 0 ]; then
    apt-get install -y --no-install-recommends --no-remove "$webpatch_tmp/webpatch_0.2.0_all.deb"
  else
    sudo apt-get install -y --no-install-recommends --no-remove "$webpatch_tmp/webpatch_0.2.0_all.deb"
  fi
  /usr/bin/webpatch --version
)
