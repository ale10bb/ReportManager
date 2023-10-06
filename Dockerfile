FROM registry.cn-shanghai.aliyuncs.com/ale10bb/python:3.12-web-flask

# requirements for RM
RUN set -eux; \
        \
        pip install --no-cache-dir mysql-connector-python redis DingtalkChatbot chinesecalendar Flask flask-jwt-extended flask_cors

# directory structure for RM
WORKDIR /ReportManager
COPY RM RM
COPY manage.py .
COPY res/docker-entrypoint.sh .

ENTRYPOINT ["/ReportManager/docker-entrypoint.sh"]
CMD [ "manage" ]