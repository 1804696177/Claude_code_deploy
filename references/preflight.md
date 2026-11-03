# 适用范围与参数检查

以下远程命令仅供获准部署或验收时使用。整理 Skill、生成配置和本地校验不需要连接设备；用户禁止实机测试时，不运行这些命令。

内容：用户需要提供的连接信息；设备与 VPS 选型；能实现什么，以及适用范围；拓扑与工作原理；依赖清单与架构选择；参数表与部署前检查。

## 用户需要提供的连接信息

实际部署前，Agent 先利用本次会话中已有的信息，再一次性列出缺少的项目请用户补充。

| 对象 | 用户需要提供或确认 | 说明 |
|---|---|---|
| 本地路由器 | LAN 网关/管理 IP | 例如 `192.168.1.1`；必须是用户自己的路由器，不能直接照抄示例 |
| 本地路由器 | SSH 用户名 | OpenWrt 常用 `root`，仍需用户确认；后续应用脚本要求 root 权限 |
| 本地路由器 | SSH 密码，或已有 SSH 密钥认证方式 | SSH 密码不一定等同于 Wi-Fi 密码或管理网页密码 |
| 本地路由器 | SSH 端口、SSH 是否已启用 | 通常为 22，使用实际值 |
| VPS | 公网 IPv4 | 用于 SSH 管理和隧道连接；不能填写文档保留地址 |
| VPS | SSH 用户名 | 原教程使用 `root`；也可使用有 sudo 权限的账户 |
| VPS | SSH 密码，或已有 SSH 密钥认证方式 | 不等同于云服务商网站的账号密码 |
| VPS | SSH 端口、sudo 提权方式（如需要） | 防火墙必须保留实际管理端口，不能一律假定为 22 |

密码在确需认证时通过可用的安全交互方式提供；不写入 README、`site.env`、生成配置、命令行参数或日志，也不在回复中复述。已有可用密钥/SSH agent 时不再索要密码，不要求粘贴私钥内容。当前工具不支持安全交互输入时，由用户完成认证或配置密钥后继续。只整理教程或离线生成配置时，不需要真实登录密码。

用户不清楚 CPU、固件、WAN/LAN 设备名等技术信息时，不要求其猜测；可以使用用户提供的系统信息，或在允许设备访问的部署任务中做只读检查。禁止设备访问或实机测试时，列为待确认项。

## 设备与 VPS 选型

- 一台符合下文适用范围的 OpenWrt 路由器。
- 一台国外 Linux VPS。建议：**最好带双 ISP 和线路优化**。不把这一选型偏好当作协议要求，也不据此承诺住宅 IP 属性或账号可用性。
- 一个运行在本地管理电脑上的 Agent，能读取本 Skill、执行本地命令，并在用户授权范围内通过 SSH/SCP 管理两端。无需从 VPS 直接访问家中 LAN 地址。

这里的 VPS“双 ISP”选型与家中路由器“双 WAN”拓扑不是同一要求；本脚本仍仅支持单 DHCP WAN。

实际切换与验收前，提醒用户关闭并退出 Clash 等其他代理，并检查系统代理状态，避免二次代理干扰。若 Agent 本身依赖该代理保持连接，先安排管理连接，避免提前断开后无法继续部署。详细客户端操作见 [维护说明](operations.md)。

## 能实现什么，以及适用范围

### 本方案的能力

| 目标 | 实现方式 | 验收依据 |
|---|---|---|
| 国内外统一出口 | 路由器 TUN 接管 IPv4，无中国大陆直连规则 | 国内探针、外网 IP、目标网站 trace 一致 |
| 加密与流量外观 | VLESS + REALITY + XTLS Vision，TCP 443 | 两端完成真实握手，业务请求成功 |
| DNS 不经国内运营商 | dnsmasq → 本机 Xray → 隧道 → 1.1.1.1 | DNS 泄漏检测与 WAN 阻断规则 |
| WebRTC 不暴露另一公网地址 | UDP/STUN 同样通过隧道 | 浏览器检测 + 两个独立 STUN 服务器 |
| 禁用 IPv6 | 网络分配、内核、防火墙三层处理 | 无 IPv6 外网路由，显式 IPv6 请求失败 |
| 隧道失效不直连 | 与 Xray 进程独立的 nftables 规则 | 停止服务后 HTTPS、DNS 均不能绕过 |
| 精简 VPS 入站端口 | UFW 默认拒绝，仅放行必要端口 | 规则审计、SSH 重新连接 |

REALITY 是 TLS 外观伪装与认证机制，不保证永不被识别或封锁。固定 VPS 出口也不等于住宅 IP，商业数据库仍可能标记机房、VPN 或代理。WebRTC 测试通过只说明这次测试未发现第二个公网出口，不能保证设备上的其他网络接口、其他 VPN 或蜂窝网络永远不会产生另外的出口。

这里的“全局”指通过这台路由器的常规 TCP/UDP 互联网连接。局域网通信、ARP、DHCP 等维持本地网络的流量不会送到美国；不承诺承载所有原始 IP 协议，也不要把 ICMP ping 当成唯一验收方法。

网络连通性不代表账号、地区或服务可用性验证通过。

### 自动应用脚本的明确范围

配套的 `apply-router.sh` 只用于**新部署**，要求：

- VPS：使用 systemd 的 Debian/Ubuntu，示例以 Debian 12 / Ubuntu 22.04、24.04 的命令习惯编写；不据此宣称所有发行版均已实机验证。
- 路由器：OpenWrt / 兼容发行版，已有 firewall4（fw4）+ nftables、UCI、procd、dnsmasq。
- 拓扑：一条 DHCP IPv4 WAN，一个静态 LAN 网段；路由器真正作为网关，而非单纯 AP 或旁路由。
- LAN、WAN 使用不同的 Linux 网络设备；可以从 LAN 管理路由器。
- 没有正在生效的其他 VPN、策略路由、多 WAN 或代理插件。
- 现有 `/etc/init.d/us-vpn`、`/etc/us-vpn` 等路径不存在，避免覆盖旧安装。

**PPPoE、双 WAN、多个 VLAN/访客网、旁路由、桥接 AP、fw3/iptables、企业防火墙、Docker 混合网关不属于脚本的直接适用范围。**这些情况可以借鉴原理，但要重新设计接口匹配、区域转发与例外规则。不要为了让脚本通过而删除它的检查。

内核模块必须与正在运行的 OpenWrt 固件完全匹配。遇到 kmod 版本/校验不匹配，不要强制安装。

## 拓扑与工作原理

```text
Mac / iPhone / 其他 LAN 设备
       │  默认网关 = OpenWrt 的 LAN IP
       ▼
OpenWrt LAN（例如 br-lan，10.0.0.1/24）
       │  全部常规 IPv4 TCP/UDP
       ▼
Xray TUN：us-tun，172.31.255.1/30，MTU 1400
       │  VLESS + REALITY + Vision
       │  经真实 WAN 接口绑定，连接 VPS_IP:443/TCP
       ▼
Linux VPS / Xray 服务
       │  IPv4 出站
       ▼
国内网站、国外网站、STUN 服务器、公共 DNS
```

DNS 单独进入本机监听端口：

```text
设备 UDP/TCP 53 → 路由器 dnsmasq:53
              → 127.0.0.1:5353（Xray tunnel 入站）
              → 同一条 REALITY 隧道
              → VPS → 1.1.1.1:53
```

DNS 在路由器至 VPS 这一段受隧道加密保护；VPS 到 1.1.1.1 使用普通 DNS，本方案没有额外部署 DoH 服务器。设备自行使用 DoH/DoT 时，其连接仍走全局隧道，但检测页可能显示设备选择的其他解析服务。

两条 `0.0.0.0/1` 与 `128.0.0.0/1` 路由覆盖全部 IPv4 空间；局域网更具体的路由仍优先。Xray 的加密连接绑定 WAN 真实设备，避免被送回 TUN。不能把路由器自己的默认路由改成 VPS 公网地址：VPS 不是本地链路的下一跳。

## 依赖清单与架构选择

### 三个执行位置

全文代码块之前标明执行位置：

- **管理电脑**：有 SSH/SCP 的 Mac、Linux 或 Windows OpenSSH，用于连接两台设备和中转文件。
- **VPS**：使用 root 或先 `sudo -i`；需要联网下载官方发布包。
- **路由器**：通过 LAN SSH 登录 root；这里执行的防火墙命令会影响全网连接。

不要把路由器脚本粘贴进管理电脑终端直接运行。不要从 VPS 直接访问 `10.0.0.1` 来传文件；那是你的家庭私网地址，VPS 通常无法访问。

### 软件依赖

| 位置 | 必需项 | 用途 |
|---|---|---|
| 管理电脑 | SSH、SCP；可选 Python 3、dig、curl | 登录、中转、独立验证 |
| VPS | curl、ca-certificates、python3、openssl、systemd、ufw | 下载校验、生成配置、TLS 检查、服务和防火墙 |
| VPS | 匹配 CPU 的 Xray 26.10.29 | 服务端 |
| 路由器 | firewall4、nftables、UCI、ubus、jsonfilter、procd、dnsmasq | 防火墙、网络和服务管理 |
| 路由器 | kmod-tun，存在 `/dev/net/tun` | TUN 支持 |
| 路由器 | curl、ca-bundle、ip 命令；建议 ip-full | 连通性验证及路由诊断 |
| 路由器 | 与 CPU/浮点 ABI 匹配的 Xray 26.10.29 | 客户端 |

Python 脚本只使用标准库，不需要 pip。路由器不需要安装 Python、Go 编译器、Docker、sing-box 或 Web 管理面板。内存和空间以实际固件为准；机器应先确认二进制、配置和运行内存有余量。

### 官方安装包对应关系

| 硬件/ABI | 官方 ZIP | ZIP 内应提取 |
|---|---|---|
| Linux x86_64 / amd64 | `Xray-linux-64.zip` | `xray` |
| Linux ARM64 / aarch64 | `Xray-linux-arm64-v8a.zip` | `xray` |
| MT7621、mipsel_24kc、MIPS little-endian 无硬浮点 | `Xray-linux-mips32le.zip` | **`xray_softfloat`** |
| MIPS 32 位 big-endian 无硬浮点 | `Xray-linux-mips32.zip` | `xray_softfloat`，需确认设备 ABI |
| ARM 32 位 | `Xray-linux-arm32-v5/v6/v7a.zip` | `xray`，必须对应 CPU 能力 |

`uname -m` 在某些 MT7621 固件上只输出 `mips`，无法单独判断大小端。同时读取 `/etc/openwrt_release` 的 `DISTRIB_ARCH`、`DISTRIB_TARGET` 和 `ubus call system board`。

架构注意事项：MT7621 使用 ZIP 中普通的 `xray` 会报 **Illegal instruction**，而同一个 ZIP 中的 `xray_softfloat` 可正常运行。下载脚本提取后统一命名为 `xray`，复制到路由器后再命名为 `xray-us-vpn`。

本 Skill 沿用原项目锁定的版本，不表示该版本是最新版本，也不表示本次重构做过实机验证。以后升级必须重新核对配置字段、TLS 指纹和 REALITY 兼容性，不能只更新一端后假设另一端必然兼容。

## 参数表与部署前检查

### 先写下自己的参数

| 参数 | 含义 | 文档示例/默认值 |
|---|---|---|
| VPS_IP | 新 VPS 的真实公网 IPv4 | 文中 `203.0.113.10` 仅为不可用示例，必须替换 |
| ROUTER_IP | 路由器 LAN 管理地址 | `10.0.0.1`；其他机器可能为 `192.168.1.1` |
| SNI | 经过 VPS 验证的 REALITY 目标域名 | `www.asus.com`，不是永久保证可用 |
| WAN_IF | UCI 逻辑 WAN 接口 | `wan` |
| WAN_DEV | 内核实际 L3 上网设备 | 示例为 `wan`，其他机器可能是 `eth1`、`eth0.2` |
| LAN_IF | UCI LAN 接口；本脚本要求 DHCP 段同名 | `lan` |
| LAN_DEV | LAN 网桥/设备 | `br-lan` |
| WAN6_IF | UCI IPv6 WAN 接口 | `wan6`，不存在也可以 |
| LAN_ZONE / WAN_ZONE | 防火墙区域的 name | `lan` / `wan`，不是数组下标 |
| TUN_CIDR | 不与任何现有网络重叠的私有 /30 | `172.31.255.1/30` |

**WAN_IF 和 WAN_DEV 不一定相同。**比如逻辑接口叫 `wan`，实际网卡可能叫 `eth1`。Xray 的接口绑定和 nftables 的 `oifname` 要填写 WAN_DEV。

### 路由器检查：先只读，不修改

在**路由器**运行：

```sh
cat /etc/openwrt_release
ubus call system board
uname -m
df -h
free
ip -4 addr
ip -4 route
ip -6 route
ubus call network.interface.wan status
ubus call network.interface.lan status
uci show network
uci show firewall
uci show dhcp
command -v fw4 nft uci ubus jsonfilter ip curl nohup
ls -l /dev/net/tun
dnsmasq --help | grep -i 'filter-AAAA'
ps w
```

确认：

1. LAN 与上级网络不重叠，例如 LAN `10.0.0.0/24`、WAN `192.168.1.0/24`。
2. `wan` 的协议为 DHCP；只有一条 IPv4 默认路由。
3. 记录 `l3_device`：这是后面使用的 WAN_DEV 和 LAN_DEV。
4. 路由器确实是客户端默认网关。客户端接在另一台 Wi-Fi/AP 上时，可能根本不经过它。
5. `/dev/net/tun` 存在，且 dnsmasq 支持 AAAA 过滤。
6. 没有其他代理进程接管路由；需要停用的旧插件，应先记录其启用状态和配置。
7. TUN 网段没有与现有 LAN、WAN、容器、虚拟机、远程网络重叠。
8. 使用 LAN 管理 SSH，最好有网线或本地恢复方式，不能从将被封锁的 WAN 管理入口操作。

缺少普通依赖时，在**路由器**选择与固件相符的一组命令：

```sh
# 使用 opkg 的固件：
opkg update
opkg install kmod-tun ca-bundle curl ip-full
```

```sh
# 原生使用 apk 的固件：
apk update
apk add kmod-tun ca-bundle curl ip-full
```

不要仅根据版本字符串猜包管理器；某些定制固件有兼容包装命令。fw4/nftables 应已经随目标固件安装，若当前是 fw3，本方案不指导直接替换防火墙体系。

如果是 PassWall 等旧方案，先从它的管理页面停用，并记录原状态；确认其进程、TUN、策略路由已经退出。脚本备份的是执行当时的状态，不会自动恢复你在此前手动停用的旧插件。

### VPS 检查

在**VPS**运行：

```sh
sudo -i
uname -m
cat /etc/os-release
ss -lntup
ip -4 route
systemctl --version | head -1
ufw status verbose
```

先确认 TCP 443 没被网站、面板、另一套代理占用。如果已有业务，要先规划其必要端口和迁移方式；不能直接套用“仅留 22/443”的新机器规则。Docker 或云安全组也可能独立改变端口暴露情况，需分别审计。

供应商控制台/安全组至少放行入站 TCP 22、443，允许需要的出站访问。不需要为了本方案把所有 UDP 入站端口放开。
