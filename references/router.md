# 路由器安装与切换

以下远程命令仅供获准部署或验收时使用。整理 Skill、生成配置和本地校验不需要连接设备；用户禁止实机测试时，不运行这些命令。先完成 [服务端准备](server.md)，读取 [回滚方案](operations.md)。切换前 SOCKS 验证是必需步骤；未获准验证时停在生成配置阶段。

内容：把路由器文件安全传过去；切换前的 SOCKS 连通性测试；路由器全局接管与自动回滚。

## 把路由器文件安全传过去

### 在 VPS 下载正确的路由器程序

以 **MT7621 路由器**为例，在**VPS**运行：

```sh
cd /root/claude-code-network
python3 scripts/download-xray.py \
  --asset Xray-linux-mips32le.zip \
  --member xray_softfloat \
  --out /root/xray-router-download
```

ARM64 路由器使用 `--asset Xray-linux-arm64-v8a.zip --member xray`；其他型号按架构表选择。VPS 与路由器 CPU 可以不同，下载后不应在 VPS 上执行 MIPS 路由器程序。

### 通过管理电脑中转

在**管理电脑**创建独立目录，填入真实地址：

```sh
umask 077
mkdir vpn-transfer
cd vpn-transfer
scp -r root@203.0.113.10:/root/vpn-generated/router ./router-stage
scp root@203.0.113.10:/root/xray-router-download/xray ./xray-us-vpn
scp -O -r ./router-stage root@10.0.0.1:/root/us-vpn-stage
scp -O ./xray-us-vpn root@10.0.0.1:/tmp/xray-us-vpn
ssh root@10.0.0.1
```

`-O` 是 OpenSSH scp 的传统协议选项，用来兼容没有 SFTP 子系统的 Dropbear。这里需要大写字母 O，不是数字 0。如果你的 scp 实现不支持该参数，使用它支持的 SSH 文件传输方式，而不是改用公开 HTTP 分享凭据。

只中转 `router/`，不要把服务器 `server/config.json` 或 `/root/reality-keys.txt` 传到路由器。即使客户端没有服务器私钥，它的 UUID 等仍属于访问凭据，不能公开。

在**路由器**安装二进制：

```sh
chmod 755 /tmp/xray-us-vpn
/tmp/xray-us-vpn version
# 确认可运行后再放到持久存储：
cp /tmp/xray-us-vpn /usr/bin/xray-us-vpn
chmod 755 /usr/bin/xray-us-vpn
chmod 700 /root/us-vpn-stage
chmod 600 /root/us-vpn-stage/*.json /root/us-vpn-stage/site.env
/usr/bin/xray-us-vpn run -test -config /root/us-vpn-stage/config.json
```

运行报错时先解决架构、ABI 或配置问题，不要继续改防火墙。模板通过 `run -test` 只是语法/初始化检查，不代表实际握手或流量转发已成功。

## 切换前的 SOCKS 连通性测试

这一步不会改默认路由或 LAN 转发。在**路由器**运行：

```sh
/usr/bin/xray-us-vpn run -test -config /root/us-vpn-stage/preflight.json
nohup /usr/bin/xray-us-vpn run \
  -config /root/us-vpn-stage/preflight.json \
  >/tmp/us-vpn-preflight.log 2>&1 </dev/null &
echo $! > /tmp/us-vpn-preflight.pid
```

确认进程已启动后：

```sh
curl -4fsS --max-time 25 \
  --proxy socks5h://127.0.0.1:2081 https://api.ipify.org
printf '\n'
curl -4fsS --max-time 25 \
  --proxy socks5h://127.0.0.1:2081 \
  https://www.cloudflare.com/cdn-cgi/trace
cat /tmp/us-vpn-preflight.log
```

必须看到你的新 VPS 出口 IPv4。若供应商做了公网 NAT，应先对照 VPS 自己访问同一查询服务得到的出口；出口不等于连接 IP 时，后续验收应以实际固定出站 IP 为准，不要误以为任意不同地址都正常。

发生 `reality verification failed` 时核对公钥、Short ID、UUID、SNI、端口、两端版本及目标站点，不要盲目关闭证书校验。本 Skill 使用两端同版本 Xray；不要假定不同内核兼容。

确认测试成功后，在**路由器**停止这个临时实例并打标记：

```sh
# 先确认该 PID 仍对应刚才的 preflight.json 进程：
cat /tmp/us-vpn-preflight.pid
ps w | grep '[p]reflight.json'
# 确认后：
kill "$(cat /tmp/us-vpn-preflight.pid)"
touch /root/us-vpn-stage/preflight-ok
```

不要跳过测试后直接创建标记。正式部署不需要把 SOCKS 2081 开放给 LAN 或公网。

## 路由器全局接管与自动回滚

### 应用前最后核对

在**路由器**运行：

```sh
cat /root/us-vpn-stage/site.env
uci changes
ip -4 route
```

`uci changes` 应没有输出；如果存在未提交修改，先确认并处理，脚本不会替你自动提交未知改动。所有 LAN 客户端会受切换影响，正在下载、通话或 SSH 的连接可能重连。

脚本会拒绝已存在的同名安装和名为 `vpn` 的既有防火墙区域。还应手动确认没有旧策略路由残留，没有其他管理程序不断重写防火墙。脚本的范围检查不能替代对复杂自定义固件的理解。

### 应用

在**路由器**通过 LAN SSH 运行：

```sh
sh /root/us-vpn-stage/apply-router.sh /root/us-vpn-stage
```

脚本按下列顺序执行：

1. 校验 OpenWrt、DHCP WAN、单默认路由、接口名、单 dnsmasq、TUN 和 Xray 配置。
2. 新建 `/root/us-vpn-backup-日期-时间/`，保存 network、firewall、dhcp、原 IPv6 内核状态及 UPnP 状态。
3. 安装 `/root/us-vpn-rollback.sh`，记录备份路径，并启动 **10 分钟自动恢复计时器**。
4. 安装正式 Xray 配置、procd 服务、nftables 阻断规则和 IPv6 sysctl 文件。
5. 关闭 LAN 的原区域转发，新增 LAN→VPN；关闭流量卸载和已存在的 Full Cone 选项。
6. 创建标准 fw4 TCP/UDP 53 重定向；若存在定制固件的 dns_redirect 选项，关闭它以避免重复接管。
7. 关闭 WAN6、IPv6 前缀分配、RA/DHCPv6/NDP；dnsmasq 只向本机 Xray 5353 请求 DNS。
8. 关闭 UPnP，加载防火墙，启动并启用 us-vpn，重启 dnsmasq。

脚本中途出错会尝试恢复。切换后网络不可用但 LAN SSH 仍可用时，可以立即执行回滚；如果连操作也无法继续，保持路由器通电，等待计时器恢复。**计时器只在当前启动周期有效，验收前不要重启或断电。**

### 十分钟内完成基本验收并确认

在**路由器**运行：

```sh
/etc/init.d/us-vpn status
ip -4 route
curl -4fsS --max-time 20 https://api.ipify.org
printf '\n'
nslookup example.com 127.0.0.1
nft list chain inet fw4 us_vpn_forward_guard
nft list chain inet fw4 us_vpn_output_guard
```

然后在一台 LAN 客户端访问外网，并确认出口是 VPS。成功后，在**路由器**运行：

```sh
B=$(cat /root/us-vpn-backup.current)
touch "$B/confirmed"
```

这个标记会取消自动回滚。没有确认标记，10 分钟后会恢复原配置，即使当前看起来能上网。不要在未验证时先打标记。剩余详细验收可以在确认后进行，手动回滚仍然可用。

### 为什么服务停了也不会泄漏

阻断规则直接属于 fw4，独立于 Xray：

- 转发 IPv6 一律丢弃。
- IPv4 转发只能流向 LAN 或 `us-tun`，不能去其他接口。
- 路由器自身只允许本地回环、LAN、TUN，以及 WAN→VPS:443、WAN DHCP。
- 其他出站流量丢弃。

规则使用比普通 fw4 filter 链更早的优先级，避免已有连接的快速放行绕过它；流量卸载同时关闭。手动停止 Xray 不等于恢复普通直连，需要明确执行回滚才能恢复。

这个严格策略也会阻止直接访问上级 WAN 网段里的管理设备。若需要访问光猫，必须自行明确设计仅针对光猫管理地址的例外，并重新检查 DNS、WebRTC 和断线行为；不要简单放开整个 WAN。
