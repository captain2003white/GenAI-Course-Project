# Push to GitHub — 操作指南

**远程仓库:** `git@github.com:captain2003white/GenAI-Course-Project.git`
**SSH 已认证:** ✅ 以 `captain2003white` 身份通过认证

---

## 操作步骤

请在项目根目录（`d:\za\1\NLP\GenAI-Course-Project-main`）依次执行以下命令：

### 1. 初始化 Git

```bash
cd d:\za\1\NLP\GenAI-Course-Project-main
git init
```

### 2. 添加远程仓库

```bash
git remote add origin git@github.com:captain2003white/GenAI-Course-Project.git
```

### 3. 拉取远程分支信息

```bash
git fetch origin
```

### 4. 将本地改动摆在远程主分支之上

这一步把当前所有本地文件作为"相对于远程 commit 的改动"，不会丢失任何内容：

```bash
git reset origin/main
```

执行后你会看到类似这样的输出：
```
Unstaged changes after reset:
M      backend/main.py
M      backend/models/schemas.py
...（列出所有改动/新增的文件）
```

### 5. 添加所有文件并提交

```bash
git add .
git commit -m "Round 2: Multi-source architecture + web shopping sources (Platzi, Brave, eBay) + frontend enhancements"
```

### 6. 推送到 GitHub

```bash
git push -u origin main
```

---

## 验证

推送成功后，打开浏览器访问：
- **https://github.com/captain2003white/GenAI-Course-Project**

你应该能看到所有改动文件。

---

## 回滚方案（如果出错）

如果推送失败，先检查：

```bash
# 看远程有什么分支
git branch -r

# 如果需要强制覆盖远程（谨慎使用）
git push -u origin main --force
```

> ⚠️ `--force` 会覆盖远程仓库的历史，只有确定远程没有你需要保留的改动时才使用。
