FROM postgres:15-alpine

RUN apk update && \
    apk add --no-cache git make build-base clang llvm && \
    cd /tmp && \
    git clone --branch v0.5.1 https://github.com/pgvector/pgvector.git && \
    cd pgvector && \
    make with_llvm=no && \
    make install with_llvm=no && \
    cd / && \
    rm -rf /tmp/pgvector && \
    apk del git make build-base clang llvm
