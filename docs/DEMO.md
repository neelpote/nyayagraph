# Demo Guide

Run `make demo-reset` before presenting.

1. Open `http://localhost:3000` and sign in as `io@nyaya.local` / `NyayaDemo!2026`.
2. Search or open `MH-PUNE-2026-00142`.
3. Show the cited AI brief, 14 documents, 18 evidence records and three alerts.
4. Open Timeline and highlight `21:20`, `21:27` and restricted `22:05` without deciding truth.
5. Open Knowledge Graph and explain that only authorized nodes are returned.
6. Open E-12: show both SHA-256 fingerprints, valid signature, custody gap and visibly labelled ledger mode.
7. In Verification, select the forensic version and upload `seed/documents/forensic-original.pdf`; expect `VERIFIED`.
8. Upload `seed/documents/forensic-modified.pdf`; expect `HASH_MISMATCH`.
9. Sign out and use `expert@nyaya.local`. Witness-03 disappears; asking about it returns `Insufficient authorized evidence available.`
10. Sign back in as IO. In Access, select Witness-03, enter `expert@nyaya.local`, a future expiry and a justification.
11. Sign in as expert again; Witness-03 and its citation are now visible. Show the access/audit provenance event.
12. Return as IO and generate the court verification report. Scan/open its QR URL to show only authenticity booleans.

If Fabric or the public chain is unavailable, explicitly show `DATABASE DEV` or `PENDING/LOCAL`. Never describe those states as a real network transaction.
