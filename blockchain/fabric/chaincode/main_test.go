package main

import (
	"crypto/x509"
	"encoding/json"
	"strings"
	"testing"

	"github.com/hyperledger/fabric-chaincode-go/v2/shim"
	"github.com/hyperledger/fabric-contract-api-go/v2/contractapi"
	"google.golang.org/protobuf/types/known/timestamppb"
)

type testIdentity struct {
	mspID string
}

func (i testIdentity) GetID() (string, error)    { return "test-user", nil }
func (i testIdentity) GetMSPID() (string, error) { return i.mspID, nil }
func (i testIdentity) GetAttributeValue(string) (string, bool, error) {
	return "", false, nil
}
func (i testIdentity) AssertAttributeValue(string, string) error { return nil }
func (i testIdentity) GetX509Certificate() (*x509.Certificate, error) {
	return nil, nil
}

type testStub struct {
	shim.ChaincodeStubInterface
	state map[string][]byte
}

func (s *testStub) GetState(key string) ([]byte, error) {
	return s.state[key], nil
}

func (s *testStub) PutState(key string, value []byte) error {
	s.state[key] = append([]byte(nil), value...)
	return nil
}

func (s *testStub) GetTxTimestamp() (*timestamppb.Timestamp, error) {
	return timestamppb.New(timestamppb.Now().AsTime()), nil
}

func (s *testStub) GetTxID() string { return "test-tx" }

func newTestContext(mspID string) (*contractapi.TransactionContext, *testStub) {
	stub := &testStub{state: make(map[string][]byte)}
	ctx := &contractapi.TransactionContext{}
	ctx.SetStub(stub)
	ctx.SetClientIdentity(testIdentity{mspID: mspID})
	return ctx, stub
}

func TestRegisterCaseRejectsUnauthorizedMSP(t *testing.T) {
	ctx, stub := newTestContext(fslMSP)
	err := (&SmartContract{}).RegisterCase(
		ctx,
		strings.Repeat("a", 64),
		strings.Repeat("b", 64),
		fslMSP,
		strings.Repeat("c", 64),
	)

	if err == nil || !strings.Contains(err.Error(), "not authorized") {
		t.Fatalf("expected unauthorized MSP error, got %v", err)
	}
	if len(stub.state) != 0 {
		t.Fatalf("unauthorized invocation wrote ledger state: %#v", stub.state)
	}
}

func TestRegisterCaseRequiresClientIdentity(t *testing.T) {
	stub := &testStub{state: make(map[string][]byte)}
	ctx := &contractapi.TransactionContext{}
	ctx.SetStub(stub)
	err := (&SmartContract{}).RegisterCase(ctx, strings.Repeat("a", 64), strings.Repeat("b", 64),
		policeMSP, strings.Repeat("c", 64))
	if err == nil || !strings.Contains(err.Error(), "authenticated client identity") {
		t.Fatalf("expected missing identity error, got %v", err)
	}
}

func TestRegisterCaseStoresInvokerMSPInsteadOfCallerOrganization(t *testing.T) {
	ctx, stub := newTestContext(policeMSP)
	caseKey := strings.Repeat("a", 64)
	err := (&SmartContract{}).RegisterCase(
		ctx,
		caseKey,
		strings.Repeat("b", 64),
		courtMSP,
		strings.Repeat("c", 64),
	)
	if err != nil {
		t.Fatalf("register case: %v", err)
	}

	var stored Artifact
	if err := json.Unmarshal(stub.state["case:"+caseKey], &stored); err != nil {
		t.Fatalf("decode stored artifact: %v", err)
	}
	if stored.Organization != policeMSP {
		t.Fatalf("stored organization = %q, want authenticated MSP %q", stored.Organization, policeMSP)
	}
}

func TestRegisterCaseRejectsNonHexCommitment(t *testing.T) {
	ctx, stub := newTestContext(policeMSP)
	err := (&SmartContract{}).RegisterCase(ctx, strings.Repeat("a", 64), strings.Repeat("z", 64),
		policeMSP, strings.Repeat("c", 64))
	if err == nil || !strings.Contains(err.Error(), "hexadecimal") {
		t.Fatalf("expected hexadecimal validation error, got %v", err)
	}
	if len(stub.state) != 0 {
		t.Fatalf("invalid invocation wrote ledger state: %#v", stub.state)
	}
}

func TestTransferCustodyRequiresRegisteredEvidence(t *testing.T) {
	ctx, stub := newTestContext(policeMSP)
	err := (&SmartContract{}).TransferCustody(ctx, "missing", strings.Repeat("d", 64), "", "PoliceMSP",
		"FSLMSP", strings.Repeat("c", 64))
	if err == nil || !strings.Contains(err.Error(), "evidence does not exist") {
		t.Fatalf("expected missing evidence error, got %v", err)
	}
	if len(stub.state) != 0 {
		t.Fatalf("invalid custody invocation wrote ledger state: %#v", stub.state)
	}
}

func TestTransferCustodyStoresOnlyCompositeHash(t *testing.T) {
	ctx, stub := newTestContext(policeMSP)
	contract := &SmartContract{}
	if err := contract.RegisterEvidence(ctx, "evidence-1", strings.Repeat("a", 64), strings.Repeat("b", 64),
		policeMSP, strings.Repeat("c", 64)); err != nil {
		t.Fatalf("register evidence: %v", err)
	}
	if err := contract.TransferCustody(ctx, "evidence-1", strings.Repeat("d", 64), "", "PoliceMSP",
		"FSLMSP", strings.Repeat("c", 64)); err != nil {
		t.Fatalf("transfer custody: %v", err)
	}
	var event ProvenanceEvent
	if err := json.Unmarshal(stub.state["custody:test-tx"], &event); err != nil {
		t.Fatalf("decode custody event: %v", err)
	}
	if len(event.PayloadHash) != 64 || strings.Contains(event.PayloadHash, "PoliceMSP") {
		t.Fatalf("custody payload was not reduced to a hash: %q", event.PayloadHash)
	}
}

func TestContractMetadataBuildsWithCompatibleSignatures(t *testing.T) {
	if _, err := contractapi.NewChaincode(&SmartContract{}); err != nil {
		t.Fatalf("build chaincode contract metadata: %v", err)
	}
}
