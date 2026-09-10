# Project execution API

Incremental local implementation. Every mutation requires the existing session, CSRF/Origin checks and a stable `Idempotency-Key`. No tenant ID is accepted from the client. All project operations also require an unexpired project grant. Dates must include a time zone. Collection endpoints accept `page` and `page_size` (1–100).

`POST /internal/projects` now accepts optional `contract_id`. It must identify the same tenant's active contract backed by its accepted quote with a matching amount; cross-tenant, inactive or inconsistent references are rejected. The PM creation form lists eligible contracts. Omitting it keeps the existing behavior and derived contract margin stays unknown. Existing projects are not automatically rebound to a contract.

## Tasks

- `GET /internal/projects/{project_id}/tasks`: PM/engineer/reviewer, paged collection.
- `GET /customer/projects/{project_id}/tasks`: customer_contact, customer-visible projection only.
- `POST /internal/projects/{project_id}/tasks`: PM creates a task.
- `POST /internal/tasks/{task_id}`: PM replaces editable fields, requires `expected_version` from the last response. Stale versions return `409 STALE_VERSION`.

Create body (update body adds `expected_version`):

```json
{
  "title": "確認掃描範圍",
  "status": "open",
  "visibility": "customer",
  "customer_note": "請確認本次測試資產。",
  "internal_note": "僅內部可見的協調事項",
  "batch_id": null,
  "assigned_to": null,
  "due_at": "2026-10-01T09:00:00+08:00",
  "dependency_ids": []
}
```

`status`: `open | in_progress | blocked | done`. `visibility`: `internal | customer`; defaults to internal. Blocking manually requires a nonempty note. `effective_status` is blocked while prerequisites remain unfinished. Completing a blocked dependency chain returns `409 DEPENDENCY_BLOCKED`; cycles return `409 DEPENDENCY_CYCLE`. At most 20 dependencies per task and 1000 tasks per project. Reopening a prerequisite of a completed task requires reopening the dependent first. Dependency/assignee/batch references must belong to the authorized project; assignees need an active account, tenant membership and project grant.

Response fields: `id, project_id, batch_id, title, status, effective_status, due_at, visibility, customer_note, dependency_ids, version`; internal responses additionally contain `internal_note, assigned_to`. Customer dependencies contain only visible task IDs. Existing project detail `milestones` now uses this same projection. Updating an existing legacy task creates its details row at version 2 without replacing the original task.

## Meeting decisions

- `GET /internal/projects/{project_id}/decisions`: PM/engineer/reviewer.
- `GET /customer/projects/{project_id}/decisions`: customer_contact, customer-visible projection only.
- `POST /internal/projects/{project_id}/decisions`: PM; append a decision. Corrections are a new decision, preserving previous minutes.

```json
{
  "title": "範圍確認會議決議",
  "occurred_at": "2026-09-10T15:00:00+08:00",
  "visibility": "customer",
  "customer_text": "本批次依已確認資產執行。",
  "internal_note": "內部評估備註",
  "batch_id": null,
  "publication_id": null,
  "task_ids": []
}
```

Customer-visible decisions require `customer_text`. Optional links validate the same project and batch. A batch link captures its current `scope_version`; report links accept a published report ID, never an unpublished job ID. Response adds `id, project_id, scope_version`. Internal response includes `internal_note, actor_id`; customer response omits both and filters internal task links. At most 20 linked tasks.

## Hours and cost

- `GET /internal/cost-projects`: only PM/finance, paged selector containing only `{id,name,year}` for projects with an active grant. This does not grant finance access to technical project details.
- `GET /internal/projects/{project_id}/costs`: only PM/finance **and** project grant.
- `POST /internal/projects/{project_id}/costs`: same authorization, append a line item.
- `POST /internal/costs/{cost_id}/void`: `{ "reason": "更正誤植，另建正確紀錄" }`; retains original fields and records void reason/time.

```json
{
  "phase": "estimated",
  "category": "analysis",
  "minutes": 120,
  "cost_minor": null,
  "currency": null,
  "task_id": null,
  "note": "待確認費率，先記錄預估工時"
}
```

`phase`: `estimated | actual`. `category`: `onsite | travel | analysis | review | retest | tools | cloud | outsource | other`. Minutes and minor currency units are nonnegative integers. `cost_minor` and uppercase three-letter `currency` must be supplied together; null means unpriced, never zero. Entered amount is the total for this line; there is no automatic hourly rate, currency conversion, tax or margin assumption.

GET returns the paged entries plus `totals.estimated` and `totals.actual`, each `{ minutes, amounts: [{currency,cost_minor}], unpriced_entries, cost_status: "unconfigured" | "entered" }`, excluding voided entries. Different currencies stay separate. `legacy_entries` preserves earlier `time_entries`; because those rows lack phase/currency, they are labeled `unclassified_excluded` and excluded from new totals. No costs appear on customer routes or ordinary engineer/reviewer views.

GET also returns `margin:{basis,contract_amount_minor,currency,contract_reason,estimated_cost_minor,estimated_gross_margin_minor,estimated_reason,actual_cost_minor,actual_gross_margin_minor,actual_reason}`. Basis is **合約金額減已登錄成本，非正式收入認列**. Contract amount/currency require the project's linked active contract and its matching quote; no invoice receipts, GMV, payment balance or assumed revenue are substituted. Each phase's cost and gross margin require entered, fully priced costs in exactly the contract currency. Missing contract, no entries, unpriced entries, mixed/mismatching currencies, unclassified legacy costs or an inconsistent contract/quote produce null derived amounts plus reason codes. Negative entered-cost margin is retained. Reasons include `no_active_contract`, `contract_quote_unavailable`, `contract_amount_unconfigured`, `contract_quote_amount_mismatch`, `contract_currency_unconfigured`, `cost_not_entered`, `unpriced_entries`, `mixed_cost_currencies`, `cost_currency_mismatch`, `unclassified_legacy_entries`.

## Dispatch configuration

Existing `GET /internal/dispatch` returns people `items` (with actual `roles, skills, qualifications, qualification_status`), assigned `batches`, `policy` and `tools`. No inferred all-service qualifications. The collection reports unconfigured state when policy or qualifications are absent. PM configures; PM/engineer/reviewer can read:

- `GET/POST /internal/dispatch/policy`: POST `{expected_version:0, travel_buffer_minutes:0, reason:"明示批准的交通緩衝政策"}`. GET includes `status`, `version`; absent policy has status unconfigured and null buffer. Zero is accepted only when explicitly entered.
- `GET/POST /internal/dispatch/qualifications`: POST `{expected_version:0, user_id:"...", role:"engineer", service_code:"VA", valid_until:null, active:true, reason:"已確認適任資格"}`. Role is engineer/reviewer; qualification must cover the full scheduled work interval. Repeat POST for the same user/role/service with current expected_version to change/revoke.
- `GET/POST /internal/dispatch/tools`: POST `{expected_version:0, name:"已確認工具池", capacity:2, service_codes:["VA"], active:true, reason:"已確認兩份同時可用授權"}`. Tool name is the immutable upsert key; capacity 1–100. Reducing capacity/services or deactivating with future reservations returns `409 TOOL_IN_USE`.

All creation/upserts use `expected_version:0` only for an absent setting; updates require the returned positive version. `409 STALE_VERSION` means refresh before retry. Service codes use the existing seven catalog codes.

Existing `POST /internal/batches/{batch_id}/schedule` keeps `start_at,end_at,engineer_id,reviewer_id,equipment,reason` and adds optional `equipment_units` (default 1). `equipment` must equal a configured tool name. Response adds `scheduling_checks:{status:"verified",policy_version,travel_buffer_minutes,tool_id,equipment_units}`.

New confirmations fail closed for missing policy (`DISPATCH_POLICY_UNCONFIGURED`), missing/expired qualification (`QUALIFICATION_UNCONFIGURED`), unconfigured tool (`TOOL_UNCONFIGURED`), person/reviewer conflict (`SCHEDULE_CONFLICT`), or capacity shortage (`TOOL_CAPACITY_CONFLICT`). Each person is exclusive across tenants; when one authorized actor performs engineering and review, a single person reservation is stored. Independent review still follows the project policy. Tool pools belong to the current tenant, with numbered capacity slots held for the entire buffered interval. Different physical/license units must have distinct configured slots; no automatic split or reassignment is attempted. The existing PostgreSQL global advisory transaction lock protects reservation checks and writes. Legacy equipment reservations remain respected; existing confirmed schedules are not rewritten by configuration changes.

The explicitly named development helper seeds synthetic qualifications, 30-minute buffer and five capacity-one test tools only in development/test. It only adds missing rows. These fixtures are not evidence of real personnel credentials or production dispatch policy.

## Database integration

Import `execution_models` before `m.metadata.create_all`. `execution_models.EXECUTION_TABLES` contains seven new tables on the existing metadata: task_details, task_dependencies, meeting_decisions, project_cost_entries, dispatch_policies, dispatch_qualifications, dispatch_tools. All use the existing tenant table registry and composite tenant references; additive migration 0009 must enable/force RLS and install tenant policy. `project_routes.router` includes the new execution router. No existing database, tasks, reservations, evidence or backup is reset.
