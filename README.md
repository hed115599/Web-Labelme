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

---
```bash
pip install Flask Pillow
```

&num;&num;&num; 2&period; 启动服务

&ast;&ast;使用默认目录与端口启动：&ast;&ast;
默认数据存放于 &grave;&period;&sol;data&sol;images&grave;，服务端口为 &grave;5000&grave;。
&grave;&grave;&grave;bash
python app.py
&grave;&grave;&grave;

&ast;&ast;自定义数据路径与端口启动：&ast;&ast;
你可以通过命令行参数 &grave;&hyphen;&hyphen;data&hyphen;dir&grave; 指定任意包含图片的文件夹，并通过 &grave;&hyphen;&hyphen;port&grave; 修改端口：
&grave;&grave;&grave;bash
python app.py --data-dir /path/to/your/dataset --port 8080
&grave;&grave;&grave;

&num;&num;&num; 3&period; 开始标注
打开浏览器，访问：&grave;http://localhost:5000&grave; （或你指定的对应 IP 与端口），即可看到前端标注控制台。
