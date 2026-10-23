(
  set -eu
  webpatch_tmp=$(mktemp -d)
  trap 'rm -rf "$webpatch_tmp"' EXIT
  curl -fsSL --retry 5 --retry-all-errors --retry-max-time 180 \
    --connect-timeout 15 --max-time 60 \
    --proto '=https' --proto-redir '=https' --tlsv1.2 \
    https://github.com/ninex98/webpatch/releases/latest/download/install.sh \
    -o "$webpatch_tmp/install.sh"
  sh "$webpatch_tmp/install.sh"
  /usr/bin/webpatch --version
)
