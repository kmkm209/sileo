# ZZ Repo（Sileo 自建源）

Sileo 添加：

```
https://kmkm209.github.io/sileo
```

## 本地构建

```bash
cd sileo-repo
python3 make_deb.py
python3 build.py
```

- 新包放到 `srcpkgs/<名字>/`，`DEBIAN/control` + `data/` 目录树
- 或直接把现成 `.deb` 丢进 `debs/`
- 再跑上面两条命令刷新 `Packages` / `Release`

## 发布到 GitHub Pages

1. GitHub 新建公开仓库 `sileo`（用户 `kmkm209`）
2. Settings → Pages → Source 选 **GitHub Actions**
3. 推送：

```bash
cd sileo-repo
git init
git add .
git commit -m "init sileo repo"
git branch -M main
git remote add origin https://github.com/kmkm209/sileo.git
git push -u origin main
```

4. 等 Actions 绿了，Sileo → 源 → 添加 `https://kmkm209.github.io/sileo`

仓库必须公开，Sileo 才能拉 `Release` / `Packages.bz2`。
