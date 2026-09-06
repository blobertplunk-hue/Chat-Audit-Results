package main

import (
  "context"
  "crypto/sha256"
  "encoding/hex"
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

func die(err error) { if err != nil { panic(err) } }
func writeJSON(path string, v any) { b, err := json.MarshalIndent(v, "", "  "); die(err); die(os.MkdirAll(filepath.Dir(path), 0755)); die(os.WriteFile(path, append(b, '\n'), 0644)) }
func tokenHash(s string) string { h := sha256.Sum256([]byte(s)); return hex.EncodeToString(h[:]) }

func currentTask(ctx context.Context, st *contextstore.Store, c *orchestrator.Conductor) (string, orchestrator.PlanTask, error) {
  es, err := c.RecallSpec(ctx); if err != nil { return "", orchestrator.PlanTask{}, err }
  pv, err := c.PlanView(ctx); if err != nil || len(pv.Tasks)==0 { return "", orchestrator.PlanTask{}, fmt.Errorf("plan: %w", err) }
  return es.Hash, pv.Tasks[0], nil
}

func seedProof(dataDir, out, qToken, cToken string) {
  ctx := context.Background()
  st, err := contextstore.Open(dataDir); die(err); defer st.Close()
  c := orchestrator.NewWithStore(st)
  es, err := c.RecallSpec(ctx); die(err)
  _, task, err := currentTask(ctx, st, c); die(err)
  candDir := filepath.Join(dataDir, "stage008b-seed-candidate")
  _ = os.RemoveAll(candDir)
  die(os.MkdirAll(candDir, 0755))
  art, err := sandbox.GenerateTimeServiceFixture(candDir, sandbox.GenSpec{
    Module: "orion-generated/service", Route: es.ResponseContract.Route, Port: es.ResponseContract.Port,
    Format: es.ResponseContract.Format(), TimeZone: es.ResponseContract.TimeZone, Cases: es.ResponseContract.Cases,
  }); die(err)
  contract := testsynth.Contract{Route: es.ResponseContract.Route, Format: es.ResponseContract.Format(), TimeZone: es.ResponseContract.TimeZone, Cases: es.ResponseContract.Cases}
  rep, err := proof.ProveAll(ctx, candDir, contract, stpa.SkeletonModel()); die(err)
  verdict := fmt.Sprint(rep.Outcome.Verdict)
  if verdict != "Accept" { panic("seed proof did not Accept: "+verdict) }
  rb, err := json.Marshal(rep); die(err)
  die(st.ProofMemoPut(ctx, es.Hash, art.ContentHash, string(rb)))
  detailBytes, _ := json.Marshal(map[string]any{"qualification_token":qToken,"candidate_token":cToken,"candidate_hash":art.ContentHash,"report_sha256":tokenHash(string(rb))})
  var proofID, artifactID string
  die(st.WithTx(ctx, func(tx *contextstore.Tx) error {
    var e error
    artifactID, e = tx.Artifacts().Create(ctx, task.ID, "stage008b-candidate", art.Path, art.ContentHash); if e != nil { return e }
    proofID, e = tx.Proofs().Create(ctx, task.ID, contextstore.Proof{Mode:"converged", Verdict:"Accept", RunCount:len(rep.Modes), Detail:string(detailBytes)}); if e != nil { return e }
    return tx.Tasks().SetProofAndStatus(ctx, task.ID, proofID, "proven")
  }))
  writeJSON(out, map[string]any{"spec_hash":es.Hash,"task_id":task.ID,"proof_id":proofID,"artifact_id":artifactID,"candidate_hash":art.ContentHash,"qualification_token":qToken,"candidate_token":cToken,"verdict":verdict,"present_modes":rep.PresentModes(),"process_pid":os.Getpid()})
}

func mismatch(dataDir, out, cToken string) {
  ctx := context.Background(); st, err := contextstore.Open(dataDir); die(err); defer st.Close(); c := orchestrator.NewWithStore(st)
  es, err := c.RecallSpec(ctx); die(err)
  candDir := filepath.Join(dataDir, "stage008b-mismatch-candidate"); _ = os.RemoveAll(candDir); die(os.MkdirAll(candDir, 0755))
  art, err := sandbox.GenerateTimeServiceFixture(candDir, sandbox.GenSpec{Module:"orion-generated/service-c1", Route:es.ResponseContract.Route, Port:es.ResponseContract.Port, Format:es.ResponseContract.Format(), TimeZone:es.ResponseContract.TimeZone, Cases:es.ResponseContract.Cases}); die(err)
  _, hit, err := st.ProofMemoGet(ctx, es.Hash, art.ContentHash); die(err)
  writeJSON(out, map[string]any{"spec_hash":es.Hash,"candidate_token":cToken,"candidate_hash":art.ContentHash,"memo_hit":hit,"process_pid":os.Getpid()})
  if hit { panic("wrong candidate unexpectedly reused proof memo") }
}

func inspect(dataDir, oldTask, oldProof, out string) {
  ctx := context.Background(); st, err := contextstore.Open(dataDir); die(err); defer st.Close(); c := orchestrator.NewWithStore(st)
  proj, sp, err := st.CurrentOrLastDeliveredProjectSpec(ctx); die(err)
  pv, err := c.PlanView(ctx); die(err)
  oldTaskRow, oldTaskErr := st.Task(ctx, oldTask)
  oldProofRow, oldProofErr := st.ProofByTaskMode(ctx, oldTask, "converged")
  current := make([]map[string]any,0,len(pv.Tasks))
  for _, pt := range pv.Tasks { tr, e := st.Task(ctx, pt.ID); if e != nil { continue }; current = append(current,map[string]any{"id":tr.ID,"status":tr.Status,"proof_id":tr.ProofID,"reproof_required":tr.ReproofRequired,"title":tr.Title}) }
  writeJSON(out,map[string]any{"project_id":proj.ID,"project_status":proj.Status,"spec_hash":sp.Hash,"current_tasks":current,"old_task_present":oldTaskErr==nil,"old_task_status":oldTaskRow.Status,"old_task_proof_id":oldTaskRow.ProofID,"old_proof_present":oldProofErr==nil,"old_proof_id":oldProofRow.ID,"old_proof_matches":oldProofErr==nil && oldProofRow.ID==oldProof,"old_proof_verdict":oldProofRow.Verdict,"process_pid":os.Getpid()})
}

func main() {
  if len(os.Args) < 2 { panic("usage: probe <seed-proof|mismatch|inspect> ...") }
  switch os.Args[1] {
  case "seed-proof": if len(os.Args)!=6 { panic("seed-proof data out qtoken ctoken") }; seedProof(os.Args[2],os.Args[3],os.Args[4],os.Args[5])
  case "mismatch": if len(os.Args)!=5 { panic("mismatch data out ctoken") }; mismatch(os.Args[2],os.Args[3],os.Args[4])
  case "inspect": if len(os.Args)!=6 { panic("inspect data oldTask oldProof out") }; inspect(os.Args[2],os.Args[3],os.Args[4],os.Args[5])
  default: panic("unknown command")
  }
}
