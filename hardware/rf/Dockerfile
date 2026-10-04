# openEMS (FDTD) + Python bindings, headless. Build: docker build -t horae-openems hardware/rf
FROM ubuntu:24.04
ENV DEBIAN_FRONTEND=noninteractive
RUN apt-get update && apt-get install -y --no-install-recommends build-essential cmake git ca-certificates \
    libhdf5-dev libvtk9-dev libboost-all-dev libcgal-dev libtinyxml-dev python3-dev python3-pip python3-numpy \
    python3-matplotlib python3-scipy cython3 python3-h5py python3-setuptools python3-venv pkg-config && rm -rf /var/lib/apt/lists/*
RUN git clone --recursive --depth 1 https://github.com/thliebig/openEMS-Project.git /src && cd /src && \
    ./update_openEMS.sh /opt/openEMS --python --disable-GUI 2>&1 | tail -50 || (cat /src/build_*.log 2>/dev/null | tail -100; exit 1)
ENV LD_LIBRARY_PATH=/opt/openEMS/lib PATH=/opt/openEMS/venv/bin:/opt/openEMS/bin:$PATH
WORKDIR /work
