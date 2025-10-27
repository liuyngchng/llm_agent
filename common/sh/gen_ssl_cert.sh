#!/bin/bash
# 进入证书目录
cd ./common/cert/

# 备份旧证书
cp srv.crt srv.crt.backup
cp srv.key srv.key.backup

# 使用更完整的方法生成证书
cat > ssl_config.cnf << EOF
[req]
distinguished_name = req_distinguished_name
x509_extensions = v3_req
prompt = no

[req_distinguished_name]
C = CN
ST = Beijing
L = Beijing
O = YourCompany
CN = localhost

[v3_req]
keyUsage = keyEncipherment, dataEncipherment
extendedKeyUsage = serverAuth
subjectAltName = @alt_names

[alt_names]
DNS.1 = localhost
DNS.2 = 127.0.0.1
IP.1 = 127.0.0.1
IP.2 = 172.17.0.1
IP.3 = 11.10.36.2  # 添加你的宿主机IP
EOF

# 生成新证书
openssl req -x509 -newkey rsa:2048 -nodes \
  -keyout srv.key -out srv.crt -days 365 \
  -config ssl_config.cnf

# 设置正确的权限
chmod 644 srv.crt
chmod 600 srv.key