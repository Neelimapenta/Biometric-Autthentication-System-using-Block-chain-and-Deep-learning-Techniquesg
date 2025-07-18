package main

import (
    "encoding/json"
    "fmt"
    "log"

    "github.com/hyperledger/fabric-contract-api-go/contractapi"
)

type SmartContract struct {
    contractapi.Contract
}

type CIDRecord struct {
    ID  string json:"id"
    CID string json:"cid"
}

// ===================== RegisterHash =====================
// Emits a RegisterFace event if the given hash doesn't already exist
func (s *SmartContract) RegisterHash(ctx contractapi.TransactionContextInterface, hash string, vector string) error {
    exists, err := s.CIDRecordExists(ctx, hash)
    if err != nil {
        return err
    }
    if exists {
        return fmt.Errorf("hash %s already exists", hash)
    }

    payload := map[string]string{"hash": hash, "vector": vector}
    data, err := json.Marshal(payload)
    if err != nil {
        return err
    }

    // Emit event to trigger off-chain listener
    if err := ctx.GetStub().SetEvent("RegisterFace", data); err != nil {
        return fmt.Errorf("failed to emit RegisterFace event: %v", err)
    }
    return nil
}

// ===================== ConfirmCIDUpload =====================
// Called after off-chain IPFS upload completes
func (s *SmartContract) ConfirmCIDUpload(ctx contractapi.TransactionContextInterface, hash string, cid string) error {
    exists, err := s.CIDRecordExists(ctx, hash)
    if err != nil {
        return err
    }
    if exists {
        return fmt.Errorf("record %s already exists", hash)
    }

    record := CIDRecord{ID: hash, CID: cid}
    data, err := json.Marshal(record)
    if err != nil {
        return err
    }
    return ctx.GetStub().PutState(hash, data)
}

// ===================== AuthenticateFace =====================
// Emits Authenticate event with vector for off-chain matching
func (s *SmartContract) AuthenticateFace(ctx contractapi.TransactionContextInterface, vector string) error {
    payload := map[string]string{"vector": vector}
    data, err := json.Marshal(payload)
    if err != nil {
        return err
    }
    return ctx.GetStub().SetEvent("AuthenticateFace", data)
}

// ===================== RequestDeleteCIDRecord =====================
// Emits deletion request event if a record exists
func (s *SmartContract) RequestDeleteCIDRecord(ctx contractapi.TransactionContextInterface, hash string) error {
    rec, err := ctx.GetStub().GetState(hash)
    if err != nil {
        return fmt.Errorf("failed to read state: %v", err)
    }
    if rec == nil {
        return fmt.Errorf("record %s does not exist", hash)
    }
    return ctx.GetStub().SetEvent("RequestDelete", rec)
}

// ===================== DeleteCIDRecord =====================
// Deletes the CID record after off-chain confirmation
func (s *SmartContract) DeleteCIDRecord(ctx contractapi.TransactionContextInterface, hash string) error {
    exists, err := s.CIDRecordExists(ctx, hash)
    if err != nil {
        return err
    }
    if !exists {
        return fmt.Errorf("record %s does not exist", hash)
    }
    return ctx.GetStub().DelState(hash)
}

// ===================== ReadCIDRecord =====================
func (s *SmartContract) ReadCIDRecord(ctx contractapi.TransactionContextInterface, hash string) (*CIDRecord, error) {
    data, err := ctx.GetStub().GetState(hash)
    if err != nil || data == nil {
        return nil, fmt.Errorf("record %s does not exist", hash)
    }
    var rec CIDRecord
    if err := json.Unmarshal(data, &rec); err != nil {
        return nil, err
    }
    return &rec, nil
}

// ===================== GetAllCIDRecords =====================
func (s *SmartContract) GetAllCIDRecords(ctx contractapi.TransactionContextInterface) ([]*CIDRecord, error) {
    iter, err := ctx.GetStub().GetStateByRange("", "")
    if err != nil {
        return nil, err
    }
    defer iter.Close()

    var records []*CIDRecord
    for iter.HasNext() {
        item, err := iter.Next()
        if err != nil {
            return nil, err
        }
        var rec CIDRecord
        if err := json.Unmarshal(item.Value, &rec); err != nil {
            continue
        }
        records = append(records, &rec)
    }
    return records, nil
}

// ===================== CIDRecordExists =====================
func (s *SmartContract) CIDRecordExists(ctx contractapi.TransactionContextInterface, hash string) (bool, error) {
    data, err := ctx.GetStub().GetState(hash)
    if err != nil {
        return false, err
    }
    return data != nil, nil
}

// ===================== InitLedger =====================
func (s *SmartContract) InitLedger(ctx contractapi.TransactionContextInterface) error {
    return nil
}

// ===================== MAIN =====================
func main() {
    chaincode, err := contractapi.NewChaincode(new(SmartContract))
    if err != nil {
        log.Panicf("Error creating chaincode: %v", err)
    }
    if err := chaincode.Start(); err != nil {
        log.Panicf("Error starting SmartContract chaincode: %v", err)
    }
}
