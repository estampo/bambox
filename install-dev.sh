#!/bin/sh
# Install bambox-bridge from the latest CI build on main.
#
# This installs the most recent development build — not a release.
# For stable releases, use install.sh instead.
#
# Requires: gh (GitHub CLI), authenticated
#
# Usage:
#   ./install-dev.sh
#
# Environment variables:
#   BAMBOX_INSTALL_DIR  Override install location (default: ~/.local/bin)
#   BAMBOX_RUN_ID       Install from a specific workflow run ID

main() {
    set -e

    REPO="estampo/bambox"
    BIN_NAME="bambox-bridge"
    WORKFLOW="build-bridge.yml"
    INSTALL_DIR="${BAMBOX_INSTALL_DIR:-$HOME/.local/bin}"
    RUN_ID="${BAMBOX_RUN_ID:-}"

    # -- Dependency check ------------------------------------------------------

    need_cmd gh
    need_cmd chmod
    need_cmd uname
    need_cmd mktemp

    # Verify gh is authenticated
    if ! gh auth status >/dev/null 2>&1; then
        err "GitHub CLI is not authenticated. Run 'gh auth login' first."
    fi

    # -- Platform detection ----------------------------------------------------

    OS=$(uname -s)
    ARCH=$(uname -m)

    case "$OS" in
        Linux)  PLATFORM="linux" ;;
        Darwin) PLATFORM="macos" ;;
        *)      err "Unsupported OS: $OS (only Linux and macOS are supported)" ;;
    esac

    case "$ARCH" in
        x86_64|amd64)   ARCH_TAG="x86_64" ;;
        arm64|aarch64)  ARCH_TAG="arm64" ;;
        *)              err "Unsupported architecture: $ARCH" ;;
    esac

    if [ "$PLATFORM" = "linux" ] && [ "$ARCH_TAG" = "arm64" ]; then
        err "Linux arm64 binaries are not yet available."
    fi

    ARTIFACT="${BIN_NAME}-${PLATFORM}-${ARCH_TAG}"

    # -- Resolve run -----------------------------------------------------------

    if [ -z "$RUN_ID" ]; then
        info "Finding latest successful bridge build on main..."
        RUN_ID=$(gh run list \
            --repo "$REPO" \
            --workflow "$WORKFLOW" \
            --branch main \
            --status completed \
            --json databaseId,conclusion \
            --jq '[.[] | select(.conclusion == "success")][0].databaseId' \
        ) || true
        if [ -z "$RUN_ID" ] || [ "$RUN_ID" = "null" ]; then
            err "No successful bridge build found on main. Check https://github.com/${REPO}/actions/workflows/${WORKFLOW}"
        fi
    fi

    # -- Download artifact -----------------------------------------------------

    TMPDIR=$(mktemp -d 2>/dev/null || mktemp -d -t bambox_install)
    # shellcheck disable=SC2064
    trap "rm -rf '$TMPDIR'" EXIT INT TERM

    info "Downloading ${ARTIFACT} from run ${RUN_ID}..."
    if ! gh run download "$RUN_ID" \
        --repo "$REPO" \
        --name "$ARTIFACT" \
        --dir "$TMPDIR"; then
        err "Download failed. Artifact '${ARTIFACT}' may not exist in run ${RUN_ID}."
    fi

    TMPFILE="${TMPDIR}/bambox-bridge"
    if [ ! -f "$TMPFILE" ]; then
        err "Expected binary not found in artifact. Contents: $(ls "$TMPDIR")"
    fi

    chmod +x "$TMPFILE"

    # -- Install ---------------------------------------------------------------

    mkdir -p "$INSTALL_DIR" 2>/dev/null || true

    if is_writable "$INSTALL_DIR"; then
        mv "$TMPFILE" "${INSTALL_DIR}/${BIN_NAME}"
    elif has_cmd sudo; then
        info "Elevated permissions required to install to ${INSTALL_DIR}"
        sudo mkdir -p "$INSTALL_DIR"
        sudo mv "$TMPFILE" "${INSTALL_DIR}/${BIN_NAME}"
        sudo chmod +x "${INSTALL_DIR}/${BIN_NAME}"
    else
        err "${INSTALL_DIR} is not writable and sudo is not available.\nSet BAMBOX_INSTALL_DIR to a writable directory."
    fi

    # macOS: remove quarantine attribute
    if [ "$OS" = "Darwin" ]; then
        xattr -d com.apple.quarantine "${INSTALL_DIR}/${BIN_NAME}" 2>/dev/null || true
    fi

    # -- Success ---------------------------------------------------------------

    # Get the commit SHA for this run
    COMMIT=$(gh run view "$RUN_ID" --repo "$REPO" --json headSha --jq '.headSha[:8]') || true

    echo ""
    success "Installed ${BIN_NAME} (main@${COMMIT:-unknown}) to ${INSTALL_DIR}/${BIN_NAME}"
    echo ""
    if ! echo "$PATH" | tr ':' '\n' | grep -qx "$INSTALL_DIR"; then
        warn "Add ${INSTALL_DIR} to your PATH:"
        echo "  export PATH=\"${INSTALL_DIR}:\$PATH\""
        echo ""
    fi
    echo "Run '${BIN_NAME} --help' to get started."
}

# -- Helpers -------------------------------------------------------------------

info() {
    printf '\033[1;34m==>\033[0m %s\n' "$1"
}

success() {
    printf '\033[1;32m==>\033[0m %s\n' "$1"
}

warn() {
    printf '\033[1;33m==>\033[0m %s\n' "$1"
}

err() {
    printf '\033[1;31merror:\033[0m %s\n' "$1" >&2
    exit 1
}

need_cmd() {
    if ! command -v "$1" >/dev/null 2>&1; then
        err "Required command '$1' not found. Please install it and try again."
    fi
}

has_cmd() {
    command -v "$1" >/dev/null 2>&1
}

is_writable() {
    if [ -d "$1" ]; then
        [ -w "$1" ]
    else
        _parent=$(dirname "$1")
        [ -d "$_parent" ] && [ -w "$_parent" ]
    fi
}

main "$@"
