# PyPI 发布指南

## 首次发布配置

### 方式一：Trusted Publishing（推荐）

无需管理 token，使用 GitHub OIDC 认证。

**步骤：**

1. 登录 [PyPI](https://pypi.org/)（没有账号先注册）

2. 进入 Account settings → Publishing

3. 添加 Trusted Publisher：
   - PyPI Project Name: `marmot`（如果项目不存在，勾选 "This is a new project"）
   - Owner: 你的 GitHub 用户名
   - Repository name: `marmot`
   - Workflow name: `publish.yml`
   - Environment name: 留空

4. 保存后，创建 GitHub Release 即可自动发布

### 方式二：API Token

**步骤：**

1. 登录 PyPI → Account settings → API tokens

2. 创建新 token（选择 "Entire account" 或特定项目）

3. 在 GitHub 仓库设置中添加 Secret：
   - Settings → Secrets and variables → Actions
   - Name: `PYPI_API_TOKEN`
   - Value: 你的 token

4. 修改 `.github/workflows/publish.yml`，使用 token 认证：
   ```yaml
   - name: Publish to PyPI
     uses: pypa/gh-action-pypi-publish@release/v1
     with:
       password: ${{ secrets.PYPI_API_TOKEN }}
   ```

## 发布流程

### 自动发布（推荐）

```bash
# 1. 更新版本号
# 编辑 pyproject.toml: version = "0.1.0" → "0.1.1"

# 2. 提交代码
git add .
git commit -m "chore: bump version to 0.1.1"
git push

# 3. 创建 tag 和 release
git tag v0.1.1
git push origin v0.1.1

# 4. 在 GitHub 上创建 Release
# 自动触发发布到 PyPI
```

### 手动发布

```bash
# 1. 构建
python -m build

# 2. 检查
twine check dist/*

# 3. 上传到 TestPyPI（测试）
twine upload --repository testpypi dist/*

# 4. 测试安装
pip install --index-url https://test.pypi.org/simple/ marmot

# 5. 确认无误后，上传到 PyPI
twine upload dist/*
```

## 版本号规范

遵循 [语义化版本](https://semver.org/lang/zh-CN/)：

- `0.x.x` — 开发阶段，API 可能变化
- `1.0.0` — 正式稳定版
- `1.0.1` — Bug 修复
- `1.1.0` — 新功能，向后兼容
- `2.0.0` — 重大变更，不兼容

## 注意事项

1. **版本不可覆盖**：PyPI 不允许重复上传同一版本
2. **包名先到先得**：尽快发布占位，防止被抢注
3. **README 会显示在 PyPI**：确保格式正确
4. **测试先发 TestPyPI**：验证流程后再发正式环境
5. **删除只能手动申请**：发布后无法删除，只能发新版本

## 相关链接

- PyPI: https://pypi.org/
- TestPyPI: https://test.pypi.org/
- 项目管理: https://pypi.org/manage/projects/
