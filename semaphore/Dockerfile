FROM semaphoreui/semaphore:v2.17.12

# infrahub-sdk follows uv.lock and opsmill.infrahub the collection version this
# image has been running; tests/unit/test_pinned_versions.py holds the first to
# the lockfile, so a dependency bump that misses this file fails.
ARG INFRAHUB_SDK_VERSION=1.22.0
ARG OPSMILL_INFRAHUB_COLLECTION_VERSION=1.9.0

USER root

RUN apk add --no-cache python3 py3-pip && \
    pip3 install --break-system-packages "infrahub-sdk==${INFRAHUB_SDK_VERSION}"

USER semaphore
RUN mkdir -p /opt/semaphore/collections
RUN ansible-galaxy collection install "opsmill.infrahub:==${OPSMILL_INFRAHUB_COLLECTION_VERSION}" -p /opt/semaphore/collections
