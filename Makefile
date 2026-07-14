# import .env
include .env
export

AWS_REGION ?= ap-southeast-1 # set if not already set
REPO_URL   ?= $(ACCOUNT_ID).dkr.ecr.$(AWS_REGION).amazonaws.com/$(ECR_REPO_NAME)
WORKSPACE  := $(shell pwd)
FUNCS      := silver_cold # func1 func2

.PHONY: bootstrap_ecr login build push digests apply deploy

bootstrap_ecr: # create ecr
	cd infra && terraform apply -target=aws_ecr_repository.lambda_repo -auto-approve

login:
	AWS_ACCESS_KEY_ID=$(ECR_BUILDER_ACCESS_KEY) \
	AWS_SECRET_ACCESS_KEY=$(ECR_BUILDER_SECRET_KEY) \
	aws ecr get-login-password --region $(AWS_REGION) \
		| docker login --username AWS --password-stdin $(REPO_URL)

build:
	@for pkg in $(FUNCS); do \
		echo "building $$pkg"; \
		docker build --platform linux/arm64 \
			-t $(REPO_URL):$$pkg \
			-f packages/$$pkg/Dockerfile \
			$(WORKSPACE) || exit 1; \
	done

push: bootstrap_ecr login build
	@for pkg in $(FUNCS); do \
		echo "pushing $$pkg"; \
		docker push $(REPO_URL):$$pkg || exit 1; \
	done

# digests target:
# - fetches each pushed image's digest from ECR
# - writes infra/digests.auto.tfvars.json for terraform to consume
digests: push
	@rm -f infra/digests.auto.tfvars.json.tmp
	@echo '{ "image_digests": {' > infra/digests.auto.tfvars.json.tmp
	@first=1; \
	for pkg in $(FUNCS); do \
		digest=$$(aws ecr describe-images --repository-name $(ECR_REPO_NAME) \
			--image-ids imageTag=$$pkg --region $(AWS_REGION) \
			--query 'imageDetails[0].imageDigest' --output text); \
		test -z "$$digest" && echo "Error: failed to get digest for $$pkg" && exit 1; \
		test $$first -eq 0 && echo ',' >> infra/digests.auto.tfvars.json.tmp; \
		printf '  "%s": "%s"' "$$pkg" "$$digest" >> infra/digests.auto.tfvars.json.tmp; \
		echo '' >> infra/digests.auto.tfvars.json.tmp; \
		first=0; \
	done
	@echo '}}' >> infra/digests.auto.tfvars.json.tmp
	@mv infra/digests.auto.tfvars.json.tmp infra/digests.auto.tfvars.json
	@cat infra/digests.auto.tfvars.json

apply: digests
	cd infra && terraform apply -auto-approve

deploy: apply
	@echo "Deployed: $(FUNCS)"