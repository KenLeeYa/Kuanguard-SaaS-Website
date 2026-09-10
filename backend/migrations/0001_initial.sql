
CREATE TABLE courses (
	id VARCHAR(36) NOT NULL, 
	created_at TIMESTAMP WITH TIME ZONE NOT NULL, 
	slug VARCHAR(120), 
	title VARCHAR(120), 
	version INTEGER, 
	description TEXT, 
	preview TEXT, 
	points INTEGER, 
	duration_minutes INTEGER, 
	pass_percent INTEGER, 
	max_attempts INTEGER, 
	status VARCHAR(120), 
	rights TEXT, 
	language VARCHAR(120), 
	CONSTRAINT pk_courses PRIMARY KEY (id), 
	CONSTRAINT uq_courses_slug UNIQUE (slug)
)

;


CREATE TABLE inbox (
	id VARCHAR(36) NOT NULL, 
	created_at TIMESTAMP WITH TIME ZONE NOT NULL, 
	provider VARCHAR(120), 
	event_id VARCHAR(240), 
	payload_hash VARCHAR(64), 
	status VARCHAR(120), 
	order_id VARCHAR(36), 
	CONSTRAINT pk_inbox PRIMARY KEY (id), 
	CONSTRAINT uq_inbox_provider_event_id UNIQUE (provider, event_id)
)

;


CREATE TABLE leads (
	id VARCHAR(36) NOT NULL, 
	created_at TIMESTAMP WITH TIME ZONE NOT NULL, 
	company VARCHAR(120), 
	contact_name VARCHAR(120), 
	email VARCHAR(254), 
	services JSON, 
	scope TEXT, 
	desired_date VARCHAR(30), 
	status VARCHAR(120), 
	CONSTRAINT pk_leads PRIMARY KEY (id)
)

;


CREATE TABLE oidc_states (
	id VARCHAR(36) NOT NULL, 
	created_at TIMESTAMP WITH TIME ZONE NOT NULL, 
	state_hash VARCHAR(64), 
	nonce VARCHAR(120), 
	verifier VARCHAR(128), 
	expires_at TIMESTAMP WITH TIME ZONE, 
	CONSTRAINT pk_oidc_states PRIMARY KEY (id), 
	CONSTRAINT uq_oidc_states_state_hash UNIQUE (state_hash)
)

;


CREATE TABLE resource_slots (
	id VARCHAR(36) NOT NULL, 
	created_at TIMESTAMP WITH TIME ZONE NOT NULL, 
	tenant_id VARCHAR(36), 
	batch_id VARCHAR(36), 
	resource VARCHAR(120), 
	start_at TIMESTAMP WITH TIME ZONE, 
	end_at TIMESTAMP WITH TIME ZONE, 
	CONSTRAINT pk_resource_slots PRIMARY KEY (id)
)

;


CREATE TABLE service_catalog (
	id VARCHAR(36) NOT NULL, 
	created_at TIMESTAMP WITH TIME ZONE NOT NULL, 
	code VARCHAR(120), 
	slug VARCHAR(120), 
	name VARCHAR(120), 
	mode VARCHAR(120), 
	summary TEXT, 
	deliverables JSON, 
	version INTEGER, 
	CONSTRAINT pk_service_catalog PRIMARY KEY (id), 
	CONSTRAINT uq_service_catalog_code UNIQUE (code), 
	CONSTRAINT uq_service_catalog_slug UNIQUE (slug)
)

;


CREATE TABLE tenants (
	id VARCHAR(36) NOT NULL, 
	created_at TIMESTAMP WITH TIME ZONE NOT NULL, 
	name VARCHAR(120) NOT NULL, 
	verified BOOLEAN, 
	status VARCHAR(120), 
	CONSTRAINT pk_tenants PRIMARY KEY (id)
)

;


CREATE TABLE users (
	id VARCHAR(36) NOT NULL, 
	created_at TIMESTAMP WITH TIME ZONE NOT NULL, 
	name VARCHAR(120) NOT NULL, 
	email VARCHAR(254) NOT NULL, 
	oidc_subject VARCHAR(400), 
	active BOOLEAN, 
	CONSTRAINT pk_users PRIMARY KEY (id), 
	CONSTRAINT uq_users_email UNIQUE (email), 
	CONSTRAINT uq_users_oidc_subject UNIQUE (oidc_subject)
)

;


CREATE TABLE audit_events (
	id VARCHAR(36) NOT NULL, 
	created_at TIMESTAMP WITH TIME ZONE NOT NULL, 
	tenant_id VARCHAR(36) NOT NULL, 
	actor_id VARCHAR(36), 
	action VARCHAR(120), 
	resource_id VARCHAR(120), 
	trace_id VARCHAR(36), 
	summary TEXT, 
	CONSTRAINT pk_audit_events PRIMARY KEY (id), 
	CONSTRAINT uq_audit_events_tenant_id_id UNIQUE (tenant_id, id), 
	CONSTRAINT fk_audit_events_tenant_id_tenants FOREIGN KEY(tenant_id) REFERENCES tenants (id)
)

;


CREATE TABLE deletion_requests (
	id VARCHAR(36) NOT NULL, 
	created_at TIMESTAMP WITH TIME ZONE NOT NULL, 
	tenant_id VARCHAR(36) NOT NULL, 
	data_class VARCHAR(120), 
	status VARCHAR(120), 
	reason TEXT, 
	requested_by VARCHAR(36), 
	backup_expiry TIMESTAMP WITH TIME ZONE, 
	CONSTRAINT pk_deletion_requests PRIMARY KEY (id), 
	CONSTRAINT uq_deletion_requests_tenant_id_id UNIQUE (tenant_id, id), 
	CONSTRAINT fk_deletion_requests_tenant_id_tenants FOREIGN KEY(tenant_id) REFERENCES tenants (id)
)

;


CREATE TABLE grants (
	id VARCHAR(36) NOT NULL, 
	created_at TIMESTAMP WITH TIME ZONE NOT NULL, 
	tenant_id VARCHAR(36) NOT NULL, 
	user_id VARCHAR(36), 
	resource_id VARCHAR(36), 
	scope VARCHAR(120), 
	expires_at TIMESTAMP WITH TIME ZONE, 
	reason TEXT, 
	CONSTRAINT pk_grants PRIMARY KEY (id), 
	CONSTRAINT uq_grants_tenant_id_user_id_resource_id_scope UNIQUE (tenant_id, user_id, resource_id, scope), 
	CONSTRAINT uq_grants_tenant_id_id UNIQUE (tenant_id, id), 
	CONSTRAINT fk_grants_tenant_id_tenants FOREIGN KEY(tenant_id) REFERENCES tenants (id), 
	CONSTRAINT fk_grants_user_id_users FOREIGN KEY(user_id) REFERENCES users (id)
)

;


CREATE TABLE idempotency (
	id VARCHAR(36) NOT NULL, 
	created_at TIMESTAMP WITH TIME ZONE NOT NULL, 
	tenant_id VARCHAR(36) NOT NULL, 
	actor_id VARCHAR(36), 
	operation VARCHAR(120), 
	key VARCHAR(128), 
	payload_hash VARCHAR(64), 
	response JSON, 
	CONSTRAINT pk_idempotency PRIMARY KEY (id), 
	CONSTRAINT uq_idempotency_tenant_id_actor_id_operation_key UNIQUE (tenant_id, actor_id, operation, key), 
	CONSTRAINT uq_idempotency_tenant_id_id UNIQUE (tenant_id, id), 
	CONSTRAINT fk_idempotency_tenant_id_tenants FOREIGN KEY(tenant_id) REFERENCES tenants (id)
)

;


CREATE TABLE invitations (
	id VARCHAR(36) NOT NULL, 
	created_at TIMESTAMP WITH TIME ZONE NOT NULL, 
	tenant_id VARCHAR(36) NOT NULL, 
	email VARCHAR(254), 
	role VARCHAR(120), 
	department VARCHAR(120), 
	token_hash VARCHAR(64), 
	expires_at TIMESTAMP WITH TIME ZONE, 
	status VARCHAR(120), 
	CONSTRAINT pk_invitations PRIMARY KEY (id), 
	CONSTRAINT uq_invitations_tenant_id_id UNIQUE (tenant_id, id), 
	CONSTRAINT fk_invitations_tenant_id_tenants FOREIGN KEY(tenant_id) REFERENCES tenants (id)
)

;


CREATE TABLE jobs (
	id VARCHAR(36) NOT NULL, 
	created_at TIMESTAMP WITH TIME ZONE NOT NULL, 
	tenant_id VARCHAR(36), 
	kind VARCHAR(120), 
	resource_id VARCHAR(36), 
	status VARCHAR(120), 
	attempts INTEGER, 
	lease_until TIMESTAMP WITH TIME ZONE, 
	available_at TIMESTAMP WITH TIME ZONE, 
	error_code VARCHAR(120), 
	CONSTRAINT pk_jobs PRIMARY KEY (id), 
	CONSTRAINT uq_jobs_kind_resource_id UNIQUE (kind, resource_id), 
	CONSTRAINT fk_jobs_tenant_id_tenants FOREIGN KEY(tenant_id) REFERENCES tenants (id)
)

;


CREATE TABLE lessons (
	id VARCHAR(36) NOT NULL, 
	created_at TIMESTAMP WITH TIME ZONE NOT NULL, 
	course_id VARCHAR(36), 
	title VARCHAR(120), 
	content TEXT, 
	position INTEGER, 
	min_seconds INTEGER, 
	video_id VARCHAR(120), 
	CONSTRAINT pk_lessons PRIMARY KEY (id), 
	CONSTRAINT fk_lessons_course_id_courses FOREIGN KEY(course_id) REFERENCES courses (id)
)

;


CREATE TABLE memberships (
	id VARCHAR(36) NOT NULL, 
	created_at TIMESTAMP WITH TIME ZONE NOT NULL, 
	tenant_id VARCHAR(36) NOT NULL, 
	user_id VARCHAR(36) NOT NULL, 
	role VARCHAR(120) NOT NULL, 
	department VARCHAR(120), 
	active BOOLEAN, 
	CONSTRAINT pk_memberships PRIMARY KEY (id), 
	CONSTRAINT uq_memberships_tenant_id_user_id_role UNIQUE (tenant_id, user_id, role), 
	CONSTRAINT fk_memberships_tenant_id_tenants FOREIGN KEY(tenant_id) REFERENCES tenants (id), 
	CONSTRAINT fk_memberships_user_id_users FOREIGN KEY(user_id) REFERENCES users (id)
)

;


CREATE TABLE notifications (
	id VARCHAR(36) NOT NULL, 
	created_at TIMESTAMP WITH TIME ZONE NOT NULL, 
	tenant_id VARCHAR(36) NOT NULL, 
	user_id VARCHAR(36), 
	title VARCHAR(120), 
	text TEXT, 
	read_at TIMESTAMP WITH TIME ZONE, 
	CONSTRAINT pk_notifications PRIMARY KEY (id), 
	CONSTRAINT uq_notifications_tenant_id_id UNIQUE (tenant_id, id), 
	CONSTRAINT fk_notifications_tenant_id_tenants FOREIGN KEY(tenant_id) REFERENCES tenants (id)
)

;


CREATE TABLE orders (
	id VARCHAR(36) NOT NULL, 
	created_at TIMESTAMP WITH TIME ZONE NOT NULL, 
	tenant_id VARCHAR(36) NOT NULL, 
	points INTEGER, 
	amount_minor INTEGER, 
	currency VARCHAR(120), 
	status VARCHAR(120), 
	rate_version VARCHAR(120), 
	provider VARCHAR(120), 
	terms TEXT, 
	actor_id VARCHAR(36), 
	CONSTRAINT pk_orders PRIMARY KEY (id), 
	CONSTRAINT ck_orders_positive_order CHECK (points > 0 AND amount_minor > 0), 
	CONSTRAINT uq_orders_tenant_id_id UNIQUE (tenant_id, id), 
	CONSTRAINT fk_orders_tenant_id_tenants FOREIGN KEY(tenant_id) REFERENCES tenants (id)
)

;


CREATE TABLE payment_routes (
	id VARCHAR(36) NOT NULL, 
	created_at TIMESTAMP WITH TIME ZONE NOT NULL, 
	tenant_id VARCHAR(36), 
	order_id VARCHAR(36), 
	merchant VARCHAR(120), 
	CONSTRAINT pk_payment_routes PRIMARY KEY (id), 
	CONSTRAINT fk_payment_routes_tenant_id_tenants FOREIGN KEY(tenant_id) REFERENCES tenants (id), 
	CONSTRAINT uq_payment_routes_order_id UNIQUE (order_id)
)

;


CREATE TABLE questionnaires (
	id VARCHAR(36) NOT NULL, 
	created_at TIMESTAMP WITH TIME ZONE NOT NULL, 
	tenant_id VARCHAR(36) NOT NULL, 
	title VARCHAR(120), 
	supplier VARCHAR(120), 
	due_at TIMESTAMP WITH TIME ZONE, 
	status VARCHAR(120), 
	CONSTRAINT pk_questionnaires PRIMARY KEY (id), 
	CONSTRAINT uq_questionnaires_tenant_id_id UNIQUE (tenant_id, id), 
	CONSTRAINT fk_questionnaires_tenant_id_tenants FOREIGN KEY(tenant_id) REFERENCES tenants (id)
)

;


CREATE TABLE questions (
	id VARCHAR(36) NOT NULL, 
	created_at TIMESTAMP WITH TIME ZONE NOT NULL, 
	course_id VARCHAR(36), 
	prompt TEXT, 
	choices JSON, 
	correct_choice INTEGER, 
	explanation TEXT, 
	position INTEGER, 
	CONSTRAINT pk_questions PRIMARY KEY (id), 
	CONSTRAINT fk_questions_course_id_courses FOREIGN KEY(course_id) REFERENCES courses (id)
)

;


CREATE TABLE quotes (
	id VARCHAR(36) NOT NULL, 
	created_at TIMESTAMP WITH TIME ZONE NOT NULL, 
	tenant_id VARCHAR(36) NOT NULL, 
	family_id VARCHAR(36), 
	version INTEGER, 
	title VARCHAR(120), 
	amount_minor INTEGER, 
	currency VARCHAR(120), 
	services JSON, 
	valid_until TIMESTAMP WITH TIME ZONE, 
	status VARCHAR(120), 
	accepted_by VARCHAR(36), 
	accepted_at TIMESTAMP WITH TIME ZONE, 
	lead_id VARCHAR(36), 
	CONSTRAINT pk_quotes PRIMARY KEY (id), 
	CONSTRAINT uq_quotes_tenant_id_family_id_version UNIQUE (tenant_id, family_id, version), 
	CONSTRAINT ck_quotes_quote_amount CHECK (amount_minor >= 0), 
	CONSTRAINT uq_quotes_tenant_id_id UNIQUE (tenant_id, id), 
	CONSTRAINT fk_quotes_tenant_id_tenants FOREIGN KEY(tenant_id) REFERENCES tenants (id), 
	CONSTRAINT fk_quotes_lead_id_leads FOREIGN KEY(lead_id) REFERENCES leads (id)
)

;


CREATE TABLE recipient_groups (
	id VARCHAR(36) NOT NULL, 
	created_at TIMESTAMP WITH TIME ZONE NOT NULL, 
	tenant_id VARCHAR(36) NOT NULL, 
	name VARCHAR(120), 
	owner_id VARCHAR(36), 
	version INTEGER, 
	CONSTRAINT pk_recipient_groups PRIMARY KEY (id), 
	CONSTRAINT uq_recipient_groups_tenant_id_id UNIQUE (tenant_id, id), 
	CONSTRAINT fk_recipient_groups_tenant_id_tenants FOREIGN KEY(tenant_id) REFERENCES tenants (id)
)

;


CREATE TABLE reservations (
	id VARCHAR(36) NOT NULL, 
	created_at TIMESTAMP WITH TIME ZONE NOT NULL, 
	tenant_id VARCHAR(36) NOT NULL, 
	purpose VARCHAR(120), 
	business_id VARCHAR(120), 
	quantity INTEGER, 
	status VARCHAR(120), 
	expires_at TIMESTAMP WITH TIME ZONE, 
	policy_version VARCHAR(120), 
	CONSTRAINT pk_reservations PRIMARY KEY (id), 
	CONSTRAINT uq_reservations_tenant_id_purpose_business_id UNIQUE (tenant_id, purpose, business_id), 
	CONSTRAINT ck_reservations_positive_reservation CHECK (quantity > 0), 
	CONSTRAINT uq_reservations_tenant_id_id UNIQUE (tenant_id, id), 
	CONSTRAINT fk_reservations_tenant_id_tenants FOREIGN KEY(tenant_id) REFERENCES tenants (id)
)

;


CREATE TABLE retention_policies (
	id VARCHAR(36) NOT NULL, 
	created_at TIMESTAMP WITH TIME ZONE NOT NULL, 
	tenant_id VARCHAR(36) NOT NULL, 
	data_class VARCHAR(120), 
	days INTEGER, 
	version INTEGER, 
	approved BOOLEAN, 
	CONSTRAINT pk_retention_policies PRIMARY KEY (id), 
	CONSTRAINT uq_retention_policies_tenant_id_id UNIQUE (tenant_id, id), 
	CONSTRAINT fk_retention_policies_tenant_id_tenants FOREIGN KEY(tenant_id) REFERENCES tenants (id)
)

;


CREATE TABLE sessions (
	id VARCHAR(36) NOT NULL, 
	created_at TIMESTAMP WITH TIME ZONE NOT NULL, 
	token_hash VARCHAR(64) NOT NULL, 
	tenant_id VARCHAR(36) NOT NULL, 
	user_id VARCHAR(36) NOT NULL, 
	csrf_token VARCHAR(64) NOT NULL, 
	expires_at TIMESTAMP WITH TIME ZONE, 
	revoked BOOLEAN, 
	CONSTRAINT pk_sessions PRIMARY KEY (id), 
	CONSTRAINT uq_sessions_token_hash UNIQUE (token_hash), 
	CONSTRAINT fk_sessions_tenant_id_tenants FOREIGN KEY(tenant_id) REFERENCES tenants (id), 
	CONSTRAINT fk_sessions_user_id_users FOREIGN KEY(user_id) REFERENCES users (id)
)

;


CREATE TABLE tickets (
	id VARCHAR(36) NOT NULL, 
	created_at TIMESTAMP WITH TIME ZONE NOT NULL, 
	tenant_id VARCHAR(36) NOT NULL, 
	subject VARCHAR(120), 
	text TEXT, 
	status VARCHAR(120), 
	actor_id VARCHAR(36), 
	CONSTRAINT pk_tickets PRIMARY KEY (id), 
	CONSTRAINT uq_tickets_tenant_id_id UNIQUE (tenant_id, id), 
	CONSTRAINT fk_tickets_tenant_id_tenants FOREIGN KEY(tenant_id) REFERENCES tenants (id)
)

;


CREATE TABLE wallets (
	id VARCHAR(36) NOT NULL, 
	created_at TIMESTAMP WITH TIME ZONE NOT NULL, 
	tenant_id VARCHAR(36) NOT NULL, 
	frozen BOOLEAN, 
	policy_version VARCHAR(120), 
	CONSTRAINT pk_wallets PRIMARY KEY (id), 
	CONSTRAINT uq_wallets_tenant_id UNIQUE (tenant_id), 
	CONSTRAINT uq_wallets_tenant_id_id UNIQUE (tenant_id, id), 
	CONSTRAINT fk_wallets_tenant_id_tenants FOREIGN KEY(tenant_id) REFERENCES tenants (id)
)

;


CREATE TABLE campaigns (
	id VARCHAR(36) NOT NULL, 
	created_at TIMESTAMP WITH TIME ZONE NOT NULL, 
	tenant_id VARCHAR(36) NOT NULL, 
	name VARCHAR(120), 
	group_id VARCHAR(36), 
	owner_id VARCHAR(36), 
	scheduled_at TIMESTAMP WITH TIME ZONE, 
	status VARCHAR(120), 
	remediation_course_id VARCHAR(36), 
	timezone VARCHAR(120), 
	rate_version VARCHAR(120), 
	provider VARCHAR(120), 
	template_revision VARCHAR(120), 
	CONSTRAINT pk_campaigns PRIMARY KEY (id), 
	CONSTRAINT fk_campaigns_tenant_id_group_id_recipient_groups FOREIGN KEY(tenant_id, group_id) REFERENCES recipient_groups (tenant_id, id), 
	CONSTRAINT uq_campaigns_tenant_id_id UNIQUE (tenant_id, id), 
	CONSTRAINT fk_campaigns_tenant_id_tenants FOREIGN KEY(tenant_id) REFERENCES tenants (id)
)

;


CREATE TABLE contracts (
	id VARCHAR(36) NOT NULL, 
	created_at TIMESTAMP WITH TIME ZONE NOT NULL, 
	tenant_id VARCHAR(36) NOT NULL, 
	quote_id VARCHAR(36), 
	title VARCHAR(120), 
	status VARCHAR(120), 
	version INTEGER, 
	amount_minor INTEGER, 
	services JSON, 
	accepted_by VARCHAR(36), 
	CONSTRAINT pk_contracts PRIMARY KEY (id), 
	CONSTRAINT fk_contracts_tenant_id_quote_id_quotes FOREIGN KEY(tenant_id, quote_id) REFERENCES quotes (tenant_id, id), 
	CONSTRAINT uq_contracts_tenant_id_quote_id UNIQUE (tenant_id, quote_id), 
	CONSTRAINT uq_contracts_tenant_id_id UNIQUE (tenant_id, id), 
	CONSTRAINT fk_contracts_tenant_id_tenants FOREIGN KEY(tenant_id) REFERENCES tenants (id)
)

;


CREATE TABLE enrollments (
	id VARCHAR(36) NOT NULL, 
	created_at TIMESTAMP WITH TIME ZONE NOT NULL, 
	tenant_id VARCHAR(36) NOT NULL, 
	course_id VARCHAR(36), 
	learner_id VARCHAR(36), 
	cohort VARCHAR(120), 
	status VARCHAR(120), 
	reservation_id VARCHAR(36), 
	expires_at TIMESTAMP WITH TIME ZONE, 
	started_at TIMESTAMP WITH TIME ZONE, 
	completed_at TIMESTAMP WITH TIME ZONE, 
	source VARCHAR(120), 
	CONSTRAINT pk_enrollments PRIMARY KEY (id), 
	CONSTRAINT fk_enrollments_tenant_id_reservation_id_reservations FOREIGN KEY(tenant_id, reservation_id) REFERENCES reservations (tenant_id, id), 
	CONSTRAINT uq_enrollments_tenant_id_course_id_learner_id_cohort UNIQUE (tenant_id, course_id, learner_id, cohort), 
	CONSTRAINT uq_enrollments_tenant_id_id UNIQUE (tenant_id, id), 
	CONSTRAINT fk_enrollments_tenant_id_tenants FOREIGN KEY(tenant_id) REFERENCES tenants (id), 
	CONSTRAINT fk_enrollments_course_id_courses FOREIGN KEY(course_id) REFERENCES courses (id), 
	CONSTRAINT fk_enrollments_learner_id_users FOREIGN KEY(learner_id) REFERENCES users (id)
)

;


CREATE TABLE invoices (
	id VARCHAR(36) NOT NULL, 
	created_at TIMESTAMP WITH TIME ZONE NOT NULL, 
	tenant_id VARCHAR(36) NOT NULL, 
	order_id VARCHAR(36), 
	status VARCHAR(120), 
	attempts INTEGER, 
	CONSTRAINT pk_invoices PRIMARY KEY (id), 
	CONSTRAINT fk_invoices_tenant_id_order_id_orders FOREIGN KEY(tenant_id, order_id) REFERENCES orders (tenant_id, id), 
	CONSTRAINT uq_invoices_tenant_id_order_id UNIQUE (tenant_id, order_id), 
	CONSTRAINT uq_invoices_tenant_id_id UNIQUE (tenant_id, id), 
	CONSTRAINT fk_invoices_tenant_id_tenants FOREIGN KEY(tenant_id) REFERENCES tenants (id)
)

;


CREATE TABLE payments (
	id VARCHAR(36) NOT NULL, 
	created_at TIMESTAMP WITH TIME ZONE NOT NULL, 
	tenant_id VARCHAR(36) NOT NULL, 
	order_id VARCHAR(36), 
	provider_ref VARCHAR(120), 
	amount_minor INTEGER, 
	currency VARCHAR(120), 
	status VARCHAR(120), 
	CONSTRAINT pk_payments PRIMARY KEY (id), 
	CONSTRAINT fk_payments_tenant_id_order_id_orders FOREIGN KEY(tenant_id, order_id) REFERENCES orders (tenant_id, id), 
	CONSTRAINT uq_payments_tenant_id_order_id UNIQUE (tenant_id, order_id), 
	CONSTRAINT uq_payments_tenant_id_id UNIQUE (tenant_id, id), 
	CONSTRAINT fk_payments_tenant_id_tenants FOREIGN KEY(tenant_id) REFERENCES tenants (id), 
	CONSTRAINT uq_payments_provider_ref UNIQUE (provider_ref)
)

;


CREATE TABLE point_lots (
	id VARCHAR(36) NOT NULL, 
	created_at TIMESTAMP WITH TIME ZONE NOT NULL, 
	tenant_id VARCHAR(36) NOT NULL, 
	order_id VARCHAR(36), 
	source VARCHAR(120), 
	purpose VARCHAR(120), 
	quantity INTEGER, 
	expires_at TIMESTAMP WITH TIME ZONE, 
	paid_amount_minor INTEGER, 
	CONSTRAINT pk_point_lots PRIMARY KEY (id), 
	CONSTRAINT fk_point_lots_tenant_id_order_id_orders FOREIGN KEY(tenant_id, order_id) REFERENCES orders (tenant_id, id), 
	CONSTRAINT ck_point_lots_positive_lot CHECK (quantity > 0), 
	CONSTRAINT uq_point_lots_tenant_id_id UNIQUE (tenant_id, id), 
	CONSTRAINT fk_point_lots_tenant_id_tenants FOREIGN KEY(tenant_id) REFERENCES tenants (id)
)

;


CREATE TABLE questionnaire_answers (
	id VARCHAR(36) NOT NULL, 
	created_at TIMESTAMP WITH TIME ZONE NOT NULL, 
	tenant_id VARCHAR(36) NOT NULL, 
	questionnaire_id VARCHAR(36), 
	question TEXT, 
	answer TEXT, 
	evidence_reference TEXT, 
	review_status VARCHAR(120), 
	CONSTRAINT pk_questionnaire_answers PRIMARY KEY (id), 
	CONSTRAINT fk_questionnaire_answers_tenant_id_questionnaire_id_que_f3e3 FOREIGN KEY(tenant_id, questionnaire_id) REFERENCES questionnaires (tenant_id, id), 
	CONSTRAINT uq_questionnaire_answers_tenant_id_id UNIQUE (tenant_id, id), 
	CONSTRAINT fk_questionnaire_answers_tenant_id_tenants FOREIGN KEY(tenant_id) REFERENCES tenants (id)
)

;


CREATE TABLE recipients (
	id VARCHAR(36) NOT NULL, 
	created_at TIMESTAMP WITH TIME ZONE NOT NULL, 
	tenant_id VARCHAR(36) NOT NULL, 
	group_id VARCHAR(36), 
	email VARCHAR(254), 
	name VARCHAR(120), 
	department VARCHAR(120), 
	learner_id VARCHAR(36), 
	CONSTRAINT pk_recipients PRIMARY KEY (id), 
	CONSTRAINT fk_recipients_tenant_id_group_id_recipient_groups FOREIGN KEY(tenant_id, group_id) REFERENCES recipient_groups (tenant_id, id), 
	CONSTRAINT uq_recipients_tenant_id_group_id_email UNIQUE (tenant_id, group_id, email), 
	CONSTRAINT uq_recipients_tenant_id_id UNIQUE (tenant_id, id), 
	CONSTRAINT fk_recipients_tenant_id_tenants FOREIGN KEY(tenant_id) REFERENCES tenants (id)
)

;


CREATE TABLE refunds (
	id VARCHAR(36) NOT NULL, 
	created_at TIMESTAMP WITH TIME ZONE NOT NULL, 
	tenant_id VARCHAR(36) NOT NULL, 
	order_id VARCHAR(36), 
	amount_minor INTEGER, 
	points INTEGER, 
	status VARCHAR(120), 
	reason TEXT, 
	actor_id VARCHAR(36), 
	CONSTRAINT pk_refunds PRIMARY KEY (id), 
	CONSTRAINT fk_refunds_tenant_id_order_id_orders FOREIGN KEY(tenant_id, order_id) REFERENCES orders (tenant_id, id), 
	CONSTRAINT uq_refunds_tenant_id_id UNIQUE (tenant_id, id), 
	CONSTRAINT fk_refunds_tenant_id_tenants FOREIGN KEY(tenant_id) REFERENCES tenants (id)
)

;


CREATE TABLE attempts (
	id VARCHAR(36) NOT NULL, 
	created_at TIMESTAMP WITH TIME ZONE NOT NULL, 
	tenant_id VARCHAR(36) NOT NULL, 
	enrollment_id VARCHAR(36), 
	score INTEGER, 
	passed BOOLEAN, 
	question_version INTEGER, 
	answers JSON, 
	CONSTRAINT pk_attempts PRIMARY KEY (id), 
	CONSTRAINT fk_attempts_tenant_id_enrollment_id_enrollments FOREIGN KEY(tenant_id, enrollment_id) REFERENCES enrollments (tenant_id, id), 
	CONSTRAINT uq_attempts_tenant_id_id UNIQUE (tenant_id, id), 
	CONSTRAINT fk_attempts_tenant_id_tenants FOREIGN KEY(tenant_id) REFERENCES tenants (id)
)

;


CREATE TABLE certificates (
	id VARCHAR(36) NOT NULL, 
	created_at TIMESTAMP WITH TIME ZONE NOT NULL, 
	tenant_id VARCHAR(36) NOT NULL, 
	enrollment_id VARCHAR(36), 
	verification_hash VARCHAR(64), 
	course_title VARCHAR(120), 
	learner_name VARCHAR(120), 
	issued_at TIMESTAMP WITH TIME ZONE, 
	CONSTRAINT pk_certificates PRIMARY KEY (id), 
	CONSTRAINT fk_certificates_tenant_id_enrollment_id_enrollments FOREIGN KEY(tenant_id, enrollment_id) REFERENCES enrollments (tenant_id, id), 
	CONSTRAINT uq_certificates_tenant_id_enrollment_id UNIQUE (tenant_id, enrollment_id), 
	CONSTRAINT uq_certificates_tenant_id_id UNIQUE (tenant_id, id), 
	CONSTRAINT fk_certificates_tenant_id_tenants FOREIGN KEY(tenant_id) REFERENCES tenants (id)
)

;


CREATE TABLE message_plans (
	id VARCHAR(36) NOT NULL, 
	created_at TIMESTAMP WITH TIME ZONE NOT NULL, 
	tenant_id VARCHAR(36) NOT NULL, 
	campaign_id VARCHAR(36), 
	recipient_id VARCHAR(36), 
	reservation_id VARCHAR(36), 
	status VARCHAR(120), 
	provider_ref VARCHAR(120), 
	accepted_at TIMESTAMP WITH TIME ZONE, 
	tracking_hash VARCHAR(64), 
	CONSTRAINT pk_message_plans PRIMARY KEY (id), 
	CONSTRAINT fk_message_plans_tenant_id_campaign_id_campaigns FOREIGN KEY(tenant_id, campaign_id) REFERENCES campaigns (tenant_id, id), 
	CONSTRAINT fk_message_plans_tenant_id_recipient_id_recipients FOREIGN KEY(tenant_id, recipient_id) REFERENCES recipients (tenant_id, id), 
	CONSTRAINT fk_message_plans_tenant_id_reservation_id_reservations FOREIGN KEY(tenant_id, reservation_id) REFERENCES reservations (tenant_id, id), 
	CONSTRAINT uq_message_plans_tenant_id_campaign_id_recipient_id UNIQUE (tenant_id, campaign_id, recipient_id), 
	CONSTRAINT uq_message_plans_tenant_id_id UNIQUE (tenant_id, id), 
	CONSTRAINT fk_message_plans_tenant_id_tenants FOREIGN KEY(tenant_id) REFERENCES tenants (id)
)

;


CREATE TABLE progress_events (
	id VARCHAR(36) NOT NULL, 
	created_at TIMESTAMP WITH TIME ZONE NOT NULL, 
	tenant_id VARCHAR(36) NOT NULL, 
	enrollment_id VARCHAR(36), 
	lesson_id VARCHAR(36), 
	seconds INTEGER, 
	last_at TIMESTAMP WITH TIME ZONE, 
	CONSTRAINT pk_progress_events PRIMARY KEY (id), 
	CONSTRAINT fk_progress_events_tenant_id_enrollment_id_enrollments FOREIGN KEY(tenant_id, enrollment_id) REFERENCES enrollments (tenant_id, id), 
	CONSTRAINT uq_progress_events_tenant_id_enrollment_id_lesson_id UNIQUE (tenant_id, enrollment_id, lesson_id), 
	CONSTRAINT uq_progress_events_tenant_id_id UNIQUE (tenant_id, id), 
	CONSTRAINT fk_progress_events_tenant_id_tenants FOREIGN KEY(tenant_id) REFERENCES tenants (id), 
	CONSTRAINT fk_progress_events_lesson_id_lessons FOREIGN KEY(lesson_id) REFERENCES lessons (id)
)

;


CREATE TABLE projects (
	id VARCHAR(36) NOT NULL, 
	created_at TIMESTAMP WITH TIME ZONE NOT NULL, 
	tenant_id VARCHAR(36) NOT NULL, 
	name VARCHAR(120), 
	year INTEGER, 
	status VARCHAR(120), 
	contract_id VARCHAR(36), 
	company_name VARCHAR(120), 
	timezone VARCHAR(120), 
	CONSTRAINT pk_projects PRIMARY KEY (id), 
	CONSTRAINT fk_projects_tenant_id_contract_id_contracts FOREIGN KEY(tenant_id, contract_id) REFERENCES contracts (tenant_id, id), 
	CONSTRAINT uq_projects_tenant_id_id UNIQUE (tenant_id, id), 
	CONSTRAINT fk_projects_tenant_id_tenants FOREIGN KEY(tenant_id) REFERENCES tenants (id)
)

;


CREATE TABLE reservation_lots (
	id VARCHAR(36) NOT NULL, 
	created_at TIMESTAMP WITH TIME ZONE NOT NULL, 
	tenant_id VARCHAR(36) NOT NULL, 
	reservation_id VARCHAR(36), 
	lot_id VARCHAR(36), 
	quantity INTEGER, 
	CONSTRAINT pk_reservation_lots PRIMARY KEY (id), 
	CONSTRAINT fk_reservation_lots_tenant_id_reservation_id_reservations FOREIGN KEY(tenant_id, reservation_id) REFERENCES reservations (tenant_id, id), 
	CONSTRAINT fk_reservation_lots_tenant_id_lot_id_point_lots FOREIGN KEY(tenant_id, lot_id) REFERENCES point_lots (tenant_id, id), 
	CONSTRAINT uq_reservation_lots_tenant_id_reservation_id_lot_id UNIQUE (tenant_id, reservation_id, lot_id), 
	CONSTRAINT uq_reservation_lots_tenant_id_id UNIQUE (tenant_id, id), 
	CONSTRAINT fk_reservation_lots_tenant_id_tenants FOREIGN KEY(tenant_id) REFERENCES tenants (id)
)

;


CREATE TABLE wallet_transactions (
	id VARCHAR(36) NOT NULL, 
	created_at TIMESTAMP WITH TIME ZONE NOT NULL, 
	tenant_id VARCHAR(36) NOT NULL, 
	lot_id VARCHAR(36), 
	reservation_id VARCHAR(36), 
	kind VARCHAR(120), 
	business_key VARCHAR(240), 
	available_delta INTEGER, 
	reserved_delta INTEGER, 
	consumed_delta INTEGER, 
	expired_delta INTEGER, 
	refunded_delta INTEGER, 
	reason TEXT, 
	CONSTRAINT pk_wallet_transactions PRIMARY KEY (id), 
	CONSTRAINT fk_wallet_transactions_tenant_id_lot_id_point_lots FOREIGN KEY(tenant_id, lot_id) REFERENCES point_lots (tenant_id, id), 
	CONSTRAINT fk_wallet_transactions_tenant_id_reservation_id_reservations FOREIGN KEY(tenant_id, reservation_id) REFERENCES reservations (tenant_id, id), 
	CONSTRAINT uq_wallet_transactions_tenant_id_business_key_lot_id UNIQUE (tenant_id, business_key, lot_id), 
	CONSTRAINT uq_wallet_transactions_tenant_id_id UNIQUE (tenant_id, id), 
	CONSTRAINT fk_wallet_transactions_tenant_id_tenants FOREIGN KEY(tenant_id) REFERENCES tenants (id)
)

;


CREATE TABLE comments (
	id VARCHAR(36) NOT NULL, 
	created_at TIMESTAMP WITH TIME ZONE NOT NULL, 
	tenant_id VARCHAR(36) NOT NULL, 
	project_id VARCHAR(36), 
	finding_id VARCHAR(36), 
	text TEXT, 
	visibility VARCHAR(120), 
	actor_id VARCHAR(36), 
	CONSTRAINT pk_comments PRIMARY KEY (id), 
	CONSTRAINT fk_comments_tenant_id_project_id_projects FOREIGN KEY(tenant_id, project_id) REFERENCES projects (tenant_id, id), 
	CONSTRAINT uq_comments_tenant_id_id UNIQUE (tenant_id, id), 
	CONSTRAINT fk_comments_tenant_id_tenants FOREIGN KEY(tenant_id) REFERENCES tenants (id)
)

;


CREATE TABLE entitlements (
	id VARCHAR(36) NOT NULL, 
	created_at TIMESTAMP WITH TIME ZONE NOT NULL, 
	tenant_id VARCHAR(36) NOT NULL, 
	project_id VARCHAR(36), 
	service_code VARCHAR(120), 
	unit VARCHAR(120), 
	quantity INTEGER, 
	CONSTRAINT pk_entitlements PRIMARY KEY (id), 
	CONSTRAINT fk_entitlements_tenant_id_project_id_projects FOREIGN KEY(tenant_id, project_id) REFERENCES projects (tenant_id, id), 
	CONSTRAINT uq_entitlements_tenant_id_id UNIQUE (tenant_id, id), 
	CONSTRAINT fk_entitlements_tenant_id_tenants FOREIGN KEY(tenant_id) REFERENCES tenants (id)
)

;


CREATE TABLE raw_events (
	id VARCHAR(36) NOT NULL, 
	created_at TIMESTAMP WITH TIME ZONE NOT NULL, 
	tenant_id VARCHAR(36) NOT NULL, 
	campaign_id VARCHAR(36), 
	message_id VARCHAR(36), 
	event_type VARCHAR(120), 
	provider_event_id VARCHAR(240), 
	occurred_at TIMESTAMP WITH TIME ZONE, 
	classification VARCHAR(120), 
	classification_version VARCHAR(120), 
	CONSTRAINT pk_raw_events PRIMARY KEY (id), 
	CONSTRAINT fk_raw_events_tenant_id_campaign_id_campaigns FOREIGN KEY(tenant_id, campaign_id) REFERENCES campaigns (tenant_id, id), 
	CONSTRAINT fk_raw_events_tenant_id_message_id_message_plans FOREIGN KEY(tenant_id, message_id) REFERENCES message_plans (tenant_id, id), 
	CONSTRAINT uq_raw_events_tenant_id_provider_event_id UNIQUE (tenant_id, provider_event_id), 
	CONSTRAINT uq_raw_events_tenant_id_id UNIQUE (tenant_id, id), 
	CONSTRAINT fk_raw_events_tenant_id_tenants FOREIGN KEY(tenant_id) REFERENCES tenants (id)
)

;


CREATE TABLE time_entries (
	id VARCHAR(36) NOT NULL, 
	created_at TIMESTAMP WITH TIME ZONE NOT NULL, 
	tenant_id VARCHAR(36) NOT NULL, 
	project_id VARCHAR(36), 
	category VARCHAR(120), 
	minutes INTEGER, 
	cost_minor INTEGER, 
	actor_id VARCHAR(36), 
	note TEXT, 
	CONSTRAINT pk_time_entries PRIMARY KEY (id), 
	CONSTRAINT fk_time_entries_tenant_id_project_id_projects FOREIGN KEY(tenant_id, project_id) REFERENCES projects (tenant_id, id), 
	CONSTRAINT ck_time_entries_nonnegative_time_cost CHECK (minutes >= 0 AND cost_minor >= 0), 
	CONSTRAINT uq_time_entries_tenant_id_id UNIQUE (tenant_id, id), 
	CONSTRAINT fk_time_entries_tenant_id_tenants FOREIGN KEY(tenant_id) REFERENCES tenants (id)
)

;


CREATE TABLE work_packages (
	id VARCHAR(36) NOT NULL, 
	created_at TIMESTAMP WITH TIME ZONE NOT NULL, 
	tenant_id VARCHAR(36) NOT NULL, 
	project_id VARCHAR(36) NOT NULL, 
	service_code VARCHAR(120), 
	status VARCHAR(120), 
	allowance INTEGER, 
	CONSTRAINT pk_work_packages PRIMARY KEY (id), 
	CONSTRAINT fk_work_packages_tenant_id_project_id_projects FOREIGN KEY(tenant_id, project_id) REFERENCES projects (tenant_id, id), 
	CONSTRAINT uq_work_packages_tenant_id_project_id_service_code UNIQUE (tenant_id, project_id, service_code), 
	CONSTRAINT uq_work_packages_tenant_id_id UNIQUE (tenant_id, id), 
	CONSTRAINT fk_work_packages_tenant_id_tenants FOREIGN KEY(tenant_id) REFERENCES tenants (id)
)

;


CREATE TABLE batches (
	id VARCHAR(36) NOT NULL, 
	created_at TIMESTAMP WITH TIME ZONE NOT NULL, 
	tenant_id VARCHAR(36) NOT NULL, 
	project_id VARCHAR(36) NOT NULL, 
	package_id VARCHAR(36), 
	service_code VARCHAR(120), 
	title VARCHAR(120), 
	status VARCHAR(120), 
	scope_version INTEGER, 
	version INTEGER, 
	engineer_id VARCHAR(36), 
	reviewer_id VARCHAR(36), 
	reviewed_by VARCHAR(36), 
	reviewed_at TIMESTAMP WITH TIME ZONE, 
	start_at TIMESTAMP WITH TIME ZONE, 
	end_at TIMESTAMP WITH TIME ZONE, 
	original_start_at TIMESTAMP WITH TIME ZONE, 
	equipment VARCHAR(120), 
	timezone VARCHAR(120), 
	retest_of VARCHAR(36), 
	retest_deadline TIMESTAMP WITH TIME ZONE, 
	review_note TEXT, 
	CONSTRAINT pk_batches PRIMARY KEY (id), 
	CONSTRAINT fk_batches_tenant_id_project_id_projects FOREIGN KEY(tenant_id, project_id) REFERENCES projects (tenant_id, id), 
	CONSTRAINT fk_batches_tenant_id_package_id_work_packages FOREIGN KEY(tenant_id, package_id) REFERENCES work_packages (tenant_id, id), 
	CONSTRAINT fk_batches_tenant_id_retest_of_batches FOREIGN KEY(tenant_id, retest_of) REFERENCES batches (tenant_id, id), 
	CONSTRAINT uq_batches_tenant_id_id UNIQUE (tenant_id, id), 
	CONSTRAINT fk_batches_tenant_id_tenants FOREIGN KEY(tenant_id) REFERENCES tenants (id)
)

;


CREATE TABLE acceptances (
	id VARCHAR(36) NOT NULL, 
	created_at TIMESTAMP WITH TIME ZONE NOT NULL, 
	tenant_id VARCHAR(36) NOT NULL, 
	project_id VARCHAR(36), 
	batch_id VARCHAR(36), 
	decision VARCHAR(120), 
	comment TEXT, 
	actor_id VARCHAR(36), 
	CONSTRAINT pk_acceptances PRIMARY KEY (id), 
	CONSTRAINT fk_acceptances_tenant_id_project_id_projects FOREIGN KEY(tenant_id, project_id) REFERENCES projects (tenant_id, id), 
	CONSTRAINT fk_acceptances_tenant_id_batch_id_batches FOREIGN KEY(tenant_id, batch_id) REFERENCES batches (tenant_id, id), 
	CONSTRAINT uq_acceptances_tenant_id_id UNIQUE (tenant_id, id), 
	CONSTRAINT fk_acceptances_tenant_id_tenants FOREIGN KEY(tenant_id) REFERENCES tenants (id)
)

;


CREATE TABLE changes (
	id VARCHAR(36) NOT NULL, 
	created_at TIMESTAMP WITH TIME ZONE NOT NULL, 
	tenant_id VARCHAR(36) NOT NULL, 
	project_id VARCHAR(36), 
	batch_id VARCHAR(36), 
	kind VARCHAR(120), 
	reason TEXT, 
	proposed_assets JSON, 
	proposed_start TIMESTAMP WITH TIME ZONE, 
	old_amount_minor INTEGER, 
	new_amount_minor INTEGER, 
	status VARCHAR(120), 
	version INTEGER, 
	requested_by VARCHAR(36), 
	confirmed_by VARCHAR(36), 
	CONSTRAINT pk_changes PRIMARY KEY (id), 
	CONSTRAINT fk_changes_tenant_id_project_id_projects FOREIGN KEY(tenant_id, project_id) REFERENCES projects (tenant_id, id), 
	CONSTRAINT fk_changes_tenant_id_batch_id_batches FOREIGN KEY(tenant_id, batch_id) REFERENCES batches (tenant_id, id), 
	CONSTRAINT uq_changes_tenant_id_id UNIQUE (tenant_id, id), 
	CONSTRAINT fk_changes_tenant_id_tenants FOREIGN KEY(tenant_id) REFERENCES tenants (id)
)

;


CREATE TABLE entitlement_ledger (
	id VARCHAR(36) NOT NULL, 
	created_at TIMESTAMP WITH TIME ZONE NOT NULL, 
	tenant_id VARCHAR(36) NOT NULL, 
	entitlement_id VARCHAR(36), 
	batch_id VARCHAR(36), 
	kind VARCHAR(120), 
	quantity INTEGER, 
	business_key VARCHAR(120), 
	reason TEXT, 
	CONSTRAINT pk_entitlement_ledger PRIMARY KEY (id), 
	CONSTRAINT fk_entitlement_ledger_tenant_id_entitlement_id_entitlements FOREIGN KEY(tenant_id, entitlement_id) REFERENCES entitlements (tenant_id, id), 
	CONSTRAINT fk_entitlement_ledger_tenant_id_batch_id_batches FOREIGN KEY(tenant_id, batch_id) REFERENCES batches (tenant_id, id), 
	CONSTRAINT uq_entitlement_ledger_tenant_id_id UNIQUE (tenant_id, id), 
	CONSTRAINT fk_entitlement_ledger_tenant_id_tenants FOREIGN KEY(tenant_id) REFERENCES tenants (id), 
	CONSTRAINT uq_entitlement_ledger_business_key UNIQUE (business_key)
)

;


CREATE TABLE imports (
	id VARCHAR(36) NOT NULL, 
	created_at TIMESTAMP WITH TIME ZONE NOT NULL, 
	tenant_id VARCHAR(36) NOT NULL, 
	batch_id VARCHAR(36), 
	filename VARCHAR(120), 
	source_hash VARCHAR(64), 
	object_key VARCHAR(500), 
	size INTEGER, 
	parser_version VARCHAR(120), 
	parsed JSON, 
	status VARCHAR(120), 
	actor_id VARCHAR(36), 
	CONSTRAINT pk_imports PRIMARY KEY (id), 
	CONSTRAINT fk_imports_tenant_id_batch_id_batches FOREIGN KEY(tenant_id, batch_id) REFERENCES batches (tenant_id, id), 
	CONSTRAINT uq_imports_tenant_id_batch_id_source_hash UNIQUE (tenant_id, batch_id, source_hash), 
	CONSTRAINT uq_imports_tenant_id_id UNIQUE (tenant_id, id), 
	CONSTRAINT fk_imports_tenant_id_tenants FOREIGN KEY(tenant_id) REFERENCES tenants (id)
)

;


CREATE TABLE retest_requests (
	id VARCHAR(36) NOT NULL, 
	created_at TIMESTAMP WITH TIME ZONE NOT NULL, 
	tenant_id VARCHAR(36) NOT NULL, 
	batch_id VARCHAR(36), 
	finding_ids JSON, 
	reason TEXT, 
	status VARCHAR(120), 
	actor_id VARCHAR(36), 
	CONSTRAINT pk_retest_requests PRIMARY KEY (id), 
	CONSTRAINT fk_retest_requests_tenant_id_batch_id_batches FOREIGN KEY(tenant_id, batch_id) REFERENCES batches (tenant_id, id), 
	CONSTRAINT uq_retest_requests_tenant_id_id UNIQUE (tenant_id, id), 
	CONSTRAINT fk_retest_requests_tenant_id_tenants FOREIGN KEY(tenant_id) REFERENCES tenants (id)
)

;


CREATE TABLE schedule_history (
	id VARCHAR(36) NOT NULL, 
	created_at TIMESTAMP WITH TIME ZONE NOT NULL, 
	tenant_id VARCHAR(36) NOT NULL, 
	batch_id VARCHAR(36), 
	old_start TIMESTAMP WITH TIME ZONE, 
	new_start TIMESTAMP WITH TIME ZONE, 
	new_end TIMESTAMP WITH TIME ZONE, 
	reason TEXT, 
	actor_id VARCHAR(36), 
	CONSTRAINT pk_schedule_history PRIMARY KEY (id), 
	CONSTRAINT fk_schedule_history_tenant_id_batch_id_batches FOREIGN KEY(tenant_id, batch_id) REFERENCES batches (tenant_id, id), 
	CONSTRAINT uq_schedule_history_tenant_id_id UNIQUE (tenant_id, id), 
	CONSTRAINT fk_schedule_history_tenant_id_tenants FOREIGN KEY(tenant_id) REFERENCES tenants (id)
)

;


CREATE TABLE scope_assets (
	id VARCHAR(36) NOT NULL, 
	created_at TIMESTAMP WITH TIME ZONE NOT NULL, 
	tenant_id VARCHAR(36) NOT NULL, 
	batch_id VARCHAR(36), 
	asset VARCHAR(500), 
	version INTEGER, 
	CONSTRAINT pk_scope_assets PRIMARY KEY (id), 
	CONSTRAINT fk_scope_assets_tenant_id_batch_id_batches FOREIGN KEY(tenant_id, batch_id) REFERENCES batches (tenant_id, id), 
	CONSTRAINT uq_scope_assets_tenant_id_batch_id_asset_version UNIQUE (tenant_id, batch_id, asset, version), 
	CONSTRAINT uq_scope_assets_tenant_id_id UNIQUE (tenant_id, id), 
	CONSTRAINT fk_scope_assets_tenant_id_tenants FOREIGN KEY(tenant_id) REFERENCES tenants (id)
)

;


CREATE TABLE snapshots (
	id VARCHAR(36) NOT NULL, 
	created_at TIMESTAMP WITH TIME ZONE NOT NULL, 
	tenant_id VARCHAR(36) NOT NULL, 
	batch_id VARCHAR(36), 
	version INTEGER, 
	sha256 VARCHAR(64), 
	dataset JSON, 
	reviewer_id VARCHAR(36), 
	CONSTRAINT pk_snapshots PRIMARY KEY (id), 
	CONSTRAINT fk_snapshots_tenant_id_batch_id_batches FOREIGN KEY(tenant_id, batch_id) REFERENCES batches (tenant_id, id), 
	CONSTRAINT uq_snapshots_tenant_id_batch_id_version UNIQUE (tenant_id, batch_id, version), 
	CONSTRAINT uq_snapshots_tenant_id_id UNIQUE (tenant_id, id), 
	CONSTRAINT fk_snapshots_tenant_id_tenants FOREIGN KEY(tenant_id) REFERENCES tenants (id)
)

;


CREATE TABLE tasks (
	id VARCHAR(36) NOT NULL, 
	created_at TIMESTAMP WITH TIME ZONE NOT NULL, 
	tenant_id VARCHAR(36) NOT NULL, 
	project_id VARCHAR(36), 
	batch_id VARCHAR(36), 
	title VARCHAR(120), 
	status VARCHAR(120), 
	due_at TIMESTAMP WITH TIME ZONE, 
	assigned_to VARCHAR(36), 
	visibility VARCHAR(120), 
	CONSTRAINT pk_tasks PRIMARY KEY (id), 
	CONSTRAINT fk_tasks_tenant_id_project_id_projects FOREIGN KEY(tenant_id, project_id) REFERENCES projects (tenant_id, id), 
	CONSTRAINT fk_tasks_tenant_id_batch_id_batches FOREIGN KEY(tenant_id, batch_id) REFERENCES batches (tenant_id, id), 
	CONSTRAINT uq_tasks_tenant_id_id UNIQUE (tenant_id, id), 
	CONSTRAINT fk_tasks_tenant_id_tenants FOREIGN KEY(tenant_id) REFERENCES tenants (id)
)

;


CREATE TABLE coverage (
	id VARCHAR(36) NOT NULL, 
	created_at TIMESTAMP WITH TIME ZONE NOT NULL, 
	tenant_id VARCHAR(36) NOT NULL, 
	batch_id VARCHAR(36), 
	asset VARCHAR(500), 
	status VARCHAR(120), 
	source_import_id VARCHAR(36), 
	CONSTRAINT pk_coverage PRIMARY KEY (id), 
	CONSTRAINT fk_coverage_tenant_id_batch_id_batches FOREIGN KEY(tenant_id, batch_id) REFERENCES batches (tenant_id, id), 
	CONSTRAINT fk_coverage_tenant_id_source_import_id_imports FOREIGN KEY(tenant_id, source_import_id) REFERENCES imports (tenant_id, id), 
	CONSTRAINT uq_coverage_tenant_id_batch_id_asset UNIQUE (tenant_id, batch_id, asset), 
	CONSTRAINT uq_coverage_tenant_id_id UNIQUE (tenant_id, id), 
	CONSTRAINT fk_coverage_tenant_id_tenants FOREIGN KEY(tenant_id) REFERENCES tenants (id)
)

;


CREATE TABLE findings (
	id VARCHAR(36) NOT NULL, 
	created_at TIMESTAMP WITH TIME ZONE NOT NULL, 
	tenant_id VARCHAR(36) NOT NULL, 
	batch_id VARCHAR(36), 
	source_import_id VARCHAR(36), 
	source_id VARCHAR(120), 
	fingerprint VARCHAR(64), 
	asset VARCHAR(500), 
	title TEXT, 
	severity VARCHAR(120), 
	description TEXT, 
	solution TEXT, 
	port VARCHAR(30), 
	location TEXT, 
	evidence TEXT, 
	check_status VARCHAR(120), 
	status VARCHAR(120), 
	details JSON, 
	CONSTRAINT pk_findings PRIMARY KEY (id), 
	CONSTRAINT fk_findings_tenant_id_batch_id_batches FOREIGN KEY(tenant_id, batch_id) REFERENCES batches (tenant_id, id), 
	CONSTRAINT fk_findings_tenant_id_source_import_id_imports FOREIGN KEY(tenant_id, source_import_id) REFERENCES imports (tenant_id, id), 
	CONSTRAINT uq_findings_tenant_id_batch_id_fingerprint UNIQUE (tenant_id, batch_id, fingerprint), 
	CONSTRAINT uq_findings_tenant_id_id UNIQUE (tenant_id, id), 
	CONSTRAINT fk_findings_tenant_id_tenants FOREIGN KEY(tenant_id) REFERENCES tenants (id)
)

;


CREATE TABLE report_jobs (
	id VARCHAR(36) NOT NULL, 
	created_at TIMESTAMP WITH TIME ZONE NOT NULL, 
	tenant_id VARCHAR(36) NOT NULL, 
	batch_id VARCHAR(36), 
	snapshot_id VARCHAR(36), 
	status VARCHAR(120), 
	manifest JSON, 
	output_key VARCHAR(500), 
	error TEXT, 
	CONSTRAINT pk_report_jobs PRIMARY KEY (id), 
	CONSTRAINT fk_report_jobs_tenant_id_batch_id_batches FOREIGN KEY(tenant_id, batch_id) REFERENCES batches (tenant_id, id), 
	CONSTRAINT fk_report_jobs_tenant_id_snapshot_id_snapshots FOREIGN KEY(tenant_id, snapshot_id) REFERENCES snapshots (tenant_id, id), 
	CONSTRAINT uq_report_jobs_tenant_id_snapshot_id UNIQUE (tenant_id, snapshot_id), 
	CONSTRAINT uq_report_jobs_tenant_id_id UNIQUE (tenant_id, id), 
	CONSTRAINT fk_report_jobs_tenant_id_tenants FOREIGN KEY(tenant_id) REFERENCES tenants (id)
)

;


CREATE TABLE dispositions (
	id VARCHAR(36) NOT NULL, 
	created_at TIMESTAMP WITH TIME ZONE NOT NULL, 
	tenant_id VARCHAR(36) NOT NULL, 
	finding_id VARCHAR(36), 
	decision VARCHAR(120), 
	reason TEXT, 
	reviewer_id VARCHAR(36), 
	expires_at TIMESTAMP WITH TIME ZONE, 
	CONSTRAINT pk_dispositions PRIMARY KEY (id), 
	CONSTRAINT fk_dispositions_tenant_id_finding_id_findings FOREIGN KEY(tenant_id, finding_id) REFERENCES findings (tenant_id, id), 
	CONSTRAINT uq_dispositions_tenant_id_id UNIQUE (tenant_id, id), 
	CONSTRAINT fk_dispositions_tenant_id_tenants FOREIGN KEY(tenant_id) REFERENCES tenants (id)
)

;


CREATE TABLE publications (
	id VARCHAR(36) NOT NULL, 
	created_at TIMESTAMP WITH TIME ZONE NOT NULL, 
	tenant_id VARCHAR(36) NOT NULL, 
	batch_id VARCHAR(36), 
	report_job_id VARCHAR(36), 
	snapshot_id VARCHAR(36), 
	version INTEGER, 
	published_by VARCHAR(36), 
	note TEXT, 
	supersedes_id VARCHAR(36), 
	CONSTRAINT pk_publications PRIMARY KEY (id), 
	CONSTRAINT fk_publications_tenant_id_batch_id_batches FOREIGN KEY(tenant_id, batch_id) REFERENCES batches (tenant_id, id), 
	CONSTRAINT fk_publications_tenant_id_report_job_id_report_jobs FOREIGN KEY(tenant_id, report_job_id) REFERENCES report_jobs (tenant_id, id), 
	CONSTRAINT fk_publications_tenant_id_snapshot_id_snapshots FOREIGN KEY(tenant_id, snapshot_id) REFERENCES snapshots (tenant_id, id), 
	CONSTRAINT fk_publications_tenant_id_supersedes_id_publications FOREIGN KEY(tenant_id, supersedes_id) REFERENCES publications (tenant_id, id), 
	CONSTRAINT uq_publications_tenant_id_report_job_id UNIQUE (tenant_id, report_job_id), 
	CONSTRAINT uq_publications_tenant_id_id UNIQUE (tenant_id, id), 
	CONSTRAINT fk_publications_tenant_id_tenants FOREIGN KEY(tenant_id) REFERENCES tenants (id)
)

;
CREATE INDEX ix_grants_tenant_id ON grants (tenant_id);
CREATE INDEX ix_invitations_tenant_id ON invitations (tenant_id);
CREATE INDEX ix_quotes_tenant_id ON quotes (tenant_id);
CREATE INDEX ix_contracts_tenant_id ON contracts (tenant_id);
CREATE INDEX ix_projects_tenant_id ON projects (tenant_id);
CREATE INDEX ix_work_packages_tenant_id ON work_packages (tenant_id);
CREATE INDEX ix_batches_tenant_id ON batches (tenant_id);
CREATE INDEX ix_scope_assets_tenant_id ON scope_assets (tenant_id);
CREATE INDEX ix_schedule_history_tenant_id ON schedule_history (tenant_id);
CREATE INDEX ix_tasks_tenant_id ON tasks (tenant_id);
CREATE INDEX ix_changes_tenant_id ON changes (tenant_id);
CREATE INDEX ix_comments_tenant_id ON comments (tenant_id);
CREATE INDEX ix_acceptances_tenant_id ON acceptances (tenant_id);
CREATE INDEX ix_time_entries_tenant_id ON time_entries (tenant_id);
CREATE INDEX ix_imports_tenant_id ON imports (tenant_id);
CREATE INDEX ix_coverage_tenant_id ON coverage (tenant_id);
CREATE INDEX ix_findings_tenant_id ON findings (tenant_id);
CREATE INDEX ix_dispositions_tenant_id ON dispositions (tenant_id);
CREATE INDEX ix_retest_requests_tenant_id ON retest_requests (tenant_id);
CREATE INDEX ix_snapshots_tenant_id ON snapshots (tenant_id);
CREATE INDEX ix_report_jobs_tenant_id ON report_jobs (tenant_id);
CREATE INDEX ix_publications_tenant_id ON publications (tenant_id);
CREATE INDEX ix_wallets_tenant_id ON wallets (tenant_id);
CREATE INDEX ix_orders_tenant_id ON orders (tenant_id);
CREATE INDEX ix_payments_tenant_id ON payments (tenant_id);
CREATE INDEX ix_point_lots_tenant_id ON point_lots (tenant_id);
CREATE INDEX ix_reservations_tenant_id ON reservations (tenant_id);
CREATE INDEX ix_reservation_lots_tenant_id ON reservation_lots (tenant_id);
CREATE INDEX ix_wallet_transactions_tenant_id ON wallet_transactions (tenant_id);
CREATE INDEX ix_refunds_tenant_id ON refunds (tenant_id);
CREATE INDEX ix_invoices_tenant_id ON invoices (tenant_id);
CREATE INDEX ix_entitlements_tenant_id ON entitlements (tenant_id);
CREATE INDEX ix_entitlement_ledger_tenant_id ON entitlement_ledger (tenant_id);
CREATE INDEX ix_recipient_groups_tenant_id ON recipient_groups (tenant_id);
CREATE INDEX ix_recipients_tenant_id ON recipients (tenant_id);
CREATE INDEX ix_campaigns_tenant_id ON campaigns (tenant_id);
CREATE INDEX ix_message_plans_tenant_id ON message_plans (tenant_id);
CREATE INDEX ix_raw_events_tenant_id ON raw_events (tenant_id);
CREATE INDEX ix_enrollments_tenant_id ON enrollments (tenant_id);
CREATE INDEX ix_progress_events_tenant_id ON progress_events (tenant_id);
CREATE INDEX ix_attempts_tenant_id ON attempts (tenant_id);
CREATE INDEX ix_certificates_tenant_id ON certificates (tenant_id);
CREATE INDEX ix_tickets_tenant_id ON tickets (tenant_id);
CREATE INDEX ix_notifications_tenant_id ON notifications (tenant_id);
CREATE INDEX ix_questionnaires_tenant_id ON questionnaires (tenant_id);
CREATE INDEX ix_questionnaire_answers_tenant_id ON questionnaire_answers (tenant_id);
CREATE INDEX ix_retention_policies_tenant_id ON retention_policies (tenant_id);
CREATE INDEX ix_deletion_requests_tenant_id ON deletion_requests (tenant_id);
CREATE INDEX ix_audit_events_tenant_id ON audit_events (tenant_id);
CREATE INDEX ix_idempotency_tenant_id ON idempotency (tenant_id);