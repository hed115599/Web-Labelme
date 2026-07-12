from flask import Flask, jsonify, request, send_from_directory, render_template
from PIL import Image
import os
import json
import argparse

app = Flask(__name__)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# 默认标注目录：图片和标注放在同一个文件夹
DEFAULT_DATA_DIR = os.path.join(BASE_DIR, "data", "images")

# 启动时可通过参数覆盖
DATA_DIR = DEFAULT_DATA_DIR


def is_image_file(filename):
    return filename.lower().endswith((".jpg", ".jpeg", ".png", ".bmp", ".webp"))


def get_annotation_path(image_name):
    json_name = os.path.splitext(image_name)[0] + ".json"
    return os.path.join(DATA_DIR, json_name)


def has_annotation(image_name):
    """判断图片是否已标注：JSON 文件存在且 shapes 非空"""
    json_path = get_annotation_path(image_name)
    if not os.path.exists(json_path):
        return False
    try:
        with open(json_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return bool(data.get("shapes"))
    except (json.JSONDecodeError, OSError):
        return False


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/api/images", methods=["GET"])
def list_images():
    files = [f for f in os.listdir(DATA_DIR) if is_image_file(f)]
    files.sort()

    # ?detail=1 返回带标注状态的详细信息
    if request.args.get("detail"):
        return jsonify([
            {"name": f, "annotated": has_annotation(f)}
            for f in files
        ])

    return jsonify(files)


@app.route("/images/<path:filename>", methods=["GET"])
def get_image(filename):
    return send_from_directory(DATA_DIR, filename)


@app.route("/api/annotation", methods=["GET"])
def get_annotation():
    image_name = request.args.get("image")
    if not image_name:
        return jsonify({"error": "missing image parameter"}), 400

    image_name = os.path.basename(image_name)
    image_path = os.path.join(DATA_DIR, image_name)

    if not os.path.exists(image_path):
        return jsonify({"error": "image not found"}), 404

    json_path = get_annotation_path(image_name)

    with Image.open(image_path) as img:
        width, height = img.size

    if os.path.exists(json_path):
        with open(json_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        data["version"] = data.get("version", "5.0.1")
        data["flags"] = data.get("flags", {})
        data["shapes"] = data.get("shapes", [])
        data["imagePath"] = image_name
        data["imageData"] = data.get("imageData", None)
        data["imageWidth"] = data.get("imageWidth", width)
        data["imageHeight"] = data.get("imageHeight", height)

        for shape in data["shapes"]:
            shape["flags"] = shape.get("flags", {})
            if "group_id" not in shape:
                shape["group_id"] = None

        return jsonify(data)

    return jsonify({
        "version": "5.0.1",
        "flags": {},
        "shapes": [],
        "imagePath": image_name,
        "imageData": None,
        "imageHeight": height,
        "imageWidth": width
    })


@app.route("/api/annotation", methods=["POST"])
def save_annotation():
    data = request.get_json()
    if not data:
        return jsonify({"error": "invalid json"}), 400

    image_path = data.get("imagePath")
    annotation = data.get("annotation")

    if not image_path or annotation is None:
        return jsonify({"error": "missing imagePath or annotation"}), 400

    image_name = os.path.basename(image_path)

    # 安全检查：只允许保存目录中真实存在的图片对应的标注
    if not os.path.exists(os.path.join(DATA_DIR, image_name)):
        return jsonify({"error": "image not found"}), 404

    json_path = get_annotation_path(image_name)

    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(annotation, f, ensure_ascii=False, indent=2)

    return jsonify({
        "success": True,
        "saved": os.path.basename(json_path),
        "annotated": bool(annotation.get("shapes"))
    })


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Simple image annotation server")
    parser.add_argument(
        "--data-dir",
        default=DEFAULT_DATA_DIR,
        help="要标注的文件夹路径。默认图片和标注文件保存在同一个文件夹中"
    )
    parser.add_argument(
        "--port",
        type=int,
        default=5000,
        help="服务端口，默认 5000"
    )
    args = parser.parse_args()

    DATA_DIR = os.path.abspath(args.data_dir)
    os.makedirs(DATA_DIR, exist_ok=True)

    print(f"Using data directory: {DATA_DIR}")
    print("Images and annotations will be stored in the same folder.")

    app.run(debug=True, host="0.0.0.0", port=args.port)
