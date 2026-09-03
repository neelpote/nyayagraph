#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPOSITORY_ROOT="$(cd "${SCRIPT_DIR}/../../.." && pwd)"
CHAINCODE_DIR="$(cd "${SCRIPT_DIR}/../chaincode" && pwd)"
FABRIC_SAMPLES_DIR="${FABRIC_SAMPLES_DIR:-${REPOSITORY_ROOT}/.fabric-samples}"
NETWORK_DIR="${FABRIC_SAMPLES_DIR}/test-network"
if [[ ! -x "${NETWORK_DIR}/network.sh" ]]; then
  echo "Fabric samples not found at ${FABRIC_SAMPLES_DIR}. Set FABRIC_SAMPLES_DIR."
  exit 1
fi

cd "${NETWORK_DIR}"
./network.sh deployCC -c justicechannel -ccn nyayagraph -ccp "${CHAINCODE_DIR}" -ccl go
export OVERRIDE_ORG=""
export VERBOSE="false"
source scripts/envVar.sh
setGlobals 1
peer lifecycle chaincode querycommitted --channelID justicechannel --name nyayagraph >/dev/null
echo "NyayaGraph chaincode is committed on the LOCAL DEVELOPMENT justicechannel."
