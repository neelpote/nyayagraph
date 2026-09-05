#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPOSITORY_ROOT="$(cd "${SCRIPT_DIR}/../../.." && pwd)"
FABRIC_SAMPLES_DIR="${FABRIC_SAMPLES_DIR:-${REPOSITORY_ROOT}/.fabric-samples}"
NETWORK_DIR="${FABRIC_SAMPLES_DIR}/test-network"
if [[ ! -x "${NETWORK_DIR}/network.sh" ]]; then
  echo "Fabric samples not found at ${FABRIC_SAMPLES_DIR}. Set FABRIC_SAMPLES_DIR."
  exit 1
fi

cd "${NETWORK_DIR}"
./network.sh down

for backup in \
  scripts/deployCCAAS.sh.nyayagraph-original scripts/deployCC.sh.nyayagraph-original \
  scripts/envVar.sh.nyayagraph-original setOrgEnv.sh.nyayagraph-original \
  configtx/configtx.yaml.nyayagraph-original bft-config/configtx.yaml.nyayagraph-original \
  compose/compose-bft-test-net.yaml.nyayagraph-original compose/compose-test-net.yaml.nyayagraph-original; do
  if [[ -f "${backup}" ]]; then
    mv -- "${backup}" "${backup%.nyayagraph-original}"
  fi
done
