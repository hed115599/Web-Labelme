from flask import Flask, jsonify, request, send_from_directory, render_template
from PIL import Image
from pathlib import Path
import argparse
import json
import os
import random
import tempfile


app = Flask(__name__)

BASE_DIR = Path(__file__).resolve().parent
DEFAULT_DATA_DIR = BASE_DIR / "data" / "images"

DATA_DIR = DEFAULT_DATA_DIR

# 示例：
# {
#     "车辆": ["car", "vehicle"],
#     "行人": ["person", "pedestrian"]
# }
FILENAME_GROUPS = {}

# 示例：
# {
#     "user1": 100,
#     "user2": 200
# }
USER_QUOTAS = {}

# {
#     "user1": {"a/1.jpg", "a/2.jpg"},
#     "user2": {"b/1.jpg"}
# }
USER_ASSIGNMENTS = {}

ASSIGNMENT_FILE = None
ASSIGNMENT_SEED = 12345

IMAGE_SUFFIXES = {
    ".jpg",
    ".jpeg",
    ".png",
    ".bmp",
    ".webp"
}
IGNORED_DIRECTORY_NAMES = {
    ".ipynb_checkpoints"
}


def is_image_file(filename):
    return Path(filename).suffix.lower() in IMAGE_SUFFIXES


def normalize_relative_path(path):
    """
    将路径转换为统一的 POSIX 相对路径，例如：
    folder\\a.jpg -> folder/a.jpg
    """
    return Path(str(path).replace("\\", "/")).as_posix().lstrip("/")

def contains_ignored_directory(path):
    """
    检查相对路径中是否包含需要忽略的目录。
    """
    normalized_path = normalize_relative_path(path)

    return any(
        part in IGNORED_DIRECTORY_NAMES
        for part in Path(normalized_path).parts
    )


def get_safe_data_path(relative_path):
    """
    防止 ../ 目录穿越，并禁止访问忽略目录。
    """
    relative_path = normalize_relative_path(relative_path)

    if contains_ignored_directory(relative_path):
        return None

    root = DATA_DIR.resolve()
    target = (root / relative_path).resolve()

    try:
        target.relative_to(root)
    except ValueError:
        return None

    return target


def get_image_path(image_name):
    path = get_safe_data_path(image_name)

    if (
        path is None
        or not path.is_file()
        or not is_image_file(path.name)
    ):
        return None

    return path


def get_annotation_path(image_name):
    """
    图片和标注放在同一个目录。

    例如：
        sub/a.jpg
        sub/a.json
    """
    image_path = get_safe_data_path(image_name)

    if image_path is None:
        return None

    return image_path.with_suffix(".json")


def scan_images():
    """
    递归扫描 DATA_DIR，返回相对于 DATA_DIR 的路径。

    扫描时跳过 .ipynb_checkpoints 等忽略目录。
    """
    if not DATA_DIR.exists():
        return []

    result = []

    for root, directory_names, filenames in os.walk(DATA_DIR):
        # 原地修改目录列表，阻止 os.walk 进入忽略目录
        directory_names[:] = [
            directory_name
            for directory_name in directory_names
            if directory_name not in IGNORED_DIRECTORY_NAMES
        ]

        root_path = Path(root)

        for filename in filenames:
            if not is_image_file(filename):
                continue

            path = root_path / filename
            relative = path.relative_to(DATA_DIR).as_posix()

            result.append(relative)

    result.sort(key=lambda value: value.lower())

    return result


def has_annotation(image_name):
    """
    JSON 文件存在且 shapes 非空时，视为已标注。
    """
    json_path = get_annotation_path(image_name)

    if json_path is None or not json_path.exists():
        return False

    try:
        with json_path.open("r", encoding="utf-8") as file:
            data = json.load(file)

        return bool(data.get("shapes"))
    except (json.JSONDecodeError, OSError, TypeError):
        return False


def get_image_folder(image_name):
    """
    返回图片所属相对目录。

    根目录图片返回空字符串。
    """
    parent = Path(image_name).parent.as_posix()

    return "" if parent == "." else parent


def get_filename_groups(image_name):
    """
    根据图片文件名是否包含关键词进行分类。

    只检查文件名，不检查目录名。
    匹配时忽略大小写。

    一张图片可以属于多个分类。
    """
    if not FILENAME_GROUPS:
        return []

    filename = Path(image_name).name.casefold()
    matched = []

    for group_name, keywords in FILENAME_GROUPS.items():
        if any(keyword.casefold() in filename for keyword in keywords):
            matched.append(group_name)

    if not matched:
        matched.append("__other__")

    return matched


def read_json_argument(value, argument_name):
    """
    支持两种参数形式：

    1. 直接传 JSON：
       --filename-groups '["_left_", "_right_"]'

    2. 从 JSON 文件读取：
       --filename-groups @groups.json
    """
    if not value:
        return None

    try:
        if value.startswith("@"):
            file_path = Path(value[1:]).expanduser().resolve()

            with file_path.open("r", encoding="utf-8") as file:
                return json.load(file)

        return json.loads(value)

    except (OSError, json.JSONDecodeError) as error:
        raise ValueError(
            f"{argument_name} 不是有效的 JSON: {error}"
        ) from error


def normalize_filename_groups(data):
    """
    文件名分类使用字符串列表。

    例如：

    [
        "_left_",
        "_right_",
        "#night#",
        "@rain@"
    ]

    返回：

    {
        "_left_": ["_left_"],
        "_right_": ["_right_"],
        "#night#": ["#night#"],
        "@rain@": ["@rain@"]
    }
    """
    if data is None:
        return {}

    if not isinstance(data, list):
        raise ValueError(
            "--filename-groups 必须是 JSON 字符串列表，"
            '例如：["_left_", "_right_", "#night#"]'
        )

    result = {}

    for value in data:
        if not isinstance(value, str):
            raise ValueError(
                "--filename-groups 中的每一项都必须是字符串"
            )

        value = value.strip()

        if not value:
            continue

        # 自动去重
        result[value] = [value]

    return result


def normalize_user_quotas(data):
    if data is None:
        return {}

    if not isinstance(data, dict):
        raise ValueError(
            "--user-quotas 必须是 JSON 对象/字典，"
            '例如：{"user1": 100, "user2": 200}'
        )

    result = {}

    for user, quota in data.items():
        user = str(user).strip()

        if not user:
            continue

        try:
            quota = int(quota)
        except (TypeError, ValueError) as error:
            raise ValueError(
                f"用户 {user} 的分配数量必须是整数"
            ) from error

        if quota < 0:
            raise ValueError(
                f"用户 {user} 的分配数量不能小于 0"
            )

        result[user] = quota

    return result


def atomic_write_json(path, data):
    """
    原子写入，避免写入过程中程序退出导致 JSON 损坏。
    """
    path.parent.mkdir(parents=True, exist_ok=True)

    fd, temp_name = tempfile.mkstemp(
        prefix=path.name + ".",
        suffix=".tmp",
        dir=str(path.parent)
    )

    try:
        with os.fdopen(fd, "w", encoding="utf-8") as file:
            json.dump(
                data,
                file,
                ensure_ascii=False,
                indent=2
            )

        os.replace(temp_name, path)
    except Exception:
        try:
            os.unlink(temp_name)
        except OSError:
            pass

        raise


def build_user_assignments(image_names):
    """
    根据 USER_QUOTAS 分配图片。

    特点：
    1. 同一张图片只分配给一个用户；
    2. 已经保存的分配结果优先保留；
    3. 新图片从剩余配额中继续分配；
    4. 分配结果持久化。
    """
    global USER_ASSIGNMENTS

    if not USER_QUOTAS:
        USER_ASSIGNMENTS = {}
        return

    valid_images = set(image_names)

    old_assignments = {}

    if ASSIGNMENT_FILE and ASSIGNMENT_FILE.exists():
        try:
            with ASSIGNMENT_FILE.open("r", encoding="utf-8") as file:
                saved = json.load(file)

            old_assignments = saved.get("assignments", {})
        except (OSError, json.JSONDecodeError, TypeError):
            old_assignments = {}

    result = {
        user: []
        for user in USER_QUOTAS
    }

    used_images = set()

    # 优先保留原来的分配结果
    for user, quota in USER_QUOTAS.items():
        saved_images = old_assignments.get(user, [])

        if not isinstance(saved_images, list):
            continue

        for image_name in saved_images:
            image_name = normalize_relative_path(image_name)

            if len(result[user]) >= quota:
                break

            if (
                image_name in valid_images
                and image_name not in used_images
            ):
                result[user].append(image_name)
                used_images.add(image_name)

    # 将尚未分配的图片按固定种子打乱
    unassigned = [
        image_name
        for image_name in image_names
        if image_name not in used_images
    ]

    random.Random(ASSIGNMENT_SEED).shuffle(unassigned)

    cursor = 0

    for user, quota in USER_QUOTAS.items():
        remaining = quota - len(result[user])

        if remaining <= 0:
            continue

        selected = unassigned[cursor:cursor + remaining]

        result[user].extend(selected)
        used_images.update(selected)

        cursor += len(selected)

    USER_ASSIGNMENTS = {
        user: set(image_names)
        for user, image_names in result.items()
    }

    if ASSIGNMENT_FILE:
        atomic_write_json(
            ASSIGNMENT_FILE,
            {
                "version": 1,
                "seed": ASSIGNMENT_SEED,
                "quotas": USER_QUOTAS,
                "assignments": result
            }
        )


def get_request_user(data=None):
    """
    用户可以通过以下方式传入：
    GET:  ?user=user1
    POST: {"user": "user1"}

    如果配置了用户但没有传 user，默认使用第一个用户。
    """
    user = request.args.get("user")

    if not user and isinstance(data, dict):
        user = data.get("user")

    if user:
        user = str(user).strip()

    if not USER_QUOTAS:
        return None

    if not user:
        return next(iter(USER_QUOTAS), None)

    return user


def validate_user(user):
    if not USER_QUOTAS:
        return None

    if user not in USER_QUOTAS:
        return (
            jsonify({
                "error": "invalid user",
                "message": f"未知用户: {user}"
            }),
            400
        )

    return None


def user_can_access_image(user, image_name):
    if not USER_QUOTAS:
        return True

    return image_name in USER_ASSIGNMENTS.get(user, set())


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/api/config", methods=["GET"])
def get_config():
    users = []

    for user, quota in USER_QUOTAS.items():
        users.append({
            "name": user,
            "quota": quota,
            "assigned": len(USER_ASSIGNMENTS.get(user, set()))
        })

    filename_groups = [
        {
            "id": group_name,
            "label": group_name,
            "keywords": keywords
        }
        for group_name, keywords in FILENAME_GROUPS.items()
    ]

    if FILENAME_GROUPS:
        filename_groups.append({
            "id": "__other__",
            "label": "其他/未匹配",
            "keywords": []
        })

    return jsonify({
        "users": users,
        "defaultUser": users[0]["name"] if users else None,
        "filenameGroups": filename_groups,
        "assignmentEnabled": bool(USER_QUOTAS)
    })


@app.route("/api/images", methods=["GET"])
def list_images():
    user = get_request_user()

    user_error = validate_user(user)

    if user_error:
        return user_error

    files = scan_images()

    if USER_QUOTAS:
        files = [
            image_name
            for image_name in files
            if user_can_access_image(user, image_name)
        ]

    if request.args.get("detail"):
        return jsonify([
            {
                "name": image_name,
                "folder": get_image_folder(image_name),
                "groups": get_filename_groups(image_name),
                "annotated": has_annotation(image_name)
            }
            for image_name in files
        ])

    return jsonify(files)


@app.route("/images/<path:filename>", methods=["GET"])
def get_image(filename):
    image_path = get_image_path(filename)

    if image_path is None:
        return jsonify({"error": "image not found"}), 404

    relative_path = image_path.relative_to(DATA_DIR).as_posix()

    return send_from_directory(
        str(DATA_DIR),
        relative_path
    )


@app.route("/api/annotation", methods=["GET"])
def get_annotation():
    image_name = request.args.get("image")

    if not image_name:
        return jsonify({
            "error": "missing image parameter"
        }), 400

    image_name = normalize_relative_path(image_name)
    user = get_request_user()

    user_error = validate_user(user)

    if user_error:
        return user_error

    if not user_can_access_image(user, image_name):
        return jsonify({
            "error": "image is not assigned to this user"
        }), 403

    image_path = get_image_path(image_name)

    if image_path is None:
        return jsonify({
            "error": "image not found"
        }), 404

    json_path = get_annotation_path(image_name)

    try:
        with Image.open(image_path) as image:
            width, height = image.size
    except OSError:
        return jsonify({
            "error": "cannot open image"
        }), 500

    if json_path and json_path.exists():
        try:
            with json_path.open("r", encoding="utf-8") as file:
                data = json.load(file)
        except (OSError, json.JSONDecodeError):
            return jsonify({
                "error": "invalid annotation json"
            }), 500

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
    data = request.get_json(silent=True)

    if not isinstance(data, dict):
        return jsonify({
            "error": "invalid json"
        }), 400

    image_name = data.get("imagePath")
    annotation = data.get("annotation")
    user = get_request_user(data)

    user_error = validate_user(user)

    if user_error:
        return user_error

    if not image_name or not isinstance(annotation, dict):
        return jsonify({
            "error": "missing imagePath or annotation"
        }), 400

    image_name = normalize_relative_path(image_name)

    if not user_can_access_image(user, image_name):
        return jsonify({
            "error": "image is not assigned to this user"
        }), 403

    image_path = get_image_path(image_name)

    if image_path is None:
        return jsonify({
            "error": "image not found"
        }), 404

    json_path = get_annotation_path(image_name)

    if json_path is None:
        return jsonify({
            "error": "invalid annotation path"
        }), 400

    # 不信任前端传来的 imagePath，后端强制设置
    annotation["imagePath"] = image_name
    annotation["imageData"] = None

    try:
        atomic_write_json(json_path, annotation)
    except OSError as error:
        return jsonify({
            "error": "save failed",
            "message": str(error)
        }), 500

    annotated = bool(annotation.get("shapes"))

    return jsonify({
        "success": True,
        "saved": json_path.relative_to(DATA_DIR).as_posix(),
        "annotated": annotated
    })


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Simple image annotation server"
    )

    parser.add_argument(
        "--data-dir",
        default=str(DEFAULT_DATA_DIR),
        help="要标注的文件夹路径，支持递归扫描子目录"
    )

    parser.add_argument(
        "--port",
        type=int,
        default=5000,
        help="服务端口，默认 5000"
    )

    parser.add_argument(
        "--filename-groups",
        default="",
        help=(
            "文件名分类 JSON。"
            "例如：'{\"车辆\":[\"car\",\"vehicle\"],\"行人\":[\"person\"]}'；"
            "也可以使用 @groups.json"
        )
    )

    parser.add_argument(
        "--user-quotas",
        default="",
        help=(
            "用户标注数量 JSON。"
            "例如：'{\"user1\":100,\"user2\":200}'；"
            "也可以使用 @users.json"
        )
    )

    parser.add_argument(
        "--assignment-file",
        default="",
        help="用户分配结果保存路径"
    )

    parser.add_argument(
        "--assignment-seed",
        type=int,
        default=12345,
        help="随机分配种子，默认 12345"
    )

    args = parser.parse_args()

    DATA_DIR = Path(args.data_dir).expanduser().resolve()
    DATA_DIR.mkdir(parents=True, exist_ok=True)

    try:
        FILENAME_GROUPS = normalize_filename_groups(
            read_json_argument(
                args.filename_groups,
                "--filename-groups"
            )
        )

        USER_QUOTAS = normalize_user_quotas(
            read_json_argument(
                args.user_quotas,
                "--user-quotas"
            )
        )
    except ValueError as error:
        parser.error(str(error))

    ASSIGNMENT_SEED = args.assignment_seed

    if args.assignment_file:
        ASSIGNMENT_FILE = Path(
            args.assignment_file
        ).expanduser().resolve()
    else:
        ASSIGNMENT_FILE = (
            DATA_DIR / ".web_labelme_assignments.json"
        )

    all_images = scan_images()
    build_user_assignments(all_images)

    print(f"Using data directory: {DATA_DIR}")
    print(f"Found images: {len(all_images)}")
    print(f"Filename groups: {FILENAME_GROUPS or 'disabled'}")
    print(f"User quotas: {USER_QUOTAS or 'disabled'}")

    if USER_QUOTAS:
        print(f"Assignment file: {ASSIGNMENT_FILE}")

        for user, quota in USER_QUOTAS.items():
            assigned_count = len(
                USER_ASSIGNMENTS.get(user, set())
            )

            print(
                f"User {user}: "
                f"quota={quota}, assigned={assigned_count}"
            )

    app.run(
        debug=True,
        host="0.0.0.0",
        port=args.port
    )
