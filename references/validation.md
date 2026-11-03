# 线上验收

以下远程命令仅供获准部署或验收时使用。整理 Skill、生成配置和本地校验不需要连接设备；用户禁止实机测试时，不运行这些命令。本文件所有检查都会读取设备状态或发起网络流量，均不属于离线校验。

内容：逐项验收与断线测试。

## 逐项验收与断线测试

### 客户端先关闭二次代理

让 Mac/iPhone 连接这台路由器。先退出 Clash、其他 VPN 等软件，并检查系统代理是否实际关闭。浏览器出口与 STUN 出口不一致，常见原因就是二次代理。

在 **Mac** 查看：

```sh
scutil --proxy
route -n get 1.1.1.1
```

HTTPEnable、HTTPSEnable、SOCKSEnable 应为 0，默认网关应指向你的 OpenWrt。另有应用专属代理、环境变量代理、iCloud 中继或其他网络扩展时，也要单独确认。

### HTTP 与目标服务出口

在**管理电脑/客户端**运行：

```sh
curl --noproxy '*' -4fsS --max-time 20 https://api.ipify.org
printf '\n'
curl --noproxy '*' -4fsS --max-time 20 \
  https://www.cloudflare.com/cdn-cgi/trace
curl --noproxy '*' -4fsS --max-time 20 \
  https://claude.ai/cdn-cgi/trace
curl --noproxy '*' -4fsS --max-time 20 \
  https://api.anthropic.com/cdn-cgi/trace
curl --noproxy '*' -4fsS --max-time 20 \
  https://platform.claude.com/cdn-cgi/trace
```

比较 `ip=`、`loc=`，应一致；Cloudflare 机房代码用于辅助观察，不应把某次 CDN 节点变化本身当成泄漏。403、验证码或账号错误与隧道是否连通不是同一个问题。

### DNS

在**客户端**运行，替换路由器地址：

```sh
dig @10.0.0.1 example.com A +short +time=4 +tries=1
dig @8.8.8.8 example.com A +short +time=4 +tries=1
dig +tcp @8.8.8.8 example.com A +short +time=4 +tries=1
dig @10.0.0.1 example.com AAAA +short +time=4 +tries=1
```

A 查询应成功；经本路由器 DNS 的 AAAA 应被过滤。两项指定 8.8.8.8 的 DNS 查询会被标准 53 端口接管，除非设备使用另一个网络入口。dnsmasq 可以缓存结果，验证断线时要使用全新域名，不能只查询已经缓存的 example.com。

在**路由器**检查实际配置与规则：

```sh
uci show dhcp | grep -E 'server=|noresolv|filter_aaaa'
nft list ruleset | grep -E 'VPN-DNS|dport 53|redirect to :53'
```

浏览器打开 CleanIP 的检测，解析器应不出现本地宽带运营商。公共解析器本身可能用 IPv6 去访问权威 DNS；那是解析器的服务器地址，不等于你的客户端有 IPv6 出口。

### STUN / WebRTC

在有 Python 3 的**管理电脑**，进入Skill目录运行：

```sh
python3 scripts/check-stun.py 你的VPS实际出口IPv4
```

脚本向 Google、Cloudflare 的公共 STUN 服务发 UDP 请求，打印每个返回的公网 IP 和是否匹配期望值。两个都匹配是独立于浏览器的补充证据；超时是“没有结果”，不能当作“确认无泄漏”。

再用浏览器访问 <https://cleanip.io/claude>，点击开始检测：

- WebRTC 的公网 IP 应与网页出口相同。
- 不应出现国内宽带公网 IP 或另一个国外代理 IP。
- 私有 LAN 地址、mDNS 名称与另一个公网出口不是一回事。
- DNS、IPv4/IPv6、各域名出口分别检查，不只看总分。

### IPv6

在**路由器**运行：

```sh
sysctl net.ipv6.conf.all.disable_ipv6
sysctl net.ipv6.conf.default.disable_ipv6
ip -6 addr
ip -6 route
```

在 **Mac/Linux 客户端**运行：

```sh
curl --noproxy '*' -g -6fsS --connect-timeout 3 --max-time 5 \
  'https://[2606:4700:4700::1111]/cdn-cgi/trace'
```

该请求应失败；浏览器应未检测到 IPv6。不要仅用 `curl -6 https://某域名` 判断，因为某些系统会把 IPv4 地址映射成 `::ffff:` 形式，这仍可能是 IPv4 连接。必要时重连客户端 Wi-Fi，清除以前的 IPv6 地址和路由租约。

### 断线不直连：真实测试

先确认已按[路由器安装](router.md)的基本验收与确认步骤取消自动回滚计时器。测试期间全网会短暂不能上网。在**路由器**先安排恢复，再停止：

```sh
nohup sh -c 'sleep 30; /etc/init.d/us-vpn start' \
  >/tmp/us-vpn-recovery-test.log 2>&1 </dev/null &
/etc/init.d/us-vpn stop
```

立即在**客户端**运行：

```sh
curl --noproxy '*' --connect-timeout 3 --max-time 5 -fsS \
  https://1.1.1.1/cdn-cgi/trace
dig @8.8.8.8 "vpn-test-$(date +%s).example.com" A +time=2 +tries=1
```

HTTPS 应超时/失败。DNS 不应获得经 WAN 直接返回的正常公网解析；不同 dnsmasq 版本可能超时或直接 SERVFAIL，都要结合规则计数判断。NXDOMAIN 也可能来自缓存，所以使用新域名并检查计数。

在**路由器**查看：

```sh
nft list chain inet fw4 us_vpn_forward_guard
nft list chain inet fw4 us_vpn_output_guard
```

直接 WAN 流量的丢弃计数应增加，LAN SSH 管理仍应可用。30 秒后服务恢复，再次查询出口并做 STUN 测试。若恢复失败，用 LAN SSH 检查日志，必要时手动 `/etc/init.d/us-vpn start`。

### 持久化验收

依次做，不能同时重启两端：

1. 路由器 `/etc/init.d/us-vpn restart` 后验证出口。
2. 路由器 `/etc/init.d/firewall reload` 后验证出口及断线阻断链。
3. 检查 `/etc/rc.d/` 中 us-vpn 链接，VPS `systemctl is-enabled xray` 应为 enabled。
4. 在有现场恢复条件时重启路由器，确认 WAN 获取地址、LAN DHCP、DNS、TUN、IPv6 和断线保护全部恢复。
5. 路由器稳定后，再重启 VPS，确认 SSH 和隧道服务都能恢复。

只记录本次实际完成的验收。未执行的整机重启、断线和真实握手测试应明确标为未验证。
