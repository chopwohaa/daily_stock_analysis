# 1. 使用轻量级 Python 镜像
FROM python:3.10-slim

# 2. 设置环境变量（确保 Python 输出直接打印到日志）
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PORT=7860

# 3. 设置工作目录
WORKDIR /app

# 4. 安装系统依赖（如 git 等，有些库需要编译）
RUN apt-get update && apt-get install -y \
    build-essential \
    git \
    && rm -rf /var/lib/apt/lists/*

# 5. 先复制依赖文件（利用 Docker 缓存）
COPY requirements.txt .

# 6. 安装 Python 库
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# 7. 复制项目所有代码到镜像中
COPY . .

# 8. 暴露 Hugging Face 要求的 7860 端口
EXPOSE 7860

# 9. 启动命令
# 注意：这里需要根据你项目的实际启动脚本修改。
# 如果是启动 FastAPI: CMD ["uvicorn", "api.main:app", "--host", "0.0.0.0", "--port", "7860"]
# 如果是直接运行主脚本（如果是带 Web 界面的脚本）:
CMD ["streamlit", "run", "webui.py", "--server.port", "7860", "--server.address", "0.0.0.0"]
