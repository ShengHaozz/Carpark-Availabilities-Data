# -- build package
FROM public.ecr.aws/lambda/python:3.13 AS build

RUN pip install --no-cache-dir uv

WORKDIR /build

COPY pyproject.toml uv.lock ./
COPY packages/silver_cold/ packages/silver_cold/ 
# need to copy with packages/ as need pyproject.toml in root

RUN uv build --package silver_cold -o dist

RUN uv pip install --system --no-cache-dir dist/silver_cold-*.whl --target /asset

# -- copy to lambda --
FROM public.ecr.aws/lambda/python:3.13

COPY --from=build /asset ${LAMBDA_TASK_ROOT}

CMD [ "silver_cold.handler" ]