# 客户端、维护与恢复

以下远程命令仅供获准部署或验收时使用。整理 Skill、生成配置和本地校验不需要连接设备；用户禁止实机测试时，不运行这些命令。

内容：Mac / iPhone 的使用要求；日常管理、更新与重启；回滚与恢复；常见问题与排查顺序。

## Mac / iPhone 的使用要求

### Mac

连接该路由器的 Wi-Fi 或 LAN，网关和 DNS 使用自动分配。退出本地 Clash 后，再检查系统代理开关，而不是只看菜单栏图标是否消失。

如确实需要手工关闭系统代理，先用 `networksetup -listallnetworkservices` 找到当前服务名；然后在 Mac 上对实际网络服务执行：

```sh
networksetup -setwebproxystate 'Wi-Fi' off
networksetup -setsecurewebproxystate 'Wi-Fi' off
networksetup -setsocksfirewallproxystate 'Wi-Fi' off
scutil --proxy
```

如果当前使用 Ethernet，应替换服务名。这些命令不负责关闭应用自己设置的代理。不要为验证而公开打印包含认证信息的代理环境变量。

### iPhone

1. 连接 OpenWrt 提供的 Wi-Fi，检查路由器地址是否正确。
2. 关闭其他 VPN/代理应用后测试；Wi-Fi 的 HTTP 代理通常设为关闭。
3. 若使用 iCloud 专用代理或该 Wi-Fi 的“限制 IP 地址跟踪”，Safari 可能再次经 Apple 中转。要求所有出口一致时，需要在该网络上自行调整并复测。
4. 测试时不要切到蜂窝网络；要排除蜂窝回落，可临时开启飞行模式后单独打开 Wi-Fi。
5. 在 Safari 重新运行检测。Mac 的通过结果不能替代 iPhone 的验证。

## 日常管理、更新与重启

### 路由器

```sh
/etc/init.d/us-vpn status
logread -e xray
/etc/init.d/us-vpn restart
ip -4 route
nft list chain inet fw4 us_vpn_output_guard
```

这是独立服务，不在 PassWall 节点列表中管理。不要另行开启 PassWall、OpenClash 等接管同一流量。LuCI 修改防火墙之后，仍应确认自定义 nftables 文件被加载。

### VPS

```sh
systemctl status xray --no-pager
journalctl -u xray -n 50 --no-pager
systemctl restart xray
systemctl is-enabled xray
ufw status verbose
```

访问日志默认关闭，警告/错误保留。排查时可以短暂提高日志级别，定位后改回；不要把带 UUID、密钥或用户访问详情的完整日志公开发布。

如果你的 SSH 自己正通过这个隧道连接 VPS，重启服务器 Xray 会让该 SSH 会话中断。远程执行的后续命令可能没运行完，所以应重新登录核实；不要把连接断开误判为服务器必然启动失败。

### 最终安装位置与端口清单

| 位置 | 文件或服务 | 用途 |
|---|---|---|
| VPS | `/usr/local/bin/xray` | Xray 程序 |
| VPS | `/usr/local/etc/xray/config.json` | VLESS/REALITY 服务端，含私钥 |
| VPS | `/etc/systemd/system/xray.service` | 专用账户运行及开机启动 |
| VPS | `/etc/sysctl.d/99-vpn-disable-ipv6.conf` | 持久化禁用 IPv6 |
| VPS | `/etc/ufw/` | 默认拒绝入站，放行必要端口 |
| VPS | `/root/vpn-setup-backup/` | 安装前防火墙与 IPv6 记录 |
| 路由器 | `/usr/bin/xray-us-vpn` | 匹配路由器 CPU 的程序 |
| 路由器 | `/etc/us-vpn/config.json` | TUN、DNS 入站及 VPS 出站 |
| 路由器 | `/etc/init.d/us-vpn` | procd 服务、自动重启及开机启动 |
| 路由器 | `/etc/nftables.d/90-us-vpn-guard.nft` | 防止直连和 IPv6 泄漏 |
| 路由器 | `/etc/sysctl.d/99-us-vpn-ipv6.conf` | 持久化禁用 IPv6 |
| 路由器 | `/etc/config/network` | 关闭 WAN6、IPv6 分配和运营商 DNS |
| 路由器 | `/etc/config/firewall` | VPN 区域、转发、DNS 接管与卸载选项 |
| 路由器 | `/etc/config/dhcp` | dnsmasq 上游、AAAA 过滤、RA/DHCPv6/NDP |
| 路由器 | `/root/us-vpn-backup-日期-时间/` | 这次安装对应的原状态和确认标记 |
| 路由器 | `/root/us-vpn-backup.current`、`/root/us-vpn-rollback.sh` | 备份定位与回滚入口 |

| 端口 | 监听/访问范围 | 是否长期保留 |
|---|---|---|
| VPS TCP 22 | SSH 管理入口 | 保留；可另行按管理来源限制 |
| VPS TCP 443 | REALITY 隧道入口 | 保留 |
| 路由器 TCP/UDP 53 | LAN 使用的 dnsmasq | 保留，遵循原 LAN 管理防火墙 |
| 路由器 127.0.0.1 TCP/UDP 5353 | Xray DNS 隧道入站 | 保留，仅回环 |
| 路由器 127.0.0.1 TCP 2081 | 安装前 SOCKS 测试 | 测试后停止，不对外开放 |

这里没有新增 VPS 上的公开 SOCKS/HTTP 代理端口，也不需要开放公网 UDP 53、2081 或 5353。路由器原有 LAN SSH/LuCI 管理服务继续按原规则运行。

安装中间目录含客户端凭据；不要传到公共网盘或代码仓库。验收后可以加密归档，管理电脑的 `vpn-transfer` 和路由器的 `/root/us-vpn-stage` 不再用于正式服务，但应先确认正式文件安装完整，再清理这些中间副本。保留恢复备份与对应版本号。

### 更新

先备份两端二进制、配置和服务文件，再在测试条件下确认新版本兼容。不要重新运行生成器覆盖旧 UUID/密钥来进行普通升级；更新程序与轮换凭据是不同操作。

更新前后都要做 `run -test`、真实 SOCKS/隧道请求、DNS/STUN/IPv6 验证。若升级失败，恢复旧二进制和旧配置并重启服务。对于资源有限的路由器，下载、解压可以放在 VPS/管理电脑进行，避免 /tmp 内存不足。

## 回滚与恢复

### 路由器一键恢复

在**路由器 LAN SSH**运行：

```sh
sh /root/us-vpn-rollback.sh
```

它会停止并禁用 us-vpn、移除本次防泄漏和 IPv6 sysctl 文件、恢复 network/firewall/dhcp、恢复原 IPv6 内核值及原 UPnP 状态，并重新加载服务。恢复后会重新具有安装前的直连/IPv6 行为，**不再具有本次断线保护**。

脚本保留备份、二进制、停用的服务文件和配置供检查，不会删除原始恢复证据。确认无误后再决定是否归档这些文件。重新安装不能直接重复运行新安装脚本，应先核对残留文件并移走已停用的本次专用文件，不能删除其他服务的目录来“清理”。

### VPS 恢复

先确保路由器已经恢复直连，或还有其他管理路径。VPS 上可以先停止并禁用新安装的服务：

```sh
systemctl disable --now xray
```

然后按部署前记录恢复 UFW 和 IPv6：

- `/root/vpn-setup-backup/ufw.before/` 是原 UFW 规则配置。
- `ufw.defaults.before` 是 `/etc/default/ufw`，包括原默认策略，也必须恢复。
- `ufw-status.before.txt` 记录原来是否启用。
- `ipv6.before.txt` 记录原内核值。
- 新安装的 `/etc/sysctl.d/99-vpn-disable-ipv6.conf` 应移走或恢复原版本，再应用原来的内核值。

不要在生产服务器上不加区分地 `ufw reset` 或清空整个 nftables/iptables 规则集。如果原 UFW 是关闭的，恢复后可关闭 UFW；如果原来开启，恢复原规则并重载。先保住新的 SSH 连接，再关闭旧会话。

对于本方案的全新 UFW 安装，以下是**先检查后执行**的恢复示例；若使用了不同的备份目录，替换路径。先确认备份内是原 `ufw.conf`、`user.rules` 等文件，而非多嵌套一层目录：

```sh
# VPS，保留当前 SSH 会话，并准备供应商控制台：
ls -la /root/vpn-setup-backup/ufw.before/
cat /root/vpn-setup-backup/ufw-status.before.txt
cat /root/vpn-setup-backup/ipv6.before.txt
# 核对无误后，恢复原 UFW 文件：
cp -a /root/vpn-setup-backup/ufw.before/. /etc/ufw/
cp -a /root/vpn-setup-backup/ufw.defaults.before /etc/default/ufw
# 原状态是 active 时执行：
ufw reload
# 原状态是 inactive 时，应改为执行 ufw disable，不要两条一起运行。
```

恢复 IPv6 时，先移走本次新建的 sysctl 文件；**仅当此文件是本方案新建且原来不存在**时使用：

```sh
mv /etc/sysctl.d/99-vpn-disable-ipv6.conf \
  /root/vpn-setup-backup/99-vpn-disable-ipv6.conf.removed
# 使用备份中的原值，而不是固定设为 0：
sysctl -p /root/vpn-setup-backup/ipv6.before.txt
```

有同名旧文件时应恢复旧文件，而不是直接移走。若原网络还依赖 IPv6 DHCP/RA，恢复内核值后可能需要对应网络服务重新获取地址；在控制台中按发行版网络管理方式处理。UFW 恢复后仍要新开 SSH 验证，再关闭旧会话。

删除 xray 用户之前确认它没有被其他服务使用。没有必要仅为了停止 VPN 就删除用户或软件包。

## 常见问题与排查顺序

| 现象 | 优先检查 | 处理方向 |
|---|---|---|
| Illegal instruction | CPU、大小端、硬/软浮点 | MT7621 提取 `xray_softfloat` |
| Exec format error | 使用了另一架构的程序 | 按发行版架构重新下载 |
| `/dev/net/tun` 不存在 | kmod-tun、内核匹配 | 安装与当前固件匹配的模块 |
| `unknown field` / 配置不支持 | 两端 Xray 版本 | 对照锁定版本，不照抄其他版本字段 |
| `invalid public_key` / 握手失败 | 公钥是否误读、Hash32 是否误用 | 使用 `Password (PublicKey)`，核对 UUID/SNI/Short ID |
| `reality verification failed` | 两端内核兼容性、SNI、目标站点 | 核对两端版本和配置；不要仅反复改时间 |
| SOCKS 成功、全局失败 | WAN_DEV、TUN 路由、fw4 VPN 区域 | 对照 `l3_device`、路由和防火墙链 |
| 能连 IP、打不开域名 | dnsmasq→5353、Xray 服务、CA | 检查本地 DNS 链路，不能改回运营商 DNS 来掩盖问题 |
| 浏览器与 STUN 地址不同 | 本地代理、iCloud 中继、扩展 | 关闭二次代理后重新验证 |
| `curl -6` 似乎仍成功 | 是否实际连接 `::ffff:` 地址 | 使用字面量 IPv6 地址验证 |
| 一开始正常，十分钟后恢复 | 没有创建 confirmed 标记 | 检查回滚日志，重新按步骤部署 |
| 停止服务后仍能上网 | 自定义规则没加载、其他网络接口、流量卸载 | 先停止使用该环境，修复阻断再验收 |
| 重启后 DNS/隧道未启动 | 开机服务、WAN DHCP、时间、日志 | 先用 LAN SSH 排查，不直接放开 WAN 回退 |
| 443 超时 | 云安全组、UFW、服务监听、运营商线路 | 从路由器与外部独立网络分别检查 |
| 国内网站慢 | 所有流量经 VPS、路由器 CPU | 检查往返时延、线路和路由器负载 |
| 本地软件仍显示地区/代理迹象 | 语言时区、定位权限、账号、IP 分类 | 网络层通过不等于应用层身份或环境不可识别 |

故障排查顺序建议：物理网络和 WAN → SSH/443 可达性 → Xray 程序架构 → JSON 校验 → SOCKS 真实握手 → TUN 路由 → DNS → 防火墙 → 浏览器和设备本地代理。
