# import .env
include .env
export

BOOTSTRAP_PROFILE ?= bootstrap
ECR_BUILDER_PROFILE ?= ecr-builder
APP_BUILDER_PROFILE ?= app-builder

AWS_REGION ?= ap-southeast-1
REPO_URL   ?= $(ACCOUNT_ID).dkr.ecr.$(AWS_REGION).amazonaws.com/$(ECR_REPO_NAME)
WORKSPACE  := $(shell pwd)
FUNCS      := silver_cold gold

.PHONY: terraform_init profile bootstrap ecr_up ecr_down notif_up notif_down login build push digests apply deploy

terraform_init:
	terraform -chdir=infra/app init
	terraform -chdir=infra/bootstrap init
	terraform -chdir=infra/ecr init
	terraform -chdir=infra/notifications init

profile: terraform_init
	@test -n "$(TF_VAR_ACCESS_KEY)" || (echo "TF_VAR_ACCESS_KEY is not set" && exit 1)
	@test -n "$(TF_VAR_SECRET_KEY)" || (echo "TF_VAR_SECRET_KEY is not set" && exit 1)

	@echo "Making bootstrap profile"
	@aws configure set aws_access_key_id "$(TF_VAR_ACCESS_KEY)" --profile "$(BOOTSTRAP_PROFILE)"
	@aws configure set aws_secret_access_key "$(TF_VAR_SECRET_KEY)" --profile "$(BOOTSTRAP_PROFILE)"
	@aws configure set region "$(AWS_REGION)" --profile "$(BOOTSTRAP_PROFILE)"
	@echo "AWS profile '$(BOOTSTRAP_PROFILE)' configured"

bootstrap: profile # create ecr
	@echo "Making required roles"

	@BOOTSTRAP_USER_ARN=$$(aws iam get-user \
		--profile "$(BOOTSTRAP_PROFILE)" \
		--query 'User.Arn' \
		--output text); \
	echo "Bootstrap user ARN: $$BOOTSTRAP_USER_ARN"; \
	AWS_PROFILE=$(BOOTSTRAP_PROFILE) \
	terraform -chdir=infra/bootstrap apply \
	-var="bootstrap_user_arn=$$BOOTSTRAP_USER_ARN" \
	-auto-approve

	@echo "Making ecr-builder profile"
	@aws configure set role_arn "$$(terraform -chdir=infra/bootstrap output -raw ecr_builder_role_arn)" --profile "$(ECR_BUILDER_PROFILE)"
	@aws configure set source_profile "$(BOOTSTRAP_PROFILE)" --profile "$(ECR_BUILDER_PROFILE)"
	@aws configure set region "$(AWS_REGION)" --profile "$(ECR_BUILDER_PROFILE)"
	@echo "AWS profile '$(ECR_BUILDER_PROFILE)' configured"

	@echo "Making app-builder profile"
	@aws configure set role_arn "$$(terraform -chdir=infra/bootstrap output -raw app_builder_role_arn)" --profile "$(APP_BUILDER_PROFILE)"
	@aws configure set source_profile "$(BOOTSTRAP_PROFILE)" --profile "$(APP_BUILDER_PROFILE)"
	@aws configure set region "$(AWS_REGION)" --profile "$(APP_BUILDER_PROFILE)"
	@echo "AWS profile '$(APP_BUILDER_PROFILE)' configured"

ecr_up:
	AWS_PROFILE=$(ECR_BUILDER_PROFILE) \
	terraform -chdir=infra/ecr apply \
	-var="ecr_repo_name=$(ECR_REPO_NAME)" \
	-auto-approve

ecr_down:
	AWS_PROFILE=$(ECR_BUILDER_PROFILE) \
	terraform -chdir=infra/ecr destroy --auto-approve

login:
	AWS_PROFILE=$(ECR_BUILDER_PROFILE) \
	aws ecr get-login-password --region $(AWS_REGION) \
		| docker login --username AWS --password-stdin $(REPO_URL)

build:
	@for pkg in $(FUNCS); do \
		echo "building $$pkg"; \
		docker build --platform linux/arm64 \
			--provenance=false \
			-t $(REPO_URL):$$pkg \
			-f packages/$$pkg/Dockerfile \
			$(WORKSPACE) || exit 1; \
	done

push: login build
	@for pkg in $(FUNCS); do \
		echo "pushing $$pkg"; \
		docker push $(REPO_URL):$$pkg || exit 1; \
	done

# digests target:
# - fetches each pushed image's digest from ECR
# - writes infra/digests.auto.tfvars.json for terraform to consume
digests: push
	@rm -f infra/app/digests.auto.tfvars.json.tmp
	@echo '{ "image_digests": {' > infra/app/digests.auto.tfvars.json.tmp
	@first=1; \
	for pkg in $(FUNCS); do \
		digest=$$(aws ecr describe-images --repository-name $(ECR_REPO_NAME) \
			--image-ids imageTag=$$pkg --region $(AWS_REGION) \
			--query 'imageDetails[0].imageDigest' --output text); \
		test -z "$$digest" && echo "Error: failed to get digest for $$pkg" && exit 1; \
		test $$first -eq 0 && echo ',' >> infra/app/digests.auto.tfvars.json.tmp; \
		printf '  "%s": "%s"' "$$pkg" "$$digest" >> infra/app/digests.auto.tfvars.json.tmp; \
		echo '' >> infra/app/digests.auto.tfvars.json.tmp; \
		first=0; \
	done
	@echo '}}' >> infra/app/digests.auto.tfvars.json.tmp
	@mv infra/app/digests.auto.tfvars.json.tmp infra/app/digests.auto.tfvars.json
	@cat infra/app/digests.auto.tfvars.json

apply: digests
	@echo 'terrform -chdir=infra/app apply -auto-approve'
	@terraform -chdir=infra/app apply \
	-var="datamall_account_key=$(DATAMALL_ACCOUNT_KEY)" \
	-var="ecr_repo_url=$(REPO_URL)" \
	-auto-approve

deploy: apply
	@echo "Deployed: $(FUNCS)"

notif_up:
	@SFN_ARN=$$(terraform -chdir=infra/app output -raw step_function_arn); \
	BRONZE_LAMBDA_ARNS=$$(terraform -chdir=infra/app output -json bronze_lambda_arns); \
	terraform -chdir=infra/notifications apply \
		-var="telegram_bot_token=$(TELEGRAM_BOT_TOKEN)" \
		-var="telegram_chat_id=$(TELEGRAM_CHAT_ID)" \
		-var="state_machine_arns=[\"$$SFN_ARN\"]" \
		-var="bronze_lambda_arns=$$BRONZE_LAMBDA_ARNS" \
		-auto-approve

notif_down:
	@terraform -chdir=infra/notifications destroy \
	-var="telegram_bot_token=$(TELEGRAM_BOT_TOKEN)" \
	-var="telegram_chat_id=$(TELEGRAM_CHAT_ID)" \
	-auto-approve

dbt_parse:
	@S3_BUCKET=$$(terraform -chdir=infra/app output -raw bucket_name) \
	uv run --package gold dbt parse --project-dir packages/gold --profiles-dir packages/gold

dbt_debug:
	@S3_BUCKET=$$(terraform -chdir=infra/app output -raw bucket_name) \
	uv run --package gold dbt debug --project-dir packages/gold --profiles-dir packages/gold

dbt_snapshot:
	@S3_BUCKET=$$(terraform -chdir=infra/app output -raw bucket_name) \
	uv run --package gold dbt snapshot --project-dir packages/gold --profiles-dir packages/gold

dbt_run:
	@S3_BUCKET=$$(terraform -chdir=infra/app output -raw bucket_name) \
	uv run --package gold dbt run --project-dir packages/gold --profiles-dir packages/gold

dbt_test:
	@S3_BUCKET=$$(terraform -chdir=infra/app output -raw bucket_name) \
	uv run --package gold dbt test --project-dir packages/gold --profiles-dir packages/gold


