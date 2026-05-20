# quality

Future home for reusable validation logic shared by training quality checks and
benchmark orchestration.

Phase 1 only creates the module boundary. Later phases can move compile,
runtime, semantic, and scoring helpers here in small compatibility-preserving
steps, leaving existing CLIs in place until each migration slice is verified.
