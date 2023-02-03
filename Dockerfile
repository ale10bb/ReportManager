FROM registry.cn-hongkong.aliyuncs.com/ale10bb/python:3.11-web-flask

# requirements for RM
RUN set -eux; \
        \
        savedAptMark="$(apt-mark showmanual)"; \
        apt-get update; \
        apt-get install -y --no-install-recommends wget; \
        \
        wget -O rarlinux-x64-620.tar.gz https://www.rarlab.com/rar/rarlinux-x64-620.tar.gz; \
        wget -O /etc/rarreg.key https://gist.githubusercontent.com/MuhammadSaim/de84d1ca59952cf1efaa8c061aab81a1/raw/ca31cbda01412e85949810d52d03573af281f826/rarreg.key; \
        tar -xf rarlinux-x64-620.tar.gz -C /opt; \
        ln -s /opt/rar/unrar /usr/bin/unrar; \
        ln -s /opt/rar/rar /usr/bin/rar; \
        rm rarlinux-x64-620.tar.gz; \
        \
        apt-mark auto '.*' > /dev/null; \
        [ -z "$savedAptMark" ] || apt-mark manual $savedAptMark > /dev/null; \
        apt-get purge -y --auto-remove -o APT::AutoRemove::RecommendsImportant=false; \
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