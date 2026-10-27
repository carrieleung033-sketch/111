# GitHub skills 与工具

已通过现有 GitHub HTTPS 通道获取并检查 [openai/skills](https://github.com/openai/skills)，调研提交：49f948faa9258a0c61caceaf225e179651397431。

- [speech](https://github.com/openai/skills/tree/main/skills/.curated/speech)：适合下一阶段生成商品口播，依赖 OpenAI API 与密钥。
- [transcribe](https://github.com/openai/skills/tree/main/skills/.curated/transcribe)：适合转写原视频音轨，为字幕制作提供时间与文本数据。
- 本次仅获取并阅读相关技能，未安装到用户的全局技能目录，也未宣称已接入语音或转写。

Skill 是供编码代理遵循的工作指引与辅助脚本，不等同于应用内的视频模型接口。当前工作台剪辑由本机 FFmpeg 实际执行，AI 脚本使用独立 API 适配。

下一阶段可按原仓库的安装说明引入所需技能，先检查每个技能的许可与依赖，再接入应用。GitHub API 在本环境返回代理 403，但 Git HTTPS 克隆已成功，未请求额外 GitHub token。

## 已安装到本项目的技能

以下 10 项已通过官方 skill-installer 的 Git 模式下载到 `.agents/skills/`。每个技能的文件均与已检出的上游固定提交逐字节比对；`skills.lock.json` 记录来源、提交与 SHA-256 清单。外部技能目录被 Git 忽略，通过锁定清单恢复，避免将无关上游内容加入应用代码。

| 来源 | 已安装技能 | 对应用途 |
| --- | --- | --- |
| [HeyGen](https://github.com/heygen-com/skills) | heygen-avatar、heygen-video、heygen-translate | 数字人身份、口播生成、多语言本地化 |
| [Remotion](https://github.com/remotion-dev/skills) | remotion-best-practices、remotion-saas、remotion-captions | 视频模板、在线渲染架构、字幕开发 |
| [inference.sh](https://github.com/inference-sh/skills) | ai-video-generation、image-to-video、storyboard-creation、video-ad-specs | 商品场景、图生视频、分镜、广告格式 |

验证：`python tools/manage_skills.py --verify`。在新环境恢复：`python tools/manage_skills.py --install`。该脚本仅下载、比对与复制，不执行第三方安装脚本，不修改已有技能。目录存在但哈希不符时停止，保留本地修改。

### 安装与运行的区别

安装的是供 Codex/编码代理调用的 skill 指引与参考文件，不是已经上线的员工功能。在后续本项目的 Codex 会话中可以调用这些技能；若客户端未重新发现项目技能，需要重新加载会话。

- 当前 FFmpeg 剪辑已可运行。
- HeyGen CLI、inference.sh belt CLI 和相关登录目前未配置；未执行技能中的远程安装命令，也未调用付费生成。
- HeyGen API、商品视频生成服务仍需实现适配器并接入任务队列；仅安装 skill 不会改变 `needs_provider` 状态。
- Remotion 尚未作为应用依赖安装；如采用其团队商业渲染方案，需按其产品许可与方案配置，不把 skill 下载视为运行时许可。
- 没有发现并验证可直接完成“按国家查询 TikTok 全部爆款”的技能；不将视频生成或网页浏览技能当作真实平台数据源。

HeyGen 上游为 MIT，许可证已保留在 `docs/third-party/heygen-skills-LICENSE.txt`。Remotion skill 仓库根目录未见单独 LICENSE；inference.sh README 标记 MIT，但仓库根目录未见独立 LICENSE 文件。本次仅安装到项目环境并保留来源记录，未将它们打包进应用镜像。实际服务条款与代码许可分别核对。

先前获取的 `openai/skills` README 现已标记 deprecated，并推荐 `openai/plugins`；本次已检查新仓库，未将旧目录直接当作当前官方视频生成方案安装。
