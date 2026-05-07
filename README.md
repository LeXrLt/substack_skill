# Substack Scraper Skill

一个用于下载 [Substack](https://substack.com/) 用户帖子和笔记的 OpenClaw 技能。

只需用自然语言告诉 OpenClaw 你想下载谁的内容，它会自动完成一切。

---

## 安装

打开 OpenClaw 对话窗口，直接说：

> 帮我安装 substack 技能，地址是 https://github.com/LeXrLt/substack_skill.git

OpenClaw 会自动把技能克隆到本地并配置好环境，无需你手动操作任何命令。

---

## 使用方法

安装完成后，你随时可以用自然语言让 OpenClaw 帮你下载 Substack 内容。

### 下载某个用户的最近帖子

> 下载 substack 用户 takashiyasui 最近的 30 条帖子

### 指定数量

> 帮我抓取 substack 用户 a16z 最近的 100 条内容

### 下载全部内容

> 把 substack 用户 yamashida 的所有帖子都下载下来

### 英文也可以

> Fetch the latest 50 posts from @takashiyasui on Substack

---

## 下载的内容在哪里？

下载完成后，文件会保存在技能目录下的 `output` 文件夹中，按以下结构组织：

```
output/
└── 用户名/
    └── 2026/
        ├── 04/
        │   ├── 20260413_143533_post_Visual_Notes_003.txt
        │   ├── 20260414_122313_note_Six_months_old.txt
        │   └── ...
        └── 05/
            ├── 20260506_140155_post_Visual_Notes_004.txt
            ├── 20260505_134308_note_Editing_photos.txt
            └── ...
```

**文件命名规则**：`日期时间_类型_标题.txt`

- **日期时间**：发帖的精确时间（如 `20260506_140155` 表示 2026年5月6日 14:01:55）
- **类型**：`post`（文章）、`note`（笔记/动态）、`comment_restack`（转发）
- **标题**：帖子标题或内容摘要

---

## 每个文件里有什么？

打开任意一个 `.txt` 文件，你会看到：

**笔记/动态（note）示例：**
```
Type: note
Date: 2026-05-05 13:43:08 UTC
Comment ID: 254076027

============================================================

Editing photos from my recent trip to Kyoto...

------------------------------------------------------------
Attachments (5):
  [Image] https://substack-post-media.s3.amazonaws.com/public/images/xxx.jpeg
  [Image] https://substack-post-media.s3.amazonaws.com/public/images/yyy.jpeg
```

**文章（post）示例：**
```
Type: post
Title: Visual Notes 004
Subtitle: This season, this hour.
Date: 2026-05-06 14:01:55 UTC
URL: https://takashiyasui.substack.com/p/visual-notes-004

============================================================

(Preview) After years of walking around Tokyo...
```

---

## 常见问题

**Q：需要登录 Substack 账号吗？**

不需要。本技能只下载公开可见的内容。

**Q：下载速度慢怎么办？**

如果网络较慢，可以先少量下载试试，比如先下载 10 条看看效果。

**Q：可以下载付费文章的完整内容吗？**

不可以。付费文章只能获取到公开预览部分。

---

## 技术信息

- **语言**：Python 3
- **依赖**：requests
- **Skill 地址**：https://github.com/LeXrLt/substack_skill.git
