package main

import (
  "os"
  "path/filepath"
  "testing"
)

func TestPrepareCandidateDirCreatesCleanDirectory(t *testing.T) {
  root := t.TempDir()
  dir := filepath.Join(root, "candidate")
  if err := os.MkdirAll(dir, 0o755); err != nil { t.Fatal(err) }
  if err := os.WriteFile(filepath.Join(dir, "stale.txt"), []byte("stale"), 0o644); err != nil { t.Fatal(err) }

  prepareCandidateDir(dir)

  st, err := os.Stat(dir)
  if err != nil { t.Fatalf("candidate directory missing after preparation: %v", err) }
  if !st.IsDir() { t.Fatalf("candidate path is not a directory") }
  if _, err := os.Stat(filepath.Join(dir, "stale.txt")); !os.IsNotExist(err) {
    t.Fatalf("stale file survived candidate preparation: %v", err)
  }
}
