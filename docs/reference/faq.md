# FAQ

## Can I upload a document in the web interface?

No. The UI is a static preview; no upload route exists.

## Can I ask questions about indexed documents?

No complete query API exists. `BM25Store.search()` is a standalone adapter.

## Does the system OCR scanned PDFs?

Not through the current `process_pdf()` path. Pages without native text are skipped.

## Is Redis the task queue?

No. `TaskQueue` is in-memory. Redis is present in Compose and used by the cost tracker.

## Is this production-ready?

No. See the [readiness matrix](../quality/release-checklist.md).

## Is the 8 GiB M4 profile verified?

No. Audit host reported 16 GiB RAM and the OpenSearch container was near its 1 GiB cap.
