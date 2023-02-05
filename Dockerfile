FROM registry.cn-shanghai.aliyuncs.com/ale10bb/python:3.11-web-flask-rar

# requirements for RM
RUN set -eux; \
        \
        apt-get update; \
        apt-get install -y --no-install-recommends unar; \
        rm -rf /var/lib/apt/lists/*; \
        \
        pip install --no-cache-dir walkdir python-docx mysql-connector-python DBUtils DingtalkChatbot chinesecalendar; \
        pip install --no-cache-dir https://github.com/ale10bb/zmail/archive/refs/tags/v0.2.8.1.tar.gz

# directory structure for RM
WORKDIR /ReportManager
RUN set -eux; \
        mkdir storage; \
        mkdir storage/archive; \
        mkdir storage/temp; \
        touch storage/RM.log
VOLUME [ "/ReportManager/storage" ]
COPY RM RM
COPY minimal_web.py .
COPY res res

ENTRYPOINT ["/ReportManager/res/docker-entrypoint.sh"]
CMD [ "main" ]