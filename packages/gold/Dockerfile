# -- build package --
FROM public.ecr.aws/lambda/python:3.14 AS build

# Install build tools needed for C-extensions (e.g. mmh3)
RUN dnf install -y gcc && dnf clean all

RUN pip install --no-cache-dir uv

WORKDIR /build

COPY pyproject.toml uv.lock ./
COPY packages/gold/ packages/gold/

RUN uv build --package gold -o dist

RUN uv pip install --system --no-cache-dir dist/gold-*.whl --target /asset

# Copy dbt project definitions into the asset directory
COPY packages/gold/dbt_project.yml /asset/
COPY packages/gold/profiles.yml /asset/
COPY packages/gold/models /asset/models
COPY packages/gold/snapshots /asset/snapshots
COPY packages/gold/tests /asset/tests
COPY packages/gold/macros /asset/macros
COPY packages/gold/analyses /asset/analyses

# -- copy to lambda runtime --
FROM public.ecr.aws/lambda/python:3.14

COPY --from=build /asset ${LAMBDA_TASK_ROOT}

CMD [ "gold.handler.handler" ]
