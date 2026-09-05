package main

import (
	"crypto/sha256"
	"encoding/hex"
	"encoding/json"
	"fmt"
	"strconv"
	"time"

	"github.com/hyperledger/fabric-contract-api-go/v2/contractapi"
)

// SmartContract stores provenance fingerprints only. It must never receive case
// numbers, names, evidence content, storage locations, or other personal data.
type SmartContract struct{ contractapi.Contract }

const (
	policeMSP      = "PoliceMSP"
	fslMSP         = "FSLMSP"
	prosecutionMSP = "ProsecutionMSP"
	courtMSP       = "CourtMSP"
)

type Artifact struct {
	ArtifactID      string `json:"artifactId"`
	ArtifactType    string `json:"artifactType"`
	CaseCommitment  string `json:"caseCommitment"`
	Hash            string `json:"hash"`
	Version         int    `json:"version"`
	Organization    string `json:"organization"`
	ActorCommitment string `json:"actorCommitment"`
	PreviousHash    string `json:"previousHash,omitempty"`
	TransactionTime string `json:"transactionTime"`
}

type ProvenanceEvent struct {
	EventID         string `json:"eventId"`
	EventType       string `json:"eventType"`
	ArtifactID      string `json:"artifactId,omitempty"`
	PayloadHash     string `json:"payloadHash"`
	Organization    string `json:"organization"`
	ActorCommitment string `json:"actorCommitment"`
	TransactionTime string `json:"transactionTime"`
}

func requireInvokerMSP(ctx contractapi.TransactionContextInterface, operation string, allowed ...string) (string, error) {
	identity := ctx.GetClientIdentity()
	if identity == nil {
		return "", fmt.Errorf("%s requires an authenticated client identity", operation)
	}
	mspID, err := identity.GetMSPID()
	if err != nil {
		return "", fmt.Errorf("resolve invoker MSP for %s: %w", operation, err)
	}
	for _, allowedMSP := range allowed {
		if mspID == allowedMSP {
			return mspID, nil
		}
	}
	return "", fmt.Errorf("MSP %q is not authorized for %s", mspID, operation)
}

func txTime(ctx contractapi.TransactionContextInterface) (string, error) {
	stamp, err := ctx.GetStub().GetTxTimestamp()
	if err != nil {
		return "", err
	}
	return time.Unix(stamp.Seconds, int64(stamp.Nanos)).UTC().Format(time.RFC3339Nano), nil
}

func putJSON(ctx contractapi.TransactionContextInterface, key string, value any) error {
	data, err := json.Marshal(value)
	if err != nil {
		return err
	}
	return ctx.GetStub().PutState(key, data)
}

func requireAbsent(ctx contractapi.TransactionContextInterface, key string) error {
	value, err := ctx.GetStub().GetState(key)
	if err != nil {
		return err
	}
	if value != nil {
		return fmt.Errorf("state already exists: %s", key)
	}
	return nil
}

func requireHex32(name, value string) error {
	if len(value) != 64 {
		return fmt.Errorf("%s must be 64 hexadecimal characters", name)
	}
	if _, err := hex.DecodeString(value); err != nil {
		return fmt.Errorf("%s must be 64 hexadecimal characters", name)
	}
	return nil
}

func hashParts(parts ...string) string {
	payload, _ := json.Marshal(parts)
	hash := sha256.Sum256(payload)
	return hex.EncodeToString(hash[:])
}

func (s *SmartContract) RegisterCase(ctx contractapi.TransactionContextInterface, caseKey, caseCommitment, _ string, actorCommitment string) error {
	organization, err := requireInvokerMSP(ctx, "RegisterCase", policeMSP)
	if err != nil {
		return err
	}
	if err := requireHex32("case key", caseKey); err != nil {
		return err
	}
	if err := requireHex32("case commitment", caseCommitment); err != nil {
		return err
	}
	if err := requireHex32("actor commitment", actorCommitment); err != nil {
		return err
	}
	if err := requireAbsent(ctx, "case:"+caseKey); err != nil {
		return err
	}
	timestamp, err := txTime(ctx)
	if err != nil {
		return err
	}
	return putJSON(ctx, "case:"+caseKey, Artifact{ArtifactID: caseKey, ArtifactType: "CASE_COMMITMENT",
		CaseCommitment: caseCommitment, Hash: caseCommitment, Version: 1, Organization: organization,
		ActorCommitment: actorCommitment, TransactionTime: timestamp})
}

func (s *SmartContract) RegisterDocument(ctx contractapi.TransactionContextInterface, artifactID, caseCommitment, hash, version, _ string, actorCommitment, previousHash string) error {
	organization, err := requireInvokerMSP(ctx, "RegisterDocument", policeMSP, fslMSP, prosecutionMSP, courtMSP)
	if err != nil {
		return err
	}
	return s.registerArtifact(ctx, artifactID, "DOCUMENT", caseCommitment, hash, version, organization, actorCommitment, previousHash)
}

func (s *SmartContract) RegisterEvidence(ctx contractapi.TransactionContextInterface, artifactID, caseCommitment, hash, _ string, actorCommitment string) error {
	organization, err := requireInvokerMSP(ctx, "RegisterEvidence", policeMSP, fslMSP)
	if err != nil {
		return err
	}
	return s.registerArtifact(ctx, artifactID, "EVIDENCE", caseCommitment, hash, "1", organization, actorCommitment, "")
}

func (s *SmartContract) CreateVersion(ctx contractapi.TransactionContextInterface, artifactID, caseCommitment, hash, version, _ string, actorCommitment, previousHash string) error {
	organization, err := requireInvokerMSP(ctx, "CreateVersion", policeMSP, fslMSP, prosecutionMSP, courtMSP)
	if err != nil {
		return err
	}
	return s.registerArtifact(ctx, artifactID, "DOCUMENT_VERSION", caseCommitment, hash, version, organization, actorCommitment, previousHash)
}

func (s *SmartContract) registerArtifact(ctx contractapi.TransactionContextInterface, artifactID, artifactType, caseCommitment, hash, versionText, organization, actorCommitment, previousHash string) error {
	if artifactID == "" {
		return fmt.Errorf("artifact ID is required")
	}
	key := "artifact:" + artifactID
	if err := requireAbsent(ctx, key); err != nil {
		return err
	}
	version, err := strconv.Atoi(versionText)
	if err != nil || version < 1 {
		return fmt.Errorf("invalid version")
	}
	if err := requireHex32("hash", hash); err != nil {
		return err
	}
	if err := requireHex32("case commitment", caseCommitment); err != nil {
		return err
	}
	if err := requireHex32("actor commitment", actorCommitment); err != nil {
		return err
	}
	if previousHash != "" {
		if err := requireHex32("previous hash", previousHash); err != nil {
			return err
		}
	}
	timestamp, err := txTime(ctx)
	if err != nil {
		return err
	}
	return putJSON(ctx, key, Artifact{ArtifactID: artifactID, ArtifactType: artifactType,
		CaseCommitment: caseCommitment, Hash: hash, Version: version, Organization: organization,
		ActorCommitment: actorCommitment, PreviousHash: previousHash, TransactionTime: timestamp})
}

func (s *SmartContract) TransferCustody(ctx contractapi.TransactionContextInterface, evidenceID, eventHash, previousHash, fromOrg, toOrg, actorCommitment string) error {
	organization, err := requireInvokerMSP(ctx, "TransferCustody", policeMSP, fslMSP, prosecutionMSP, courtMSP)
	if err != nil {
		return err
	}
	evidence, err := ctx.GetStub().GetState("artifact:" + evidenceID)
	if err != nil {
		return err
	}
	if evidence == nil {
		return fmt.Errorf("evidence does not exist: %s", evidenceID)
	}
	var artifact Artifact
	if err := json.Unmarshal(evidence, &artifact); err != nil || artifact.ArtifactType != "EVIDENCE" {
		return fmt.Errorf("artifact is not evidence: %s", evidenceID)
	}
	if err := requireHex32("event hash", eventHash); err != nil {
		return err
	}
	if previousHash != "" {
		if err := requireHex32("previous hash", previousHash); err != nil {
			return err
		}
	}
	if fromOrg == "" || toOrg == "" || fromOrg == toOrg {
		return fmt.Errorf("custody transfer requires distinct source and destination organizations")
	}
	if err := requireHex32("actor commitment", actorCommitment); err != nil {
		return err
	}
	return s.recordEvent(ctx, "custody:"+ctx.GetStub().GetTxID(), "TRANSFER_CUSTODY", evidenceID,
		hashParts(eventHash, previousHash, fromOrg, toOrg), organization, actorCommitment)
}

func (s *SmartContract) GrantAccess(ctx contractapi.TransactionContextInterface, grantID, resourceCommitment, subjectCommitment, expiresCommitment, actorCommitment string) error {
	organization, err := requireInvokerMSP(ctx, "GrantAccess", policeMSP, prosecutionMSP, courtMSP)
	if err != nil {
		return err
	}
	if grantID == "" {
		return fmt.Errorf("grant ID is required")
	}
	for _, field := range []struct{ name, value string }{
		{"resource commitment", resourceCommitment}, {"subject commitment", subjectCommitment},
		{"expiry commitment", expiresCommitment}, {"actor commitment", actorCommitment},
	} {
		if err := requireHex32(field.name, field.value); err != nil {
			return err
		}
	}
	return s.recordEvent(ctx, "access-grant:"+grantID, "GRANT_ACCESS", "",
		hashParts(resourceCommitment, subjectCommitment, expiresCommitment), organization, actorCommitment)
}

func (s *SmartContract) RevokeAccess(ctx contractapi.TransactionContextInterface, grantID, resourceCommitment, actorCommitment string) error {
	organization, err := requireInvokerMSP(ctx, "RevokeAccess", policeMSP, prosecutionMSP, courtMSP)
	if err != nil {
		return err
	}
	if grantID == "" {
		return fmt.Errorf("grant ID is required")
	}
	if err := requireHex32("resource commitment", resourceCommitment); err != nil {
		return err
	}
	if err := requireHex32("actor commitment", actorCommitment); err != nil {
		return err
	}
	return s.recordEvent(ctx, "access-revoke:"+grantID, "REVOKE_ACCESS", "", hashParts(resourceCommitment), organization, actorCommitment)
}

func (s *SmartContract) RecordAccess(ctx contractapi.TransactionContextInterface, eventID, resourceCommitment, decision, actorCommitment string) error {
	organization, err := requireInvokerMSP(ctx, "RecordAccess", policeMSP, fslMSP, prosecutionMSP, courtMSP)
	if err != nil {
		return err
	}
	if eventID == "" {
		return fmt.Errorf("event ID is required")
	}
	if err := requireHex32("resource commitment", resourceCommitment); err != nil {
		return err
	}
	if err := requireHex32("actor commitment", actorCommitment); err != nil {
		return err
	}
	if decision != "ALLOWED" && decision != "DENIED" {
		return fmt.Errorf("decision must be ALLOWED or DENIED")
	}
	return s.recordEvent(ctx, "access-event:"+eventID, "RECORD_ACCESS", "", hashParts(resourceCommitment, decision), organization, actorCommitment)
}

func (s *SmartContract) RecordCheckpoint(ctx contractapi.TransactionContextInterface, batchID, merkleRoot, metadataCommitment, actorCommitment string) error {
	organization, err := requireInvokerMSP(ctx, "RecordCheckpoint", policeMSP, courtMSP)
	if err != nil {
		return err
	}
	if batchID == "" {
		return fmt.Errorf("batch ID is required")
	}
	if err := requireHex32("Merkle root", merkleRoot); err != nil {
		return err
	}
	if err := requireHex32("metadata commitment", metadataCommitment); err != nil {
		return err
	}
	if err := requireHex32("actor commitment", actorCommitment); err != nil {
		return err
	}
	return s.recordEvent(ctx, "checkpoint:"+batchID, "RECORD_CHECKPOINT", "", hashParts(merkleRoot, metadataCommitment), organization, actorCommitment)
}

func (s *SmartContract) recordEvent(ctx contractapi.TransactionContextInterface, key, eventType, artifactID, payloadHash, organization, actorCommitment string) error {
	if err := requireAbsent(ctx, key); err != nil {
		return err
	}
	timestamp, err := txTime(ctx)
	if err != nil {
		return err
	}
	return putJSON(ctx, key, ProvenanceEvent{EventID: key, EventType: eventType, ArtifactID: artifactID,
		PayloadHash: payloadHash, Organization: organization, ActorCommitment: actorCommitment, TransactionTime: timestamp})
}

func (s *SmartContract) VerifyArtifact(ctx contractapi.TransactionContextInterface, artifactID, expectedHash string) (bool, error) {
	if _, err := requireInvokerMSP(ctx, "VerifyArtifact", policeMSP, fslMSP, prosecutionMSP, courtMSP); err != nil {
		return false, err
	}
	if artifactID == "" {
		return false, fmt.Errorf("artifact ID is required")
	}
	if err := requireHex32("expected hash", expectedHash); err != nil {
		return false, err
	}
	data, err := ctx.GetStub().GetState("artifact:" + artifactID)
	if err != nil {
		return false, err
	}
	if data == nil {
		return false, nil
	}
	var artifact Artifact
	if err := json.Unmarshal(data, &artifact); err != nil {
		return false, err
	}
	return artifact.Hash == expectedHash, nil
}

func main() {
	chaincode, err := contractapi.NewChaincode(&SmartContract{})
	if err != nil {
		panic(err)
	}
	if err := chaincode.Start(); err != nil {
		panic(err)
	}
}
