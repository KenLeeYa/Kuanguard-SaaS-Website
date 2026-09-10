# Implementation coordination contract

Working root: `C:/Users/KY/Documents/Codex projects/KuanGuard`.
Specification: `docs/implementation-spec.md` (user-authorized input).
All data created here are synthetic development fixtures. No production activation.

## Ownership

- Main: `backend/kuanguard` except parsers/reports, database, API, wallet, campaigns, LMS, tests and integration documentation.
- UI: `apps/web/**`, `docs/design-system.md`, `docs/route-map.md`, UI screenshots/tests. Do not edit backend.
- Reports: `backend/kuanguard/parsers.py`, `backend/kuanguard/reports.py`, `backend/tests/test_parsers_reports.py`, `samples/reports/**`, parser/report documentation. Pure Python functions, no database dependencies.
- Infrastructure: `infra/**`, `scripts/cloudflare_onboard.py`, `scripts/backup_restore.py`, `tests/test_infra.py`, DNS/activation documentation. Do not edit compose or main Python configuration until coordinating.

## Runtime and HTTP contract

- Next.js/React/TypeScript UI `http://127.0.0.1:3180`, FastAPI `http://127.0.0.1:8180`.
- UI calls relative `/api/...`; Next rewrites to `API_INTERNAL_URL` (default `http://127.0.0.1:8180`) without `/api` prefix.
- Cookie `kg_session` is HttpOnly, host-only, SameSite=Lax (Secure outside development). GET `/auth/me` returns `{user:{id,name},tenant:{id,name},roles:string[],csrf_token:string,development:boolean}` or 401.
- All authenticated mutations require header `X-CSRF-Token` from `/auth/me` and accepted Origin. Client never sends arbitrary tenant ID.
- GET `/auth/dev/profiles` development only, returns `{items:[{key,label,roles}]}`. POST `/auth/dev/login` body `{profile_key}`. No fake authentication in production. Profiles: `customer-a`, `engineer-a`, `reviewer-a`, `finance-a`, `learner-a`, `customer-b`, `learner-b`, `pm-a`.
- POST `/auth/logout`. GET `/health`.
- Collections return `{items:[],total:number,page:number,page_size:number}`; details are plain JSON.
- Errors use `{detail:{code,message,trace_id}}`; UI may handle plain `detail` strings too.
- Mutations with billing/create/publish use `Idempotency-Key` random UUID, stable across retries.
- Dates are ISO UTC; UI formats Asia/Taipei with explicit label. Lists page/page_size capped 100.

## API routes and primary payloads

- GET `/public/services`: `{items:[{code,slug,name,mode,summary,deliverables:string[],status}]}`. Codes `VA,WVA,SHC,PT,SOURCE,PHISHING,TRAINING`.
- POST `/public/quote-requests`: `{company,contact_name,email,services:string[],scope,desired_date?}` -> lead with id/status.
- GET `/public/courses`, `/public/courses/{id}`: public course metadata and text preview.
- GET `/customer/dashboard`: `{projects,upcoming,risks,wallet?,training?,campaigns?,updated_at,notice}`.
- GET `/customer/projects`, `/customer/projects/{id}` includes `work_packages`, `batches`, `milestones`, `comments`, published `findings`, `reports`.
- GET `/customer/calendar`, `/customer/findings`, `/customer/reports`.
- POST `/customer/findings/{id}/replies`: `{text}`. POST `/customer/retest-requests`: `{batch_id,finding_ids:string[],reason}`.
- POST `/customer/projects/{id}/comments`: `{text}`. POST `/customer/projects/{id}/acceptance`: `{batch_id,decision,comment}`; decision `accepted,partial,returned`.
- GET `/customer/quotes`, `/customer/contracts`, `/customer/orders`, `/customer/entitlements`. POST `/customer/quotes/{id}/accept`: `{version,intent:"accept"}`.
- GET/POST `/customer/tickets` (`{subject,text}`), GET `/customer/organization`.
- GET `/customer/wallet`: `{available,reserved,consumed,expiring,lots,transactions,policy_version,sandbox}`.
- POST `/customer/wallet/orders`: `{points:100|500|1000}`. POST `/development/payments/{order_id}/settle` dev only signed sandbox processing.
- GET/POST `/customer/campaigns`: create `{name,group_id,scheduled_at,remediation_course_id?}`.
- GET `/customer/recipient-groups`. POST `/customer/recipient-imports`: `{name,csv}` header `email,department,name`; dedicated authorized endpoint.
- POST `/customer/campaigns/{id}/schedule`: `{confirmed:true}` reserves points. POST `.../cancel`, `.../pause`, `.../resume`; GET `.../{id}` includes message statuses/events/metrics.
- POST `/development/campaigns/{id}/dispatch`: local outbox simulation, no real mail. POST `/customer/suspicious-mail-reports`: `{campaign_id?,description}`.
- GET `/customer/training/courses`, `/customer/training/enrollments`, `/customer/training/learners`.
- POST `/customer/training/enrollments`: `{course_id,learner_id,cohort:"2026"}` reserves points. POST `/customer/training/enrollments/{id}/cancel`.
- GET `/learner/enrollments`, `/learner/enrollments/{id}`. POST `.../{id}/start`. GET `.../{id}/lessons`; POST `.../{id}/progress` `{lesson_id,seconds}` server-validates elapsed time. GET `.../{id}/questions`; POST `/learner/attempts` `{enrollment_id,answers:[{question_id,choice}]}`. GET `/learner/certificates/{id}`.
- GET `/internal/overview`, `/internal/projects`, `/internal/projects/{id}`, `/internal/leads`, `/internal/quotes`, `/internal/billing`, `/internal/audit`, `/internal/integrations`.
- POST `/internal/projects`: `{name,company_name,year}` creates project for current authorized tenant, seven work packages.
- POST `/internal/quotes`: `{lead_id?,title,amount_minor,services:string[],valid_until}`; new immutable version via `/internal/quotes/{id}/revise`.
- POST `/internal/projects/{id}/batches`: `{service_code,title,planned_assets:string[]}`.
- POST `/internal/batches/{id}/schedule`: `{start_at,end_at,engineer_id,reviewer_id,equipment,reason}` with conflict checks.
- POST `/internal/imports/preview`: `{batch_id,filename,content}` (size-limited local text import) -> `{id,findings,coverage,errors,warnings,source_hash,status}`. Accept sample `.csv`, `.nessus`, SHC `.json`, PT `.json`, SARIF `.sarif`; worker normalization.
- POST `/internal/imports/{id}/commit` -> committed findings. GET `/internal/imports`.
- POST `/internal/batches/{id}/review`: `{decision:"approved"|"returned",note}` assigned reviewer; v1.1 allows one verified actor with explicit roles unless the project's independent-review policy requires a different actor.
- POST `/internal/report-jobs`: `{batch_id}` creates durable background report job. GET `/internal/report-jobs`.
- POST `/internal/publications`: `{report_job_id,note}` publishes immutable complete artifact bundle; user review required, idempotent.
- GET `/internal/reports`, `/internal/findings`, `/internal/courses` and `/internal/dispatch`.
- GET `/customer/reports/{id}/download/{format}` authenticated proxy, formats docx/pdf/pptx/xlsx/csv, second authorization and audit.

## Parser/report function contract

`parse_assessment(filename: str, content: bytes, service_code: str, planned_assets: list[str]) -> dict`:
`{schema_version,parser_version,source_hash,findings:[{source_id,asset,title,severity,description,solution,port?,location?,evidence?,check_status?,rule_id?}],coverage:[{asset,status}],errors:[],warnings:[],metadata:{}}`.
Severity `Critical,High,Medium,Low,Informational,Unknown`; coverage `completed,not_tested,failed,insufficient`.
Pure parser rejects unsupported formats/schema, external entities, excessive sizes; no source execution.
`build_snapshot(parsed: dict, context: dict) -> dict` immutable normalized report payload, includes statistics and service-specific semantics.
`generate_bundle(snapshot: dict, output_dir: pathlib.Path) -> dict` produces report.docx/report.pdf/summary.pptx/summary.xlsx/all.csv/manifest.json from one snapshot; includes checksums and truthful structural/font/visual QA status. No external provider calls.

## Delivery boundaries

Do not invent finished external integrations, customer statistics, certifications, approved fonts/templates, paid course catalogs or prices. Public prices are inquiry; dev wallet rates clearly sandbox. Preserve all seven core flows; report unimplemented requirements honestly. No real DNS mutation, SMTP, purchases, real payments or unrelated repositories.
