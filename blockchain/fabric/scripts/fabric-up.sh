#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPOSITORY_ROOT="$(cd "${SCRIPT_DIR}/../../.." && pwd)"
FABRIC_SAMPLES_DIR="${FABRIC_SAMPLES_DIR:-${REPOSITORY_ROOT}/.fabric-samples}"
NETWORK_DIR="${FABRIC_SAMPLES_DIR}/test-network"
if [[ ! -x "${NETWORK_DIR}/network.sh" ]]; then
  echo "Fabric samples not found at ${FABRIC_SAMPLES_DIR}."
  echo "Install official Fabric 2.5 samples/binaries, then set FABRIC_SAMPLES_DIR."
  exit 1
fi
if ! command -v perl >/dev/null; then
  echo "perl is required to prepare the local development MSP names."
  exit 1
fi

# The official sample calls its two members Org1MSP/Org2MSP. NyayaGraph's
# chaincode intentionally authorizes the real domain names, so adapt the ignored
# local test-network files before generating channel material.
patched_files=()
restore_on_error() {
  status=$?
  trap - EXIT
  if (( status != 0 )); then
    for file in "${patched_files[@]-}"; do
      [[ -n "${file}" && -e "${file}.nyayagraph-original" ]] && mv -- "${file}.nyayagraph-original" "${file}"
    done
  fi
  exit "${status}"
}
trap restore_on_error EXIT

for relative_path in \
  scripts/deployCCAAS.sh scripts/deployCC.sh scripts/envVar.sh setOrgEnv.sh \
  configtx/configtx.yaml bft-config/configtx.yaml \
  compose/compose-bft-test-net.yaml compose/compose-test-net.yaml; do
  file="${NETWORK_DIR}/${relative_path}"
  if [[ -f "${file}" ]]; then
    if [[ ! -e "${file}.nyayagraph-original" ]]; then
      cp -p -- "${file}" "${file}.nyayagraph-original"
      patched_files+=("${file}")
    fi
    perl -pi -e 's/Org1MSP/PoliceMSP/g; s/Org2MSP/FSLMSP/g' "${file}"
  fi
done

cd "${NETWORK_DIR}"
./network.sh up -ca
export PATH="${FABRIC_SAMPLES_DIR}/bin:${PATH}"
export FABRIC_CFG_PATH="${FABRIC_SAMPLES_DIR}/config"
export OVERRIDE_ORG=""
export VERBOSE="false"
source scripts/envVar.sh
setGlobals 1
channel_exists=false
for _ in 1 2 3 4 5; do
  if peer channel getinfo -c justicechannel >/dev/null 2>&1; then
    channel_exists=true
    break
  fi
  sleep 3
done
if [[ "${channel_exists}" == "true" ]]; then
  echo "Channel 'justicechannel' already exists; reusing its active ledger."
else
  ./network.sh createChannel -c justicechannel
fi
trap - EXIT
echo "LOCAL DEVELOPMENT Fabric test network is running. See blockchain/fabric/README.md for topology scope."
