# setup environment and run build_conda.sh
#   should work on local machine (run from CASMcode repo or with CASM_BUILD_DIR set) or travis for osx and linux
#
#   requires repository settings:
#     CASM_CONDA_TOKEN
#     CASM_CONDA_ID_USER
#     CASM_GIT_ID_USER (if not on travis)
#     CASM_BRANCH (if not on travis)
#     CASM_DOCKER_CONTAINER
#     CASM_DOCKER_CMD
#     CASM_CONDA_FEATURE (typically xcode/condagcc/condagcc_centos6)
#
#   notable optional env variable:
#     CASM_CONDA_LABEL=("main" if $TRAVIS_TAG exists, "dev" otherwise)
#     CASM_BUILD_BOOST (If non-zero length, build casm-boost, otherwise skip)

set -e
BUILD_SCRIPTS_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" >/dev/null && pwd )"
export CASM_BUILD_DIR=$(dirname $BUILD_SCRIPTS_DIR)
export CASM_REPO_SLUG=${CASM_REPO_SLUG:-$TRAVIS_REPO_SLUG}
export CASM_GIT_ID_USER=${CASM_GIT_ID_USER:-${CASM_REPO_SLUG%/*}}
export CASM_BRANCH=${CASM_BRANCH:-$TRAVIS_BRANCH}

if [ -n "$TRAVIS_TAG" ]; then
  CASM_DEFAULT_CONDA_LABEL="main"
else
  CASM_DEFAULT_CONDA_LABEL="dev"
fi

### Nothing past here should use travis-ci variables

. $CASM_BUILD_DIR/build_scripts/install-functions.sh
. $CASM_BUILD_DIR/build_scripts/build_versions.sh
detect_os

# these should pick up the correct info from the travis environment, otherwise set yourself
check_var "CASM_CONDA_LABEL" "Conda channel label (\"dev\" or \"main\")" "$CASM_DEFAULT_CONDA_LABEL"

# build and push conda packages
bash $CASM_BUILD_DIR/build_conda_docker.sh \
  || { echo "build_conda_docker.sh failed"; exit 1; }
