# 2026-09-20 网站字号与可访问性修复上线

2026-09-20 完成网站字号和基础可访问性修复并部署到[官网与工作台](https://agent-communication.online)。本次调整提高正文、表单和辅助文字的可读性，补齐键盘焦点、跳过链接、响应式布局和触摸目标；不会把本记录当作完整 WCAG 认证。

## 固定版本

| 仓库或产物 | 发布标识 |
| --- | --- |
| Deploy（部署源码） | `c1bd0a9152f9285cd4690f803ba1b890ea1577be` |
| Web（应用源码） | `21dcb5d26361f936f8d914712a8007f25bc39b04` |
| Web（静态官网跟随修复） | `3a2b2517f238023b4c6800a41bf51f7b314a4eee` |
| Platform | `2ed906d28f27d76cbdcf463b4031d364aae63486` |
| SDK | `ecf829dc31099ea889abf2633cbe47afd522eab5` |
| Web Docker 镜像 | `sha256:5a6029f249a64d8bb655b19b432e3bd43bcc3f7e3e28850ef686e04347e33c18` |

静态官网由 nginx 以只读目录挂载，跟随静态提交同步后无需重新构建 Web 应用镜像；镜像仍对应上表的 Web 应用源码。记录文件后续提交只更新文档，不改变上述应用版本和子模块引用。

## 变更和验收

- Web 组件将字号改为可随用户根字号缩放的 `rem`，正文和辅助文字提高到可读尺寸；窄屏表单输入保持至少 16px，控件、链接和通知补充可见焦点、键盘语义和足够触摸区域。
- 官网使用一致的字号尺度、响应式换行和跳过链接；FAQ 链接触摸区域补足到 44px。
- Web Node 测试 173 项通过；生产构建通过。构建仍报告原有的 React hook 依赖提示和 Next.js 多锁文件提示，这两项不影响构建结果。
- 使用内置浏览器检查首页和注册页的 320px 窄屏布局：页面无横向溢出，表单输入为 16px，注册页控件可见且可操作。线上 HTTPS 首页、登录、注册、健康接口和静态安装说明可访问；未创建或修改生产账户，也未发送生产消息。
- 完整自动化浏览器套件未在本机运行，原因是本地环境没有可用的绑定 Chromium 服务；本次记录只包含已执行的源码、构建、内置浏览器和线上检查结果。

## 数据保留和回滚

发布前备份目录为 `/root/agent-comm-backups/a11y-20260920-21dcb5d`，包含部署配置、环境文件、Web/Platform 数据卷归档和发布前检查点。生产数据卷、`.env`、证书及 nginx 配置均保留。

回滚时先在服务器核对备份清单，再恢复旧 Deploy 提交 `cb0909d975e0b6e52ba9dd949fcc2753e0aaaa7b` 及其原 Web 子模块 `739136e422c8dab516b661740a454a50db079929`，并使用保留的旧 Web 镜像 `sha256:bf4d40418a55bb3ab72e947df4fde46b9dbab46e094820fbcdf4832c2d5c3754`。恢复源码和镜像后执行：

```sh
cd /root/agent-collaboration-deploy
git fetch origin main
git checkout cb0909d975e0b6e52ba9dd949fcc2753e0aaaa7b
git submodule update --init --recursive
docker image tag agent-collaboration-web:rollback-a11y-20260920-21dcb5d agent-collaboration-deploy-web:latest
docker compose up -d --no-deps --no-build web platform
docker exec agent-nginx nginx -t
docker exec agent-nginx nginx -s reload
```

回滚保留当前数据库卷，不用备份覆盖新数据；如果应用迁移已改变数据结构，必须先确认旧镜像兼容性，再执行回滚。通用流程见[部署指南](../operations/DEPLOYMENT.md)。
