# 带货视频生成与自动剪辑选型

核查日期：2026-10-28。适用规模：每月 100–500 条，每条 15–30 秒；先看效果与合格成片成本，再决定预算。下列为读取官方页面和 GitHub 文档的调研，尚未执行付费样片或完成质量评测。价格为美元，以服务商结算页为准。

## 当前工作台与脚本

`server.py` 已预留 OpenAI API，默认模型 `gpt-4o-mini`，通过 `OPENAI_MODEL` 可配置。仅当运行环境有可用的 `OPENAI_API_KEY` 时才发起模型请求；否则返回标有“模板草稿·未调用 AI”的固定模板。用户近期截图属于模板模式，并未调用模型。无法从开发机的环境变量确认 Render 的密钥状态。ChatGPT 网页会员不是该 API 的认证方式。

当前 FFmpeg 支持素材裁切、拼接与可选本地 BGM；尚未做语音生成、烧录字幕或根据脚本智能选镜头。默认 TikTok 官方音乐库模式导出无 BGM，音乐在 TikTok 发布时添加。切换到本地音乐模式、上传授权文件并调整音量后重新生成，才会把音乐编码进 MP4。素材原声目前不保留。

## 优先候选

| 方案 | 已核查内容 | 适合的位置 | 局限/验证事项 |
| --- | --- | --- | --- |
| fal Wan 2.2 A14B Turbo | 官方页面显示 720p $0.10/次，580p $0.075/次，480p $0.05/次 | 低成本商品图生视频首轮试稿 | 单次短片不是完整 15–30 秒带货成片；须验证时长、参数、商品外观一致性和实际扣费 |
| fal Kling 2.6 Pro 图生视频 | 无音频 $0.07/秒；原生音频 $0.14/秒；音频含语音控制 $0.168/秒 | 商品关键动态镜头的对照模型 | 东南亚语言语音、商品文字与细节必须用样片验证 |
| HeyGen | 已检查官方数字人/翻译 skill 与定价页；网页个人套餐与 API 是不同入口 | 数字人口播与多语言本地化 | 不把网页会员额度当成 API 额度；API 实际价格待核对，不能承诺最便宜 |
| Creatify | 官方页面提供 AI Actors、产品广告、模板及 API 入口 | 带货场景的一体化应用对照 | 页面同时有月付/年付显示；未核实 API 套餐价格，不拿个人套餐估算集成成本 |
| FFmpeg + 已安装 Remotion skills | 现有 FFmpeg 剪辑可运行；Remotion skill 已安装 | 共用字幕、配音、BGM、片头片尾与批量模板 | FFmpeg 仍需服务器算力与开发；Remotion 运行时尚未安装，团队用途需核对产品许可 |
| Shotstack | 官方页 PAYG $10/50 分钟，约 $0.10/30 秒纯渲染 | 当服务器算力不足时考虑云端剪辑 | 费用只代表剪辑/渲染，不含 AI 画面生成或数字人口播 |
| Creatomate | 官方页有 API、模板编辑器、预览 SDK 与 50 credits 试用 | 想减少模板编辑器开发量时比较 | 本次页面未提取出可靠具体套餐金额，不做价格排名 |

Wan Turbo 的低价适合优先验证，不等于已证明成片效果最佳。不要一次购买所有平台；用相同商品、脚本和目标语言做对照，以合格成片的总费用评估。

## 成本示例

按 Kling 2.6 Pro 无音频公开价计算，假设一次成功：

- 每条只生成 5 秒关键镜头，余下使用真实商品素材，组成 15–30 秒成片：生成画面 $0.35/条，每月 100–500 条约 $35–175。
- 每条全部生成 15 秒画面：$1.05/条，每月约 $105–525。
- 每条全部生成 30 秒画面（分多个片段生成）：$2.10/条，每月约 $210–1,050。

上述不含重试、脚本、配音、数字人、剪辑、存储、服务器与税费。原生音频会改变费用。若第一次合格率只有一半，预算不能仍按每条只生成一次估算。Wan Turbo 尚未实际验证可生成长度，不据单次价格推算完整成片月费。

建议小样比较：同一商品做 2 条商品场景视频、2 条数字人口播、1 条参考结构改编。检查商品真实性、东南亚语自然度、口型、字幕和镜头连贯性。样片调用需要可用账号及额度，本次未执行。

## 新发现的 GitHub 自动剪辑项目

### MoneyPrinterTurbo

来源：https://github.com/harry0703/MoneyPrinterTurbo

已下载并检查提交 `950ba89899d3b6ef080c18ad5791e7c9ead0ac66` 的 README、配置示例、MIT LICENSE 与 `docs/skill/SKILL.md`。提供脚本、素材、配音、字幕、BGM、成片流水线，也有 AI 视频素材提供商配置，适合参考其字幕与语音编排。普通素材匹配不保证出现用户实际商品，不能直接取代商品图生视频。

配套 skill 名为 `moneyprinterturbo-video`，其兼容性明确写 macOS/Windows，不直接当作本 Linux 云工作台的已验证生产插件。因此仅下载调研，未执行其安装/收费生成脚本，未接入员工任务。服务端项目是否复用需单独验证依赖、资源占用与语言支持。

### Editly

来源：https://github.com/mifi/editly

已下载并检查提交 `dc46674052eacd15ef6e0f563a58eb378b3804ad`，MIT。Node.js + FFmpeg 的声明式视频剪辑工具，支持标题、字幕、转场、混音、自动音量压低。它是工具库，不是 skill，也不会生成 AI 画面。依赖 headless-gl 等原生组件，初期保持已有 FFmpeg 更简单；需要更复杂转场时再评估。

## 官方核查来源

- Wan Turbo：https://fal.ai/models/fal-ai/wan/v2.2-a14b/image-to-video/turbo
- Kling：https://fal.ai/models/fal-ai/kling-video/v2.6/pro/image-to-video
- HeyGen：https://www.heygen.com/pricing （网页套餐；API 单独入口与计费待核）
- HeyGen skills：https://github.com/heygen-com/skills
- Creatify：https://creatify.ai/pricing
- Shotstack：https://shotstack.io/pricing/
- Creatomate：https://creatomate.com/pricing
- Remotion skills：https://github.com/remotion-dev/skills

没有将 GitHub README 中赞助商广告价格作为已验证官方模型报价，也没有把“支持某语言”当作已做过该语言质量测试。
