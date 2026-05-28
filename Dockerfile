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

# 新增：安装 Node.js（用于编译前端）
RUN curl -fsSL https://deb.nodesource.com/setup_18.x | bash - \
    && apt-get install -y nodejs \
    && rm -rf /var/lib/apt/lists/*

# 7. 复制项目所有代码到镜像中
COPY . .

# 8. 暴露 Hugging Face 要求的 7860 端口
EXPOSE 7860

# 9. 启动命令
# 注意：这里需要根据你项目的实际启动脚本修改。
# 如果是启动 FastAPI: CMD ["uvicorn", "api.main:app", "--host", "0.0.0.0", "--port", "7860"]
# 如果是直接运行主脚本（如果是带 Web 界面的脚本）:
# 使用 python -m 调用，这样可以 100% 确保使用的是当前 Python 环境下的 streamlit
# 关键点：通过环境变量覆盖代码中的默认值，确保后端和前端都统一到 7860
CMD ["sh", "-c", "WEBUI_HOST=0.0.0.0 WEBUI_PORT=7860 python webui.py"]
