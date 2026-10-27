# 共享在线版：当前状态和部署

## 工作流

员工登录 → 选择商品场景 / 数字人口播 / 爆款参考创作 / 已有素材剪辑 → 输入脚本并提交 → 后台队列 → 团队任务与成片下载。

当前可执行的是已有素材剪辑；脚本作为简报保存，尚不驱动镜头生成或自动选段。商品场景、数字人、参考分析提交后均保存为 `needs_provider`，明确告知生成服务未接入，不会虚构成片或自动扣费。接入后还需补齐模型轮询、生成素材入库、保留口播音轨、字幕对齐和审核。

爆款参考模式支持 TikTok 链接、目标市场和目标成片类型。目标市场是员工指定值，不是平台验证结果。Creative Center Top Ads 链接只提供广告灵感入口，不代表已覆盖自然流量爆款；系统不自动抓取或判断播放量。后续需确定官方可用数据来源和账号权限，再实现国家筛选、数据更新时间、热度排序与视频分析。参考创作应提炼结构并基于本商品事实改编，使用自有或授权的画面、人物与声音。

## 本机运行

```sh
cd /workspace/111
python team.py --create-user manager
python team.py --create-user employee1
python team.py
```

密码通过隐藏输入创建，至少 12 字符；没有默认密码，也不自动创建账号。默认监听 127.0.0.1:8000。`server.py` 为旧的本地无登录原型，切勿对公网暴露；共享版必须运行 `team.py`。

## 服务器部署准备

提供 Dockerfile，尚未部署到公网。本机 Python 集成测试通过；容器构建拉取 Python 基础镜像成功，但容器内访问 Debian 软件源被拒绝，FFmpeg 安装阶段受阻，镜像构建尚未验证完成。需在能访问官方 Debian 软件源的构建环境重试。示例：

```sh
docker build -t clipcart .
docker volume create clipcart-data
docker run --rm -it -v clipcart-data:/app/.runtime clipcart python team.py --create-user manager
docker run -d --name clipcart --restart unless-stopped -p 127.0.0.1:8000:8000 -v clipcart-data:/app/.runtime clipcart
```

服务器前方配置 HTTPS 反向代理，保留 Host 与 Origin，不直接暴露 Python 端口。容器默认 Secure Cookie，需要 HTTPS；仅本机 HTTP 调试可设 COOKIE_SECURE=0。密钥经安全环境变量注入，不放入镜像、仓库或聊天。数据库与所有素材在同一持久卷，需一起备份；不要在已有容器重启时使用初始化删除命令。

## 团队范围与限制

- 登录用户均为同一团队，能查看所有团队任务与素材。无部门隔离、管理员角色或多租户。
- 密码 PBKDF2 哈希、会话 HttpOnly/SameSite，登录失败限流；会话 12 小时有效。上线还需按实际规模做安全和并发评估。
- SQLite 持久化账号、会话与任务；单个后台线程串行剪辑，限制积压任务 50 条。
- 服务重启后排队任务继续，运行中任务标记失败，员工可重新提交；待接入任务不会自动执行。
- 不支持多个应用副本；生产横向扩容前应迁移数据库、对象存储和外部队列。
- 任务最近 100 条可见，浏览器每 5 秒刷新。暂未实现审核状态流转、生成服务重试、配额或费用统计。
- TikTok 商用音乐库仍为官方跳转入口，音乐在 TikTok 发布时添加。

## 可替换生成接口

`providers.py` 定义统一的脚本请求、异步提交、状态轮询和结果结构。目前注册表为空，没有已安装的真实模型适配器；后续确定服务商后实现并验证适配器，再将它接入任务执行器。参考分析和国家热度检索需各自实现数据适配，不能用模型配置替代真实平台数据。

## Render 首次部署测试版

先将代码上传到 GitHub，确认 `main` 包含 `Dockerfile`、`team.py`、`server.py`、`providers.py` 和 `web/`，再在 Render 创建 Docker Web Service。仓库根目录部署，Dockerfile 路径默认 `./Dockerfile`；不填写 Go 构建或启动命令。

在 Render 的 Environment Variables 添加：

- `BOOTSTRAP_USERNAME`：首次登录用户名，例如 `manager`。
- `BOOTSTRAP_PASSWORD`：自己设置的至少 12 字符密码，作为秘密值填写，不发到聊天或提交到仓库。

容器已配置 `BIND_HOST=0.0.0.0`、`COOKIE_SECURE=1`；端口由 Render 提供的 `PORT` 自动读取。健康检查路径可设为 `/healthz`。首次空数据库启动时自动创建初始账号；已有用户时不会重新创建或重置密码。

Free 仅用于界面临时测试，没有持久磁盘；重启、休眠或重新部署可能丢失本地任务与文件，并通过环境变量重新初始化账号，不适合存放员工正式数据。正式使用需选择支持持久磁盘的方案，挂载 `/app/.runtime` 并验证应用用户对磁盘有写权限；费用以 Render 页面为准。没有持久磁盘时不要删除初始化环境变量，否则数据重置后需要重新配置才能创建登录账号。

点击 Deploy 后，只有日志显示服务启动并且浏览器能打开 Render 提供的网址、完成登录，才能确认网站部署成功。当前尚未执行 Render 部署。AI 视频与数字人生成也仍待实际接入。
