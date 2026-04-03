FROM ubuntu:22.04 AS builder

ARG CURA_VERSION=5.9.0

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential cmake git python3 python3-pip pkg-config \
    && pip3 install conan==2.* \
    && rm -rf /var/lib/apt/lists/*

RUN conan profile detect

WORKDIR /build
RUN git clone --depth 1 --branch ${CURA_VERSION} \
    https://github.com/Ultimaker/CuraEngine.git .

RUN conan install . --build=missing --update -s build_type=Release \
    && cmake --preset release \
    && cmake --build --preset release --parallel

# Also grab the base definitions from Cura's fdmprinter resource
RUN git clone --depth 1 --branch ${CURA_VERSION} \
    https://github.com/Ultimaker/Cura.git /cura-src

# ---------------------------------------------------------------------------
FROM ubuntu:22.04

COPY --from=builder /build/build/Release/CuraEngine /usr/local/bin/CuraEngine
COPY --from=builder /cura-src/resources/definitions/ /opt/cura/definitions/
COPY --from=builder /cura-src/resources/extruders/ /opt/cura/extruders/

ENTRYPOINT ["CuraEngine"]
