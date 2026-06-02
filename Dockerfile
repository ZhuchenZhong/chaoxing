FROM python:3.13-slim

WORKDIR /app

COPY . /app

RUN pip install uv -i https://pypi.tuna.tsinghua.edu.cn/simple && \
    uv sync --frozen

# 创建配置文件目录并提供默认配置
RUN mkdir -p /config && \
    cp config_template.ini /config/config.ini

# 定义卷，用户可以挂载自己的配置文件
VOLUME /config

# 使用配置文件启动应用
ENV CHAOXING_HOME=/config/.chaoxing
ENTRYPOINT ["uv", "run", "chaoxing", "run", "-c", "/config/config.ini"]
