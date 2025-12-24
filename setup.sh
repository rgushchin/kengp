#!/bin/bash
set -e

# Check for rust and cargo
echo "Checking for Rust and Cargo..."
if ! command -v rustc &> /dev/null || ! command -v cargo &> /dev/null; then
    echo "Error: rustc and cargo are required but not found. Please install Rust: https://rustup.rs/"
    exit 1
fi

# Check for lancedb dependencies: protobuf_compiler and libssl-dev
echo "Checking for lancedb dependencies..."
MISSING_DEPS=0

# Check for protobuf_compiler (protoc)
if ! command -v protoc &> /dev/null; then
    echo "Error: protobuf_compiler (protoc) is required but not found."
    MISSING_DEPS=1
fi

# Check for libssl-dev (openssl headers)
# Using pkg-config if available, otherwise check common header paths
if command -v pkg-config &> /dev/null; then
    if ! pkg-config --exists openssl; then
         echo "Error: libssl-dev (OpenSSL development headers) is required but not found."
         MISSING_DEPS=1
    fi
elif [ ! -f /usr/include/openssl/ssl.h ] && [ ! -f /usr/include/x86_64-linux-gnu/openssl/ssl.h ]; then
     echo "Error: libssl-dev (OpenSSL development headers) is required but not found."
     MISSING_DEPS=1
fi

if [ $MISSING_DEPS -eq 1 ]; then
    echo "Please install the missing dependencies:"
    echo "  Ubuntu: sudo apt-get install protobuf-compiler libssl-dev"
    echo "  Fedora: sudo dnf install protobuf-compiler openssl-devel"
    exit 1
fi

# Function to handle Linux kernel setup
setup_linux() {
    if [ -d "linux" ]; then
        echo "./linux already exists. Skipping kernel setup."
        return
    fi

    echo "Linux kernel source not found in ./linux."
    echo "Please choose an option to set it up:"
    echo "1) Clone official linux repository (git://git.kernel.org/pub/scm/linux/kernel/git/torvalds/linux.git)"
    echo "2) Create a new worktree using an existing folder (Note: Ensure you are comfortable sharing this repository with your LLM provider)"
    echo "3) Clone a local linux repository (Note: Ensure you are comfortable sharing this repository with your LLM provider)"
    read -r -p "Enter option [1-3]: " choice

    case "$choice" in
        1)
            echo "Cloning official linux repository..."
            git clone git://git.kernel.org/pub/scm/linux/kernel/git/torvalds/linux.git linux
            ;;
        2)
            read -e -r -p "Enter path to existing kernel repository: " src_path
            # Expand tilde (~)
            src_path="${src_path/#\~/$HOME}"
            if [ -d "$src_path" ]; then
                # Use absolute path for the worktree
                abs_src_path=$(realpath "$src_path")
                abs_dest_path=$(pwd)/linux
                
                echo "Creating git worktree from $abs_src_path..."
                # We need to run git worktree add from the source repository
                (cd "$abs_src_path" && git worktree add "$abs_dest_path")
                echo "Worktree created at ./linux"
            else
                echo "Error: '$src_path' is not a directory."
                exit 1
            fi
            ;;
        3)
            read -e -r -p "Enter path to local repository: " repo_path
            # Expand tilde (~)
            repo_path="${repo_path/#\~/$HOME}"
            if [ -d "$repo_path" ]; then
                abs_repo_path=$(realpath "$repo_path")
                echo "Cloning local repository from $abs_repo_path..."
                git clone "$abs_repo_path" linux
            else
                echo "Error: '$repo_path' is not a directory."
                exit 1
            fi
            ;;
        *)
            echo "Invalid selection: $choice"
            exit 1
            ;;
    esac

    if [ ! -d "linux" ]; then
        echo "Error: ./linux does not exist or is not a directory."
        exit 1
    fi
}

echo "Checking out submodules..."
git submodule init
git submodule update

setup_linux

echo "Building semcode..."
(cd semcode && cargo build --release)

echo "Indexing linux kernel..."
(cd linux && ../semcode/target/release/semcode-index -s .)

# LLM Settings
echo ""
echo "Configuring LLM Settings..."
read -r -p "Enter LLM CLI agent to use [gemini]: " llm_agent
llm_agent=${llm_agent:-gemini}

if ! command -v "$llm_agent" &> /dev/null; then
    echo "Warning: '$llm_agent' command not found in your PATH."
    echo "Please ensure it is installed and added to your \$PATH."
fi

read -r -p "Enter model to use [gemini-3-pro-preview]: " llm_model
llm_model=${llm_model:-gemini-3-pro-preview}

cat <<EOF > .engp.json
{
  "llm_agent": "$llm_agent",
  "llm_model": "$llm_model"
}
EOF
echo "Settings saved to .engp.json"

echo "Done"
