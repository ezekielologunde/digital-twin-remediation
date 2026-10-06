# Public repository release

Prepared 5 October 2026 from Research-evidence-v0.2.zip, SHA-256:
`6fe6cabd3aefb483a28a304b3e09d3ce63db93cc3abb2e0818cd8aa59cb69bca`.

The original evidence payload and its manifest are preserved unchanged. Repository README, DATA.md, NOTICE.md, release verification script, CI workflow, and Overleaf download are additions. MANIFEST.json describes the original payload only, not these release additions.

Historical publication/package-validation.json inside that payload predates the enclosing v0.2 archive. It is retained for provenance and must not be mistaken for the verification receipt of this public checkout. Use scripts/verify_release.py to verify this checkout. Historical packaging scripts are not the release verification entry point and may reference files outside this curated subset.

The Overleaf upload archive retains its author-review instructions and placeholders. No verified PDF is included. Public release of artifacts does not resolve journal authorship, declarations, or acceptance.

The authenticated GitHub token lacks workflow scope. The optional CI definition is provided in docs/verify-workflow.yml.example; automated GitHub verification is not enabled. Local verification passed before publication.
