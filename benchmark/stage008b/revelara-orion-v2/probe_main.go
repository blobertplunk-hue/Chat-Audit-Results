package main

import (
	"context"
	"encoding/json"
	"fmt"
	"os"
	"path/filepath"

	"github.com/revelara-ai/orion/internal/contextstore"
	"github.com/revelara-ai/orion/internal/orchestrator"
	"github.com/revelara-ai/orion/internal/proof"
	"github.com/revelara-ai/orion/internal/proof/hazard/stpa"
	"github.com/revelara-ai/orion/internal/proof/testsynth"
	"github.com/revelara-ai/orion/internal/sandbox"
)

func die(err error) {
	if err != nil {
		panic(err)
	}
}

func writeJSON(path string, v any) {
	b, err := json.MarshalIndent(v, "", "  ")
	die(err)
	die(os.MkdirAll(filepath.Dir(path), 0o755))
	die(os.WriteFile(path, append(b, '\n'), 0o644))
}

func currentTask(ctx context.Context, st *contextstore.Store, c *orchestrator.Conductor) (string, orchestrator.PlanTask, error) {
	es, err := c.RecallSpec(ctx)
	if err != nil {
		return "", orchestrator.PlanTask{}, err
	}
	pv, err := c.PlanView(ctx)
	if err != nil {
		return "", orchestrator.PlanTask{}, err
	}
	if len(pv.Tasks) == 0 {
		return "", orchestrator.PlanTask{}, fmt.Errorf("plan has no tasks")
	}
	return es.Hash, pv.Tasks[0], nil
}

func seedProof(dataDir, out, qToken, cToken string) {
	ctx := context.Background()
	st, err := contextstore.Open(dataDir)
	die(err)
	defer st.Close()
	c := orchestrator.NewWithStore(st)
	es, err := c.RecallSpec(ctx)
	die(err)
	_, task, err := currentTask(ctx, st, c)
	die(err)

	candDir := filepath.Join(dataDir, "stage008b-seed-candidate")
	_ = os.RemoveAll(candDir)
	die(os.MkdirAll(candDir, 0o755))
	art, err := sandbox.GenerateTimeServiceFixture(candDir, sandbox.GenSpec{
		Module:   "orion-generated/service",
		Route:    es.ResponseContract.Route,
		Port:     es.ResponseContract.Port,
		Format:   es.ResponseContract.Format(),
		TimeZone: es.ResponseContract.TimeZone,
		Cases:    es.ResponseContract.Cases,
	})
	die(err)

	contract := testsynth.Contract{
		Route:    es.ResponseContract.Route,
		Format:   es.ResponseContract.Format(),
		TimeZone: es.ResponseContract.TimeZone,
		Cases:    es.ResponseContract.Cases,
	}
	rep, err := proof.ProveAll(ctx, candDir, contract, stpa.SkeletonModel())
	die(err)
	verdict := fmt.Sprint(rep.Outcome.Verdict)
	if verdict != "Accept" {
		panic("adapter precondition proof did not Accept: " + verdict)
	}
	rb, err := json.Marshal(rep)
	die(err)
	die(st.ProofMemoPut(ctx, es.Hash, art.ContentHash, string(rb)))

	detailBytes, _ := json.Marshal(map[string]any{
		"qualification_token": qToken,
		"candidate_token":     cToken,
		"candidate_hash":      art.ContentHash,
	})
	var proofID, artifactID string
	die(st.WithTx(ctx, func(tx *contextstore.Tx) error {
		var e error
		artifactID, e = tx.Artifacts().Create(ctx, task.ID, "stage008b-candidate", art.Path, art.ContentHash)
		if e != nil {
			return e
		}
		proofID, e = tx.Proofs().Create(ctx, task.ID, contextstore.Proof{
			Mode: "converged", Verdict: "Accept", RunCount: len(rep.Modes), Detail: string(detailBytes),
		})
		if e != nil {
			return e
		}
		return tx.Tasks().SetProofAndStatus(ctx, task.ID, proofID, "proven")
	}))

	writeJSON(out, map[string]any{
		"spec_hash":           es.Hash,
		"task_id":             task.ID,
		"proof_id":            proofID,
		"artifact_id":         artifactID,
		"candidate_hash":      art.ContentHash,
		"qualification_token": qToken,
		"candidate_token":     cToken,
		"verdict":             verdict,
		"present_modes":       rep.PresentModes(),
		"process_pid":         os.Getpid(),
	})
}

func main() {
	if len(os.Args) != 6 || os.Args[1] != "seed-proof" {
		panic("usage: probe seed-proof <data-dir> <out-json> <qualification-token> <candidate-token>")
	}
	seedProof(os.Args[2], os.Args[3], os.Args[4], os.Args[5])
}
