FROM python:3.11-slim

# set TZ to Asia/Shanghai by default
ENV TZ=Asia/Shanghai
RUN ln -snf /usr/share/zoneinfo/$TZ /etc/localtime && echo $TZ > /etc/timezone

# environments for RM
WORKDIR /ReportManager
RUN mkdir storage storage/archive storage/temp && touch storage/RM.log
VOLUME [ "/ReportManager/storage" ]

# requirements for RM
RUN apt-get update && apt-get install -y curl unar && \
    curl -o rarlinux-x64-612.tar.gz https://www.rarlab.com/rar/rarlinux-x64-612.tar.gz && \
    tar -xf rarlinux-x64-612.tar.gz -C /opt && rm rarlinux-x64-612.tar.gz && \
    curl -o /etc/rarreg.key https://gist.githubusercontent.com/MuhammadSaim/de84d1ca59952cf1efaa8c061aab81a1/raw/ca31cbda01412e85949810d52d03573af281f826/rarreg.key && \
    ln -s /opt/rar/unrar /usr/bin/unrar && ln -s /opt/rar/rar /usr/bin/rar && \
    apt-get autoremove -y curl && rm -rf /var/lib/apt/lists/*
RUN pip install --no-cache-dir Flask gunicorn[gevent] walkdir python-docx mysql-connector-python DBUtils DingtalkChatbot chinesecalendar && \
    pip install --no-cache-dir https://github.com/ale10bb/zmail/archive/refs/tags/v0.2.8.1.tar.gz
COPY RM RM
COPY minimal_web.py minimal_web.py
COPY template template

COPY res/docker-entrypoint.sh /docker-entrypoint.sh
ENTRYPOINT ["/docker-entrypoint.sh"]
CMD [ "main" ]