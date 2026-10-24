# api_adapter_g Docker image
# Build: ./deploy/build.sh

FROM ubuntu:24.04

# Set timezone
RUN ln -sf /usr/share/zoneinfo/Asia/Shanghai /etc/localtime && \
    ulimit -n 65535

WORKDIR /opt/app

# Copy the pre-built static Linux binary
COPY api_adapter_linux_amd64 /opt/app/api_adapter_g

# Create logs directory (volume mount point)
RUN mkdir -p /opt/app/logs

EXPOSE 16001

ENTRYPOINT ["./api_adapter_g"]