#!/bin/sh
# Install released WebPatch packages. Scanning and PHP maintenance are separate.
# Keep execution behind a complete function definition for streamed downloads.
main() {
set -eu
umask 077

fail() { printf '%s\n' "WebPatch: $*" >&2; exit 1; }
usage() {
    printf '%s\n' 'Usage: sh install.sh [--version MAJOR.MINOR.PATCH] [--verbose]' \
        'Supports Ubuntu 22.04/24.04 and Debian 12/13.' \
        'Installs WebPatch and required dependencies through APT; does not run scans or repairs.'
}

version=
verbose=0
while [ "$#" -gt 0 ]; do
    case "$1" in
        --version) [ "$#" -ge 2 ] || fail '--version requires a value'; version=$2; shift 2 ;;
        --verbose) verbose=1; shift ;;
        --help|-h) usage; exit 0 ;;
        *) fail "Unknown option: $1" ;;
    esac
done
valid_version() {
    printf '%s\n' "$1" | LC_ALL=C grep -Eq '^(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)$'
}
[ -z "$version" ] || valid_version "$version" || fail 'Version must be MAJOR.MINOR.PATCH (without v).'
[ "$(uname -s)" = Linux ] || fail 'Unsupported OS. This installer supports Ubuntu/Debian Linux only.'
[ -r /etc/os-release ] || fail 'Cannot identify Linux distribution.'
# Parse data without sourcing os-release as shell code.
os_value() { sed -n "s/^$1=//p" /etc/os-release | tr -d '\042\047'; }
os_id=$(os_value ID)
os_version=$(os_value VERSION_ID)
case "$os_id:$os_version" in
    ubuntu:22.04|ubuntu:24.04|debian:12|debian:13) ;;
    *) fail "Unsupported distribution: $os_id $os_version. No packages were changed." ;;
esac
for command in curl sha256sum dpkg dpkg-deb dpkg-query apt-get mktemp; do
    command -v "$command" >/dev/null 2>&1 || fail "Required command missing: $command"
done
if [ "$(id -u)" -ne 0 ]; then
    command -v sudo >/dev/null 2>&1 || fail 'APT installation requires root or sudo.'
fi

fetch() {
    curl --fail --silent --show-error --location --proto '=https' --proto-redir '=https' \
        --tlsv1.2 --retry 3 --connect-timeout 15 --max-time 180 "$@"
}
repository=https://github.com/ninex98/webpatch
if [ -z "$version" ]; then
    latest=$(fetch --output /dev/null --write-out '%{url_effective}' "$repository/releases/latest") || \
        fail 'Cannot resolve the latest release. A published Release is required.'
    case "$latest" in
        "$repository/releases/tag/v"*) version=${latest#"$repository/releases/tag/v"} ;;
        *) fail 'Unexpected latest-release URL; refusing to guess a version.' ;;
    esac
    valid_version "$version" || fail 'Latest release has an unsupported version.'
fi
installed=$(dpkg-query -W -f='${Status} ${Version}' webpatch 2>/dev/null || true)
case "$installed" in
    'install ok installed '*)
        installed=${installed#'install ok installed '}
        dpkg --compare-versions "$installed" gt "$version" && fail "Refusing downgrade from $installed to $version."
        ;;
esac

temporary=$(mktemp -d /tmp/webpatch-install.XXXXXXXX)
trap 'rm -rf "$temporary"' EXIT
trap 'exit 1' HUP INT TERM
asset=webpatch_${version}_all.deb
base=$repository/releases/download/v$version
printf '\n  WebPatch %s\n  %s %s\n\n' "$version" "$os_id" "$os_version"
printf '%s\n' '  [1/3] Downloading release...'
fetch --output "$temporary/$asset" "$base/$asset" || fail 'Package download failed; nothing installed.'
fetch --output "$temporary/SHA256SUMS" "$base/SHA256SUMS" || fail 'Checksum download failed; nothing installed.'
# Only accept one well-formed entry for this asset; never process arbitrary paths.
checksum=$(awk -v asset="$asset" '$2 == asset { n++; hash=$1 } END { if (n != 1) exit 1; print hash }' "$temporary/SHA256SUMS") || \
    fail 'Missing or duplicate package checksum.'
printf '%s\n' "$checksum" | LC_ALL=C grep -Eq '^[0-9a-f]{64}$' || fail 'Invalid SHA256 checksum.'
printf '%s  %s\n' "$checksum" "$asset" > "$temporary/expected.sha256"
(cd "$temporary" && sha256sum --check expected.sha256) > "$temporary/checksum.log" 2>&1 || fail 'Checksum mismatch; nothing installed.'
[ "$(dpkg-deb --field "$temporary/$asset" Package)" = webpatch ] || fail 'Unexpected package name.'
[ "$(dpkg-deb --field "$temporary/$asset" Version)" = "$version" ] || fail 'Unexpected package version.'
[ "$(dpkg-deb --field "$temporary/$asset" Architecture)" = all ] || fail 'Unexpected package architecture.'
printf '%s\n' '  [2/3] Checksum and package identity verified.'
# This file is a public release asset. Let APT's _apt user traverse the private
# directory and read only the package; logs and other files remain mode 0600.
chmod 0711 "$temporary"
chmod 0644 "$temporary/$asset"

# sudo is used only for APT, after the download, checksum and metadata checks.
# No index refresh, repository addition, PHP command or service operation here.
install_package() {
    if [ "$(id -u)" -eq 0 ]; then
        apt-get install -y --no-install-recommends --no-remove "$temporary/$asset"
    else
        sudo apt-get install -y --no-install-recommends --no-remove "$temporary/$asset"
    fi
}
printf '%s\n' '  [3/3] Installing WebPatch and required dependencies...'
if [ "$verbose" -eq 1 ]; then
    install_package || fail 'APT installation failed. Review its output; package indexes are not automatically refreshed.'
else
    if ! install_package > "$temporary/apt.log" 2>&1; then
        cat "$temporary/apt.log" >&2
        fail 'APT installation failed. Review its output; package indexes are not automatically refreshed.'
    fi
fi
[ "$(/usr/bin/webpatch --version)" = "$version" ] || fail 'Installed CLI version did not match the release.'
printf '\n  Installed WebPatch %s.\n\n  Next: webpatch scan\n\n' "$version"
}
main "$@"
