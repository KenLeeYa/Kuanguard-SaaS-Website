# Synthetic report samples

All inputs and outputs are synthetic development fixtures. No real customer, host, account, secret, source execution or network assessment was used. Documentation IPs and example.test URLs are inert labels.

Use `bundles_final/` for the reviewed sample revision. Each of its six subdirectories contains five report formats, manifest.json and snapshot.json. `qa_final/` contains all 20 rendered native PDF pages and verification.json. Office visual rendering and approved-template fidelity remain unverified.

`generate_samples.py` builds from `inputs/` into a new directory. `verify_samples.py` checks final artifacts and linked page images. Reports are immutable after their manifest is complete. Earlier locally preserved layout drafts are ignored by this directory's .gitignore.

The WVA XML is explicitly a KUANGUARD mapped profile. It is not represented as a real AppScan native export or vendor compatibility proof. See docs/parser-capabilities.md and docs/report-qa.md.
