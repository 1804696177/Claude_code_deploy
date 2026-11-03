---
name: claude-code-network
description: 为 Claude Code 使用场景准备、部署或排查 OpenWrt 与 Linux VPS 的 Xray 全局网络环境，包含 VLESS/REALITY、TUN、DNS、IPv6 阻断和断线保护。适用于该网络方案的配置生成、安装、验收、维护与回滚，不用于 Claude Code 客户端安装或账号注册。
---

# Claude Code 网络环境

将 OpenWrt LAN 的常规 IPv4 TCP/UDP 流量经 Xray TUN 送到 VPS，DNS 同走隧道，禁用 IPv6，并由独立于 Xray 的 fw4 规则阻止断线后直连。沿用原项目的 Xray `v26.10.29` 和 VLESS + REALITY + Vision 配置；不将版本锁定理解为最新版本或本次实机验证结论。

## 首次使用与信息收集

先说明需要一台 OpenWrt 路由器、一台国外 Linux VPS，以及能访问本地路由器并使用 SSH/SCP 的本地 Agent。沿用项目作者的选型建议：VPS 最好带双 ISP 和线路优化；这是偏好，不是脚本的硬性依赖，也不表示家中需要双 WAN。

开始实际部署前，按 [连接信息表](references/preflight.md#用户需要提供的连接信息) 收集本地路由器的 LAN IP、SSH 用户名、密码，以及 VPS 的公网 IP、SSH 用户名、密码，同时确认两端 SSH 端口。已有可用 SSH 密钥或 SSH agent 时，用该认证方式替代对应密码，不重复索要。只询问当前缺少的信息，不猜测用户名、密码或地址；离线准备不需要索取真实密码。

提醒用户在实际切换与验收前关闭并退出其他代理，确认系统代理也已关闭；若本地 Agent 的连接依赖现有代理，先安排可继续操作的管理路径，再停用。原 README 中的手机注册、付款、语言时区等个人记录保留在 [README.md](README.md)，回答相关使用问题时读取，不把历史结果当作成功保证。

## 执行边界

- 先区分任务是离线准备、实际部署还是故障排查。重构、阅读文档、生成文件和本地校验只在本机进行，不隐含 SSH、上传、远程命令或真实网络测试授权。
- 用户禁止在路由器或服务器上测试时，遵守该限制；不运行 SOCKS、出口 IP、DNS、STUN、断线、服务重启或整机重启测试。也不要从管理电脑发探针来间接测试这些设备。可以输出待执行步骤，明确标为未验证。
- 对实际部署，先利用已有参数和用户提供的输出确认适用性。缺少现场信息时只询问必要项；禁止设备访问时不要为补全信息自行登录。已获准的部署步骤无需重复请求批准；影响全网的断线/重启验收需在用户允许的范围内执行。
- 私钥、UUID、生成目录和设备访问凭据不写入仓库或普通报告。只把生成的 `router/` 传到路由器，服务端私钥留在服务端。使用已有 SSH 认证方式，不要求用户把密码写入文档。

## 选择工作路径

1. **确认拓扑与参数**：读取 [references/preflight.md](references/preflight.md)。自动应用脚本仅支持新安装、fw4/nftables、单 DHCP IPv4 WAN、单静态 LAN、单 dnsmasq，且 LAN/WAN 使用不同设备。PPPoE、多 WAN、VLAN/访客网、旁路由、fw3、现有 VPN 或同名安装不能直接套用。
2. **生成配置或准备 VPS**：读取 [references/server.md](references/server.md)。记录公网 IPv4、SNI、CPU/ABI、逻辑接口与实际 L3 设备、区域名和不重叠的私有 `/30`。离线准备缺少真实参数时输出参数清单；不要把示例 IP 当真实部署配置。已有 X25519 密钥文件时，生成器可在本地运行，不需要联网。
3. **安装路由器**：读取 [references/router.md](references/router.md)，同时准备 [references/operations.md](references/operations.md) 的恢复步骤。真实 SOCKS 验证成功才创建 `preflight-ok`；不允许测试时停在离线准备，不伪造标记或绕过检查。
4. **获准线上验收**：读取 [references/validation.md](references/validation.md)。分别记录 HTTP、DNS、STUN/WebRTC、IPv6、断线保护和持久化结果；配置解析成功不能替代真实握手。
5. **维护、升级或回滚**：读取 [references/operations.md](references/operations.md)。升级不重新生成凭据；回滚使用同一次安装的备份。新安装脚本不是升级脚本。

只读取当前步骤需要的参考文件。所有参考文件内的相对脚本路径均以本 Skill 根目录为基准。

## 配套文件

| 文件 | 用途与副作用 |
|---|---|
| `scripts/generate-configs.py` | 只在新输出目录生成配置，拒绝覆盖；从 `assets/templates/` 渲染 |
| `scripts/download-xray.py` | 从官方 GitHub 下载锁定版本并核对同源 SHA256；需要联网 |
| `scripts/apply-router.sh` | 修改路由器网络、DNS、防火墙及服务；仅在目标路由器授权安装时运行 |
| `scripts/rollback-router.sh` | 恢复路由器安装前的网络状态，可能重新允许直连及 IPv6 |
| `scripts/check-stun.py` | 对公共 STUN 服务发 UDP 请求；属于线上验收，不能当本地自检运行 |
| `scripts/validate-local.py` | 临时目录内检查生成器、文件权限和语法；不下载、不发网络请求、不执行部署脚本 |
| `assets/templates/` | JSON、systemd、procd、nftables 和 sysctl 模板的唯一来源，不直接执行未渲染模板 |

本地检查命令（在 Skill 根目录）：

```sh
python3 scripts/validate-local.py
```

## 不可丢失的部署约束

- `WAN_IF` 是 UCI 逻辑名，`WAN_DEV` 是实际 L3 设备，接口绑定和 nftables 使用后者。MT7621/mipsel 无硬浮点时选 `xray_softfloat`；不强装与固件不匹配的 kmod。
- 客户端使用 `Password (PublicKey)`，不能误用 `Hash32`；保留客户端 `xtls-rprx-vision-udp443` 与服务端 `xtls-rprx-vision` 的区别。
- 修改 VPS 防火墙前保留实际 SSH 端口、已有业务端口和恢复路径；文档的 TCP 22 只是示例。
- 路由器应用后有 10 分钟自动回滚。基本验收通过才写 `confirmed`；确认前不重启或断电。用户禁止基本验收时，不开始网络切换。
- 隧道失效时的断网是保护行为，不通过放开 WAN 或切回运营商 DNS 来掩盖故障。明确回滚才恢复原网络行为。

## 交付

说明生成文件位置、采用的参数与版本、已做检查、未验证项目。实际部署还需记录备份位置、确认标记状态和恢复入口。离线检查通过只能说明结构与生成行为符合预期，不宣称路由器固件兼容、网络连通或账号服务可用。

升级配置字段或核对版本时，按需查阅 [Xray 固定版本发布](https://github.com/XTLS/Xray-core/releases/tag/v26.10.29)、[TUN 配置](https://xtls.github.io/en/config/inbounds/tun.html)、[REALITY 配置](https://xtls.github.io/en/config/transports/reality.html) 和 [fw4 自定义规则说明](https://github.com/openwrt/firewall4/blob/master/root/usr/share/nftables.d/README)。原有部署经验不替代目标环境验证。
