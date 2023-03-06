FROM registry.cn-shanghai.aliyuncs.com/ale10bb/python:3.11-web-flask

# requirements for RM
RUN set -eux; \
        \
        pip install --no-cache-dir walkdir python-docx mysql-connector-python redis DingtalkChatbot chinesecalendar; \
        pip install --no-cache-dir https://github.com/ale10bb/zmail/archive/refs/tags/v0.2.8.2.tar.gz

# directory structure for RM
WORKDIR /ReportManager
COPY RM RM
COPY manage.py .
COPY res/docker-entrypoint.sh .

ENTRYPOINT ["/ReportManager/docker-entrypoint.sh"]
CMD [ "manage" ]