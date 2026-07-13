# Web-Labelme
这是一个基于 **Flask (Python)** 后端与 **HTML5/JS** 前端构建的轻量级、免安装在线图像标注工具。其数据格式完全兼容经典标注软件 **Labelme**，支持在同一目录下直接读取图片并保存标准格式的 `.json` 标注文件。

通过该工具，你可以轻松地将标注任务部署在服务器上，实现多人团队的远程/在线协同数据标注。

---

## 🚀 项目特点

* **免安装客户端**：前端基于纯 Web 环境，标注人员只需浏览器即可开始工作。
* **无缝兼容 Labelme**：自动生成符合 Labelme 规范的 `json` 格式，支持 `shapes`、`flags`、`imagePath` 等字段，标注结果可直接用于训练或二次微调。
* **状态实时同步**：支持后台实时检测数据的标注状态（已标注/未标注），防止重复标注。
* **单目录管理**：图片与 `.json` 标签存储在同一个文件夹内，方便管理、打包与迁移。
* **灵活启动**：支持命令行参数自定义标注数据路径以及服务端口。
* **任务分配**：支持分配任务给不同用户
![项目截图](./screenshot.png)

---
## 快速开始
### 安装环境
```bash
pip install Flask Pillow
```

### 启动服务
```bash
python app.py --data-dir /path/to/your/dataset --port 5000
```
或者分配不同任务给不同用户
```bash
python app.py --data-dir /path/to/your/dataset --port 5000 --user-quotas '{"user1":100,"user2":150,"user3":80}'
```

### 开始标注
打开浏览器，访问：`http://localhost:5000`（或你指定的对应 IP 与端口），即可看到前端标注控制台。



