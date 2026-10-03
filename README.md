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

仓库必须公开。推送后打开：

Settings → Pages → Build and deployment → Source 选 **Deploy from a branch** → Branch 选 `main` / `/ (root)` → Save

几分钟后 Sileo 添加：`https://kmkm209.github.io/sileo`
