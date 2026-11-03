# VPS 与配置生成

以下远程命令仅供获准部署或验收时使用。整理 Skill、生成配置和本地校验不需要连接设备；用户禁止实机测试时，不运行这些命令。先读 [前置检查](preflight.md)，部署前准备 [回滚方案](operations.md)。命令中的相对路径以 Skill 根目录为基准。

内容：VPS 安装与准备；生成两端配置；启动服务器、配置防火墙。

## VPS 安装与准备

### 准备 Skill 文件

把整个 Skill 目录放在管理电脑上。授权部署时，将 `scripts/` 与 `assets/` 按原相对结构传到 VPS 的 `/root/claude-code-network/`；路由器只接收生成的 `router/` 和匹配架构的二进制。

首次 SSH 登录核对主机指纹；密钥冲突时核实重装/更换原因，不要关闭主机校验。文中 `203.0.113.10` 为文档保留地址，所有命令执行前替换为实际参数；非 root 登录、非 22 SSH 端口按现场调整。先确认 SSH 实际端口再配置防火墙。

### 安装依赖并备份已有防火墙

在**VPS**运行：

```sh
sudo -i
apt-get update
apt-get install -y ca-certificates curl python3 openssl ufw
cd /root/claude-code-network
umask 077
mkdir -p /root/vpn-setup-backup
cp -a /etc/ufw /root/vpn-setup-backup/ufw.before
cp -a /etc/default/ufw /root/vpn-setup-backup/ufw.defaults.before
ufw status verbose > /root/vpn-setup-backup/ufw-status.before.txt
iptables-save > /root/vpn-setup-backup/iptables.before
```

这些命令只针对新部署示例。已有备份时用新目录保存，避免覆盖上一次恢复点。没有 `iptables-save` 的系统可保存 `nft list ruleset`，但要按实际防火墙管理方式恢复。

### 下载与校验服务器二进制

在 **x86_64 VPS** 运行：

```sh
python3 scripts/download-xray.py \
  --asset Xray-linux-64.zip \
  --out /root/xray-server-download
install -m 755 /root/xray-server-download/xray /usr/local/bin/xray
/usr/local/bin/xray version
```

ARM64 VPS 将 asset 改为 `Xray-linux-arm64-v8a.zip`。下载目录已存在时脚本会拒绝覆盖，应检查后改用新目录。

下载器会从 XTLS 官方 GitHub release 下载 ZIP 与 `.dgst`，读取 `SHA2-256` 并逐字节校验，再提取指定二进制。这是同源文件完整性校验，不是独立发布者签名认证。不要把任意网站提供的二进制或摘要当成官方文件。

### 确认目标站点可用

在**VPS**运行：

```sh
openssl s_client \
  -connect www.asus.com:443 \
  -servername www.asus.com \
  -tls1_3 -alpn h2 </dev/null 2>/dev/null \
  | grep -E 'TLSv1.3|ALPN protocol|Verify return code'
```

至少应看到 TLS 1.3、`ALPN protocol: h2`、证书验证成功。命令挂起、没有输出或验证失败时先检查目标可达性、系统时间、CA、DNS；不要把失败的目标直接写进配置。目标站点和 CDN 行为可能变化，所以新服务器要重新测试，不能只照抄域名。

两端都应有正确的系统时间。路由器启用断线保护后，NTP 也只能经隧道；若开机时间严重错误导致握手失败，先通过 LAN 管理手动校准时间再启动隧道，不能临时放开整个 WAN 作为常规修复。正确的系统时间用于 TLS 证书等校验。`timedatectl status` 可检查时钟同步，但这与把显示时区改成美国是两件事。

## 生成两端配置

### 生成新的 REALITY 密钥

在**VPS**运行：

```sh
cd /root/claude-code-network
umask 077
/usr/local/bin/xray x25519 > /root/reality-keys.txt
chmod 600 /root/reality-keys.txt
```

26.10.29 的输出包含 `PrivateKey`、`Password (PublicKey)`、`Hash32`。客户端使用 `Password (PublicKey)`，不能用 Hash32 替代。私钥只留在服务器。

### 生成配置

离线准备时，在管理电脑的 Skill 根目录运行同一生成器，将 `--key-file` 和 `--out` 换成本地路径；使用已有、受保护的密钥文件，不必连接 VPS 或运行上面的密钥生成命令。没有密钥时先交付参数清单，不把自测用的假密钥用于部署。输出的 `server/config.json` 含私钥，仅交付给目标服务器。

把以下参数替换为[前置检查](preflight.md)中记录的真实值，在**VPS**运行：

```sh
python3 scripts/generate-configs.py \
  --vps-ip 203.0.113.10 \
  --sni www.asus.com \
  --key-file /root/reality-keys.txt \
  --wan-interface wan \
  --wan-dev wan \
  --lan-interface lan \
  --lan-dev br-lan \
  --wan6-interface wan6 \
  --lan-zone lan \
  --wan-zone wan \
  --tun-cidr 172.31.255.1/30 \
  --out /root/vpn-generated
```

**这里的 `203.0.113.10` 是文档保留地址，生成器会明确拒绝它；必须先填写自己的真实公网 IP。**

生成器只写文件，不会启动服务或修改网络。它会新建 UUID 和 Short ID，并把双方配置中的参数保持一致。输出目录已存在时拒绝覆盖，防止意外更换运行中的凭据。

输出结构：

```text
/root/vpn-generated/
├── server/
│   ├── config.json              # 含服务端私钥，仅服务器使用
│   ├── xray.service
│   └── 99-vpn-disable-ipv6.conf
└── router/
    ├── config.json              # 路由器正式配置
    ├── preflight.json           # 仅本机 SOCKS，切换前测试
    ├── us-vpn.init
    ├── 90-us-vpn-guard.nft
    ├── 99-us-vpn-ipv6.conf
    ├── site.env                 # 本地网络设备参数，无服务器私钥
    ├── apply-router.sh
    └── rollback-router.sh
```

JSON 里 `encryption: none` 是 VLESS 字段；外层 REALITY 仍提供加密，不表示公网明文传输。客户端 flow 使用 `xtls-rprx-vision-udp443`，服务端使用 `xtls-rprx-vision`，不要把字符串后缀随意统一。

## 启动服务器、配置防火墙

### 安装服务端文件

在**VPS**运行；如果已有 `/usr/local/etc/xray/config.json` 或 `xray.service`，先停在这里备份和检查，不能直接覆盖：

```sh
adduser --system --group --no-create-home --disabled-login xray
install -d -m 750 -o root -g xray /usr/local/etc/xray
install -m 640 -o root -g xray \
  /root/vpn-generated/server/config.json \
  /usr/local/etc/xray/config.json
install -m 644 /root/vpn-generated/server/xray.service \
  /etc/systemd/system/xray.service
/usr/local/bin/xray run -test -config /usr/local/etc/xray/config.json
systemctl daemon-reload
systemctl enable --now xray
systemctl status xray --no-pager
ss -lntp
```

预期：`Configuration OK`、服务 active/running、443 有 Xray 监听。若 `xray` 用户已经存在，先确认它是预期的系统账户，不要盲目重建或修改其他服务的账户。

服务使用专用 xray 用户运行，保留绑定低端口所需的能力；模板不依赖 `LoadCredential=`。

模板服务端显式使用 IPv4 DNS 和出站策略，并在解析后匹配私网目标阻断规则。VPS 作为应用代理出站，不需要开启 Linux IP forwarding 或给它另加 MASQUERADE。

### 禁用服务器 IPv6

在**VPS**运行：

```sh
# 先记录原值，回滚时使用：
sysctl net.ipv6.conf.all.disable_ipv6 \
       net.ipv6.conf.default.disable_ipv6 \
  > /root/vpn-setup-backup/ipv6.before.txt
install -m 644 /root/vpn-generated/server/99-vpn-disable-ipv6.conf \
  /etc/sysctl.d/99-vpn-disable-ipv6.conf
sysctl -p /etc/sysctl.d/99-vpn-disable-ipv6.conf
ip -6 addr
ip -6 route
```

先确认服务器管理连接是 IPv4。已有同名 sysctl 文件时必须先备份。某些进程会保留 IPv6 形式的监听套接字，判断外部 IPv6 是否可用要结合内核值、地址和路由，不要仅凭 `ss` 中的 `[::]` 下结论。

### 放行管理端口后再启用防火墙

在**VPS**运行：

```sh
ufw show added
ufw status numbered
ufw default deny incoming
ufw default deny routed
ufw default allow outgoing
ufw allow 22/tcp comment 'SSH management'
ufw allow 443/tcp comment 'VLESS REALITY'
ufw --force enable
ufw status verbose
```

在**管理电脑另开一个终端**，再次 `ssh root@你的VPS_IP`，确认新连接可以登录。原有会话不中断并不能证明新的 SSH 连接能通过防火墙。

注意：`default deny` 不会删除原有的 ALLOW 规则。新空白 VPS 最终应只有需要的 22/443 规则；有其他规则时用 `ufw status numbered` 逐条确认用途后删除，不能直接宣称只剩两个端口。已有业务端口应按实际需要保留。删除确认无用的旧规则时，先运行 `ufw status numbered`，再用 `ufw delete 对应编号`，每删一条重新列出编号，避免编号变化删错。若确有必要的其他应用，使用 `ufw allow 实际端口/tcp` 或对应 UDP 规则并记录理由。主机防火墙与供应商安全组是两层配置，都要检查。
